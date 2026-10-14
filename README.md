# Tem Vân Giấy

Web nghiên cứu nhận diện tem hình chữ nhật cho đồ thủ công tái chế. Dùng trên trình duyệt máy tính và điện thoại; không cần cài ứng dụng.

## Chức năng

- Camera có xem trước; chụp ảnh rồi so khớp.
- Chọn ảnh JPG/PNG/WebP từ thiết bị; căn viền tự động hoặc chọn bốn góc.
- Đăng ký, sửa, xóa ảnh mẫu và hồ sơ sản phẩm bằng khóa quản lý.
- Trả hồ sơ chỉ khi có một mẫu đạt điều kiện so khớp.
- Lưu tên/mã sản phẩm, nguồn vật liệu, ngày thu gom, người làm, sử dụng nguồn thu và ghi chú bằng chứng.
- Sao lưu dữ liệu; nạp dữ liệu **mô phỏng** để kiểm tra thao tác.

## Trạng thái

Mã nguồn và bản thử nghiệm cục bộ đã kiểm tra. Giao diện có workflow GitHub Pages. Để tra cứu từ nhiều thiết bị qua Internet, cần cấu hình máy chủ HTTPS và cơ sở dữ liệu trực tuyến. Đừng coi việc giao diện đã mở được trên Pages là cơ sở dữ liệu đã hoạt động.

## Kiến trúc triển khai

1. **GitHub Pages:** phục vụ thư mục `web/`.
2. **Render:** chạy máy chủ Python/OpenCV bằng Docker.
3. **Supabase:** giữ ảnh mẫu và hồ sơ trong PostgreSQL; khóa dịch vụ chỉ nằm ở máy chủ.

SQLite được dùng khi chạy cục bộ. Không dùng SQLite nằm trên ổ tạm của Render Free để giữ dữ liệu thật lâu dài. Xem [hướng dẫn triển khai](DEPLOY.md).

## Chạy cục bộ

Yêu cầu Python 3.12. Tạo môi trường riêng rồi chạy:

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python demo\generate.py
$env:TEM_DATA_DIR = "$PWD\data"
.venv\Scripts\python server.py
```

Mở `http://localhost:8765`. Khóa quản lý tự tạo ở `data/settings.json`. Không đưa file này lên GitHub. Trên localhost, camera trình duyệt được phép hoạt động khi người dùng đồng ý. Qua mạng LAN HTTP, dùng tải ảnh; camera trực tiếp cần HTTPS.

## Thiết kế tem

Dùng giấy đã qua sử dụng, bề mặt mờ. Vùng chữ nhật trung tâm cần trống, không chứa QR/chữ/logo chung. Viền chỉ giúp căn ảnh; đặc trưng chung không được coi là dấu riêng. Chụp gần và đủ sáng để vân thực sự hiện trong ảnh. Giấy trắng quá ít chi tiết sẽ bị từ chối. Mỗi tem cần đăng ký trước.

## Nguyên lý

Tìm bốn góc → căn ảnh về 640 × 448 pixel → bỏ khoảng 10% mép → kiểm tra chi tiết → tìm điểm SIFT và đối chiếu hình học bằng RANSAC → so tương quan vân sau căn ảnh → xét ngưỡng và độ tách biệt với mẫu đứng thứ hai → trả hồ sơ khi đạt.

Đây là bản tự triển khai dùng SIFT và lọc chênh lệch Gaussian, không phải ứng dụng chính thức của bài Berchtold 2021. Các ngưỡng là tham số thử nghiệm, cần hiệu chỉnh trên giấy thật.

## Giới hạn

- So khớp ảnh không tự chứng minh tem là bản gốc vật lý. Bản sao ảnh hoặc in lại có thể được nhận khớp.
- Tem khớp không chứng minh nhựa đã qua sử dụng hoặc nội dung thu–chi đúng. Cần hồ sơ có bằng chứng.
- Kiểm thử hiện dùng vân tổng hợp và camera mô phỏng; chưa có kết quả trên tem giấy thật hoặc điện thoại thật.
- Tối đa 100 mẫu trong bản này; một tác vụ so khớp tại một thời điểm.
- Gói lưu trữ miễn phí có hạn mức/ngủ/tạm dừng; đây là phương án thử nghiệm.

## Kiểm thử

```powershell
.venv\Scripts\python -m pip install pytest
.venv\Scripts\python -m pytest tests -q
```

Mã nguồn không chứa khóa cơ sở dữ liệu hoặc thông tin sản phẩm thật. Các hồ sơ DEMO được ghi rõ là tình huống mô phỏng.
