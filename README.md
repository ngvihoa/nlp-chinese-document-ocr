# OCR tài liệu Hán văn

Pipeline xây dựng ngữ liệu đơn ngữ chữ Hán từ bộ _Việt Nam Hán Văn Tiểu Thuyết
Tập Thành_ (tập 11-20). Quy trình hiện có trong repository gồm tiền xử lý PDF,
OCR bằng PP-OCRv6 Medium, khôi phục thứ tự đọc dọc và tách câu theo quy tắc.

Sản phẩm cuối cùng của đồ án sử dụng thêm `Qwen/Qwen3.6-27B` để hiệu đính và hỗ
trợ tách câu. Phần mã nguồn Qwen chưa có trong repository tại thời điểm hiện tại.

## Quy trình

```text
PDF
  -> ảnh PNG 400 DPI
  -> tiền xử lý ảnh
  -> PP-OCRv6 Medium
  -> sắp cột dọc từ phải sang trái
  -> văn bản OCR thô
  -> hiệu đính và tách câu bằng Qwen3.6-27B
  -> ngữ liệu theo câu
```

Định dạng sản phẩm cuối cùng của mỗi tập:

```text
HVH_311_<volume>_raw.txt
HVH_311_<volume>_seg.txt
```

Lưu ý: script tách câu theo quy tắc hiện có trong repository tạo tệp `.tsv`. Tệp
`_seg.txt` là đầu ra của pipeline Qwen chưa được push.

## Cài đặt

```bash
python3 -m venv ocr_env
source ocr_env/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

Python 3.8-3.12 được khuyến nghị. Khi chạy trên Colab, sử dụng
`requirements.colab.txt` và notebook tương ứng trong `scripts/`.

## 1. Tiền xử lý PDF

```bash
python scripts/preprocessing.py \
  --input_dir ./data_input \
  --output_dir ./data_output \
  --dpi 400
```

Script kết xuất PDF thành ảnh PNG ở 400 DPI, sau đó chuyển mức xám, cắt viền,
chỉnh nghiêng, khử nhiễu, tăng tương phản và nhị phân hóa. Đầu vào phải có tên
`input_<number>.pdf`. Kết quả gồm ảnh gốc, ảnh clean và báo cáo JSON cho từng tập.

Sau khi tiền xử lý, upload các folder ảnh clean lên folder nguồn Google Drive để
pipeline OCR sử dụng.

## 2. OCR trên Google Drive

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
  --device gpu:0 \
  --reading-order vertical-rl \
  --vertical-column-tolerance 320 \
  --min-score 0.3
```

Mỗi folder con trực tiếp trong folder Drive nguồn được xem là một sách. Pipeline
xử lý tuần tự từng sách, upload kết quả sau mỗi trang và hỗ trợ tiếp tục bằng
`--resume-from-drive`. Theo mã nguồn hiện tại, OCR tạo trực tiếp tệp
`HVH_311_<volume>_raw.txt`.

Xem hướng dẫn OAuth, `.env`, cấu trúc Drive và toàn bộ ví dụ tại
[`scripts/ocr_v2/README.md`](scripts/ocr_v2/README.md).

## 3. Tách câu theo quy tắc

Script hiện có tải một tệp OCR từ Drive, chuẩn hóa văn bản, tách theo dấu câu Hán
văn và upload kết quả dạng TSV vào folder đích:

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

Theo mã nguồn hiện tại, mã tập được chuẩn hóa thành 2 chữ số: chẳng hạn
`HVH_311_016_raw.txt` được chuyển thành `HVH_311_16_seg.tsv`, còn
`HVH_311_1_raw.txt` thành `HVH_311_01_seg.tsv`. Đây là pipeline tách câu theo quy tắc, không phải pipeline
Qwen tạo sản phẩm cuối cùng `HVH_311_16_seg.txt`. Xem quy tắc tách câu, xác thực
Google Drive và cách chạy trên Colab tại
[`scripts/segmentation/README.md`](scripts/segmentation/README.md).

## 4. Đổi tên kết quả cũ

Kiểm tra thay đổi trước khi thực hiện:

```bash
python scripts/rename_existing_outputs.py \
  --ocr-output-dir ./ocr-output \
  --segment-dir ./segmentation-output \
  --dry-run
```

Bỏ `--dry-run` để chuyển các tên cũ sang quy ước `HVH_311_<volume>` và cập nhật
`sentence_id` trong các tệp TSV. Tiện ích này chỉ cần thiết với kết quả được tạo
trước khi pipeline áp dụng quy ước tên hiện tại.

## Cấu trúc mã nguồn

```text
scripts/preprocessing.py                  Chuyển PDF và tiền xử lý ảnh
scripts/ocr_v2/run_ocr_pipeline.py        Điều phối OCR và Google Drive
scripts/ocr_v2/ocr_core.py                Chạy PaddleOCR và sắp thứ tự đọc
scripts/segmentation/run_segmentation_pipeline.py
                                           Tách câu theo quy tắc
scripts/rename_existing_outputs.py        Chuẩn hóa tên kết quả đã có
```

## Báo cáo

Bản thảo báo cáo nằm tại [`report/report-draft.md`](report/report-draft.md).
