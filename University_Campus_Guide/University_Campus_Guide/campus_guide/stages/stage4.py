from __future__ import annotations

from map_data import LANDMARKS, Stage, cells_line_h, cells_line_v, walkable_cells


UNCERTAIN_BLOCKS = walkable_cells({(8, 30), (10, 30), (12, 30), (13, 30), (7, 34), (8, 34)})


STAGE = Stage(
    4,
    "Chặng 4",
    "Nhóm 4: Môi trường không chắc chắn / Unknown Environment",
    "Không chắc chắn vị trí ban đầu và tìm kiếm trên belief state",
    "Chặng này dùng 3 cách xử lý môi trường không chắc chắn: AND-OR lập kế hoạch khi hành động có nhiều kết quả, Belief State A* tìm theo f(B)=g(B)+h(B), Belief State BFS duyệt belief state bằng Queue FIFO.",
    (9, 20),
    LANDMARKS["PHONG_Y_TE"][1],
    ("AND-OR Graph Search", "Belief State A*", "Belief State BFS"),
    4,
    blocked=UNCERTAIN_BLOCKS,
    high_cost=walkable_cells(
        cells_line_h(4, 29, 31)
        | cells_line_v(39, 7, 18)
        | cells_line_h(7, 31, 39)
        | cells_line_h(9, 29, 35)
    ) - UNCERTAIN_BLOCKS,
    uncertain_starts={LANDMARKS["KTX"][1], LANDMARKS["CAN_TIN"][1]},
)
