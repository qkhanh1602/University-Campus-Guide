# University Campus Guide

**University Campus Guide** là project trực quan hóa các thuật toán Trí tuệ nhân tạo trên bản đồ trường đại học dạng lưới. Project được xây dựng bằng **Python** và **PySide6**, cho phép người dùng chọn từng chặng, chọn thuật toán, quan sát animation trên bản đồ và xem chi tiết quá trình giải thông qua **Search Trace**.

Mục tiêu chính của project không chỉ là tìm đường từ **START** đến **GOAL**, mà còn mô phỏng nhiều kiểu môi trường khác nhau để thể hiện bản chất của từng nhóm thuật toán AI.

---

## Tính năng chính

- Trực quan hóa bản đồ trường đại học dạng lưới.
- Hiển thị START, GOAL, vật cản, frontier, reached set và path cuối cùng.
- Hỗ trợ Search Trace để xem từng bước thuật toán xử lý.
- Chia project thành 6 chặng tương ứng với 6 nhóm thuật toán AI.
- Có chế độ chọn GOAL thủ công để thử nghiệm các tình huống khác nhau.
- Hỗ trợ phóng to, thu nhỏ, bật/tắt lưới và quan sát animation.
- Có file `test_core.py` để kiểm tra logic của 18 thuật toán.

---

## Công nghệ sử dụng

- **Python 3.12+**
- **PySide6**
- Cấu trúc project theo module Python
- Giao diện desktop bằng Qt/PySide6

---

## Cấu trúc project

```text
University_Campus_Guide/
├── main.py                  
├── test_core.py             # Kiểm tra logic các thuật toán
├── requirements.txt         # Danh sách thư viện cần cài
├── run_game.bat             # File chạy nhanh trên Windows
└── campus_guide/
    ├── main.py              # Khởi chạy ứng dụng PySide6
    ├── app_window.py        # Cửa sổ giao diện chính
    ├── map_data.py          # Dữ liệu bản đồ, tọa độ, chi phí và cấu hình chung
    ├── map_scene.py         # Render bản đồ và overlay thuật toán
    ├── trace_dialog.py      # Cửa sổ Search Trace chi tiết
    ├── assets/              # Hình ảnh bản đồ, pseudocode, tài nguyên minh họa
    ├── stages/              # Cấu hình từng chặng
    │   ├── stage1.py
    │   ├── stage2.py
    │   ├── stage3.py
    │   ├── stage4.py
    │   ├── stage5.py
    │   └── stage6.py
    └── algorithms/          # Các thuật toán AI được triển khai
        ├── bfs.py
        ├── dfs.py
        ├── ids.py
        ├── greedy_best_first.py
        ├── astar.py
        ├── ida_star.py
        ├── local_beam.py
        ├── simulated_annealing.py
        ├── and_or_graph_search.py
        ├── belief_astar.py
        ├── belief_bfs.py
        ├── minimax.py
        ├── alpha_beta.py
        ├── expectimax.py
        ├── backtracking_csp.py
        ├── forward_checking_csp.py
        └── min_conflicts_csp.py
```

---

## Danh sách thuật toán

| Chặng | Nhóm thuật toán | Thuật toán |
|---|---|---|
| 1 | Tìm kiếm mù / Uninformed Search | BFS, DFS, IDS |
| 2 | Tìm kiếm có thông tin / Informed Search | Greedy Best First Search, A*, IDA* |
| 3 | Tìm kiếm cục bộ / Local Search | Hill Climbing, Local Beam Search, Simulated Annealing |
| 4 | Môi trường không chắc chắn / Unknown Environment | AND-OR Graph Search, Belief State A*, Belief State BFS |
| 5 | Tìm kiếm đối kháng / Game Search | Minimax, Alpha-Beta Pruning, Expectimax |
| 6 | Thỏa mãn ràng buộc / CSP | Backtracking CSP, Forward Checking CSP, Min-Conflicts CSP |

---

## Ý tưởng từng chặng

### Chặng 1: Tìm kiếm mù
Chặng này minh họa các thuật toán không sử dụng heuristic. Các thuật toán chỉ dựa vào cấu trúc không gian trạng thái, frontier, reached set và parent để tìm đường.

### Chặng 2: Tìm kiếm có thông tin
Chặng này sử dụng heuristic Manhattan để định hướng quá trình tìm kiếm. Môi trường có thêm vùng cost cao để thể hiện sự khác nhau giữa Greedy Best First Search, A* và IDA*.

