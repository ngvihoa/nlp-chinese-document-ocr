#!/usr/bin/env python3
"""Download one OCR text file from Google Drive, segment sentences, and upload TSV."""

from __future__ import annotations

import argparse
import csv
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - optional during lightweight smoke tests
    def load_dotenv(*_: Any, **__: Any) -> bool:
        return False


PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")

DRIVE_SCOPE = "https://www.googleapis.com/auth/drive"
DRIVE_API_RETRIES = 5

SENTENCE_ENDINGS = "。！？；：.!?;:"
SENTENCE_CLOSERS = "」』”’】）》〕〉"
BRACKET_PAIRS = {
    "「": "」",
    "『": "』",
    "“": "”",
    "‘": "’",
    "（": "）",
    "(": ")",
    "【": "】",
    "[": "]",
    "《": "》",
    "〈": "〉",
    "〔": "〕",
}
BRACKET_CLOSERS = set(BRACKET_PAIRS.values())
PAGE_MARKER_PATTERN = re.compile(
    r'<page\s+id="(?P<page_id>[^"]+)">\s*(?P<content>.*?)\s*</page>',
    re.DOTALL | re.IGNORECASE,
)
DOC_VOLUME_PATTERN = re.compile(
    r"^HVH_(?:311_)?(?P<volume>\d+)(?:_(?:raw|clean))?(?:_seg)?\.(?:txt|tsv)$",
    re.IGNORECASE,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run sentence segmentation on one OCR text file stored in Google Drive.",
    )
    parser.add_argument(
        "--drive-input-folder-id",
        default=os.getenv("GOOGLE_DRIVE_SEGMENTATION_INPUT_FOLDER_ID"),
        help="Drive folder ID containing OCR text files.",
    )
    parser.add_argument(
        "--drive-output-folder-id",
        default=os.getenv("GOOGLE_DRIVE_SEGMENTATION_OUTPUT_FOLDER_ID"),
        help="Drive folder ID that receives segmentation TSV files.",
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
    parser.add_argument(
        "--use-colab-auth",
        action="store_true",
        help="Use credentials created by google.colab.auth.authenticate_user().",
    )
    parser.add_argument(
        "--file-name",
        required=True,
        help="Exact OCR raw text filename in the Drive folder, for example HVH_311_016_raw.txt.",
    )
    parser.add_argument(
        "--doc-id",
        help="Override the document id used in sentence ids. Defaults to the OCR filename prefix.",
    )
    parser.add_argument(
        "--keep-work-dir",
        type=Path,
        help="Keep local temporary files in this directory for debugging or resume checks.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Recreate and re-upload the segmentation output even if it already exists on Drive.",
    )
    return parser.parse_args()


def authenticate(client_file: Path, token_file: Path) -> Credentials:
    import google.auth
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow

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


def authenticate_colab() -> Any:
    import google.auth
    from google.auth.transport.requests import Request

    credentials, _ = google.auth.default(scopes=[DRIVE_SCOPE])
    if not credentials.valid:
        credentials.refresh(Request())
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
            .execute(num_retries=DRIVE_API_RETRIES)
        )
        items.extend(response.get("files", []))
        page_token = response.get("nextPageToken")
        if not page_token:
            return items


def find_child(service: Any, parent_id: str, name: str) -> dict[str, str] | None:
    escaped_name = name.replace("'", "\\'")
    query = f"'{parent_id}' in parents and name = '{escaped_name}' and trashed = false"
    response = (
        service.files()
        .list(
            q=query,
            spaces="drive",
            fields="files(id,name,mimeType)",
            pageSize=10,
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
        )
        .execute(num_retries=DRIVE_API_RETRIES)
    )
    files = response.get("files", [])
    return files[0] if files else None


