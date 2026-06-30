# Stage 5 Progressive Tree Trace Update

Các thay đổi trong bản này:

1. Search Trace chặng 5 không còn bị dồn phần bảng chi tiết xuống quá thấp.
   - Tăng kích thước mặc định cửa sổ trace.
   - Giảm chiều cao tối thiểu của vùng cây.
   - Tăng chiều cao tối thiểu cho bảng chi tiết.
   - Người dùng vẫn có thể kéo thanh chia giữa cây và bảng.

2. Cây đối kháng hiển thị theo từng bước.
   - Khi bấm `Bước sau`, cây sẽ mở rộng dần theo trace hiện tại.
   - Nút đang xét được tô màu vàng và ghi `ĐANG XÉT`.
   - Khi đến bước cuối hoặc Goal, cây hiển thị đầy đủ từ Start đến Goal.

3. Cây vẫn hỗ trợ kéo thả và phóng to/thu nhỏ.
   - Kéo chuột trái để pan.
   - Lăn chuột để zoom.
   - Nút `Vừa khung` tự fit toàn bộ cây vào vùng xem.

4. Core thuật toán không đổi.
   - Chỉ sửa UI Search Trace và cách hiển thị cây.
