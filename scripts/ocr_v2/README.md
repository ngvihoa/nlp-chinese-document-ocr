# OCR Google Drive Pipeline

Pipeline tải ảnh clean từ Google Drive, chạy PaddleOCR và upload kết quả trở lại
Drive. Mỗi folder con trực tiếp của folder nguồn được xem là một quyển sách.
Pipeline xử lý tuần tự từng sách và dọn dữ liệu tạm trước khi chuyển sang sách kế
tiếp, nên không tải toàn bộ kho ảnh cùng lúc.

## Cài đặt

```bash
python3 -m venv ocr_env
source ocr_env/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

## Cấu hình Google Drive

1. Bật Google Drive API trong Google Cloud project.
2. Tạo OAuth Client ID loại **Desktop app**.
3. Lưu JSON tại `secrets/google-drive-oauth-client.json`.
4. Thêm tài khoản đăng nhập vào OAuth **Test users** nếu app đang ở trạng thái Testing.
5. Lấy ID của folder nguồn và folder đích từ URL Google Drive.

Tạo `.env` ở thư mục gốc project:

```dotenv
GOOGLE_DRIVE_INPUT_FOLDER_ID=ID_FOLDER_CHA_CHUA_CAC_SACH
GOOGLE_DRIVE_OUTPUT_FOLDER_ID=ID_FOLDER_NHAN_KET_QUA
GOOGLE_OAUTH_CLIENT_FILE=./secrets/google-drive-oauth-client.json
GOOGLE_OAUTH_TOKEN_FILE=./secrets/google-drive-token.json
```

Pipeline tự đọc `.env`. Lần chạy đầu sẽ mở trình duyệt để đăng nhập và tự tạo
`secrets/google-drive-token.json`. `.env` và `secrets/` không được commit.

Folder Drive nguồn cần có dạng:

```text
input-folder/
├── 01_clean/
│   ├── page_001.png
│   └── page_002.png
└── 02_clean/
    ├── page_001.png
    └── page_002.png
```

## Test nhanh

Chạy sách đầu tiên, giới hạn 5 ảnh và dùng model mobile:

```bash
source ocr_env/bin/activate
python scripts/ocr_v2/run_ocr_pipeline.py \
  --max-books 1 \
  --max-images-per-book 5 \
  --preset mobile \
  --device cpu \
  --reading-order vertical-rl \
  --vertical-column-tolerance 320 \
  --min-score 0.3
```

## Chạy một sách

Tên truyền vào `--book-name` phải khớp chính xác tên folder trên Drive:

```bash
python scripts/ocr_v2/run_ocr_pipeline.py \
  --book-name "01_clean" \
  --preset medium \
  --device cpu \
  --reading-order vertical-rl \
  --vertical-column-tolerance 320 \
  --min-score 0.3
```

Chạy một sách nhưng chỉ lấy 20 trang đầu theo thứ tự tên file:

```bash
python scripts/ocr_v2/run_ocr_pipeline.py \
  --book-name "01_clean" \
  --max-images-per-book 20 \
  --preset mobile \
  --min-score 0.3
```

## Chạy nhiều sách có giới hạn

Chạy tối đa 3 sách, mỗi sách tối đa 10 ảnh:

```bash
python scripts/ocr_v2/run_ocr_pipeline.py \
  --max-books 3 \
  --max-images-per-book 10 \
  --preset mobile \
  --device cpu \
  --reading-order vertical-rl \
  --vertical-column-tolerance 320 \
  --min-score 0.3
```

## Chạy toàn bộ

Không truyền `--book-name`, `--max-books` hoặc `--max-images-per-book`:

```bash
source ocr_env/bin/activate
python scripts/ocr_v2/run_ocr_pipeline.py \
  --preset medium \
  --device cpu \
  --reading-order vertical-rl \
  --vertical-column-tolerance 320 \
  --min-score 0.3
```

Không cần `--recursive`: pipeline luôn duyệt đệ quy ảnh bên trong mỗi folder sách.

## Chạy trên Google Colab GPU

Notebook có sẵn tại `scripts/ocr_v2/colab_ocr_pipeline.ipynb`. Upload notebook lên
Colab hoặc mở file trực tiếp từ GitHub, sau đó:

1. Chọn **Runtime > Change runtime type > T4 GPU**.
2. Chạy lần lượt các cell để clone repository và cài PaddlePaddle GPU.
3. Đăng nhập Google bằng cell `authenticate_user()`.
4. Điền folder ID nguồn và đích.
5. Chạy cell test 5 ảnh trước, sau đó mới chạy cell toàn bộ.

Trên Colab pipeline dùng `--use-colab-auth`, không cần upload OAuth client JSON hay
token cá nhân lên runtime.

Notebook dùng `requirements.colab.txt` và gỡ PyTorch khỏi runtime vì PyTorch CUDA
12.8 và PaddlePaddle CUDA 12.6 yêu cầu các phiên bản thư viện NVIDIA khác nhau.
Pipeline OCR hiện tại không sử dụng PyTorch. Nếu đã chạy cell cài đặt cũ và gặp
dependency conflict, chọn **Runtime > Restart session**, pull code mới và chạy lại
các cell từ đầu.

## Giữ dữ liệu local

Mặc định workspace từng sách bị xóa sau khi upload. Dùng tùy chọn sau để debug
hoặc dùng `--skip-existing` ở lần chạy tiếp theo:

```bash
python scripts/ocr_v2/run_ocr_pipeline.py \
  --book-name "01_clean" \
  --max-images-per-book 5 \
  --keep-work-dir ./data_output/ocr-v2-work
```

```bash
python scripts/ocr_v2/run_ocr_pipeline.py \
  --book-name "01_clean" \
  --max-images-per-book 5 \
  --keep-work-dir ./data_output/ocr-v2-work \
  --skip-existing
```

## Reading Order Và Confidence

- `vertical-rl`: cột từ phải sang trái, chữ từ trên xuống; đây là mặc định.
- `vertical-lr`: cột từ trái sang phải.
- `horizontal`: dòng từ trên xuống.
- `raw`: giữ nguyên thứ tự PaddleOCR.
- `--vertical-column-tolerance 320`: khoảng cách tâm x tối đa để gom box vào một cột.
- `--min-score 0.3`: loại dòng nhận diện có confidence dưới `0.3`; raw JSON vẫn được giữ.

## Output

Số đầu tiên trong tên folder sách được dùng làm số sách. Ví dụ `01_clean` tạo:

```text
HVH_001/
├── raw/
│   ├── HVH_001_001/
│   └── HVH_001_002/
├── texts/
│   ├── HVH_001_001.txt
│   └── HVH_001_002.txt
├── ocr_summary.json
└── HVH_001_raw.txt
```

Ảnh được sắp theo tên rồi đánh số trang từ `001`. Folder và file đã tồn tại trên
Drive sẽ được tái sử dụng hoặc cập nhật thay vì tạo bản trùng.
