# Thiết lập PaddleOCR v6 với Engine Transformers trên Windows

Tài liệu này hướng dẫn cách dọn dẹp môi trường cũ, tạo môi trường ảo và cài đặt cấu hình tối giản cho **PaddleOCR v6** trên Windows, sử dụng backend `transformers` (PyTorch) và chạy bằng **CPU**.

## 📌 Điều kiện tiên quyết

- **Hệ điều hành:** Windows 10 hoặc Windows 11
- **Terminal khuyến nghị:** PowerShell hoặc Windows Terminal
- **Phiên bản Python hỗ trợ:** Python 3.8 đến 3.12 _(Lưu ý: Không dùng Python 3.13 hoặc mới hơn do nhiều thư viện AI chưa hỗ trợ chính thức)._
- Đã cài Python và có thể chạy được một trong các lệnh sau:

```powershell
python --version
```

hoặc:

```powershell
py --version
```

---

## 🛠️ Bước 1: Dọn dẹp môi trường cũ

Nếu trước đó bạn đã cài thử và gặp lỗi, hãy mở PowerShell tại thư mục project rồi chạy:

```powershell
# Hủy kích hoạt môi trường cũ nếu đang bật
deactivate

# Xóa thư mục môi trường ảo cũ
Remove-Item -Recurse -Force .\ocr_env

# Xóa bộ nhớ đệm tải xuống của pip
pip cache purge
```

Nếu lệnh `deactivate` hoặc `Remove-Item` báo không tìm thấy môi trường cũ thì có thể bỏ qua.

---

## 🚀 Bước 2: Khởi tạo môi trường và cài đặt

1. **Tạo môi trường ảo mới:**

   ```powershell
   python -m venv ocr_env
   ```

   Nếu máy bạn dùng Python Launcher, có thể dùng:

   ```powershell
   py -3.12 -m venv ocr_env
   ```

2. **Kích hoạt môi trường ảo:**

   ```powershell
   .\ocr_env\Scripts\Activate.ps1
   ```

   Nếu PowerShell chặn chạy script, chạy lệnh này trong cùng cửa sổ PowerShell rồi kích hoạt lại:

   ```powershell
   Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
   .\ocr_env\Scripts\Activate.ps1
   ```

3. **Nâng cấp pip và cài thư viện từ `requirements.txt`:**

   ```powershell
   python -m pip install --upgrade pip
   pip install -r requirements.txt
   ```

---

## 💻 Bước 3: Hướng dẫn sử dụng

### Cách 1: Chạy trực tiếp qua dòng lệnh (CLI)

Lệnh dưới đây chạy PaddleOCR bằng CPU, phù hợp cho máy Windows không có GPU:

```powershell
paddleocr ocr -i https://cdn-uploads.huggingface.co/production/uploads/681c1ecd9539bdde5ae1733c/3ul2Rq4Sk5Cn-l69D695U.png `
    --text_detection_model_name PP-OCRv6_medium_det `
    --text_recognition_model_name PP-OCRv6_medium_rec `
    --engine transformers `
    --use_doc_orientation_classify False `
    --use_doc_unwarping False `
    --use_textline_orientation True `
    --save_path .\output `
    --device cpu
```

Nếu muốn test nhanh hơn trên CPU yếu, có thể dùng model mobile:

```powershell
paddleocr ocr -i https://cdn-uploads.huggingface.co/production/uploads/681c1ecd9539bdde5ae1733c/3ul2Rq4Sk5Cn-l69D695U.png `
    --text_detection_model_name PP-OCRv5_mobile_det `
    --text_recognition_model_name PP-OCRv5_mobile_rec `
    --engine transformers `
    --use_doc_orientation_classify False `
    --use_doc_unwarping False `
    --use_textline_orientation True `
    --save_path .\output `
    --device cpu
```

### Cách 2: Gọi mô hình trong mã nguồn Python

Tạo file Python, ví dụ `app.py`, với nội dung sau:

```python
from paddleocr import PaddleOCR

# Khởi tạo mô hình sử dụng engine transformers
ocr = PaddleOCR(use_angle_cls=True, lang="en", engine="transformers")

# Đường dẫn tới file ảnh cần quét
img_path = r"anh_test.jpg"
result = ocr.ocr(img_path, cls=True)

# In kết quả trích xuất
print("\n--- KẾT QUẢ NHẬN DIỆN CHỮ ---")
if result and result[0]:
    for line in result[0]:
        text = line[1][0]
        confidence = line[1][1]
        print(f"Chữ: {text} | Độ chính xác: {confidence:.2f}")
else:
    print("Không phát hiện được chữ hoặc ảnh lỗi.")
```

Chạy file bằng lệnh:

```powershell
python app.py
```

---

## 🧩 Lỗi thường gặp trên Windows

### PowerShell báo không chạy được `Activate.ps1`

Chạy:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\ocr_env\Scripts\Activate.ps1
```

Thiết lập này chỉ áp dụng cho cửa sổ PowerShell hiện tại.

### Lệnh `python` không chạy

Thử dùng Python Launcher:

```powershell
py --version
py -3.12 -m venv ocr_env
```

Nếu vẫn không được, hãy cài lại Python từ trang chính thức và bật tùy chọn **Add python.exe to PATH** khi cài đặt.

### Chạy chậm trên CPU

Đây là bình thường nếu dùng model medium. Để test nhanh, hãy dùng cặp model:

```powershell
--text_detection_model_name PP-OCRv5_mobile_det
--text_recognition_model_name PP-OCRv5_mobile_rec
```
