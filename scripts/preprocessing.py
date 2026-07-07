from __future__ import annotations

import argparse
import json
import math
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import cv2
import fitz
import numpy as np
from tqdm import tqdm


MAX_SAFE_DESKEW_ANGLE = 5.0
MIN_FOREGROUND_RATIO = 0.01
MAX_FOREGROUND_RATIO = 0.6


@dataclass
class PageReport:
    page: int
    raw_image: str
    clean_image: str
    status: str
    skipped: bool = False
    crop_applied: bool = False
    deskew_applied: bool = False
    deskew_angle: float | None = None
    error: str | None = None


@dataclass
class RunReport:
    pdf: str
    dpi: int
    num_pages_requested: int | None
    num_pages_processed: int = 0
    pages: list[PageReport] = field(default_factory=list)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render and preprocess the first pages from all input PDFs.")
    parser.add_argument("--input_dir", required=True, help="Directory containing input_*.pdf files.")
    parser.add_argument("--output_dir", default="data_output", help="Output directory.")
    parser.add_argument("--dpi", type=int, default=400, help="Render DPI.")
    parser.add_argument("--num_pages", type=int, default=None, help="Optional limit on pages per PDF.")
    parser.add_argument("--force", action="store_true", help="Overwrite existing outputs.")
    return parser.parse_args()


def list_input_pdfs(input_dir: Path) -> list[tuple[int, Path]]:
    pattern = re.compile(r"^input_(\d+)\.pdf$", re.IGNORECASE)
    matched: list[tuple[int, Path]] = []
    for pdf_path in input_dir.iterdir():
        if not pdf_path.is_file():
            continue
        match = pattern.match(pdf_path.name)
        if match is None:
            continue
        matched.append((int(match.group(1)), pdf_path))
    matched.sort(key=lambda item: item[0])
    return matched


def format_doc_prefix(doc_index: int) -> str:
    return f"{doc_index:02d}"


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def to_grayscale(image: np.ndarray) -> np.ndarray:
    if image.ndim == 2:
        return image
    return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)


def light_denoise(gray: np.ndarray) -> np.ndarray:
    return cv2.medianBlur(gray, 3)


def enhance_contrast(gray: np.ndarray) -> np.ndarray:
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    return clahe.apply(gray)


def binarize_image(gray: np.ndarray) -> np.ndarray:
    return cv2.adaptiveThreshold(
        gray,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        31,
        15,
    )


def safe_crop_border(gray: np.ndarray) -> tuple[np.ndarray, bool]:
    h, w = gray.shape[:2]
    if h < 50 or w < 50:
        return gray, False

    _, inv = cv2.threshold(gray, 245, 255, cv2.THRESH_BINARY_INV)
    coords = cv2.findNonZero(inv)
    if coords is None:
        return gray, False

    x, y, crop_w, crop_h = cv2.boundingRect(coords)
    margin_x = max(8, int(w * 0.01))
    margin_y = max(8, int(h * 0.01))

    x0 = max(0, x - margin_x)
    y0 = max(0, y - margin_y)
    x1 = min(w, x + crop_w + margin_x)
    y1 = min(h, y + crop_h + margin_y)

    cropped = gray[y0:y1, x0:x1]
    if cropped.size == 0:
        return gray, False

    area_ratio = (cropped.shape[0] * cropped.shape[1]) / float(h * w)
    if area_ratio < 0.5:
        return gray, False

    return cropped, area_ratio < 0.98


def _normalize_min_area_angle(angle: float) -> float:
    if angle < -45:
        angle = 90 + angle
    if angle > 45:
        angle = angle - 90
    return angle


def deskew_if_safe(gray: np.ndarray) -> tuple[np.ndarray, bool, float | None]:
    inverted = cv2.bitwise_not(gray)
    _, thresh = cv2.threshold(inverted, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)
    points = cv2.findNonZero(thresh)
    if points is None or len(points) < 100:
        return gray, False, None

    rect = cv2.minAreaRect(points)
    angle = _normalize_min_area_angle(float(rect[-1]))
    foreground_ratio = float(np.count_nonzero(thresh)) / float(thresh.size)

    if math.isnan(angle) or abs(angle) > MAX_SAFE_DESKEW_ANGLE:
        return gray, False, angle
    if not (MIN_FOREGROUND_RATIO <= foreground_ratio <= MAX_FOREGROUND_RATIO):
        return gray, False, angle

    h, w = gray.shape[:2]
    center = (w / 2.0, h / 2.0)
    matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
    rotated = cv2.warpAffine(
        gray,
        matrix,
        (w, h),
        flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_REPLICATE,
    )
    return rotated, True, angle


