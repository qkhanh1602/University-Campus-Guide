from __future__ import annotations

from map_data import LANDMARKS, Stage


STAGE = Stage(
    1,
    "Chặng 1",
    "Nhóm 1: Tìm kiếm mù / Uninformed Search",
    "Môi trường tĩnh, ngắn và dễ chạy tay",
    "BFS dùng Queue FIFO, DFS dùng Stack LIFO, IDS dùng DFS lặp sâu dần và thấy rõ CUTOFF.",
    LANDMARKS["KHOA_CNTT"][1],
    LANDMARKS["KHU_E"][1],
    ("BFS", "DFS", "IDS"),
    1,
)
