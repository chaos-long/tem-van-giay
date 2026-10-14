# Triển khai GitHub Pages + Render + Supabase

## A. Cơ sở dữ liệu Supabase

1. Tạo một project trong tài khoản Supabase của nhóm, chọn gói Free cho thử nghiệm.
2. Trong SQL Editor, chạy `supabase_schema.sql`.
3. Lấy Project URL và **secret key** dành cho máy chủ, hoặc khóa JWT `service_role` cũ. Không dùng `anon`/publishable key cho máy chủ này.
4. Chỉ nhập các khóa vào Environment của Render. Không gửi khóa trong chat, không lưu vào `web/config.js` hoặc commit lên GitHub.

Hai bảng `tem_products` và `tem_scans` đã bật RLS và không có chính sách đọc công khai. Người dùng truy cập thông qua API Python. Ảnh mẫu được lưu base64 trong bảng, phù hợp mẫu nhỏ; mở rộng cần chuyển ảnh sang object storage.

## B. Máy chủ Render

1. Đăng nhập Render, kết nối repo dự án của nhóm.
2. Tạo **Blueprint** từ `render.yaml`, hoặc Docker Web Service từ repo.
3. Chọn đúng **Free**, không tự nâng cấp gói trả phí.
4. Điền các biến môi trường:

| Biến | Giá trị |
| --- | --- |
| `SUPABASE_URL` | Project URL HTTPS của Supabase |
| `SUPABASE_SERVICE_KEY` | Secret key / service_role, chỉ trên máy chủ |
| `TEM_ADMIN_TOKEN` | Khóa ngẫu nhiên, Blueprint tạo tự động; lưu riêng cho người quản lý |
| `TEM_ALLOWED_ORIGINS` | `https://chaos-long.github.io` |
| `TEM_DATA_DIR` | `/tmp/tem-state` cho cấu hình tạm; ảnh/hồ sơ dùng Supabase |

5. Sau triển khai, kiểm tra `https://TEN-DICH-VU.onrender.com/api/health`. Phải trả JSON `status: ok`, không phải trang báo lỗi.
6. Sao chép **địa chỉ công khai** của máy chủ. Địa chỉ này không phải bí mật.

Render Free ngủ sau 15 phút không có yêu cầu; khởi động lại có thể mất khoảng một phút. Nếu lần đầu web báo chờ quá lâu, đợi máy chủ khởi động rồi thử lại. Không lưu dữ liệu thật trong SQLite trên Render Free vì hệ thống file tạm có thể mất khi khởi động/triển khai lại.

## C. Giao diện GitHub Pages

1. Trong `web/config.js`, đặt:

```javascript
window.TEM_CONFIG = { apiBase: 'https://TEN-DICH-VU.onrender.com' };
```

Không thêm khóa quản lý hoặc khóa Supabase vào file này.

2. Commit lên nhánh `main`.
3. Trong repo GitHub → Settings → Pages → Source, chọn **GitHub Actions**.
4. Chờ workflow `Publish GitHub Pages` hoàn tất. Link dự kiến: `https://chaos-long.github.io/tem-van-giay/`.
5. Mở link trên điện thoại và máy tính. Trạng thái phải là **Đã kết nối**. Cấp quyền camera nếu muốn chụp trực tiếp; hoặc chọn ảnh.

## D. Đăng ký tem thật

1. Chọn/chụp ảnh một tem, kiểm tra vùng viền xanh và vùng căn ảnh.
2. Vào Quản lý mẫu, nhập `TEM_ADMIN_TOKEN` của máy chủ.
3. Nhập tên/mã sản phẩm và hồ sơ; đăng ký ảnh tem.
4. Chụp lại chính tem đó bằng ảnh khác để thử. So sánh cả với tem khác và bản in lại.
5. Không dùng dữ liệu DEMO làm bằng chứng cho khả năng chống giả trên giấy thật.

## E. Sao lưu

Trong Quản lý mẫu, chọn Tải bản sao lưu. Bản cục bộ xuất SQLite; bản Supabase xuất JSON chứa hồ sơ và ảnh base64. Không chứa khóa quản lý. Chế độ cloud chưa có nút khôi phục tự động; cần công cụ nhập dữ liệu hoặc quản trị Supabase.

## Hạn mức đã kiểm tra ngày 14/10/2026

- [GitHub Pages](https://docs.github.com/en/pages/getting-started-with-github-pages/what-is-github-pages): hosting tĩnh, không chạy Python.
- [Render Free](https://render.com/docs/free): dịch vụ ngủ, hệ thống file tạm; có giới hạn thời gian chạy và băng thông. Không cam kết hoạt động liên tục.
- [Supabase Free](https://supabase.com/pricing): 500 MB cơ sở dữ liệu; project có thể tạm dừng sau một tuần không hoạt động. Cần sao lưu và kiểm tra hạn mức.

Các dịch vụ có thể thay đổi điều kiện. Hướng dẫn này không tạo tài khoản, không nhập thẻ hoặc đăng ký gói trả phí thay người dùng.
