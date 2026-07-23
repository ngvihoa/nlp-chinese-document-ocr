# Sentence Segmentation Pipeline

Pipeline này tải một file OCR text từ Google Drive, tách câu theo luật, ghi TSV,
rồi upload kết quả lên Google Drive. Cách xác thực, download/upload, retry và
workspace tạm được viết cùng phong cách với `scripts/ocr_v2/run_ocr_pipeline.py`.

Script chính:

```text
scripts/segmentation/run_segmentation_pipeline.py
```

Notebook mẫu:

```text
scripts/segmentation/colab_segmentation_pipeline.ipynb
scripts/segmentation/kaggle_segmentation_pipeline.ipynb
```

## Luồng xử lý

1. Xác thực Google Drive bằng OAuth local hoặc Colab auth.
2. Tìm đúng file OCR text trong Drive input folder theo `--file-name`.
3. Tải duy nhất file đó về workspace tạm.
4. Tách câu và ghi file TSV local.
5. Upload TSV lên Drive output folder.
6. Nếu output đã tồn tại và không có `--force`, pipeline bỏ qua file đó.

Pipeline chỉ xử lý một file trong mỗi lần chạy; nó không đồng bộ toàn bộ folder.

## Cấu hình Drive

Đặt `.env` tại thư mục gốc nếu chạy local:

```dotenv
GOOGLE_DRIVE_SEGMENTATION_INPUT_FOLDER_ID=ID_FOLDER_CHUA_OCR_TEXT
GOOGLE_DRIVE_SEGMENTATION_OUTPUT_FOLDER_ID=ID_FOLDER_NHAN_SEGMENTATION_TSV
GOOGLE_OAUTH_CLIENT_FILE=./secrets/google-drive-oauth-client.json
GOOGLE_OAUTH_TOKEN_FILE=./secrets/google-drive-token.json
```

Input folder chứa OCR text:

```text
ocr_text/
├── HVH_311_016_raw.txt
├── HVH_311_019_raw.txt
```

Output folder nhận TSV:

```text
segmentation/
├── HVH_311_016_seg.tsv
├── HVH_311_019_seg.tsv
```

## Quy ước tên file

Input chuẩn là file OCR raw theo dạng `HVH_311_<mã tập>_raw.txt`. Script vẫn nhận
legacy input `HVH_<mã tập>_raw.txt` hoặc `*_clean.txt`, nhưng output luôn theo
chuẩn `HVH_311_<mã tập>_seg.tsv`.

Ví dụ:

```text
HVH_311_011_raw.txt   -> HVH_311_011_seg.tsv
HVH_011_raw.txt       -> HVH_311_011_seg.tsv
HVH_011_clean.txt     -> HVH_311_011_seg.tsv
```

Sentence ID của text phẳng dùng prefix của file output, sau khi bỏ `_seg.tsv`:

```text
HVH_311_011_000001
HVH_311_011_000002
```

Nếu input có page marker dạng `<page id="...">...</page>`, sentence ID dùng page
id trong marker:

```text
HVH_001_000001
HVH_001_000002
```

## Chạy local

Chạy bằng folder ID trong `.env`:

```bash
python scripts/segmentation/run_segmentation_pipeline.py \
  --file-name "HVH_311_016_raw.txt"
```

Chỉ định Drive folder trực tiếp:

```bash
python scripts/segmentation/run_segmentation_pipeline.py \
  --drive-input-folder-id "YOUR_INPUT_FOLDER_ID" \
  --drive-output-folder-id "YOUR_OUTPUT_FOLDER_ID" \
  --file-name "HVH_311_016_raw.txt"
```

Ghi đè output đã tồn tại:

```bash
python scripts/segmentation/run_segmentation_pipeline.py \
  --drive-input-folder-id "YOUR_INPUT_FOLDER_ID" \
  --drive-output-folder-id "YOUR_OUTPUT_FOLDER_ID" \
  --file-name "HVH_311_016_raw.txt" \
  --force
```

Giữ workspace local để debug:

```bash
python scripts/segmentation/run_segmentation_pipeline.py \
  --file-name "HVH_311_016_raw.txt" \
  --keep-work-dir ./data_output/segmentation-work
```

## Chạy trên Colab

