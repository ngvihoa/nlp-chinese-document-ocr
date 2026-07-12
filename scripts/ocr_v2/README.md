# OCR Google Drive Pipeline

Pipeline tải ảnh clean từ một folder Google Drive, chạy PaddleOCR và upload kết quả
vào folder Drive đích. Pipeline OCR cũ trong `scripts/ocr/` không bị thay đổi.

Mỗi folder con trực tiếp của folder nguồn được xem là một quyển sách. Pipeline xử
lý lần lượt từng sách và xóa dữ liệu tạm của sách đó trước khi chuyển sang sách kế
tiếp, nên không tải toàn bộ kho ảnh cùng lúc.

## Chuẩn bị

1. Bật Google Drive API trong Google Cloud project.
2. Tạo OAuth Client ID loại **Desktop app**.
3. Lưu client JSON tại `secrets/google-drive-oauth-client.json`.
4. Lấy folder ID từ URL của folder nguồn và folder đích.

`secrets/` đã được khai báo trong `.gitignore`.

## Chạy

```bash
source ocr_env/bin/activate
python scripts/ocr_v2/run_ocr_pipeline.py \
  --drive-input-folder-id "INPUT_FOLDER_ID" \
  --drive-output-folder-id "OUTPUT_FOLDER_ID"
```

Lần chạy đầu sẽ mở trình duyệt để đăng nhập Google. Sau khi cấp quyền, token
được tự động lưu tại `secrets/google-drive-token.json`.

Có thể cấu hình bằng biến môi trường:

```bash
export GOOGLE_DRIVE_INPUT_FOLDER_ID="INPUT_FOLDER_ID"
export GOOGLE_DRIVE_OUTPUT_FOLDER_ID="OUTPUT_FOLDER_ID"
export GOOGLE_OAUTH_CLIENT_FILE="./secrets/google-drive-oauth-client.json"
export GOOGLE_OAUTH_TOKEN_FILE="./secrets/google-drive-token.json"
python scripts/ocr_v2/run_ocr_pipeline.py
```

Pipeline tự động đọc file `.env` ở thư mục gốc project.

## Test với ít ảnh

Chạy một sách và chỉ OCR 5 ảnh đầu tiên (sắp xếp theo tên file):

```bash
python scripts/ocr_v2/run_ocr_pipeline.py \
  --book-name "TEN_FOLDER_SACH" \
  --max-books 1 \
  --max-images-per-book 5 \
  --preset mobile
```

Chạy tối đa 3 sách, mỗi sách 10 ảnh:

```bash
python scripts/ocr_v2/run_ocr_pipeline.py \
  --max-books 3 \
  --max-images-per-book 10 \
  --preset mobile
```

Tên output được chuẩn hóa theo số đầu tiên trong tên folder sách. Ví dụ `01_clean`
được upload vào `HVH_001/`, output trang có stem `HVH_001_001`, `HVH_001_002`,
và file text gộp là `HVH_001_raw.txt`. Nếu folder hoặc file đã tồn tại, pipeline
tái sử dụng folder và cập nhật file.

Mặc định dữ liệu local tạm sẽ bị xóa sau khi hoàn tất. Để giữ lại phục vụ debug:

```bash
python scripts/ocr_v2/run_ocr_pipeline.py \
  --drive-input-folder-id "INPUT_FOLDER_ID" \
  --drive-output-folder-id "OUTPUT_FOLDER_ID" \
  --keep-work-dir ./data_output/ocr-v2-work
```
