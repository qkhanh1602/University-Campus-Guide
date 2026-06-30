# University Campus Guide V15 - No Fallback Mode

Bản này sửa theo yêu cầu: **nếu thuật toán không tìm được Goal thì dừng**, không tự dùng A*/UCS để nối đường cho agent.

## Thay đổi chính

- Bỏ cơ chế tự thay path bằng A* khi thuật toán không tới Goal.
- Hill Climbing nếu kẹt local optimum sẽ dừng và báo lý do.
- Random Restart Hill Climbing nếu hết restart vẫn không tới Goal sẽ dừng tại best partial path.
- Bidirectional UCS nếu hai phía không gặp nhau sẽ dừng, không gọi UCS dự phòng.
- Minimax/Alpha-Beta/Negamax nếu frontier hết sẽ dừng, không gọi A* dự phòng.
- UI không cho bấm `M` để agent chạy nếu path chưa tới Goal.
- Search Trace vẫn hiển thị bước cuối để thấy thuật toán dừng ở đâu và vì sao.

## Kiểm tra

Chạy:

```powershell
py -3.12 test_core.py
```

Kết quả mong đợi:

- Các thuật toán tìm được đường: `DONE`.
- Các thuật toán đúng bản chất nhưng kẹt: `STOP`.
- Partial path vẫn phải liên tục và không đi xuyên tòa nhà.

Ở bản kiểm tra hiện tại: `Completed=15`, `stopped_without_fallback=3`.
