#!/usr/bin/env python3
"""Batch OCR cleaned images with PaddleOCR v6 CLI.

Default layout:
  input:  data_output/pages_clean
  output: data_output/ocr-output

The script calls `paddleocr ocr` for each image, then collects PaddleOCR JSON
results into plain text and a compact summary JSON.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


IMAGE_EXTENSIONS = {".bmp", ".jpeg", ".jpg", ".png", ".tif", ".tiff", ".webp"}

MODEL_PRESETS = {
    "medium": {
        "det": "PP-OCRv6_medium_det",
        "rec": "PP-OCRv6_medium_rec",
    },
    "mobile": {
        "det": "PP-OCRv5_mobile_det",
        "rec": "PP-OCRv5_mobile_rec",
    },
}


@dataclass(frozen=True)
class OcrLine:
    text: str
    score: float | None


@dataclass(frozen=True)
class ImageResult:
    image_path: Path
    raw_result_path: Path | None
    text_path: Path
    lines: list[OcrLine]
    status: str
    error: str | None = None


def parse_args() -> argparse.Namespace:
    project_root = Path(__file__).resolve().parents[2]
    default_input_dir = project_root / "data_output" / "pages_clean"
    default_output_dir = project_root / "data_output" / "ocr-output"

    parser = argparse.ArgumentParser(
        description="Run PaddleOCR v6 on a folder of cleaned Chinese/Han text images.",
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=default_input_dir,
        help=f"Folder containing cleaned images. Default: {default_input_dir}",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=default_output_dir,
        help=f"Folder for OCR outputs. Default: {default_output_dir}",
    )
    parser.add_argument(
        "--preset",
        choices=sorted(MODEL_PRESETS),
        default="medium",
        help="OCR model preset. Use mobile for faster CPU tests.",
    )
    parser.add_argument(
        "--device",
        default="cpu",
        help="PaddleOCR device, for example: cpu, gpu:0. Default: cpu",
    )
    parser.add_argument(
        "--engine",
        default="transformers",
        help="PaddleOCR engine. Default: transformers",
    )
    parser.add_argument(
        "--min-score",
        type=float,
        default=0.0,
        help="Drop recognized lines below this confidence score. Default: 0.0",
    )
    parser.add_argument(
        "--recursive",
        action="store_true",
        help="Read images from nested folders inside input-dir.",
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="Reuse existing raw PaddleOCR JSON when available.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print commands without running OCR.",
    )
    return parser.parse_args()


def find_images(input_dir: Path, recursive: bool) -> list[Path]:
    pattern = "**/*" if recursive else "*"
    return sorted(
        path
        for path in input_dir.glob(pattern)
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
    )


def safe_relative_stem(image_path: Path, input_dir: Path) -> str:
    relative = image_path.relative_to(input_dir)
    parts = [*relative.parent.parts, relative.stem]
    return "__".join(part for part in parts if part)


def build_paddleocr_command(args: argparse.Namespace, image_path: Path, raw_dir: Path) -> list[str]:
    preset = MODEL_PRESETS[args.preset]
    return [
        "paddleocr",
        "ocr",
        "-i",
        str(image_path),
        "--text_detection_model_name",
        preset["det"],
        "--text_recognition_model_name",
        preset["rec"],
        "--engine",
        args.engine,
        "--use_doc_orientation_classify",
        "False",
        "--use_doc_unwarping",
        "False",
        "--use_textline_orientation",
        "True",
        "--save_path",
        str(raw_dir),
        "--device",
        args.device,
    ]


def load_ocr_lines(result_path: Path, min_score: float) -> list[OcrLine]:
    with result_path.open("r", encoding="utf-8") as file:
        payload: dict[str, Any] = json.load(file)

    texts = payload.get("rec_texts") or []
    scores = payload.get("rec_scores") or []
    lines: list[OcrLine] = []

    for index, text in enumerate(texts):
        score = scores[index] if index < len(scores) else None
        if score is not None and score < min_score:
            continue
        lines.append(OcrLine(text=str(text), score=score))

    return lines


def write_text_file(text_path: Path, lines: list[OcrLine]) -> None:
    text_path.parent.mkdir(parents=True, exist_ok=True)
    content = "\n".join(line.text for line in lines)
    if content:
        content += "\n"
    text_path.write_text(content, encoding="utf-8")


def run_one_image(args: argparse.Namespace, image_path: Path, input_dir: Path) -> ImageResult:
    output_dir = args.output_dir.resolve()
    text_dir = output_dir / "texts"
    image_key = safe_relative_stem(image_path, input_dir)
    raw_dir = output_dir / "raw" / image_key
    result_path = raw_dir / f"{image_path.stem}_res.json"
    text_path = text_dir / f"{image_key}.txt"

    if args.skip_existing and result_path.exists():
        lines = load_ocr_lines(result_path, args.min_score)
        write_text_file(text_path, lines)
        return ImageResult(image_path, result_path, text_path, lines, "skipped")

    command = build_paddleocr_command(args, image_path, raw_dir)
    print(f"[OCR] {image_path}")
    print("      " + " ".join(command))

    if args.dry_run:
        return ImageResult(image_path, None, text_path, [], "dry-run")

    raw_dir.mkdir(parents=True, exist_ok=True)
    completed = subprocess.run(command, text=True)
    if completed.returncode != 0:
        return ImageResult(
            image_path=image_path,
            raw_result_path=None,
            text_path=text_path,
            lines=[],
            status="failed",
            error=f"paddleocr exited with code {completed.returncode}",
        )

    if not result_path.exists():
        return ImageResult(
            image_path=image_path,
            raw_result_path=None,
            text_path=text_path,
            lines=[],
            status="failed",
            error=f"Expected result JSON not found: {result_path}",
        )

    lines = load_ocr_lines(result_path, args.min_score)
    write_text_file(text_path, lines)
    return ImageResult(image_path, result_path, text_path, lines, "ok")


def write_summary(output_dir: Path, results: list[ImageResult]) -> None:
    summary = {
        "total_images": len(results),
        "ok": sum(result.status in {"ok", "skipped"} for result in results),
        "failed": sum(result.status == "failed" for result in results),
        "items": [
            {
                "image_path": str(result.image_path),
                "raw_result_path": str(result.raw_result_path) if result.raw_result_path else None,
                "text_path": str(result.text_path),
                "status": result.status,
                "error": result.error,
                "line_count": len(result.lines),
                "text": "\n".join(line.text for line in result.lines),
                "lines": [
                    {
                        "text": line.text,
                        "score": line.score,
                    }
                    for line in result.lines
                ],
            }
            for result in results
        ],
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "ocr_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    chunks: list[str] = []
    for result in results:
        chunks.append(f"===== {result.image_path.name} [{result.status}] =====")
        if result.error:
            chunks.append(result.error)
        else:
            chunks.extend(line.text for line in result.lines)
        chunks.append("")
    (output_dir / "ocr_texts.txt").write_text("\n".join(chunks), encoding="utf-8")


def main() -> int:
    args = parse_args()
    input_dir = args.input_dir.resolve()
    args.output_dir = args.output_dir.resolve()

    if shutil.which("paddleocr") is None:
        print("ERROR: Cannot find `paddleocr` in PATH. Activate ocr_env first.", file=sys.stderr)
        return 2

    if not input_dir.exists():
        print(f"ERROR: input folder does not exist: {input_dir}", file=sys.stderr)
        return 2

    images = find_images(input_dir, args.recursive)
    if not images:
        print(f"No images found in: {input_dir}")
        return 0

    print(f"Found {len(images)} image(s). Output: {args.output_dir}")
    results = [run_one_image(args, image_path, input_dir) for image_path in images]

    if args.dry_run:
        print("Dry run complete. No OCR output files were written.")
        return 0

    write_summary(args.output_dir, results)

    failed = [result for result in results if result.status == "failed"]
    print(f"Done. OK: {len(results) - len(failed)} | Failed: {len(failed)}")
    print(f"Summary: {args.output_dir / 'ocr_summary.json'}")
    print(f"Text:    {args.output_dir / 'ocr_texts.txt'}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