### Chặng 3: Tìm kiếm cục bộ
Chặng này mô phỏng đặc điểm của local search. Thuật toán không duyệt toàn bộ không gian trạng thái mà tập trung vào trạng thái hiện tại hoặc một nhóm trạng thái ứng viên.

### Chặng 4: Môi trường không chắc chắn
Chặng này thể hiện tình huống một hành động có thể sinh ra nhiều result states hoặc agent phải tìm kiếm trên tập belief states. AND-OR Graph Search minh họa rõ cơ chế OR node và AND node.

### Chặng 5: Tìm kiếm đối kháng
Chặng này mô phỏng môi trường có đối thủ hoặc yếu tố bất lợi. MAX là agent, MIN là đối thủ hoặc môi trường gây bất lợi, còn CHANCE được sử dụng trong Expectimax để mô phỏng outcome ngẫu nhiên.

### Chặng 6: CSP
Chặng này mô hình hóa bài toán tô màu tòa nhà trên campus. Mỗi tòa nhà là một biến, domain là tập màu có thể gán, constraint chính là hai tòa nhà kề nhau không được cùng màu.

---

## Cài đặt

Clone project từ GitHub:

```bash
git clone https://github.com/<username>/<repository-name>.git
cd <repository-name>
```

Cài thư viện cần thiết:

```bash
pip install -r requirements.txt
```

Hoặc trên Windows có thể dùng Python launcher:

```powershell
py -3.12 -m pip install -r requirements.txt
```

---

## Cách chạy chương trình

Chạy bằng terminal:

```bash
python main.py
```

Hoặc trên Windows:

```powershell
py -3.12 main.py
```

Có thể chạy nhanh bằng file:

```text
run_game.bat
```

---

## Kiểm thử thuật toán

Chạy file kiểm thử:

```bash
python test_core.py
```

Kết quả mong đợi:

```text
OK: 18/18 algorithms executed.
```

Lưu ý: Một số thuật toán có thể dừng trước GOAL trong một vài cấu hình môi trường. Đây không nhất thiết là lỗi, mà có thể phản ánh đúng bản chất của thuật toán, ví dụ local search bị kẹt cực trị cục bộ hoặc belief state search bị giới hạn mở rộng.

---

## Phím điều khiển

```text
1..6       Chọn chặng
Q/W/E      Chọn thuật toán trong chặng hiện tại
SPACE      Chạy hoặc tạm dừng mô phỏng
N hoặc →   Xem bước trace tiếp theo
←          Lùi bước trace
T          Mở cửa sổ Search Trace chi tiết
Y          Chọn GOAL thủ công
R          Reset GOAL mặc định
G          Bật/tắt lưới
+ / -      Tăng/giảm tốc độ mô phỏng
ESC        Thoát chương trình
Ctrl + cuộn chuột   Zoom bản đồ
```

---

## Kết quả và đánh giá

Project cho phép so sánh các thuật toán theo các tiêu chí:

- Trạng thái hoàn thành hay dừng trước GOAL
- Tổng chi phí đường đi `Cost`
- Số node mở rộng `Expanded`
- Số bước đi `Steps`
- Thời gian chạy `Time`
- Khả năng thể hiện đúng bản chất thuật toán qua Search Trace

Trong báo cáo, nhóm chọn một thuật toán đại diện cho mỗi chặng để so sánh trực quan bằng biểu đồ.

---

## Ghi chú khi đưa project lên GitHub

Các thư mục/file sau không nên đưa lên GitHub:

```text
.git/
.idea/
.vscode/
__pycache__/
*.pyc
*.zip
*.rar
*.7z
*.mp4
*.gif
```

Nên sử dụng file `.gitignore` để loại bỏ cache, môi trường ảo, file build và các file nặng không cần thiết.

---

## Thành viên nhóm

| Họ tên | MSSV |
|---|---|
| Nguyễn Quốc Khánh | 24110251 |
| Võ Cao Quốc Khánh | 24110252 |
| Đặng Nhật Phúc | 24110304 |

---

## Giảng viên hướng dẫn

**TS. Phan Thị Huyền Trang**

---

## Mục tiêu học thuật

Project giúp người học hiểu rõ hơn cách các thuật toán AI hoạt động trong từng loại môi trường khác nhau. Thay vì chỉ xem kết quả cuối cùng, người dùng có thể quan sát quá trình mở rộng node, cập nhật frontier, truy vết đường đi, đánh giá cây đối kháng và xử lý ràng buộc CSP. Nhờ đó, các khái niệm như `frontier`, `reached set`, `heuristic`, `belief state`, `game tree`, `alpha-beta pruning`, `variables`, `domains` và `constraints` trở nên trực quan và dễ tiếp cận hơn.
