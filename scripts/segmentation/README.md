# Sentence Segmentation Pipeline

Pipeline nay tai mot file OCR text tu Google Drive, tach cau, va upload file TSV tro lai
cung folder. Cac buoc download, upload, xac thuc Google Drive va workspace tam duoc
giu cung phong cach voi `scripts/ocr_v2/run_ocr_pipeline.py`.

## Input va output

Input tren Google Drive:

```text
post_processing/
├── HVH_016_clean.txt
```

Output sau khi chay:

```text
post_processing/
├── HVH_016_clean.txt
├── HVH_016_seg.tsv
```

Pipeline chi xu ly mot file cho moi lan chay. No chi tai file can xu ly, khong dong bo
toan bo folder.

## Cau hinh

Dat `.env` tai thu muc goc:

```dotenv
GOOGLE_DRIVE_POST_PROCESSING_FOLDER_ID=ID_FOLDER_POST_PROCESSING
GOOGLE_OAUTH_CLIENT_FILE=./secrets/google-drive-oauth-client.json
GOOGLE_OAUTH_TOKEN_FILE=./secrets/google-drive-token.json
```

## Chay local

```bash
python scripts/segmentation/run_segmentation_pipeline.py \
  --file-name "HVH_016_clean.txt"
```

Chi dinh ro folder Drive neu khong dung `.env`:

```bash
python scripts/segmentation/run_segmentation_pipeline.py \
  --drive-folder-id "YOUR_FOLDER_ID" \
  --file-name "HVH_016_clean.txt"
```

Ghi de output da ton tai:

```bash
python scripts/segmentation/run_segmentation_pipeline.py \
  --file-name "HVH_016_clean.txt" \
  --force
```

## Chay tren Colab

```bash
!/content/post_processing_env/bin/python scripts/segmentation/run_segmentation_pipeline.py \
  --use-colab-auth \
  --drive-folder-id "{DRIVE_POST_PROCESSING_FOLDER_ID}" \
  --file-name "HVH_016_clean.txt"
```

Notebook mau co san tai `scripts/segmentation/colab_segmentation_pipeline.ipynb`.

## Quy uoc tach cau

- Tach theo dau cau Han van va dau cau pho bien: `。！？；：.!?;:`
- Giu dau cau o cuoi cau
- Loai bo khoang trang du thua va full-width space
- Neu van ban khong co dau cau, fallback tach theo tung dong (đếm số dấu câu trước, nếu dấu câu = 0 thì mới dùng cái này)
- Sau khi tách câu nhớ gán id theo định dạng output bên dưới, và lưu vào file .tsv

## Dinh dang output

```text
sentence_id<TAB>sentence
```

Neu input co page marker:

```text
HVH_001_000001\t春正月帝幸布海口。
HVH_001_000002\t詔群臣議事。
```

Neu input la mot file OCR text phang:

```text
HVH_016_000001\t春正月帝幸布海口。
HVH_016_000002\t詔群臣議事。
```
