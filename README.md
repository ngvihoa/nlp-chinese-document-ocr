# nlp-chinese-document-ocr

Pipeline OCR tài liệu Hán văn/Chinese document bằng PaddleOCR v6.

Luồng mặc định:

```text
PDF input
  -> data_output/pages_raw/
  -> data_output/pages_clean/
  -> data_output/ocr-output/
```

OCR đang dùng thứ tự đọc mặc định `vertical-rl`: đọc theo cột dọc từ phải sang trái, trong mỗi cột từ trên xuống.

## Cài đặt

Linux:

```bash
python3 -m venv ocr_env
source ocr_env/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

Windows PowerShell:

```powershell
python -m venv ocr_env
.\ocr_env\Scripts\Activate.ps1
pip install --upgrade pip
pip install -r requirements.txt
```

## Chạy toàn bộ pipeline

Đặt PDF vào `data_input/input.pdf`, rồi chạy:

```bash
source ocr_env/bin/activate
python scripts/run_pipeline.py --pdf data_input/input.pdf
```

Lệnh trên sẽ:

1. Render và clean 10 trang đầu vào `data_output/pages_clean/`.
2. Chạy PaddleOCR v6 trên các ảnh clean.
3. Ghi kết quả vào `data_output/ocr-output/`.

## Chạy từng bước

Preprocess PDF:

```bash
python scripts/preprocess_first_10_pages.py \
  --pdf data_input/input.pdf \
  --out_dir data_output \
  --dpi 400 \
  --num_pages 10
```

OCR ảnh đã clean:

```bash
python scripts/ocr/run_ocr_pipeline.py \
  --input-dir data_output/pages_clean \
  --output-dir data_output/ocr-output \
  --preset medium \
  --device cpu \
  --reading-order vertical-rl \
  --vertical-column-tolerance 320
```

Nếu chỉ muốn sắp xếp lại text từ JSON OCR đã có, không chạy OCR lại:

```bash
python scripts/ocr/run_ocr_pipeline.py --skip-existing
```

## Output

- `data_output/pages_raw/`: ảnh render từ PDF.
- `data_output/pages_clean/`: ảnh đã preprocess để OCR.
- `data_output/preprocessing_report.json`: report bước preprocess.
- `data_output/ocr-output/raw/`: JSON và ảnh annotate gốc từ PaddleOCR.
- `data_output/ocr-output/texts/`: text OCR từng trang.
- `data_output/ocr-output/ocr_texts.txt`: toàn bộ text OCR đã gom chung.
- `data_output/ocr-output/ocr_summary.json`: summary JSON gồm text, score, polygon và trạng thái từng trang.

## Ghi chú

- `fitz` là module import của package `pymupdf`, package đúng trong `requirements.txt` là `pymupdf`.
- Nếu CPU yếu, dùng `--preset mobile` để chạy nhanh hơn.
- Nếu muốn giữ nguyên thứ tự PaddleOCR trả về, dùng `--reading-order raw`.
