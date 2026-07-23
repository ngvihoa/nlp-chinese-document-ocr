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

## Sentence segmentation

Pipeline segmentation tải một file OCR text từ folder input, tách câu, tạo file TSV
và upload kết quả vào một folder output riêng trên Google Drive:

```bash
python scripts/segmentation/run_segmentation_pipeline.py \
  --drive-input-folder-id "YOUR_INPUT_FOLDER_ID" \
  --drive-output-folder-id "YOUR_OUTPUT_FOLDER_ID" \
  --file-name "HVH_311_016_raw.txt"
```

Có thể cấu hình hai folder trong `.env`:

```dotenv
GOOGLE_DRIVE_SEGMENTATION_INPUT_FOLDER_ID=ID_FOLDER_CHUA_OCR_TEXT
GOOGLE_DRIVE_SEGMENTATION_OUTPUT_FOLDER_ID=ID_FOLDER_NHAN_SEGMENTATION_TSV
```

File `HVH_311_016_raw.txt` được chuyển thành `HVH_311_016_seg.tsv`. Xem quy tắc tách
câu, xác thực Google Drive và cách chạy trên Colab tại
[`scripts/segmentation/README.md`](scripts/segmentation/README.md).
