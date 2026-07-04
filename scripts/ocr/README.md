# OCR Pipeline

Folder này chứa script OCR hàng loạt bằng PaddleOCR v6 cho ảnh đã clean.

## Cấu trúc mặc định

```text
data_output/
├── pages_clean/           # Ảnh đã clean từ bước preprocessing
└── ocr-output/            # Kết quả OCR sẽ được ghi vào đây

scripts/
└── ocr/
    └── run_ocr_pipeline.py
```

## Chạy trên Linux

Từ thư mục gốc project:

```bash
source ocr_env/bin/activate
python scripts/ocr/run_ocr_pipeline.py
```

## Chạy trên Windows PowerShell

Từ thư mục gốc project:

```powershell
.\ocr_env\Scripts\Activate.ps1
python .\scripts\ocr\run_ocr_pipeline.py
```

## Chạy với folder ảnh khác

```bash
python scripts/ocr/run_ocr_pipeline.py \
  --input-dir ./path/to/pages_clean \
  --output-dir ./path/to/ocr-output
```

## Test nhanh trên CPU yếu

Model mặc định là `PP-OCRv6_medium_*`. Nếu máy CPU chạy chậm, dùng preset mobile:

```bash
python scripts/ocr/run_ocr_pipeline.py --preset mobile
```

## Output

Sau khi chạy xong, script sinh ra:

- `data_output/ocr-output/raw/`: JSON và ảnh kết quả gốc từ PaddleOCR.
- `data_output/ocr-output/texts/`: mỗi ảnh có một file `.txt`.
- `data_output/ocr-output/ocr_texts.txt`: toàn bộ text OCR gom chung.
- `data_output/ocr-output/ocr_summary.json`: summary JSON gồm text, confidence score và trạng thái từng ảnh.

## Tham số hay dùng

```bash
python scripts/ocr/run_ocr_pipeline.py \
  --input-dir ./data_output/pages_clean \
  --output-dir ./data_output/ocr-output \
  --preset medium \
  --device cpu \
  --min-score 0.5 \
  --recursive
```
