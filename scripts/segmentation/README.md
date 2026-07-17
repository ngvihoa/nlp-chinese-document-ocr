# Sentence Segmentation Pipeline

Pipeline này tải một file OCR text từ thư mục input trên Google Drive, tách câu và
upload file TSV vào thư mục output riêng. Các bước download, upload, xác thực
Google Drive và workspace tạm được giữ cùng phong cách với
`scripts/ocr_v2/run_ocr_pipeline.py`.

## Input và output

Thư mục input trên Google Drive:

```text
ocr_text/
├── HVH_016_clean.txt
```

Thư mục output sau khi chạy:

```text
segmentation/
├── HVH_016_seg.tsv
```

Pipeline chỉ xử lý một file cho mỗi lần chạy. Nó chỉ tải file cần xử lý, không đồng
bộ toàn bộ thư mục.

## Cấu hình

Đặt `.env` tại thư mục gốc:

```dotenv
GOOGLE_DRIVE_SEGMENTATION_INPUT_FOLDER_ID=ID_FOLDER_CHUA_OCR_TEXT
GOOGLE_DRIVE_SEGMENTATION_OUTPUT_FOLDER_ID=ID_FOLDER_NHAN_SEGMENTATION_TSV
GOOGLE_OAUTH_CLIENT_FILE=./secrets/google-drive-oauth-client.json
GOOGLE_OAUTH_TOKEN_FILE=./secrets/google-drive-token.json
```

## Chạy local

```bash
python scripts/segmentation/run_segmentation_pipeline.py \
  --file-name "HVH_016_clean.txt"
```

Chỉ định rõ các thư mục Drive nếu không dùng `.env`:

```bash
python scripts/segmentation/run_segmentation_pipeline.py \
  --drive-input-folder-id "YOUR_INPUT_FOLDER_ID" \
  --drive-output-folder-id "YOUR_OUTPUT_FOLDER_ID" \
  --file-name "HVH_016_clean.txt"
```

Ghi đè output đã tồn tại:

```bash
python scripts/segmentation/run_segmentation_pipeline.py \
  --file-name "HVH_016_clean.txt" \
  --force
```

## Chạy trên Colab

```bash
!/content/post_processing_env/bin/python scripts/segmentation/run_segmentation_pipeline.py \
  --use-colab-auth \
  --drive-input-folder-id "{DRIVE_SEGMENTATION_INPUT_FOLDER_ID}" \
  --drive-output-folder-id "{DRIVE_SEGMENTATION_OUTPUT_FOLDER_ID}" \
  --file-name "HVH_016_clean.txt"
```

Notebook mẫu có sẵn tại `scripts/segmentation/colab_segmentation_pipeline.ipynb`.

## Quy ước tách câu

- Tách theo dấu câu Hán văn và dấu câu phổ biến: `。！？；.!?;`
- Không tách câu tại dấu hai chấm `：` hoặc `:`.
- Giữ dấu câu ở cuối câu.
- Loại bỏ khoảng trắng dư thừa và khoảng trắng full-width.
- Nếu văn bản không có dấu câu, tách theo từng dòng.
- Gán ID cho từng câu theo định dạng bên dưới và lưu kết quả vào file `.tsv`.

## Định dạng output

```text
sentence_id<TAB>sentence
```

Nếu input có page marker:

```text
HVH_001_000001\t春正月帝幸布海口。
HVH_001_000002\t詔群臣議事。
```

Nếu input là một file OCR text phẳng:

```text
HVH_016_000001\t春正月帝幸布海口。
HVH_016_000002\t詔群臣議事。
```
