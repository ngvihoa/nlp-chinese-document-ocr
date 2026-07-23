# OCR Google Drive Pipeline

Pipeline tải ảnh clean từ Google Drive, chạy PaddleOCR và upload kết quả trở lại
Drive. Mỗi folder con trực tiếp của folder nguồn được xem là một quyển sách.
Pipeline xử lý tuần tự từng sách và dọn dữ liệu tạm trước khi chuyển sang sách kế
tiếp, nên không tải toàn bộ kho ảnh cùng lúc.

Pipeline này chỉ tạo kết quả OCR thô. Bước hiệu đính và tách câu bằng
`Qwen/Qwen3.6-27B` thuộc giai đoạn xử lý sau OCR và không nằm trong script này.

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

Notebook tạo virtualenv riêng tại `/content/ocr_env` để PaddlePaddle CUDA 12.6
không xung đột với PyTorch CUDA 12.8 và các package cài sẵn của Colab. Nếu đã chạy
cell cài đặt cũ và gặp dependency conflict, chọn **Runtime > Restart session**,
pull code mới và chạy lại các cell từ đầu.

Notebook dùng package `virtualenv` thay cho `python -m venv` vì một số Colab image
không cung cấp `ensurepip` cho Python hệ thống.

Các lệnh Colab dùng `--engine paddle_static`, không dùng `transformers`. Engine
`transformers` yêu cầu PyTorch/Torchvision, trong khi `paddle_static` chạy trực tiếp
trên PaddlePaddle GPU và tránh xung đột CUDA với PyTorch có sẵn của Colab.

Notebook giữ workspace tại `/content/ocr-v2-work` và dùng `--skip-existing`. Nếu
network timeout trong lúc upload, chạy lại cùng cell: raw JSON OCR đã hoàn thành
trong session sẽ được tái sử dụng. Drive API cũng tự retry tối đa 5 lần cho mỗi
request. Lưu ý `/content` sẽ mất nếu Colab reset hoặc disconnect runtime hoàn toàn.

Notebook cũng dùng `--resume-from-drive`: trước khi OCR một sách, pipeline tải output
đã upload của sách đó về workspace. Trang có raw JSON sẽ chỉ được dựng lại text và
không chạy OCR; chỉ trang chưa có JSON mới sử dụng GPU. Vì vậy vẫn resume được sau
khi Colab reset hoặc workspace local bị xóa.

Ở chế độ resume, pipeline chỉ tải các file `_res.json` từ output Drive, không tải
lại ảnh kết quả hoặc `.txt`. Nó liệt kê ảnh nguồn để giữ đúng số trang nhưng chỉ tải
file ảnh của trang chưa có JSON. Text đã tồn tại trên Drive cũng không bị upload lại.

Nếu runtime Colab và `/content/ocr-v2-work` vẫn còn sau khi interrupt, có thể bỏ
`--resume-from-drive` và chỉ giữ `--skip-existing`. Pipeline dùng JSON local, chỉ
liệt kê metadata trên Drive và chỉ tải ảnh của trang chưa hoàn thành; nó không tải
lại toàn bộ ảnh nguồn.

Mỗi trang được upload ngay sau khi OCR xong: raw JSON, ảnh kết quả và text trang.
Pipeline không chờ hoàn tất cả sách mới upload. Nếu timeout hoặc runtime dừng, chạy
lại cùng cell; `--resume-from-drive` sẽ bỏ qua OCR cho các trang đã có raw JSON.
`ocr_summary.json` và file `HVH_311_<số sách>_raw.txt` được tạo/upload khi hoàn tất sách.
Số đầu tiên trong tên folder được chuẩn hóa thành mã tập gồm 2 chữ số, ví dụ
`1_clean` tạo prefix `HVH_311_01`, còn `016_clean` tạo prefix `HVH_311_16`.

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
- Model text-line orientation mặc định bị tắt để tránh tải model phụ và vì reading
  order được xử lý từ polygon. Chỉ thêm `--use-textline-orientation` khi thực sự cần
  nhận diện dòng bị xoay 180 độ.

## Output

Số đầu tiên trong tên folder sách được dùng làm số sách. Ví dụ `01_clean` tạo:

```text
HVH_311_01/
├── raw/
│   ├── HVH_311_01_001/
│   └── HVH_311_01_002/
├── texts/
│   ├── HVH_311_01_001.txt
│   └── HVH_311_01_002.txt
├── ocr_summary.json
└── HVH_311_01_raw.txt
```

Ảnh được sắp theo tên rồi đánh số trang từ `001`. Folder và file đã tồn tại trên
Drive sẽ được tái sử dụng hoặc cập nhật thay vì tạo bản trùng.
