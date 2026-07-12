#!/usr/bin/env python3
"""Download cleaned images from Google Drive, run OCR, and upload results."""

from __future__ import annotations

import argparse
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload
from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))
load_dotenv(PROJECT_ROOT / ".env")

from scripts.ocr.run_ocr_pipeline import (  # noqa: E402
    IMAGE_EXTENSIONS,
    MODEL_PRESETS,
    find_images,
    run_one_image,
    write_summary,
)


DRIVE_SCOPE = "https://www.googleapis.com/auth/drive"
FOLDER_MIME_TYPE = "application/vnd.google-apps.folder"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run PaddleOCR on images in Google Drive and upload the results.",
    )
    parser.add_argument(
        "--drive-input-folder-id",
        default=os.getenv("GOOGLE_DRIVE_INPUT_FOLDER_ID"),
        help="Source Drive folder ID (or GOOGLE_DRIVE_INPUT_FOLDER_ID).",
    )
    parser.add_argument(
        "--drive-output-folder-id",
        default=os.getenv("GOOGLE_DRIVE_OUTPUT_FOLDER_ID"),
        help="Destination Drive folder ID (or GOOGLE_DRIVE_OUTPUT_FOLDER_ID).",
    )
    parser.add_argument(
        "--oauth-client-file",
        type=Path,
        default=Path(
            os.getenv(
                "GOOGLE_OAUTH_CLIENT_FILE",
                PROJECT_ROOT / "secrets" / "google-drive-oauth-client.json",
            )
        ),
        help="OAuth Desktop client JSON file.",
    )
    parser.add_argument(
        "--oauth-token-file",
        type=Path,
        default=Path(
            os.getenv(
                "GOOGLE_OAUTH_TOKEN_FILE",
                PROJECT_ROOT / "secrets" / "google-drive-token.json",
            )
        ),
        help="Cached OAuth token; created automatically on first login.",
    )
    parser.add_argument("--preset", choices=sorted(MODEL_PRESETS), default="medium")
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--engine", default="transformers")
    parser.add_argument("--min-score", type=float, default=0.0)
    parser.add_argument(
        "--reading-order",
        choices=("raw", "horizontal", "vertical-rl", "vertical-lr"),
        default="vertical-rl",
    )
    parser.add_argument("--vertical-column-tolerance", type=float, default=320.0)
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="Reuse local raw OCR JSON when --keep-work-dir is used.",
    )
    parser.add_argument(
        "--book-name",
        help="Only process the top-level Drive folder with this exact name.",
    )
    parser.add_argument(
        "--max-books",
        type=int,
        help="Maximum number of book folders to process.",
    )
    parser.add_argument(
        "--max-images-per-book",
        type=int,
        help="Maximum number of images downloaded from each book (useful for tests).",
    )
    parser.add_argument(
        "--keep-work-dir",
        type=Path,
        help="Keep downloaded images and local OCR output in this directory.",
    )
    return parser.parse_args()


def authenticate(client_file: Path, token_file: Path) -> Credentials:
    if not client_file.is_file():
        raise FileNotFoundError(f"OAuth client file not found: {client_file}")

    credentials: Credentials | None = None
    if token_file.is_file():
        credentials = Credentials.from_authorized_user_file(token_file, [DRIVE_SCOPE])

    if credentials and credentials.expired and credentials.refresh_token:
        credentials.refresh(Request())
    elif not credentials or not credentials.valid:
        flow = InstalledAppFlow.from_client_secrets_file(client_file, [DRIVE_SCOPE])
        credentials = flow.run_local_server(port=0)

    token_file.parent.mkdir(parents=True, exist_ok=True)
    token_file.write_text(credentials.to_json(), encoding="utf-8")
    return credentials


def list_folder_items(service: Any, folder_id: str) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    page_token: str | None = None
    query = f"'{folder_id}' in parents and trashed = false"
    while True:
        response = (
            service.files()
            .list(
                q=query,
                spaces="drive",
                fields="nextPageToken, files(id,name,mimeType)",
                pageToken=page_token,
                pageSize=1000,
                supportsAllDrives=True,
                includeItemsFromAllDrives=True,
            )
            .execute()
        )
        items.extend(response.get("files", []))
        page_token = response.get("nextPageToken")
        if not page_token:
            return items


def download_drive_images(
    service: Any,
    folder_id: str,
    destination: Path,
    limit: int | None = None,
) -> int:
    downloaded = 0
    destination.mkdir(parents=True, exist_ok=True)
    for item in sorted(list_folder_items(service, folder_id), key=lambda value: value["name"]):
        if limit is not None and downloaded >= limit:
            break
        target = destination / item["name"]
        if item["mimeType"] == FOLDER_MIME_TYPE:
            remaining = None if limit is None else limit - downloaded
            downloaded += download_drive_images(service, item["id"], target, remaining)
            continue
        if target.suffix.lower() not in IMAGE_EXTENSIONS:
            continue

        target.parent.mkdir(parents=True, exist_ok=True)
        request = service.files().get_media(fileId=item["id"], supportsAllDrives=True)
        with target.open("wb") as stream:
            downloader = MediaIoBaseDownload(stream, request)
            done = False
            while not done:
                _, done = downloader.next_chunk()
        print(f"[DOWNLOAD] {target.relative_to(destination)}")
        downloaded += 1
    return downloaded


def find_child(service: Any, parent_id: str, name: str, mime_type: str | None = None) -> str | None:
    escaped_name = name.replace("'", "\\'")
    query = f"'{parent_id}' in parents and name = '{escaped_name}' and trashed = false"
    if mime_type:
        query += f" and mimeType = '{mime_type}'"
    else:
        query += f" and mimeType != '{FOLDER_MIME_TYPE}'"
    response = (
        service.files()
        .list(
            q=query,
            spaces="drive",
            fields="files(id)",
            pageSize=1,
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
        )
        .execute()
    )
    files = response.get("files", [])
    return files[0]["id"] if files else None


