# Tem Vân Giấy

Web nghiên cứu nhận diện tem hình chữ nhật cho đồ thủ công tái chế. Dùng trên trình duyệt máy tính và điện thoại; không cần cài ứng dụng.

## Chức năng

- Camera có xem trước; chụp ảnh rồi so khớp.
- Chọn ảnh JPG/PNG/WebP từ thiết bị; căn viền tự động hoặc chọn bốn góc.
- Đăng ký, sửa, xóa ảnh mẫu và hồ sơ sản phẩm bằng khóa quản lý.
- Nhập nhiều mẫu từ bộ JSON chứa ảnh và hồ sơ, kiểm tra từng mục, báo lỗi và bỏ qua mã đã tồn tại.
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
- Đã kiểm tra tìm vùng giấy trên 30 ảnh chụp giấy của nhóm: bản cũ xử lý được 18/30, bản 0.4 xử lý được 30/30. Đây là tập dùng để sửa thuật toán, chưa phải tập đánh giá độc lập hoặc phép đo chống giả.
- Chưa thử chụp lại cùng tem bằng điện thoại thật, thay đổi ánh sáng/góc chụp hoặc tấn công bằng bản in lại.
- Tối đa 100 mẫu trong bản này; một tác vụ so khớp tại một thời điểm.
- Gói lưu trữ miễn phí có hạn mức/ngủ/tạm dừng; đây là phương án thử nghiệm.

## Kiểm thử

```powershell
.venv\Scripts\python -m pip install pytest
.venv\Scripts\python -m pytest tests -q
```

Mã nguồn không chứa khóa cơ sở dữ liệu hoặc thông tin sản phẩm thật. Các hồ sơ DEMO được ghi rõ là tình huống mô phỏng.

## Tìm viền và nhập bộ mẫu (0.4)

Tìm viền dùng cả Canny và các mặt nạ sáng/tối Otsu sau làm mượt. Nếu ảnh có chênh lệch màu đủ rõ, thêm kênh b của Lab và giao các mặt nạ để loại bớt vân nền/bóng. Thử nhiều mức xấp xỉ đa giác, giữ hình lồi bốn cạnh với tỷ lệ/cỡ phù hợp, diện tích đường viền gần diện tích tứ giác; xếp hạng theo diện tích và độ tương phản tại cả bốn cạnh. Mờ mạnh chỉ dùng để tìm vùng giấy; SIFT và DoG vẫn lấy ảnh gốc đã căn, không đổi ngưỡng nhận khớp. Giấy cong/méo, bóng đổ hoặc nền cùng màu vẫn có thể cần chọn góc thủ công.

Trong Quản lý mẫu, chọn Nhập nhiều mẫu rồi chọn tệp JSON UTF-8 `{ "records": [{ "file": "anh01.jpg", "image": "data:image/jpeg;base64,...", "product": { "product_name": "MẪU - Tên", "product_code": "MAU-001" } }] }`. `product` dùng cùng các trường của biểu mẫu đơn; `corners` là tùy chọn. Tối đa 100 mục/tệp 160 MB, mỗi ảnh vẫn dưới giới hạn API. Mỗi mục gọi API đăng ký bình thường bằng phiên quản lý hiện tại; không có đường nhập bỏ qua chất lượng, chống trùng hoặc xác thực. Khi hết thời gian/kết nối đứt, dừng và tải lại danh sách trước khi thử tiếp để tránh ghi lại một yêu cầu có thể đã thành công. Hồ sơ có mã đã tồn tại được bỏ qua, không bị ghi đè.

Giao diện giảm ảnh camera/tải lên về cạnh dài tối đa 1.200 pixel và JPEG chất lượng 90 để giảm thời gian tải. Trên bộ 30 ảnh phát triển, các ảnh giảm cỡ vẫn qua kiểm tra và khớp với PNG tham chiếu; điểm thấp nhất 0,9708 ở phép thử cục bộ. Đây là đối chiếu các bản xử lý của cùng ảnh, chưa thay thế đánh giá bằng ảnh chụp lại. Ảnh nhập hàng loạt không tự bị giảm thêm: dùng dữ liệu đã chuẩn bị trong tệp bộ mẫu.

Máy chủ đọc metadata khi đếm/liệt kê/kiểm tra mã; ảnh tham chiếu còn thiếu mới được tải vào bộ nhớ để so khớp. Mẫu vừa thêm bổ sung vào cache; mẫu đã xóa bị loại khi làm mới danh sách. 37 kiểm thử backend đạt. Trạng thái giai đoạn đăng ký chỉ cho người quản lý xem qua `/api/admin/diagnostics`; không trả khóa hay ảnh. Ngưỡng nhận khớp giữ nguyên.

## Camera điện thoại và kiểm tra ảnh chụp lại (0.5)

