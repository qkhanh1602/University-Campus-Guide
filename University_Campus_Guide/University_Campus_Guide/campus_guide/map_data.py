from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Set

GridPos = Tuple[int, int]

ROWS = 34
COLS = 46
TILE = 24

GRASS = "grass"
ROAD = "road"
PATH = "path"
PLAZA = "plaza"
FIELD = "field"
WATER = "water"
PARKING = "parking"


class IntCost(int):
    def __new__(cls, value=0):
        try:
            value = int(round(float(value)))
        except Exception:
            value = 0
        return int.__new__(cls, value)

    def __format__(self, spec: str) -> str:
        if spec.endswith("f"):
            return str(int(self))
        return int.__format__(self, spec)


WALKABLE = {ROAD, PATH, PLAZA, FIELD, PARKING}

BASE_COST = {
    ROAD: 1,
    PATH: 1,
    PLAZA: 1,
    FIELD: 1,
    PARKING: 1,
    GRASS: 3,
    WATER: 99,
}


@dataclass(frozen=True)
class Building:
    key: str
    label: str
    row: int
    col: int
    h: int
    w: int
    kind: str


@dataclass(frozen=True)
class Stage:
    idx: int
    title: str
    group: str
    environment: str
    detail: str
    start: GridPos
    goal: GridPos
    algorithms: Tuple[str, str, str]
    difficulty: int
    blocked: Set[GridPos] = field(default_factory=set)
    high_cost: Set[GridPos] = field(default_factory=set)
    risk: Set[GridPos] = field(default_factory=set)
    opponent: Set[GridPos] = field(default_factory=set)
    covered: Set[GridPos] = field(default_factory=set)
    uncertain_starts: Set[GridPos] = field(default_factory=set)
    uncertain_goals: Set[GridPos] = field(default_factory=set)


def _blank_grid() -> List[List[str]]:
    return [[GRASS for _ in range(COLS)] for _ in range(ROWS)]


def _paint(grid: List[List[str]], terrain: str, r1: int, c1: int, r2: int, c2: int) -> None:
    for r in range(max(0, r1), min(ROWS, r2 + 1)):
        for c in range(max(0, c1), min(COLS, c2 + 1)):
            grid[r][c] = terrain