def ensure_drive_folder(service: Any, parent_id: str, name: str) -> str:
    existing_id = find_child(service, parent_id, name, FOLDER_MIME_TYPE)
    if existing_id:
        return existing_id
    folder = (
        service.files()
        .create(
            body={"name": name, "mimeType": FOLDER_MIME_TYPE, "parents": [parent_id]},
            fields="id",
            supportsAllDrives=True,
        )
        .execute()
    )
    return folder["id"]


def upload_file(service: Any, path: Path, parent_id: str) -> None:
    media = MediaFileUpload(str(path), resumable=True)
    existing_id = find_child(service, parent_id, path.name)
    if existing_id:
        service.files().update(
            fileId=existing_id,
            media_body=media,
            supportsAllDrives=True,
        ).execute()
    else:
        service.files().create(
            body={"name": path.name, "parents": [parent_id]},
            media_body=media,
            supportsAllDrives=True,
        ).execute()
    print(f"[UPLOAD] {path.name}")


def upload_tree(service: Any, local_dir: Path, drive_folder_id: str) -> None:
    for path in sorted(local_dir.iterdir()):
        if path.is_dir():
            child_id = ensure_drive_folder(service, drive_folder_id, path.name)
            upload_tree(service, path, child_id)
        elif path.is_file():
            upload_file(service, path, drive_folder_id)


def book_output_name(book_name: str) -> str:
    match = re.search(r"\d+", book_name)
    if not match:
        raise ValueError(f"Book folder name does not contain a number: {book_name}")
    return f"HVH_{int(match.group()):03d}"


def normalize_page_names(input_dir: Path, book_name: str) -> tuple[Path, list[Path]]:
    prefix = book_output_name(book_name)
    images = find_images(input_dir, recursive=True)
    normalized: list[Path] = []
    staging_dir = input_dir.parent / "normalized-input"
    staging_dir.mkdir(parents=True, exist_ok=True)
    for page_number, image in enumerate(images, start=1):
        target = staging_dir / f"{prefix}_{page_number:03d}{image.suffix.lower()}"
        shutil.move(str(image), target)
        normalized.append(target)
    return staging_dir, normalized


def run_book(
    args: argparse.Namespace,
    service: Any,
    book: dict[str, str],
    destination_id: str,
    work_dir: Path,
) -> int:
    book_dir = work_dir / book["id"]
    input_dir = book_dir / "input"
    args.output_dir = book_dir / "output"
    try:
        count = download_drive_images(
            service,
            book["id"],
            input_dir,
            args.max_images_per_book,
        )
        if count == 0:
            print(f"[SKIP] {book['name']}: no supported images")
            return 0

        output_name = book_output_name(book["name"])
        normalized_input_dir, images = normalize_page_names(input_dir, book["name"])
        print(f"[BOOK] {book['name']}: OCR {len(images)} image(s)")
        results = [run_one_image(args, image, normalized_input_dir) for image in images]
        write_summary(args.output_dir, results)
        combined_text = args.output_dir / "ocr_texts.txt"
        combined_text.rename(args.output_dir / f"{output_name}_raw.txt")
        output_folder_id = ensure_drive_folder(service, destination_id, output_name)
        upload_tree(service, args.output_dir, output_folder_id)
        failed = sum(result.status == "failed" for result in results)
        print(f"[BOOK DONE] {book['name']} | OK: {len(results) - failed} | Failed: {failed}")
        return failed
    finally:
        if not args.keep_work_dir:
            shutil.rmtree(book_dir, ignore_errors=True)


def run_pipeline(args: argparse.Namespace, service: Any, work_dir: Path) -> int:
    books = [
        item
        for item in list_folder_items(service, args.drive_input_folder_id)
        if item["mimeType"] == FOLDER_MIME_TYPE
    ]
    books.sort(key=lambda item: item["name"])
    if args.book_name:
        books = [book for book in books if book["name"] == args.book_name]
    if args.max_books is not None:
        books = books[: args.max_books]
    if not books:
        print("No matching book folders found in the Drive input folder.", file=sys.stderr)
        return 1

    print(f"Processing {len(books)} book folder(s) sequentially...")
    failed_images = sum(
        run_book(args, service, book, args.drive_output_folder_id, work_dir)
        for book in books
    )
    return 1 if failed_images else 0


def main() -> int:
    args = parse_args()
    args.dry_run = False
    if not args.drive_input_folder_id or not args.drive_output_folder_id:
        print("ERROR: Both Drive input and output folder IDs are required.", file=sys.stderr)
        return 2
    if args.max_books is not None and args.max_books <= 0:
        print("ERROR: --max-books must be greater than zero.", file=sys.stderr)
        return 2
    if args.max_images_per_book is not None and args.max_images_per_book <= 0:
        print("ERROR: --max-images-per-book must be greater than zero.", file=sys.stderr)
        return 2
    if shutil.which("paddleocr") is None:
        print("ERROR: Cannot find `paddleocr` in PATH. Activate ocr_env first.", file=sys.stderr)
        return 2

    try:
        credentials = authenticate(args.oauth_client_file.resolve(), args.oauth_token_file.resolve())
        service = build("drive", "v3", credentials=credentials, cache_discovery=False)
        if args.keep_work_dir:
            work_dir = args.keep_work_dir.resolve()
            work_dir.mkdir(parents=True, exist_ok=True)
            return run_pipeline(args, service, work_dir)
        with tempfile.TemporaryDirectory(prefix="ocr-drive-") as temporary_dir:
            return run_pipeline(args, service, Path(temporary_dir))
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
