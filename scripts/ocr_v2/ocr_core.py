"""PaddleOCR execution and result processing used by the Drive pipeline."""

from __future__ import annotations

import argparse
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any


IMAGE_EXTENSIONS = {".bmp", ".jpeg", ".jpg", ".png", ".tif", ".tiff", ".webp"}

MODEL_PRESETS = {
    "medium": {"det": "PP-OCRv6_medium_det", "rec": "PP-OCRv6_medium_rec"},
    "mobile": {"det": "PP-OCRv5_mobile_det", "rec": "PP-OCRv5_mobile_rec"},
}


@dataclass(frozen=True)
class OcrLine:
    text: str
    score: float | None
    poly: list[list[float]] | None = None


@dataclass(frozen=True)
class ImageResult:
    image_path: Path
    raw_result_path: Path | None
    text_path: Path
    lines: list[OcrLine]
    status: str
    error: str | None = None


def find_images(input_dir: Path, recursive: bool = True) -> list[Path]:
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


def build_paddleocr_command(
    args: argparse.Namespace,
    image_path: Path,
    raw_dir: Path,
) -> list[str]:
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


def poly_bounds(poly: list[list[float]] | None) -> tuple[float, float, float, float]:
    if not poly:
        return (0.0, 0.0, 0.0, 0.0)
    xs = [float(point[0]) for point in poly]
    ys = [float(point[1]) for point in poly]
    return (min(xs), min(ys), max(xs), max(ys))


def sort_ocr_lines(
    lines: list[OcrLine],
    reading_order: str,
    vertical_column_tolerance: float,
) -> list[OcrLine]:
    if reading_order == "raw":
        return lines

    def centers(line: OcrLine) -> tuple[float, float, float, float]:
        left, top, right, bottom = poly_bounds(line.poly)
        return ((left + right) / 2, (top + bottom) / 2, right - left, bottom - top)

    if reading_order == "horizontal":
        return sorted(lines, key=lambda line: (centers(line)[1], centers(line)[0]))

    reverse_columns = reading_order == "vertical-rl"
    sorted_by_x = sorted(lines, key=lambda line: centers(line)[0], reverse=reverse_columns)
    columns: list[list[OcrLine]] = []
    column_centers: list[float] = []
    for line in sorted_by_x:
        x_center = centers(line)[0]
        for index, column_center in enumerate(column_centers):
            if abs(x_center - column_center) <= vertical_column_tolerance:
                columns[index].append(line)
                column_centers[index] = sum(centers(item)[0] for item in columns[index]) / len(columns[index])
                break
        else:
            columns.append([line])
            column_centers.append(x_center)

    return [line for column in columns for line in sorted(column, key=lambda item: centers(item)[1])]


def load_ocr_lines(
    result_path: Path,
    min_score: float,
    reading_order: str,
    vertical_column_tolerance: float,
) -> list[OcrLine]:
    with result_path.open("r", encoding="utf-8") as file:
        payload: dict[str, Any] = json.load(file)
    texts = payload.get("rec_texts") or []
    scores = payload.get("rec_scores") or []
    polys = payload.get("rec_polys") or []
    lines: list[OcrLine] = []
    for index, text in enumerate(texts):
        score = scores[index] if index < len(scores) else None
        if score is not None and score < min_score:
            continue
        poly = polys[index] if index < len(polys) else None
        lines.append(OcrLine(text=str(text), score=score, poly=poly))
    return sort_ocr_lines(lines, reading_order, vertical_column_tolerance)


def write_text_file(text_path: Path, lines: list[OcrLine]) -> None:
    text_path.parent.mkdir(parents=True, exist_ok=True)
    content = "\n".join(line.text for line in lines)
    text_path.write_text(f"{content}\n" if content else "", encoding="utf-8")


def run_one_image(
    args: argparse.Namespace,
    image_path: Path,
    input_dir: Path,
) -> ImageResult:
    output_dir = args.output_dir.resolve()
    image_key = safe_relative_stem(image_path, input_dir)
    raw_dir = output_dir / "raw" / image_key
    result_path = raw_dir / f"{image_path.stem}_res.json"
    text_path = output_dir / "texts" / f"{image_key}.txt"

    if args.skip_existing and result_path.exists():
        lines = load_ocr_lines(result_path, args.min_score, args.reading_order, args.vertical_column_tolerance)
        write_text_file(text_path, lines)
        return ImageResult(image_path, result_path, text_path, lines, "skipped")

    command = build_paddleocr_command(args, image_path, raw_dir)
    print(f"[OCR] {image_path}")
    raw_dir.mkdir(parents=True, exist_ok=True)
    completed = subprocess.run(command, text=True)
    if completed.returncode != 0:
        return ImageResult(image_path, None, text_path, [], "failed", f"paddleocr exited with code {completed.returncode}")
    if not result_path.exists():
        return ImageResult(image_path, None, text_path, [], "failed", f"Expected result JSON not found: {result_path}")

    lines = load_ocr_lines(result_path, args.min_score, args.reading_order, args.vertical_column_tolerance)
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
                    {"text": line.text, "score": line.score, "poly": line.poly}
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
        chunks.extend([result.error] if result.error else [line.text for line in result.lines])
        chunks.append("")
    (output_dir / "ocr_texts.txt").write_text("\n".join(chunks), encoding="utf-8")
