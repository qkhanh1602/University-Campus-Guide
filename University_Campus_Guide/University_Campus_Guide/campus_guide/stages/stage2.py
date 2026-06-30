from __future__ import annotations

from map_data import LANDMARKS, Stage, cells_line_h, cells_line_v, cells_rect, walkable_cells


STAGE = Stage(
    2,
    "Chặng 2",
    "Nhóm 2: Tìm kiếm có thông tin / Informed Search",
    "Có heuristic h(n), vùng cost cao",
    "Chặng này giữ đường đi vừa phải để so sánh Greedy theo h(n), A* theo f(n)=g(n)+h(n), và IDA* theo threshold f(n).",
    LANDMARKS["KHOI_A"][1],
    LANDMARKS["THU_VIEN"][1],
    ("Greedy Best First", "A*", "IDA*"),
    2,
    high_cost=walkable_cells(
        # Cost trap on the straight heuristic route from Khoi A to Thu vien.
        # Greedy/IDA* tend to follow this short-looking corridor, while A*
        # can justify a small detour because it accounts for accumulated cost.
        cells_line_v(22, 17, 22)
        | cells_line_h(17, 22, 23)
    ),
)