Trong Colab, chạy `auth.authenticate_user()` trước, rồi dùng:

```bash
!/content/post_processing_env/bin/python scripts/segmentation/run_segmentation_pipeline.py \
  --use-colab-auth \
  --drive-input-folder-id "{DRIVE_SEGMENTATION_INPUT_FOLDER_ID}" \
  --drive-output-folder-id "{DRIVE_SEGMENTATION_OUTPUT_FOLDER_ID}" \
  --file-name "HVH_311_016_raw.txt"
```

Notebook mẫu nằm ở:

```text
scripts/segmentation/colab_segmentation_pipeline.ipynb
```

## Chạy trên Kaggle

Notebook Kaggle hiện có tại:

```text
scripts/segmentation/kaggle_segmentation_pipeline.ipynb
```

Notebook này clone branch `Nhat`, tạo virtualenv tại
`/kaggle/working/post_processing_env`, rồi chạy cùng script segmentation với
`--use-colab-auth`. Khi dùng Kaggle, cần đảm bảo notebook có cách xác thực Google
phù hợp với môi trường đang chạy.

## Quy ước tách câu

Pipeline hiện dùng rule-based segmentation, không dùng model ML.

Dấu kết thúc câu:

```text
。！？；：.!?;:
```

Luật chính:

- Giữ dấu câu ở cuối câu.
- Giữ dấu ngoặc đóng như `」`, `』`, `”`, `’`, `】`, `）`, `》`, `〕`, `〉` cùng câu với dấu kết thúc đứng trước.
- Theo dõi các cặp ngoặc `「」`, `『』`, `“”`, `‘’`, `（）`, `()`, `【】`, `[]`, `《》`, `〈〉`, `〔〕`.
- Không tách tại `:` hoặc `：` nếu dấu đó đang nằm bên trong một cặp ngoặc.
- Không tách tại dấu `.` nếu nó nằm giữa chữ hoặc số ASCII, ví dụ `H.M.2205` hoặc `3.14`.
- Chuẩn hóa BOM, full-width space, xuống dòng Windows và khoảng trắng dư thừa.
- Nếu toàn văn bản không có dấu kết thúc câu nào, fallback sang tách từng dòng.
- Nếu có page marker, tách câu riêng trong từng page marker.

## Output TSV

File output là UTF-8 TSV và luôn có header:

```text
sentence_id<TAB>sentence
```

Ví dụ text phẳng:

```text
sentence_id	sentence
HVH_311_011_000001	春正月帝幸布海口。
HVH_311_011_000002	詔群臣議事。
```

Ví dụ có page marker:

```text
sentence_id	sentence
HVH_001_000001	春正月帝幸布海口。
HVH_001_000002	詔群臣議事。
```

## Lưu ý hiện tại

- `--doc-id` có trong CLI để override prefix sentence ID; mặc định prefix được suy ra từ tên file input theo chuẩn `HVH_311_<mã tập>`.
- Nếu output đã tồn tại trên Drive output folder, script sẽ skip trước khi download input, trừ khi dùng `--force`.
- Script yêu cầu `GOOGLE_DRIVE_SEGMENTATION_INPUT_FOLDER_ID` và `GOOGLE_DRIVE_SEGMENTATION_OUTPUT_FOLDER_ID`, hoặc truyền trực tiếp bằng CLI.

## Đổi tên output cũ

Nếu đã có sẵn file local từ các lần chạy cũ, dùng utility sau để đổi tên và sửa
`sentence_id` trong TSV:

```bash
python scripts/segmentation/rename_existing_outputs.py \
  --ocr-output-dir ./ocr_output \
  --segment-dir ./sentences_segment
```

Chạy thử trước khi ghi file:

```bash
python scripts/segmentation/rename_existing_outputs.py \
  --ocr-output-dir ./ocr_output \
  --segment-dir ./sentences_segment \
  --dry-run
```

Utility này đổi:

```text
ocr_output/HVH_011_raw.txt -> ocr_output/HVH_311_011_raw.txt
sentences_segment/HVH_011_*_seg.tsv -> sentences_segment/HVH_311_011_seg.tsv
```

Và viết lại `sentence_id` trong TSV thành:

```text
HVH_311_011_000001
HVH_311_019_000001
```
