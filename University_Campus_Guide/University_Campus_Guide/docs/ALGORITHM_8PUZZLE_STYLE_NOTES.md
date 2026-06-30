# Ghi chú chỉnh thuật toán theo 8-puzzle

## Đã chỉnh sát 8-puzzle

- BFS: Queue FIFO, pop node rồi goal-test, reached khi enqueue.
- DFS: Stack LIFO, pop node rồi goal-test, reached khi push.
- Greedy: Priority Queue theo h(n), reached khi pop.
- A*: heap theo f(n), frontier_best_f, reached, ADD/UPDATE/SKIP.
- Hill Climbing: dùng h(n), h càng nhỏ càng tốt.

## Không dùng BFS cách 2

Theo yêu cầu, project chỉ giữ một thuật toán BFS trong nhóm tìm kiếm không có thông tin.

## Lý do vẫn có A* hỗ trợ cho Local Search

Local Search thật có thể dừng tại local optimum. Để phần game vẫn cho nhân vật về Goal và không teleport, trace sẽ ghi rõ đoạn local thật dừng ở đâu, sau đó có đoạn A* hỗ trợ hiển thị.
