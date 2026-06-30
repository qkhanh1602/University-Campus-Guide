# V20 - Cải tiến sau V19

## 1. IDA* chạy rõ hơn theo style 8-puzzle
- IDA* trong project dùng `g(n) = depth` giống bài 8-puzzle, tức mỗi bước đi có cost = 1 trong phần xét threshold.
- Threshold vẫn là `f(n)=g(n)+h(n)`.
- Trace hiển thị rõ `g_depth` và `f` ở từng neighbor.
- Nhờ vậy IDA* ở chặng 2 có thể hoàn thành Goal và dễ giải thích hơn khi thuyết trình.

## 2. Không dùng fallback
- Nếu thuật toán không tìm được Goal thì dừng đúng bản chất.
- Không tự chuyển sang A*, UCS hay thuật toán khác để cứu đường.
- Agent chỉ được chạy khi path thật sự đi từ Start đến Goal.

## 3. So sánh người chơi WASD với AI
- Khi bật Manual Mode và người chơi đi đến Goal, chương trình hiện bảng so sánh:
  - Số bước của người chơi
  - Cost của người chơi
  - Số bước/cost/node đã xét của thuật toán đang chọn nếu thuật toán có path hoàn chỉnh
- Nếu thuật toán dừng giữa chừng, bảng sẽ báo rõ thuật toán chưa có path hoàn chỉnh.

## 4. Kiểm tra core
Kết quả `test_core.py` hiện tại:
- 18/18 thuật toán chạy được
- 13 thuật toán hoàn thành Goal
- 5 thuật toán dừng đúng bản chất, không fallback
- Không có path đi xuyên tòa nhà
- Không có path bị nhảy ô
