# Tem Vân Giấy

Web nghiên cứu nhận diện tem hình chữ nhật cho đồ thủ công tái chế. Dùng trên trình duyệt máy tính và điện thoại; không cần cài ứng dụng.

## Chức năng

- Camera có xem trước; chụp ảnh rồi so khớp.
- Chọn ảnh JPG/PNG/WebP từ thiết bị; căn viền tự động hoặc chọn bốn góc.
- Đăng ký, sửa, xóa ảnh mẫu và hồ sơ sản phẩm bằng khóa quản lý.
- Trả hồ sơ chỉ khi có một mẫu đạt điều kiện so khớp.
- Lưu tên/mã sản phẩm, nguồn vật liệu, ngày thu gom, người làm, sử dụng nguồn thu và ghi chú bằng chứng.
- Sao lưu dữ liệu; nạp dữ liệu **mô phỏng** để kiểm tra thao tác.
- **Xem cách nhận diện:** ảnh căn thẳng, vùng xám, hai lớp Gaussian, hiệu DoG và các điểm SIFT thực sự tìm thấy. Khi khớp duy nhất, hiện thêm các cặp trước/sau RANSAC, hai vùng đã căn và ảnh chênh lệch.

## Trạng thái

Giao diện tại https://chaos-long.github.io/tem-van-giay/ đã cấu hình API https://tem-van-giay.onrender.com. Khi tự triển khai một bản khác, làm theo DEPLOY.md để cấu hình dịch vụ và cơ sở dữ liệu của bạn. Không đưa khóa quản lý hoặc khóa Supabase vào web.

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

## Xem cách nhận diện (0.3)

Chọn/chụp ảnh ở Kiểm tra tem, rồi kéo xuống **Xem cách nhận diện**. Bấm các bước hoặc nút Trước/Tiếp để xem ảnh từ chính lần xử lý đó. Các ảnh tăng tương phản chỉ phục vụ quan sát; thuật toán vẫn dùng giá trị lọc gốc. Vòng tròn là điểm đặc trưng ảnh, không phải máy đã nhìn thấy và đếm từng sợi giấy. Nếu chất lượng kém nhưng đã tìm được tem, vẫn hiện các ảnh giúp hiểu vì sao cần chụp lại.

Sáu bước đầu gồm: căn tem, chọn vùng xám, Gaussian sigma 0,8, Gaussian sigma 4, lấy hiệu DoG và tìm điểm SIFT. Gaussian làm mờ có trọng số; sigma lớn hơn làm mượt trên phạm vi rộng hơn. Hai ảnh Gaussian được hiển thị ở 8 bit cho dễ xem, nhưng DoG dùng trực tiếp hai mảng số thực để không mất độ chính xác do làm tròn.

Sau một kết quả khớp duy nhất có thêm 5 bước: cặp ứng viên trước RANSAC, RANSAC giữ/loại cặp, các cặp được giữ, căn hai vùng và ảnh chênh lệch. Hai hình trước/sau RANSAC vẽ đúng cùng tối đa 60 cặp từ lần so khớp thực tế; xanh lam là chưa phân loại, xanh lá là giữ, đỏ là loại theo mặt nạ của phép biến đổi. Thống kê ghi tổng ứng viên, inlier/outlier và số cặp được vẽ. Nếu không có outlier thật thì không vẽ thêm đường đỏ giả.

RANSAC dùng ngưỡng sai số 3 pixel và tối đa 2.000 vòng thử. Đây là giới hạn cấu hình; OpenCV không trả lịch sử từng vòng thử, nên web không dựng hoạt ảnh các vòng lặp chưa quan sát. Ảnh chênh là minh họa phụ, không thay công thức tương quan và không thể hiện xác suất thật/giả. Không công bố ảnh mẫu hoặc ứng viên khi kết quả không khớp/chưa phân biệt được; giao diện giải thích vì sao cần hai ảnh và một mẫu được chấp nhận trước khi hiện RANSAC.

API `/api/inspect` và `/api/match` nhận `explain: true` để thêm trường `analysis`; bỏ cờ này giữ phản hồi gọn như trước. Ảnh minh họa chỉ tồn tại trong phản hồi và trình duyệt, không lưu vào cơ sở dữ liệu. Bản 0.3 giữ nguyên các ngưỡng và điều kiện nhận khớp. Khả năng chống sao chép vật lý vẫn chưa được chứng minh.

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
