# V12 - Sửa cách chạy thuật toán theo mã giả người dùng gửi

Các ảnh mã giả trong `campus_guide/assets/pseudocode/` đã được dùng để chỉnh lại phần chạy và trace.

## Đã chỉnh chính

1. **BFS**
   - Đúng kiểu `frontier <- FIFO-QUEUE()`.
   - `explored <- ∅`.
   - Lấy node đầu queue, thêm vào explored.
   - Sinh child, nếu child chưa thuộc explored/frontier thì kiểm tra Goal trước rồi mới enqueue.
   - Trace có trạng thái `GOAL-CHILD`, `ENQUEUE`, `SKIP`.

2. **DFS**
   - Đúng kiểu `frontier <- LIFO stack`.
   - `reached <- {initial}`.
   - Pop node, expand child.
   - Nếu child là Goal thì trả về ngay.
   - Child hợp lệ được add vào reached và push vào stack.

3. **IDS / DLS**
   - Giữ đúng ý mã giả: lặp depth từ 0 đến max, mỗi vòng gọi Depth-Limited Search.
   - DLS có `CUTOFF` khi đạt depth limit.
   - Trace thể hiện depth limit, cutoff, push child.

4. **A\***
   - Sửa theo mã giả: `FRONTIER = {Start}`, `REACHED = {}`.
   - Chọn node có `f(n)` nhỏ nhất.
   - Nếu neighbor nằm trong REACHED nhưng tìm được `g_new` tốt hơn thì `REOPEN`.
   - Nếu neighbor nằm trong FRONTIER và `g_new` tốt hơn thì `UPDATE`.
   - Nếu neighbor chưa thuộc cả hai thì `ADD`.
   - Trace hiện rõ `g_new`, `h`, `f`, `ADD`, `UPDATE`, `REOPEN`, `SKIP`.

5. **Greedy / Weighted A\***
   - Dùng cùng khung Priority Queue để dễ so sánh với A*.
   - Greedy ưu tiên `h(n)`.
   - Weighted A* dùng `f(n)=g(n)+w*h(n)`.

6. **Local Search**
   - Simple Hill Climbing: chọn neighbor tốt đầu tiên.
   - Steepest Hill Climbing: xét hết neighbor rồi chọn tốt nhất.
   - Random Restart Hill Climbing: nhiều restart, nhưng vẫn bảo đảm đường đi liên tục để agent không teleport.

## Kiểm tra

Đã chạy:

```powershell
py -3.12 test_core.py
```

Kết quả kỳ vọng:

```text
OK: 18/18 algorithms returned valid continuous non-building paths.
```