def download_drive_file(service: Any, file_id: str, destination: Path) -> None:
    from googleapiclient.http import MediaIoBaseDownload

    destination.parent.mkdir(parents=True, exist_ok=True)
    request = service.files().get_media(fileId=file_id, supportsAllDrives=True)
    with destination.open("wb") as stream:
        downloader = MediaIoBaseDownload(stream, request)
        done = False
        while not done:
            _, done = downloader.next_chunk(num_retries=DRIVE_API_RETRIES)
    print(f"[DOWNLOAD] {destination.name}")


def upload_file(service: Any, path: Path, parent_id: str) -> None:
    from googleapiclient.http import MediaFileUpload

    media = MediaFileUpload(str(path), resumable=True)
    existing = find_child(service, parent_id, path.name)
    if existing:
        service.files().update(
            fileId=existing["id"],
            media_body=media,
            supportsAllDrives=True,
        ).execute(num_retries=DRIVE_API_RETRIES)
    else:
        service.files().create(
            body={"name": path.name, "parents": [parent_id]},
            media_body=media,
            supportsAllDrives=True,
        ).execute(num_retries=DRIVE_API_RETRIES)
    print(f"[UPLOAD] {path.name}")


def derive_doc_id(file_name: str) -> str:
    match = DOC_VOLUME_PATTERN.match(file_name)
    if match:
        return f"HVH_311_{int(match.group('volume'))}"
    raise ValueError(f"Cannot derive doc id from file name: {file_name}")


def output_file_name(file_name: str) -> str:
    match = DOC_VOLUME_PATTERN.match(file_name)
    if not match or not file_name.lower().endswith(".txt"):
        raise ValueError(
            "Input file must match HVH_311_<volume>_raw.txt "
            f"(legacy HVH_<volume>_raw.txt or *_clean.txt are also accepted): {file_name}"
        )
    return f"HVH_311_{int(match.group('volume'))}_seg.tsv"


def normalize_text(text: str) -> str:
    text = text.replace("\ufeff", "")
    text = text.replace("\u3000", " ")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [re.sub(r"\s+", " ", line).strip() for line in text.split("\n")]
    compact_lines: list[str] = []
    previous_blank = False
    for line in lines:
        if not line:
            if previous_blank:
                continue
            previous_blank = True
            compact_lines.append("")
            continue
        previous_blank = False
        compact_lines.append(line)
    return "\n".join(compact_lines).strip()


def count_sentence_endings(text: str) -> int:
    return sum(text.count(mark) for mark in SENTENCE_ENDINGS)


def is_ascii_alphanumeric(char: str) -> bool:
    return char.isascii() and char.isalnum()


def split_sentence_chunks(text: str) -> list[str]:
    chunks: list[str] = []
    bracket_stack: list[str] = []
    position = 0
    index = 0

    while index < len(text):
        char = text[index]
        if char in BRACKET_PAIRS:
            bracket_stack.append(BRACKET_PAIRS[char])
            index += 1
            continue
        if char in BRACKET_CLOSERS:
            if bracket_stack and bracket_stack[-1] == char:
                bracket_stack.pop()
            index += 1
            continue

        is_ending = char in SENTENCE_ENDINGS
        if char in ":：" and bracket_stack:
            is_ending = False
        if (
            char == "."
            and index > 0
            and index + 1 < len(text)
            and is_ascii_alphanumeric(text[index - 1])
            and is_ascii_alphanumeric(text[index + 1])
        ):
            is_ending = False
        if not is_ending:
            index += 1
            continue

        end = index + 1
        while end < len(text) and text[end] in SENTENCE_CLOSERS:
            if bracket_stack and bracket_stack[-1] == text[end]:
                bracket_stack.pop()
            end += 1
        chunk = text[position:end].strip()
        if chunk:
            chunks.append(chunk)
        position = end
        index = end

    remainder = text[position:].strip()
    if remainder:
        chunks.extend(line.strip() for line in remainder.splitlines() if line.strip())
    return chunks


