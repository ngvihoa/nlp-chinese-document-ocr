# Thiết lập PaddleOCR v6 với Engine Transformers trên Linux

Tài liệu này hướng dẫn cách dọn dẹp hệ thống, thiết lập môi trường ảo và cài đặt cấu hình tối giản cho **PaddleOCR v6** sử dụng backend `transformers` (PyTorch) thay vì bộ cài PaddlePaddle truyền thống.

## 📌 Điều kiện tiên quyết

- **Hệ điều hành:** Linux-based (Ubuntu, Debian, Fedora, v.v.)
- **Phiên bản Python hỗ trợ:** Python 3.8 đến 3.12 _(Lưu ý: Không dùng Python 3.13 hoặc mới hơn do các thư viện AI chưa hỗ trợ chính thức)._

---

## 🛠️ Bước 1: Dọn dẹp hệ thống (Xóa cấu hình lỗi cũ)

Nếu trước đó bạn đã cài đặt thử nghiệm và gặp lỗi phân phối, hãy chạy các lệnh sau để làm sạch môi trường:

```bash
# Hủy kích hoạt môi trường cũ (nếu có)
deactivate 2>/dev/null

# Xóa thư mục môi trường ảo cũ
rm -rf ocr_env

# Xóa sạch bộ nhớ đệm tải xuống của pip
pip cache purge
```

---

## 🚀 Bước 2: Khởi tạo môi trường và cài đặt

1. **Tạo và kích hoạt môi trường ảo mới:**

   ```bash
   python3 -m venv ocr_env
   source ocr_env/bin/activate
   ```

2. **Nâng cấp công cụ cài đặt và cài từ file `requirements.txt`:**
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

---

## 💻 Bước 3: Hướng dẫn sử dụng

### Cách 1: Chạy trực tiếp qua dòng lệnh (CLI)

Bạn có thể quét ảnh ngay lập tức mà không cần viết code Python. Engine `transformers` sẽ tự động tải các file trọng số `.safetensors` từ Hugging Face về máy:

```bash
paddleocr ocr -i https://cdn-uploads.huggingface.co/production/uploads/681c1ecd9539bdde5ae1733c/3ul2Rq4Sk5Cn-l69D695U.png \
    --text_detection_model_name PP-OCRv6_medium_det \
    --text_recognition_model_name PP-OCRv6_medium_rec \
    --engine transformers \
    --use_doc_orientation_classify False \
    --use_doc_unwarping False \
    --use_textline_orientation True \
    --save_path ./output \
    --device cpu
```

### Cách 2: Gọi mô hình trong mã nguồn Python

Tạo một file Python (ví dụ: `app.py`) với nội dung sau để tích hợp vào ứng dụng của bạn:

```python
from paddleocr import PaddleOCR

# Khởi tạo mô hình ép buộc sử dụng engine transformers
ocr = PaddleOCR(use_angle_cls=True, lang='en', engine="transformers")

# Đường dẫn tới file ảnh cần quét
img_path = 'anh_test.jpg'
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

```bash
python app.py
```
