from __future__ import annotations

from dataclasses import dataclass, field
import time
from typing import Dict, List, Optional, Tuple

from map_data import GridPos, Stage, is_walkable, manhattan, movement_cost, IntCost


@dataclass
class NeighborInfo:
    node: GridPos
    action: str
    value: str
    status: str
    reason: str


@dataclass
class TraceStep:
    iteration: int
    current: GridPos
    frontier: List[GridPos] = field(default_factory=list)
    reached: List[GridPos] = field(default_factory=list)
    neighbors: List[NeighborInfo] = field(default_factory=list)
    mode: str = ""
    cost: float = 0.0
    heuristic: float = 0.0
    note: str = ""

    def __post_init__(self):
        self.cost = IntCost(self.cost)


@dataclass
class SearchResult:
    algorithm: str
    path: List[GridPos]
    cost: float
    expanded: int
    trace: List[TraceStep]
    runtime_ms: float
    status: str = "Hoàn thành"
    fallback_used: bool = False

    def __post_init__(self):
        self.cost = IntCost(self.cost)


def action_name(a: GridPos, b: GridPos) -> str:
    dr, dc = b[0] - a[0], b[1] - a[1]
    if dr == -1:
        return "UP"
    if dr == 1:
        return "DOWN"
    if dc == -1:
        return "LEFT"
    if dc == 1:
        return "RIGHT"
    return "STAY"


def move(pos: GridPos, action: str) -> GridPos:
    r, c = pos
    if action == "UP":
        return (r - 1, c)
    if action == "DOWN":
        return (r + 1, c)
    if action == "LEFT":
        return (r, c - 1)
    if action == "RIGHT":
        return (r, c + 1)
    return pos


def reconstruct(parent: Dict[GridPos, Optional[GridPos]], goal: GridPos) -> List[GridPos]:
    path: List[GridPos] = []
    cur: Optional[GridPos] = goal
    guard = 0
    while cur is not None and guard < 20000:
        path.append(cur)
        cur = parent.get(cur)
        guard += 1
    path.reverse()
    return path


def path_cost(path: List[GridPos], stage: Stage, mode: str = "normal") -> IntCost:
    if not path:
        return IntCost(0)
    total = 0
    for p in path[1:]:
        total += int(movement_cost(p, stage, mode))
    return IntCost(total)


def is_valid_path(path: List[GridPos], stage: Stage) -> bool:
    if not path:
        return False
    if path[0] != stage.start or path[-1] != stage.goal:
        return False
    for p in path:
        if not is_walkable(p, stage):
            return False
    for a, b in zip(path, path[1:]):
        if manhattan(a, b) != 1:
            return False
    return True


def h(pos: GridPos, goal: GridPos) -> int:
    return manhattan(pos, goal)


def finish_search(
    name: str,
    start_time: float,
    path: List[GridPos],
    stage: Stage,
    expanded: int,
    trace: List[TraceStep],
    mode: str = "normal",
    status: Optional[str] = None,
) -> SearchResult:
    runtime_ms = (time.perf_counter() - start_time) * 1000
    if status is None:
        status = "Hoàn thành" if is_valid_path(path, stage) else "Dừng - không tìm thấy Goal"
    result = SearchResult(name, path, path_cost(path, stage, mode), expanded, trace, round(runtime_ms, 3), status, False)
    # Keep the Stage object on the result for rich UI trace views.  This does
    # not affect the algorithm output, but it lets the Stage 5 game-tree dialog
    # draw a clean local look-ahead tree from the currently selected state.
    result.stage = stage
    return result


def stopped_search(
    name: str,
    start_time: float,
    stage: Stage,
    path: List[GridPos],
    expanded: int,
    trace: List[TraceStep],
    reason: str,
    mode: str = "normal",
) -> SearchResult:
    current = path[-1] if path else stage.start
    trace.append(TraceStep(
        len(trace) + 1,
        current,
        [],
        path[-30:],
        [],
        name,
        path_cost(path, stage, mode) if path else IntCost(0),
        h(current, stage.goal),
        reason + " Thuật toán dừng đúng bản chất, không dùng A* hỗ trợ."
    ))
    return finish_search(name, start_time, path, stage, expanded, trace, mode, status="Dừng - chưa đạt Goal")


def frontier_from_heap(heap: List[Tuple], limit: int = 16) -> List[GridPos]:
    """Return only grid positions from heap items for visual trace overlays.

    Most algorithms store heap items as (..., GridPos), but game-search
    algorithms store (..., GridPos, g_cost). The old implementation used
    item[-1], so Stage 5 sent g_cost floats to the map instead of cells.
    This helper now searches each heap row for a real GridPos and ignores
    non-position values.
    """

    def extract_pos(value) -> Optional[GridPos]:
        if (
            isinstance(value, tuple)
            and len(value) == 2
            and isinstance(value[0], int)
            and isinstance(value[1], int)
        ):
            return value

        if isinstance(value, dict):
            pos = value.get("pos")
            if (
                isinstance(pos, tuple)
                and len(pos) == 2
                and isinstance(pos[0], int)
                and isinstance(pos[1], int)
            ):
                return pos

        if isinstance(value, (tuple, list)):
            for part in reversed(value):
                pos = extract_pos(part)
                if pos is not None:
                    return pos

        return None

    out: List[GridPos] = []
    for item in sorted(heap)[:limit]:
        pos = extract_pos(item)
        if pos is not None:
            out.append(pos)
    return out
