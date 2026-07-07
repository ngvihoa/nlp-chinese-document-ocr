# Han-Nom Scanned PDF Preprocessing

Repository này hiện chỉ triển khai tiền xử lý ảnh cho PDF scan dạng image-based, và đã hỗ trợ xử lý theo lô nhiều PDF.

## Phạm vi hiện tại

- Quét `data_input/input_*.pdf`
- Render toàn bộ trang của mỗi PDF bằng `PyMuPDF` nếu không giới hạn
- Lưu ảnh gốc vào `data_output/XX_raw/`
- Tiền xử lý bảo toàn nét mảnh Han-Nom
- Lưu ảnh sạch vào `data_output/XX_clean/`
- Ghi báo cáo riêng vào `data_output/XX_report.json`

Chưa làm: OCR, segmentation, NER, translation.

## Cấu trúc

```text
preprocess_first_10_pages.py
scripts/preprocessing.py
requirements.txt
data_input/input_*.pdf
data_output/
  01_raw/
  01_clean/
  01_report.json
  02_raw/
  02_clean/
  02_report.json
```

## Cài đặt

Tạo virtual environment trên Windows PowerShell:

```powershell
py -m venv .venv
.\\.venv\\Scripts\\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## Chạy batch preprocessing

```powershell
python preprocess_first_10_pages.py --input_dir data_input --output_dir data_output --dpi 400
```

Hoặc:

```powershell
python scripts/preprocessing.py --input_dir data_input --output_dir data_output --dpi 400
```

Tùy chọn:

- `--force` để ghi đè ảnh đã có
- `--dpi` để đổi độ phân giải render
- `--num_pages` để giới hạn số trang đầu mỗi PDF, bỏ qua tùy chọn này thì xử lý hết

## Hành vi xử lý

Pipeline:

```text
gray -> safe crop -> safe deskew -> median blur -> CLAHE -> adaptive threshold
```

Nguyên tắc:

- mặc định render toàn bộ trang của mỗi PDF
- không giữ toàn bộ PDF trong memory
- PDF được xử lý theo thứ tự số trong tên file, ví dụ `input_2.pdf` trước `input_10.pdf`
- deskew chỉ áp dụng khi góc nằm trong `[-5, 5]`
- crop và deskew thất bại thì bỏ qua, không làm crash pipeline
- mặc định resume nếu file output đã tồn tại
- nếu một PDF lỗi, batch vẫn tiếp tục các PDF còn lại

## Đầu ra báo cáo

Mỗi PDF tạo một report riêng:

- `data_output/01_report.json`
- `data_output/02_report.json`
- ...

Mỗi report chứa:

- đường dẫn PDF
- DPI
- số trang yêu cầu
- số trang đã xử lý
- trạng thái từng trang
- thông tin crop / deskew / lỗi

## Giới hạn

- Chưa có OCR
- Với PDF scan chất lượng thấp, có thể cần tinh chỉnh tham số threshold hoặc crop