def _line_h(grid: List[List[str]], terrain: str, r: int, c1: int, c2: int, width: int = 1) -> None:
    for dr in range(-(width // 2), width - width // 2):
        rr = r + dr

        if 0 <= rr < ROWS:
            for c in range(max(0, c1), min(COLS, c2 + 1)):
                grid[rr][c] = terrain


def _line_v(grid: List[List[str]], terrain: str, c: int, r1: int, r2: int, width: int = 1) -> None:
    for dc in range(-(width // 2), width - width // 2):
        cc = c + dc

        if 0 <= cc < COLS:
            for r in range(max(0, r1), min(ROWS, r2 + 1)):
                grid[r][cc] = terrain


def build_grid() -> List[List[str]]:
    grid = _blank_grid()

    _line_h(grid, ROAD, 32, 1, 44, 2)
    _line_v(grid, ROAD, 1, 3, 32, 1)
    _line_v(grid, ROAD, 44, 3, 32, 1)
    _line_h(grid, ROAD, 4, 10, 40, 2)
    _line_h(grid, ROAD, 9, 8, 39, 1)
    _line_h(grid, ROAD, 15, 6, 39, 1)
    _line_h(grid, ROAD, 22, 4, 40, 2)
    _line_h(grid, ROAD, 27, 4, 43, 1)

    _line_v(grid, ROAD, 10, 8, 28, 1)
    _line_v(grid, ROAD, 16, 4, 31, 1)
    _line_v(grid, ROAD, 25, 4, 31, 1)
    _line_v(grid, ROAD, 31, 4, 31, 1)
    _line_v(grid, ROAD, 39, 9, 31, 1)

    _line_h(grid, ROAD, 7, 28, 41, 1)
    _line_v(grid, ROAD, 30, 4, 12, 1)
    _line_v(grid, ROAD, 39, 4, 10, 1)

    _line_v(grid, PLAZA, 22, 23, 32, 3)
    _paint(grid, PLAZA, 17, 18, 25, 27)
    _paint(grid, PLAZA, 26, 14, 31, 18)
    _paint(grid, PLAZA, 23, 32, 30, 38)

    _line_h(grid, PATH, 12, 12, 28, 1)
    _line_h(grid, PATH, 18, 12, 36, 1)
    _line_v(grid, PATH, 20, 5, 18, 1)
    _line_v(grid, PATH, 28, 9, 22, 1)
    _line_h(grid, PATH, 24, 16, 22, 1)
    _line_v(grid, PATH, 18, 23, 32, 1)
    _line_h(grid, PATH, 30, 5, 18, 1)

    _paint(grid, FIELD, 24, 30, 30, 35)
    _paint(grid, PARKING, 25, 37, 31, 43)
    _paint(grid, WATER, 29, 19, 31, 21)

    _paint(grid, ROAD, 31, 21, 33, 25)
    grid[32][23] = ROAD

    return grid


GRID = build_grid()

BUILDINGS: List[Building] = [
    Building("KHOI_C", "Khối C", 5, 16, 4, 4, "academic"),
    Building("KHOI_B", "Khối B", 5, 21, 4, 4, "academic"),
    Building("KTX", "Ký túc xá D", 3, 31, 2, 6, "service"),
    Building("CANTEEN", "Căn tin", 5, 36, 2, 4, "service"),
    Building("LIBRARY", "Khối Thư viện", 11, 21, 4, 5, "center"),
    Building("MEDICAL", "Phòng y tế", 9, 30, 4, 6, "center"),
    Building("KHOI_D", "Khối D", 12, 16, 4, 4, "academic"),
    Building("KHOI_A", "Khối A.1-A.5", 20, 23, 3, 6, "academic"),
    Building("HOI_TRUONG", "Hội trường lớn", 18, 17, 3, 4, "center"),
    Building("KHOI_E", "Khối E.1", 24, 12, 5, 4, "academic"),
    Building("WORKSHOP_WELD", "Xưởng thực tập hàn", 22, 4, 5, 5, "workshop"),
    Building("WORKSHOP_MECH", "Xưởng thực tập gỗ", 15, 32, 3, 4, "workshop"),
    Building("WORKSHOP_AUTO", "Xưởng điện ô tô", 15, 37, 3, 4, "workshop"),
    Building("WORKSHOP_ENGINE", "Xưởng động cơ", 19, 31, 3, 3, "workshop"),
    Building("KHOI_F", "Khối F.1", 19, 35, 3, 3, "academic"),
    Building("KHOI_G", "Khối G", 27, 33, 3, 4, "academic"),
    Building("TOYOTA", "Dịch vụ ô tô Toyota", 27, 40, 4, 4, "workshop"),
    Building("IT", "Khoa CNTT", 30, 14, 2, 4, "center"),
]

BUILDING_CELLS: Set[GridPos] = {
    (r, c)
    for b in BUILDINGS
    for r in range(b.row, b.row + b.h)
    for c in range(b.col, b.col + b.w)
}


def building_label_at(pos: GridPos) -> str | None:
    for b in BUILDINGS:
        if b.row <= pos[0] < b.row + b.h and b.col <= pos[1] < b.col + b.w:
            return b.label

    return None


LANDMARKS: Dict[str, Tuple[str, GridPos]] = {
    "CONG_CHINH": ("Cổng chính Võ Văn Ngân", (32, 23)),
    "CONG_PHU": ("Cổng phụ Võ Văn Ngân", (32, 5)),
    "KHOI_A": ("Khối A.1-A.5", (23, 22)),
    "KHOI_B": ("Khối B", (9, 23)),
    "KHOI_C": ("Khối C", (9, 18)),
    "KHOI_D": ("Khối D", (15, 20)),
    "KHU_E": ("Khối E.1", (27, 16)),
    "THU_VIEN": ("Khối Thư viện", (12, 20)),
    "HOI_TRUONG": ("Hội trường lớn", (18, 25)),
    "CAN_TIN": ("Căn tin", (7, 37)),
    "KTX": ("Ký túc xá D", (5, 31)),
    "PHONG_Y_TE": ("Phòng y tế", (9, 29)),
    "XUONG_CO": ("Xưởng thực tập gỗ", (18, 34)),
    "XUONG_OTO": ("Xưởng điện ô tô", (18, 39)),
    "XUONG_DONG_CO": ("Xưởng động cơ", (22, 33)),
    "KHOI_F": ("Khối F.1", (22, 35)),
    "KHOI_G": ("Khối G", (30, 35)),
    "SAN_BONG": ("Sân bóng đá ngoài trời", (27, 32)),
    "BAI_XE": ("Bãi xe sinh viên", (28, 38)),
    "HO_NUOC": ("Hồ nước", (30, 20)),
    "KHOA_CNTT": ("Khoa Công nghệ Thông tin", (30, 18)),
}


def cells_rect(r1: int, c1: int, r2: int, c2: int) -> Set[GridPos]:
    return {(r, c) for r in range(r1, r2 + 1) for c in range(c1, c2 + 1)}


def cells_line_h(r: int, c1: int, c2: int) -> Set[GridPos]:
    return {(r, c) for c in range(c1, c2 + 1)}


def cells_line_v(c: int, r1: int, r2: int) -> Set[GridPos]:
    return {(r, c) for r in range(r1, r2 + 1)}


def is_base_walkable(pos: GridPos) -> bool:
    r, c = pos

    if not (0 <= r < ROWS and 0 <= c < COLS):
        return False

    if pos in BUILDING_CELLS:
        return False

    return GRID[r][c] in WALKABLE


def walkable_cells(cells: Set[GridPos]) -> Set[GridPos]:
    return {pos for pos in cells if is_base_walkable(pos)}


from stages import STAGES


def in_bounds(pos: GridPos) -> bool:
    r, c = pos
    return 0 <= r < ROWS and 0 <= c < COLS


def is_walkable(pos: GridPos, stage: Stage | None = None) -> bool:
    if not in_bounds(pos):
        return False

    if pos in BUILDING_CELLS:
        return False

    if stage and pos in stage.blocked:
        return False

    if stage and pos in stage.opponent:
        return False

    r, c = pos
    return GRID[r][c] in WALKABLE


def terrain_at(pos: GridPos) -> str:
    r, c = pos
    return GRID[r][c]


def movement_cost(pos: GridPos, stage: Stage, mode: str = "normal") -> IntCost:
    base = int(BASE_COST.get(terrain_at(pos), 2))
    covered = pos in stage.covered

    if pos in stage.high_cost:
        base += 2

    if pos in stage.opponent:
        base += 3

    if pos in stage.risk:
        if mode == "rain_cover":
            base += 1 if covered else 3
        elif mode == "risk_averse":
            base += 2
        elif mode == "expected":
            base += 2
        elif mode == "monte_carlo":
            base += 2
        else:
            base += 1

    if covered and mode in {"rain_cover", "risk_averse"}:
        base = max(1, base - 1)

    return IntCost(base)


def neighbors(pos: GridPos, stage: Stage) -> List[GridPos]:
    r, c = pos
    result: List[GridPos] = []

    for nr, nc in ((r - 1, c), (r + 1, c), (r, c - 1), (r, c + 1)):
        nxt = (nr, nc)

        if is_walkable(nxt, stage):
            result.append(nxt)

    return result


def manhattan(a: GridPos, b: GridPos) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def euclidean(a: GridPos, b: GridPos) -> float:
    return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5


def landmark_name_at(pos: GridPos) -> str | None:
    for name, (label, p) in LANDMARKS.items():
        if p == pos:
            return label

    return None


TERRAIN_LABELS = {
    GRASS: "Bãi cỏ / cảnh quan",
    ROAD: "Đường nội bộ",
    PATH: "Lối đi bộ",
    PLAZA: "Sân / quảng trường",
    FIELD: "Sân bóng",
    WATER: "Hồ nước",
    PARKING: "Bãi xe",
}


def collision_reason(pos: GridPos, stage: Stage | None = None) -> str:
    if not in_bounds(pos):
        return "Ngoài bản đồ"

    building = building_label_at(pos)

    if building:
        return f"Tòa nhà: {building}"

    if stage and pos in stage.blocked:
        return "Chướng ngại / rào chắn của chặng"

    if stage and pos in stage.opponent:
        return "Đám đông/chốt chặn đối kháng"

    r, c = pos
    terrain = GRID[r][c]

    if terrain not in WALKABLE:
        return f"Không phải lối đi: {TERRAIN_LABELS.get(terrain, terrain)}"

    if stage and pos in stage.high_cost:
        return "Khu đông người, đi được nhưng cost cao"

    if stage and pos in stage.covered:
        return "Lối đi có mái che"

    if stage and pos in stage.risk:
        return "Đi được nhưng có rủi ro/bất lợi"

    return "Đi được"


def validate_path_detail(path: List[GridPos], stage: Stage) -> Tuple[bool, str]:
    if not path:
        return False, "Path rỗng"

    if path[0] != stage.start:
        return False, f"Path không bắt đầu ở START {stage.start}"

    if path[-1] != stage.goal:
        return False, f"Path không kết thúc ở GOAL {stage.goal}"

    for p in path:
        if not is_walkable(p, stage):
            return False, f"Path đi vào ô cấm {p}: {collision_reason(p, stage)}"

    for a, b in zip(path, path[1:]):
        if manhattan(a, b) != 1:
            return False, f"Path bị nhảy từ {a} sang {b}, không đi từng ô liên tiếp"

    return True, "Path hợp lệ, liên tục và không xuyên tòa nhà"


def audit_stage(stage: Stage) -> List[str]:
    warnings: List[str] = []

    for name, pos in [("START", stage.start), ("GOAL", stage.goal)]:
        if not is_walkable(pos, stage):
            warnings.append(f"{name} đặt trên ô không đi được {pos}: {collision_reason(pos, stage)}")

    for label, cells in [
        ("blocked", stage.blocked),
        ("opponent", stage.opponent),
        ("high_cost", stage.high_cost),
        ("risk", stage.risk),
    ]:
        bad = [p for p in cells if not in_bounds(p)]

        if bad:
            warnings.append(f"{label} có ô ngoài bản đồ: {bad[:5]}")

    return warnings
