# V14 - Trace metric fix

## Đã sửa

- BFS không còn hiển thị `depth + 1` gây khó hiểu.
- Neighbor của BFS nay hiển thị `depth=<số bước>`.
- Search Trace tự đổi nhãn theo nhóm thuật toán:
  - BFS/DFS/IDS: hiển thị `Độ sâu` và `Heuristic: Không dùng`.
  - UCS: hiển thị `Cost g(n)`.
  - Greedy: hiển thị `h(n)`.
  - A*: hiển thị `g(n), h(n)`.
  - Hill Climbing: hiển thị `value/h`.
- Panel trace nhanh bên phải và cửa sổ Search Trace chi tiết đều dùng cùng hệ nhãn mới.

## Giải thích BFS

Trong BFS, mỗi child được sinh ra từ current sẽ nằm sâu hơn current đúng 1 cạnh, nên:

```text
depth(child) = depth(current) + 1
```

BFS không dùng heuristic và không ưu tiên theo cost trọng số. Nó duyệt theo Queue FIFO để tìm đường có số cạnh ít nhất trong môi trường không trọng số.