def segment_plain_text(text: str) -> list[str]:
    normalized = normalize_text(text)
    if not normalized:
        return []
    if count_sentence_endings(normalized) == 0:
        return [line.strip() for line in normalized.splitlines() if line.strip()]
    blocks: list[str] = []
    for block in normalized.split("\n"):
        if not block:
            continue
        if blocks and block.startswith(tuple(SENTENCE_CLOSERS)):
            blocks[-1] += block
        else:
            blocks.append(block)

    sentences: list[str] = []
    for block in blocks:
        sentences.extend(split_sentence_chunks(block))
    return [sentence for sentence in sentences if sentence]


def segment_with_page_markers(text: str) -> list[tuple[str, str]]:
    matches = list(PAGE_MARKER_PATTERN.finditer(text))
    if not matches:
        return []

    segmented: list[tuple[str, str]] = []
    for match in matches:
        page_id = match.group("page_id").strip()
        page_text = match.group("content")
        for index, sentence in enumerate(segment_plain_text(page_text), start=1):
            sentence_id = f"{page_id}_{index:06d}"
            segmented.append((sentence_id, sentence))
    return segmented


def segment_document(text: str, doc_id: str) -> list[tuple[str, str]]:
    paged_sentences = segment_with_page_markers(text)
    if paged_sentences:
        return paged_sentences

    sentences = segment_plain_text(text)
    return [(f"{doc_id}_{index:06d}", sentence) for index, sentence in enumerate(sentences, start=1)]


def write_tsv(rows: list[tuple[str, str]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream, delimiter="\t", lineterminator="\n")
        writer.writerow(["sentence_id", "sentence"])
        writer.writerows(rows)


def run_segmentation(local_input: Path, local_output: Path, doc_id: str) -> int:
    text = local_input.read_text(encoding="utf-8")
    rows = segment_document(text, doc_id)
    write_tsv(rows, local_output)
    return len(rows)


def process_one_file(args: argparse.Namespace, service: Any, work_dir: Path) -> int:
    source_file = find_child(service, args.drive_input_folder_id, args.file_name)
    if source_file is None:
        print(
            f"ERROR: Cannot find {args.file_name} in Drive folder {args.drive_input_folder_id}.",
            file=sys.stderr,
        )
        return 2
    if source_file["mimeType"].startswith("application/vnd.google-apps."):
        print(f"ERROR: {args.file_name} is not a downloadable text file.", file=sys.stderr)
        return 2

    doc_id = args.doc_id or derive_doc_id(args.file_name)
    output_name = output_file_name(args.file_name)
    existing_output = find_child(service, args.drive_output_folder_id, output_name)
    if existing_output and not args.force:
        print(f"[SKIP] {output_name} already exists on Drive. Use --force to regenerate.")
        return 0
    local_input = work_dir / args.file_name
    local_output = work_dir / output_name
    download_drive_file(service, source_file["id"], local_input)
    sentence_count = run_segmentation(local_input, local_output, doc_id)
    upload_file(service, local_output, args.drive_output_folder_id)
    print(f"[DONE] {args.file_name} -> {output_name} | sentences: {sentence_count}")
    return 0


def main() -> int:
    from googleapiclient.discovery import build

    args = parse_args()
    if not args.drive_input_folder_id:
        print("ERROR: Drive input folder ID is required.", file=sys.stderr)
        return 2
    if not args.drive_output_folder_id:
        print("ERROR: Drive output folder ID is required.", file=sys.stderr)
        return 2

    try:
        credentials = (
            authenticate_colab()
            if args.use_colab_auth
            else authenticate(args.oauth_client_file.resolve(), args.oauth_token_file.resolve())
        )
        service = build("drive", "v3", credentials=credentials, cache_discovery=False)
        if args.keep_work_dir:
            work_dir = args.keep_work_dir.resolve()
            work_dir.mkdir(parents=True, exist_ok=True)
            return process_one_file(args, service, work_dir)
        with tempfile.TemporaryDirectory(prefix="segmentation-drive-") as temporary_dir:
            return process_one_file(args, service, Path(temporary_dir))
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
