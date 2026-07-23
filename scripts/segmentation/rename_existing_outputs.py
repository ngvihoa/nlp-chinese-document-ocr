#!/usr/bin/env python3
"""Rename existing OCR/segmentation outputs to the HVH_311_<volume> convention."""

from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path


OCR_RAW_PATTERN = re.compile(r"^HVH_(?P<volume>\d{3})_raw\.txt$", re.IGNORECASE)
SEG_TSV_PATTERN = re.compile(
    r"^HVH_(?:311_)?(?P<volume>\d{3})(?:_.*)?_seg\.tsv$",
    re.IGNORECASE,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Rename OCR raw text files and segmentation TSV files to HVH_311_<volume> names.",
    )
    parser.add_argument("--ocr-output-dir", type=Path, help="Directory containing HVH_<volume>_raw.txt files.")
    parser.add_argument("--segment-dir", type=Path, help="Directory containing segmentation .tsv files.")
    parser.add_argument("--dry-run", action="store_true", help="Print planned changes without writing files.")
    return parser.parse_args()


def target_raw_name(file_name: str) -> str | None:
    if file_name.lower().startswith("hvh_311_"):
        return None
    match = OCR_RAW_PATTERN.match(file_name)
    if not match:
        return None
    return f"HVH_311_{match.group('volume')}_raw.txt"


def target_seg_name(file_name: str) -> str | None:
    match = SEG_TSV_PATTERN.match(file_name)
    if not match:
        return None
    return f"HVH_311_{match.group('volume')}_seg.tsv"


def rename_file(path: Path, target_name: str, dry_run: bool) -> Path:
    target = path.with_name(target_name)
    if path == target:
        return target
    if target.exists():
        raise FileExistsError(f"Target already exists: {target}")
    print(f"[RENAME] {path.name} -> {target.name}")
    if not dry_run:
        path.rename(target)
    return target


def rewrite_tsv_sentence_ids(path: Path, volume: str, dry_run: bool) -> None:
    rows: list[list[str]] = []
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.reader(stream, delimiter="\t")
        rows = [row for row in reader]

    if not rows:
        return

    has_header = rows[0][:2] == ["sentence_id", "sentence"]
    data_start = 1 if has_header else 0
    prefix = f"HVH_311_{volume}"
    changed = False

    for sentence_number, row in enumerate(rows[data_start:], start=1):
        if not row:
            continue
        new_id = f"{prefix}_{sentence_number:06d}"
        if row[0] != new_id:
            row[0] = new_id
            changed = True

    if not changed:
        return

    print(f"[REWRITE IDS] {path.name}")
    if dry_run:
        return
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream, delimiter="\t", lineterminator="\n")
        writer.writerows(rows)


def process_ocr_output(directory: Path, dry_run: bool) -> None:
    if not directory.exists():
        raise FileNotFoundError(f"OCR output directory not found: {directory}")
    for path in sorted(directory.glob("*.txt")):
        target_name = target_raw_name(path.name)
        if target_name:
            rename_file(path, target_name, dry_run)


def process_segment_output(directory: Path, dry_run: bool) -> None:
    if not directory.exists():
        raise FileNotFoundError(f"Segmentation directory not found: {directory}")
    for path in sorted(directory.glob("*.tsv")):
        match = SEG_TSV_PATTERN.match(path.name)
        if not match:
            continue
        volume = match.group("volume")
        target_name = target_seg_name(path.name)
        target = rename_file(path, target_name, dry_run) if target_name else path
        rewrite_tsv_sentence_ids(target, volume, dry_run)


def main() -> int:
    args = parse_args()
    if not args.ocr_output_dir and not args.segment_dir:
        print("Nothing to do. Pass --ocr-output-dir and/or --segment-dir.")
        return 0
    if args.ocr_output_dir:
        process_ocr_output(args.ocr_output_dir, args.dry_run)
    if args.segment_dir:
        process_segment_output(args.segment_dir, args.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
