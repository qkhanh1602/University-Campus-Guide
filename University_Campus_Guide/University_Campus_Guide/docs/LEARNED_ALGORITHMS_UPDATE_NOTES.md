# V16 - Cập nhật theo thuật toán đã học

Project đã được sắp xếp lại thành 6 chặng, mỗi chặng là một môi trường và có 3 thuật toán thuộc nhóm đã học.

## Các thuật toán đã bỏ khỏi UI chính
- Dijkstra
- Bidirectional UCS
- Weighted A*
- Minimax
- Alpha-Beta Pruning
- Negamax
- Expectimax
- Risk-Averse Expectimax
- Monte Carlo Rollout

## Các thuật toán đang dùng
1. BFS, DFS, IDS
2. UCS, Greedy Best First, A*
3. IDA*, Local Beam Search, Simulated Annealing
4. Simple Hill Climbing, Steepest Hill Climbing, Random Restart Hill Climbing
5. Belief BFS, Belief UCS, Belief A*
6. Belief Greedy, Belief IDA*, Belief Local Beam

## Ghi chú
Belief Search dùng cho môi trường không chắc chắn: node = tập các vị trí có thể xảy ra. Thuật toán chỉ hoàn thành khi toàn bộ belief đạt Goal. Nếu không đạt thì dừng đúng bản chất, không dùng A* fallback.
