# University Campus Guide - PySide6 V20 Polished

Project mô phỏng tìm đường trong khuôn viên HCMUTE bằng **18 thuật toán AI** theo hướng **AI Visualizer + Mini Game**.

## Cách chạy

Mở thư mục project trong VS Code/PyCharm rồi chạy:

```powershell
py -3.12 -m pip install -r requirements.txt
py -3.12 main.py
```

Hoặc chạy file:

```text
run_game.bat
```

## Kiểm tra logic 18 thuật toán

```powershell
py -3.12 test_core.py
```

Kết quả mong đợi:

```text
OK: 18/18 algorithms executed.
```

## Danh sách 6 chặng hiện tại

| Chặng | Nhóm thuật toán | 3 thuật toán |
|---|---|---|
| 1 | Tìm kiếm mù / Uninformed Search | BFS, DFS, IDS |
| 2 | Tìm kiếm có thông tin / Informed Search | Greedy Best First, A*, IDA* |
| 3 | Tìm kiếm cục bộ / Local Search | Hill Climbing, Local Beam Search, Simulated Annealing |
| 4 | Môi trường không chắc chắn / Unknown Environment | AND-OR Graph Search, Belief State A*, Belief State BFS |
| 5 | Tìm kiếm đối kháng / Game Search | Minimax, Alpha-Beta Pruning, Expectimax |
| 6 | Thỏa mãn ràng buộc / CSP | Backtracking, Forward Checking, Min-Conflicts |

## Phím điều khiển

```text
1..6       Chọn chặng
Q/W/E      Chọn thuật toán
SPACE      Chạy / tạm dừng mô phỏng tìm kiếm
N hoặc →   Xem bước trace tiếp theo
←          Lùi bước trace
P          Bật/tắt tự chơi WASD
W/A/S/D    Di chuyển nhân vật khi Manual Mode bật
T          Mở Search Trace chi tiết
Y          Chọn GOAL bất kỳ
R          Reset GOAL gốc
L          Bật/tắt nhãn
G          Bật/tắt lưới
V          Bật/tắt lớp va chạm/collision
+ / -      Tăng/giảm tốc độ mô phỏng
ESC        Thoát
Ctrl + cuộn chuột   Zoom map
```

## Ghi chú sửa đổi bản này

- Đã đổi tên project hiển thị thành **University Campus Guide**.
- Đã chỉnh **Local Beam Search trace**: chỉ hiển thị `h(n)`/Manhattan trong bước chọn beam, không trình bày như có dùng `g(n)`.
- Đã chỉnh **Chặng 5** thành giao diện `TRACE CÂY ĐỐI KHÁNG`: khi mở trace chi tiết bằng phím **T**, UI hiển thị cây MAX → MIN/CHANCE → kết quả theo trò chơi tính điểm. Điểm ban đầu = 0; tiến gần Goal được cộng điểm, gặp mưa/bùn/đám đông/rủi ro bị trừ điểm; nhánh được chọn là nhánh có điểm tốt nhất.
- Đã chỉnh **Chặng 6** thành bài toán tô màu đồ thị CSP: Backtracking thử màu và quay lui, Forward Checking lọc domain hàng xóm, Min-Conflicts khởi tạo assignment đầy đủ rồi sửa dần biến đang xung đột.

- Đã thay thuật toán cũ ở chặng 4 bằng **Belief State BFS**.
- Đã cập nhật tên thuật toán trong `map_data.py`, `search_algorithms.py`, `belief_bfs.py`, `app_window.py` và README.
- Đã sửa lỗi trace của chặng 5: Frontier trong Game Search trước đây có thể lấy nhầm `g_cost` thay vì tọa độ ô, khiến Search Trace/overlay không cập nhật đúng theo vị trí đã tìm. Hàm `frontier_from_heap()` hiện chỉ trả về tọa độ hợp lệ dạng `(row, col)`.
- Project vẫn giữ nguyên nguyên tắc: thuật toán không tìm được thì dừng đúng bản chất, không dùng A* fallback.
