from __future__ import annotations

from map_data import LANDMARKS, Stage, cells_line_h, cells_line_v, cells_rect, walkable_cells


CSP_UNAVAILABLE_CELLS = walkable_cells({(28, 17), (29, 17), (31, 16)})


STAGE = Stage(
    6,
    "Chặng 6",
    "Nhóm 6: Thỏa mãn ràng buộc / Constraint Satisfaction Problem",
    "Campus Building Coloring as CSP: tô màu các tòa nhà sao cho các tòa kề nhau không trùng màu",
    "Chặng 6 mô phỏng bài toán tô màu đồ thị. Mỗi tòa nhà là một biến, domain là {Cam, Hồng, Xanh, Tím}. Constraint chính: hai tòa nhà kề nhau không được cùng màu. Backtracking thử màu rồi quay lui, Forward Checking loại màu khỏi hàng xóm sau khi gán, Min-Conflicts bắt đầu bằng assignment đầy đủ rồi sửa dần các biến đang xung đột.",
    LANDMARKS["CONG_CHINH"][1],
    LANDMARKS["CONG_CHINH"][1],
    ("Backtracking", "Forward Checking", "Min-Conflicts"),
    6,
    blocked=CSP_UNAVAILABLE_CELLS,
    risk=walkable_cells(
        cells_line_h(27, 20, 34)
        | cells_line_h(32, 6, 22)
        | cells_rect(29, 19, 31, 21)
        | cells_line_v(22, 23, 31)
    ) - CSP_UNAVAILABLE_CELLS,
    high_cost=walkable_cells(cells_rect(24, 30, 30, 35) | cells_line_h(22, 28, 36)) - CSP_UNAVAILABLE_CELLS,
)
