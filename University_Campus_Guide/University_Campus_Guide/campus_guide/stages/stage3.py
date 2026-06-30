from __future__ import annotations

from map_data import LANDMARKS, Stage, cells_line_h, walkable_cells


LOCAL_TRAP = walkable_cells({(9, 22), (9, 23), (9, 24), (10, 22), (10, 24), (11, 22), (11, 24)})


STAGE = Stage(
    3,
    "Chặng 3",
    "Nhóm 3: Tìm kiếm cục bộ / Local Search",
    "Đường ngắn, có dải cost cao để thấy local search không tối ưu cost",
    "Chặng này đủ ngắn để chạy tay nhưng vẫn cho thấy bản chất Local Search: Hill Climbing đi theo h(n), Local Beam giữ k trạng thái tốt nhất, Simulated Annealing có thể nhận bước xấu.",
    LANDMARKS["THU_VIEN"][1],
    LANDMARKS["PHONG_Y_TE"][1],
    ("Hill Climbing", "Local Beam Search", "Simulated Annealing"),
    3,
    blocked=LOCAL_TRAP,
    high_cost=walkable_cells(cells_line_h(9, 21, 29) | cells_line_h(12, 20, 28)) - LOCAL_TRAP,
)