- Có nút **Chụp bằng camera điện thoại** dùng file input `capture="environment"`, bên cạnh camera xem trước và tải ảnh. Tùy trình duyệt/thiết bị, nút có thể mở camera hệ thống hoặc trình chọn ảnh; không bảo đảm vượt được mọi lỗi quyền của Android.
- Nếu Chrome báo lớp phủ, đóng bong bóng chat/cửa sổ nổi/ứng dụng lọc màu và kiểm tra quyền của đúng địa chỉ web. Web không tự tắt ứng dụng khác hoặc tự cấp quyền. Xem [hướng dẫn lớp phủ của Samsung](https://www.samsung.com/us/support/troubleshooting/TSG01001313/) và [HTML capture của MDN](https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Attributes/capture).
- Camera xem trước cố gắng chọn camera sau và lấy nét liên tục khi thiết bị hỗ trợ. Lỗi liệt kê camera không đóng một luồng đang hoạt động; lỗi phát video phải giải phóng luồng camera.
- Nút **Lưu ảnh đang kiểm tra** lưu chính JPEG dùng cho yêu cầu, không lưu ảnh có vẽ viền xanh. Khi báo lỗi, cung cấp ảnh này cùng mã/ảnh tham chiếu, chụp đúng cùng mặt giấy.
- Kết quả không khớp có `reason_code` và `capture_hint` theo bước đi xa nhất trong các phép so: thiếu cặp điểm, hình học, phân bố điểm, độ chồng vùng hoặc tương quan vân. Đây là giải thích việc dừng của thuật toán, không xác định nguyên nhân vật lý và không tiết lộ ảnh/mã ứng viên bị loại. Không đổi điểm, ngưỡng 0,64, khoảng cách 0,08 hoặc điều kiện RANSAC để ép nhận.

40 kiểm thử backend và 5 kiểm thử logic camera bằng Node đều đạt. Các kiểm thử camera dùng đối tượng giả lập, chưa phải thử camera Android vật lý. Người dùng báo chụp mới cùng tờ giấy không khớp; chưa có cặp ảnh đăng ký/chụp lại để tái hiện, nên lỗi nhận diện thực tế vẫn cần điều tra. Các kết quả trước trên 30 ảnh và bản biến đổi của cùng ảnh không chứng minh nhận diện ảnh chụp lại.


## Căn tinh ảnh chụp lại (0.6)

Ảnh chụp lại cùng tờ anh06 do người dùng cung cấp ngày 23/10/2026 tái hiện lỗi thật: SIFT/RANSAC có 117 inlier ở 8/9 ô nhưng điểm vân chỉ 0,4898, dưới ngưỡng 0,64. Căn phối cảnh toàn ảnh còn sai lệch nhỏ; giấy cong nhẹ và thay đổi góc chụp có thể góp phần, không kết luận duy nhất nguyên nhân vật lý từ một ảnh.

- Giữ nguyên SIFT, ratio test 0,72, RANSAC 3 pixel, ngưỡng NCC 0,64 và khoảng cách 0,08.
- Chỉ cân nhắc căn tinh khi đã vượt kiểm tra hình học cũ, có ít nhất 30 inlier, phủ ít nhất 6/9 ô và điểm ban đầu từ 0,20 đến dưới 0,80.
- ECC tinh chỉnh homography trên DoG, khởi tạo bằng RANSAC. Phải vẫn phù hợp các điểm thật: sai số trung vị tối đa 1,5 pixel, phân vị 90 tối đa 3 pixel; chuyển động góc tối đa 9 pixel. Lỗi hội tụ hoặc vượt giới hạn thì dùng phép căn trước đó.
- Lưới 5×5 ước lượng dịch cục bộ bằng tương quan, tối đa 3 pixel mỗi nút. Mỗi ô cần ít nhất 3 inlier thật, độ dịch phù hợp phần dư đặc trưng trong 2 pixel. Nội suy thành trường dịch liên tục; lấy mẫu một lần từ ảnh đầu vào để giảm mờ. Chỉ giữ điều chỉnh khi cùng công thức NCC cải thiện.
- Hình so khớp/ảnh khác biệt dùng ảnh đã căn tinh khi bước này được giữ. Bước 12 tùy chọn hiển thị ảnh trước/sau, điểm số, số ô và giới hạn dịch thực. Thống kê RANSAC vẫn dùng mặt nạ RANSAC gốc; không dựng thêm điểm giả.

Kiểm chứng cục bộ: ảnh mới nhận N01-MAU-006 với điểm 0,6916; bốn biến thể thu nhỏ/nén của chính ảnh mới đều nhận đúng (0,6437–0,6825). So ảnh mới với đủ 33 tham chiếu; chỉ mẫu 006 vượt kiểm tra hình học. 435 cặp giữa 30 ảnh tham chiếu không có cặp đạt 0,64 trong lượt thử. Đây là dữ liệu phát triển, không phải ước lượng tỷ lệ nhận sai độc lập; một biến thể chỉ vừa qua ngưỡng nên chưa bảo đảm mọi camera/góc/ánh sáng. Không thêm ảnh chụp mới vào cơ sở dữ liệu để làm kết quả này.

Vẫn phải chừa vùng vân không chữ/hình in: các họa tiết chung đủ đậm có thể lấn át vân. Kết quả này chưa chứng minh chống chụp lại/in sao tem, xác minh giấy tái chế hoặc nguồn gốc vật liệu.

Tài liệu: [OpenCV ECC](https://docs.opencv.org/doc/doxygen/html/dc/d6b/group__video__track.html).
