# nlp-chinese-document-ocr

Pipeline preprocess và OCR tài liệu Hán văn bằng PaddleOCR. Ảnh clean được lưu
thủ công trên Google Drive; bước OCR tải và xử lý tuần tự từng folder sách rồi
upload kết quả trở lại Drive.

## Cài đặt

```bash
python3 -m venv ocr_env
source ocr_env/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

## Preprocessing

```bash
python scripts/preprocessing.py \
  --input_dir ./data_input \
  --output_dir ./data_output \
  --dpi 400
```

Sau preprocessing, upload thủ công các folder ảnh clean lên folder nguồn Google Drive.

## OCR Google Drive

Pipeline hiện hành nằm tại:

```text
scripts/ocr_v2/run_ocr_pipeline.py
```

Test nhanh với một sách và 5 ảnh:

```bash
python scripts/ocr_v2/run_ocr_pipeline.py \
  --max-books 1 \
  --max-images-per-book 5 \
  --preset mobile \
  --reading-order vertical-rl \
  --vertical-column-tolerance 320 \
  --min-score 0.3
```

Chạy toàn bộ:

```bash
python scripts/ocr_v2/run_ocr_pipeline.py \
  --preset medium \
  --device cpu \
  --reading-order vertical-rl \
  --vertical-column-tolerance 320 \
  --min-score 0.3
```

Xem hướng dẫn OAuth, `.env`, cấu trúc Drive và toàn bộ ví dụ tại
[`scripts/ocr_v2/README.md`](scripts/ocr_v2/README.md).
