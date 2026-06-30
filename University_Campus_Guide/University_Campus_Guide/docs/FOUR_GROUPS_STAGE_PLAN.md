# University Campus Guide V17 - Kế hoạch 4 nhóm chính + 2 nhóm bổ sung

Bản này sắp lại project theo đúng hướng: ưu tiên thuật toán đã học trong tài liệu lý thuyết.
Mỗi chặng vẫn có đúng 3 thuật toán để dùng các phím Q/W/E.

## 4 nhóm chính đã học

### Nhóm 1 - Tìm kiếm mù / Uninformed Search
Không dùng heuristic h(n).

- BFS: Queue FIFO, xét theo tầng.
- DFS: Stack LIFO, đi sâu trước.
- IDS: DFS lặp sâu dần theo depth limit.
- UCS: Priority Queue theo g(n), không dùng h(n).

Vì mỗi chặng chỉ có 3 thuật toán, chặng 1 dùng BFS, DFS, IDS. UCS được đặt ở chặng 2 để so sánh trực tiếp với Greedy và A* trong môi trường có cost.

### Nhóm 2 - Tìm kiếm có thông tin / Informed Search
Có dùng heuristic h(n).

- Greedy: chọn node có h(n) nhỏ nhất.
- A*: chọn node có f(n)=g(n)+h(n) nhỏ nhất.
- IDA*: giống A* nhưng dùng threshold f(n) tăng dần như IDS.

### Nhóm 3 - Tìm kiếm cục bộ / Local Search
Không tập trung lưu toàn bộ frontier lớn, mà cải thiện trạng thái hiện tại hoặc một tập trạng thái hiện tại.

- Simple Hill Climbing
- Steepest Hill Climbing
- Random Restart Hill Climbing
- Local Beam Search
- Simulated Annealing

### Nhóm 4 - Tìm kiếm trong môi trường không chắc chắn
Dùng belief state.

- Node = tập nhiều trạng thái có thể xảy ra.
- Thuật toán chỉ kết thúc khi tất cả trạng thái trong belief state đều đạt Goal Set.
- Có thể áp dụng lại BFS, UCS, Greedy, A*, IDA*, Local Beam trên belief state.

## 6 chặng trong project

| Chặng | Nhóm/môi trường | 3 thuật toán |
|---|---|---|
| 1 | Tìm kiếm mù cơ bản | BFS, DFS, IDS |
| 2 | Cost + heuristic toàn cục | UCS, Greedy Best First, A* |
| 3 | Heuristic nâng cao + Local Search nâng cao | IDA*, Local Beam Search, Simulated Annealing |
| 4 | Hill Climbing | Simple Hill Climbing, Steepest Hill Climbing, Random Restart Hill Climbing |
| 5 | Belief State cơ bản | Belief BFS, Belief UCS, Belief A* |
| 6 | Belief State nâng cao | Belief Greedy, Belief IDA*, Belief Local Beam |

## Ghi chú báo cáo

Hai chặng 5 và 6 là phần mở rộng từ nhóm môi trường không chắc chắn. Mục tiêu là giúp project vẫn đủ 6 môi trường, mỗi môi trường có 3 thuật toán, nhưng không đưa các thuật toán chưa học như Dijkstra, Weighted A*, Minimax, Alpha-Beta, Negamax, Expectimax hay Monte Carlo vào danh sách chính.
