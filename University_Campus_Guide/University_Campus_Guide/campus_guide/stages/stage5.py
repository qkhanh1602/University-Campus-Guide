from __future__ import annotations

from map_data import LANDMARKS, Stage, cells_line_h, cells_line_v, cells_rect, walkable_cells


OPPONENT_BLOCKS = walkable_cells({
    (23, 33), (24, 33), (25, 33),
    (24, 34), (25, 34),
})


STAGE = Stage(
    5,
    "Chặng 5",
    "Nhóm 5: Tìm kiếm đối kháng / Game Search",
    "Trò chơi tính điểm: tiến gần Goal được cộng điểm, môi trường xấu bị trừ điểm",
    "Chặng đối kháng dùng điểm bắt đầu = 0. Agent đi càng gần Goal càng được cộng điểm; đi qua mưa, bùn/ngập, đám đông hoặc vùng rủi ro bị trừ điểm; tới Goal được thưởng lớn. Tòa nhà/chốt chặn là vật cản cứng nên không được đi vào. Minimax chọn điểm cao nhất sau tình huống xấu nhất, Alpha-Beta cắt nhánh, Expectimax tính điểm kỳ vọng.",
    LANDMARKS["XUONG_DONG_CO"][1],
    LANDMARKS["KHOI_G"][1],
    ("Minimax", "Alpha-Beta Pruning", "Expectimax"),
    5,
    opponent=set(),
    high_cost=walkable_cells(
        cells_rect(23, 32, 27, 35)
        | cells_line_v(31, 20, 24)
        | cells_rect(26, 32, 28, 34)
        | cells_line_h(27, 31, 36)
    ),
    risk={
        (25, 30), (26, 30), (27, 30), (27, 31),
        (26, 32), (27, 32),
    },
)