def preprocess_array(image: np.ndarray) -> tuple[np.ndarray, dict[str, Any]]:
    gray = to_grayscale(image)
    cropped, crop_applied = safe_crop_border(gray)
    deskewed, deskew_applied, angle = deskew_if_safe(cropped)
    denoised = light_denoise(deskewed)
    contrasted = enhance_contrast(denoised)
    binary = binarize_image(contrasted)
    meta = {
        "crop_applied": crop_applied,
        "deskew_applied": deskew_applied,
        "deskew_angle": None if angle is None else round(angle, 4),
    }
    return binary, meta


def render_pdf_first_pages(
    pdf_path: Path,
    raw_dir: Path,
    dpi: int = 400,
    num_pages: int | None = None,
    force: bool = False,
) -> list[tuple[int, Path]]:
    ensure_dir(raw_dir)
    rendered: list[tuple[int, Path]] = []
    scale = dpi / 72.0
    matrix = fitz.Matrix(scale, scale)

    with fitz.open(pdf_path) as document:
        total_pages = document.page_count if num_pages is None else min(num_pages, document.page_count)
        for index in range(total_pages):
            output_path = raw_dir / f"page_{index + 1:03d}.png"
            if output_path.exists() and not force:
                rendered.append((index + 1, output_path))
                continue

            page = document.load_page(index)
            pixmap = page.get_pixmap(matrix=matrix, alpha=False)
            pixmap.save(output_path)
            rendered.append((index + 1, output_path))

    return rendered


def preprocess_image(input_path: Path, output_path: Path, force: bool = False) -> dict[str, Any]:
    if output_path.exists() and not force:
        return {
            "status": "skipped",
            "skipped": True,
            "crop_applied": False,
            "deskew_applied": False,
            "deskew_angle": None,
        }

    image = cv2.imread(str(input_path), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError(f"Cannot read image: {input_path}")

    cleaned, meta = preprocess_array(image)
    success = cv2.imwrite(str(output_path), cleaned)
    if not success:
        raise ValueError(f"Cannot write image: {output_path}")

    return {
        "status": "processed",
        "skipped": False,
        **meta,
    }


def write_report(report: RunReport, report_path: Path) -> None:
    ensure_dir(report_path.parent)
    payload = asdict(report)
    report_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def process_pdf(
    pdf_path: Path,
    doc_index: int,
    out_dir: Path,
    dpi: int,
    num_pages: int | None,
    force: bool,
) -> RunReport:
    prefix = format_doc_prefix(doc_index)
    raw_dir = out_dir / f"{prefix}_raw"
    clean_dir = out_dir / f"{prefix}_clean"
    report_path = out_dir / f"{prefix}_report.json"

    ensure_dir(raw_dir)
    ensure_dir(clean_dir)

    report = RunReport(
        pdf=str(pdf_path),
        dpi=dpi,
        num_pages_requested=num_pages,
    )

    print("    Rendering pages...")
    rendered_pages = render_pdf_first_pages(
        pdf_path=pdf_path,
        raw_dir=raw_dir,
        dpi=dpi,
        num_pages=num_pages,
        force=force,
    )

    print("    Preprocessing pages...")
    for page_number, raw_path in tqdm(rendered_pages, desc=f"{prefix}", unit="page", leave=False):
        clean_path = clean_dir / f"page_{page_number:03d}_clean.png"
        page_report = PageReport(
            page=page_number,
            raw_image=str(raw_path),
            clean_image=str(clean_path),
            status="processed",
        )
        try:
            result = preprocess_image(raw_path, clean_path, force=force)
            page_report.status = result["status"]
            page_report.skipped = result["skipped"]
            page_report.crop_applied = result["crop_applied"]
            page_report.deskew_applied = result["deskew_applied"]
            page_report.deskew_angle = result["deskew_angle"]
            report.num_pages_processed += 0 if result["skipped"] else 1
        except Exception as exc:
            page_report.status = "error"
            page_report.error = str(exc)
        report.pages.append(page_report)

    write_report(report, report_path)
    return report


def main() -> int:
    args = parse_args()
    input_dir = Path(args.input_dir)
    out_dir = Path(args.output_dir)
    ensure_dir(out_dir)

    pdf_files = list_input_pdfs(input_dir)
    if not pdf_files:
        print(f"No input_*.pdf files found in {input_dir}")
        return 1

    for position, (doc_index, pdf_path) in enumerate(pdf_files, start=1):
        prefix = format_doc_prefix(doc_index)
        print(f"Processing PDF {position}/{len(pdf_files)}")
        try:
            process_pdf(
                pdf_path=pdf_path,
                doc_index=doc_index,
                out_dir=out_dir,
                dpi=args.dpi,
                num_pages=args.num_pages,
                force=args.force,
            )
        except Exception as exc:
            error_report = RunReport(
                pdf=str(pdf_path),
                dpi=args.dpi,
                num_pages_requested=args.num_pages,
            )
            error_report.pages.append(
                PageReport(
                    page=0,
                    raw_image="",
                    clean_image="",
                    status="error",
                    error=str(exc),
                )
            )
            write_report(error_report, out_dir / f"{prefix}_report.json")
            print(f"    Error: {exc}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
