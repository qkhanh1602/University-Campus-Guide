# University Campus Guide V20 - Final 6 Groups Plan

Bản này sắp lại 6 chặng theo cấu trúc hiện tại trong code: mỗi chặng là một môi trường và có đúng 3 thuật toán chính.

| Chặng | Nhóm thuật toán | 3 thuật toán |
|---|---|---|
| 1 | Tìm kiếm mù / Uninformed Search | BFS, DFS, IDS |
| 2 | Tìm kiếm có thông tin / Informed Search | Greedy Best First, A*, IDA* |
| 3 | Tìm kiếm cục bộ / Local Search | Hill Climbing, Local Beam Search, Simulated Annealing |
| 4 | Môi trường không chắc chắn / Unknown Environment | AND-OR Graph Search, Belief State A*, Belief State BFS |
| 5 | Tìm kiếm đối kháng / Game Search | Minimax, Alpha-Beta Pruning, Expectimax |
| 6 | Thỏa mãn ràng buộc / CSP | Backtracking, Forward Checking, Min-Conflicts |

## Ghi chú

- Chặng 4 dùng belief state/search trong môi trường không chắc chắn.
- Chặng 5 dùng game search và đã sửa trace frontier để hiển thị đúng tọa độ đã tìm.
- Nếu thuật toán không tìm được Goal thì dừng, không dùng A* fallback.
- Test core kiểm tra path liên tục, không xuyên tòa nhà/chướng ngại.
