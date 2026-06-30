from __future__ import annotations

from dataclasses import dataclass
from heapq import heappop, heappush
from itertools import count
from typing import Dict, List, Optional, Tuple

from map_data import BUILDINGS, GridPos, LANDMARKS, Stage, is_walkable, movement_cost, neighbors

from .common import path_cost, reconstruct


Variable = str
Assignment = Dict[Variable, "CSPValue"]
Domains = Dict[Variable, List["CSPValue"]]

COLORS: List[Tuple[str, str, str]] = [
    ("ORANGE", "Cam", "#f37b2f"),
    ("PINK", "Hong", "#ef6d99"),
    ("BLUE", "Xanh", "#328ec7"),
    ("PURPLE", "Tim", "#9d65ca"),
]

BUILDING_ORDER: List[Variable] = [
    "KHOI_D",
    "KHOI_B",
    "KHOI_C",
    "LIBRARY",
    "MEDICAL",
    "HOI_TRUONG",
    "KHOI_A",
    "WORKSHOP_ENGINE",
    "WORKSHOP_MECH",
    "WORKSHOP_AUTO",
    "KHOI_F",
    "KTX",
    "CANTEEN",
    "KHOI_E",
    "IT",
    "WORKSHOP_WELD",
    "KHOI_G",
    "TOYOTA",
]

CSP_ADJACENCY: Dict[Variable, List[Variable]] = {
    "WORKSHOP_WELD": [],
    "KHOI_G": [],
    "TOYOTA": [],
    "KHOI_E": ["IT"],
    "IT": ["KHOI_E"],
    "WORKSHOP_MECH": ["MEDICAL", "WORKSHOP_AUTO", "WORKSHOP_ENGINE", "KHOI_F"],
    "WORKSHOP_AUTO": ["WORKSHOP_MECH", "WORKSHOP_ENGINE", "KHOI_F"],
    "WORKSHOP_ENGINE": ["WORKSHOP_MECH", "WORKSHOP_AUTO", "KHOI_F", "KHOI_A"],
    "KHOI_F": ["WORKSHOP_MECH", "WORKSHOP_ENGINE", "WORKSHOP_AUTO"],
    "KHOI_A": ["HOI_TRUONG", "WORKSHOP_ENGINE"],
    "HOI_TRUONG": ["KHOI_A", "KHOI_D"],
    "KHOI_D": ["LIBRARY", "HOI_TRUONG", "KHOI_B", "KHOI_C"],
    "LIBRARY": ["KHOI_D", "KHOI_B", "KHOI_C"],
    "MEDICAL": ["WORKSHOP_MECH"],
    "KHOI_B": ["KHOI_C", "KHOI_D", "LIBRARY"],
    "KHOI_C": ["KHOI_B", "KHOI_D", "LIBRARY"],
    "KTX": ["CANTEEN"],
    "CANTEEN": ["KTX"],
}

BUILDING_LABELS: Dict[Variable, str] = {b.key: b.label for b in BUILDINGS}

BUILDING_DOORS: Dict[Variable, GridPos] = {
    "KHOI_C": LANDMARKS["KHOI_C"][1],
    "KHOI_B": LANDMARKS["KHOI_B"][1],
    "KTX": LANDMARKS["KTX"][1],
    "CANTEEN": LANDMARKS["CAN_TIN"][1],
    "LIBRARY": LANDMARKS["THU_VIEN"][1],
    "MEDICAL": LANDMARKS["PHONG_Y_TE"][1],
    "KHOI_D": LANDMARKS["KHOI_D"][1],
    "KHOI_A": LANDMARKS["KHOI_A"][1],
    "HOI_TRUONG": LANDMARKS["HOI_TRUONG"][1],
    "KHOI_E": LANDMARKS["KHU_E"][1],
    "WORKSHOP_WELD": (27, 6),
    "WORKSHOP_MECH": LANDMARKS["XUONG_CO"][1],
    "WORKSHOP_AUTO": LANDMARKS["XUONG_OTO"][1],
    "WORKSHOP_ENGINE": LANDMARKS["XUONG_DONG_CO"][1],
    "KHOI_F": LANDMARKS["KHOI_F"][1],
    "KHOI_G": LANDMARKS["KHOI_G"][1],
    "TOYOTA": (31, 42),
    "IT": LANDMARKS["KHOA_CNTT"][1],
}


@dataclass(frozen=True)
class CSPValue:
    name: str
    pos: GridPos
    category: str
    risk: bool = False
    crowded: bool = False
    short: str = ""
    color_hex: str = "#ffffff"
    building_key: str = ""

    def label(self) -> str:
        return self.short or self.name


def _csp_variables() -> List[Variable]:
    return BUILDING_ORDER[:]


def _building_label(key: Variable) -> str:
    return BUILDING_LABELS.get(key, key)


def _csp_edges() -> List[Tuple[Variable, Variable]]:
    edges: List[Tuple[Variable, Variable]] = []
    seen: set[Tuple[Variable, Variable]] = set()
    for a, bs in CSP_ADJACENCY.items():
        for b in bs:
            if a not in BUILDING_ORDER or b not in BUILDING_ORDER:
                continue
            edge = tuple(sorted((a, b)))
            if edge not in seen:
                seen.add(edge)
                edges.append((a, b))
    return edges


def _adjacent(var: Variable) -> List[Variable]:
    return [v for v in CSP_ADJACENCY.get(var, []) if v in BUILDING_ORDER]


def _color_value(building_key: Variable, color_code: str, label: str, color_hex: str) -> CSPValue:
    return CSPValue(
        name=color_code,
        pos=BUILDING_DOORS[building_key],
        category="color",
        short=label,
        color_hex=color_hex,
        building_key=building_key,
    )


def _csp_domains(stage: Stage) -> Domains:
    return {
        var: [_color_value(var, code, label, color_hex) for code, label, color_hex in COLORS]
        for var in BUILDING_ORDER
    }


def _value_text(value: CSPValue) -> str:
    building = _building_label(value.building_key)
    return f"{building} = {value.label()}"


def _domain_text(values: List[CSPValue]) -> str:
    if not values:
        return "{ }"
    return "{ " + "; ".join(v.label() for v in values) + " }"


def _domains_text(domains: Domains) -> str:
    lines = []
    for var in BUILDING_ORDER:
        if var in domains:
            lines.append(f"D({_building_label(var)}) = {_domain_text(domains[var])}")
    return "\n".join(lines)


def _assignment_text(assignment: Assignment) -> str:
    lines = []
    for var in BUILDING_ORDER:
        if var in assignment:
            lines.append(f"{var} ({_building_label(var)}) = {assignment[var].label()}")
        else:
            lines.append(f"{var} ({_building_label(var)}) = chua to")
    return "\n".join(lines)


def _constraint_lines() -> List[str]:
    return [
        "- Hai tòa nhà kề nhau không được cùng màu.",
    ]


def _csp_representation(stage: Stage, assignment: Assignment | List[GridPos] | None = None, domains: Optional[Domains] = None, variables: Optional[List[Variable]] = None) -> str:
    domains = domains or _csp_domains(stage)
    variables = variables or _csp_variables()
    if not isinstance(assignment, dict):
        assignment = {}
    variable_names = ", ".join(_building_label(v) for v in variables)
    constraint_lines = "\n".join(_constraint_lines())
    return (
        "CSP REPRESENTATION\n"
        f"- Variables: {variable_names}\n"
        "- DOMAIN = { Cam, Hồng, Xanh, Tím }\n"
        "- Constraints:\n"
        f"{constraint_lines}\n"
        "CURRENT ASSIGNMENT / DOMAINS\n"
        "Assignment hiện tại: building = color; building chưa chọn thì = chưa tô\n"
        f"{_assignment_text(assignment)}\n"
        "Miền giá trị còn lại:\n"
        f"{_domains_text(domains)}\n"
        "SOLVING STEPS"
    )


def _assigned_positions(assignment: Assignment) -> List[GridPos]:
    return [assignment[var].pos for var in BUILDING_ORDER if var in assignment]


def _assignment_values(assignment: Assignment) -> List[CSPValue]:
    return [assignment[var] for var in BUILDING_ORDER if var in assignment]


def _check_value(stage: Stage, assignment: Assignment, var: Variable, value: CSPValue) -> Tuple[bool, List[str]]:
    reasons: List[str] = []
    if not is_walkable(value.pos, stage):
        reasons.append("o dai dien cua toa nha khong di duoc")
    for other_var in _adjacent(var):
        other_value = assignment.get(other_var)
        if other_value and other_value.name == value.name:
            reasons.append(f"vi pham {_building_label(var)} != {_building_label(other_var)}: cung mau {value.label()}")
    return not reasons, reasons or ["hop le: khong trung mau voi toa nha ke ben da gan"]


def _assignment_conflicts(stage: Stage, assignment: Assignment, complete: bool = False) -> Tuple[int, List[str]]:
    reasons: List[str] = []
    if complete:
        for var in BUILDING_ORDER:
            if var not in assignment:
                reasons.append(f"{_building_label(var)} chua duoc to mau")
    for a, b in _csp_edges():
        if a in assignment and b in assignment and assignment[a].name == assignment[b].name:
            reasons.append(f"{_building_label(a)} va {_building_label(b)} ke nhau nhung cung mau {assignment[a].label()}")
    return len(reasons), reasons or ["assignment mau thoa toan bo rang buoc ke nhau khac mau"]


def _forward_domains(stage: Stage, assignment: Assignment, domains: Domains) -> Tuple[Domains, List[Tuple[Variable, CSPValue, str]]]:
    out: Domains = {}
    removed: List[Tuple[Variable, CSPValue, str]] = []
    for var in BUILDING_ORDER:
        if var in assignment:
            out[var] = [assignment[var]]
            continue
        kept: List[CSPValue] = []
        for value in domains.get(var, []):
            ok, reasons = _check_value(stage, assignment, var, value)
            if ok:
                kept.append(value)
            else:
                removed.append((var, value, "; ".join(reasons)))
        out[var] = kept
    return out, removed


def _compatible(stage: Stage, xi: Variable, vi: CSPValue, xj: Variable, vj: CSPValue) -> bool:
    if xj in _adjacent(xi):
        return vi.name != vj.name
    return True


def _segment_step_cost(stage: Stage, pos: GridPos) -> float:
    return max(0.1, movement_cost(pos, stage, "normal"))


def _shortest_segment(stage: Stage, a: GridPos, b: GridPos) -> List[GridPos]:
    serial = count()
    heap: List[Tuple[float, int, GridPos]] = [(0.0, next(serial), a)]
    parent: Dict[GridPos, Optional[GridPos]] = {a: None}
    best: Dict[GridPos, float] = {a: 0.0}
    while heap:
        cost, _, cur = heappop(heap)
        if cost != best.get(cur):
            continue
        if cur == b:
            return reconstruct(parent, b)
        for nb in neighbors(cur, stage):
            new_cost = cost + _segment_step_cost(stage, nb)
            if new_cost < best.get(nb, float("inf")):
                best[nb] = new_cost
                parent[nb] = cur
                heappush(heap, (new_cost, next(serial), nb))
    return []


def _merge_segments(segments: List[List[GridPos]]) -> List[GridPos]:
    out: List[GridPos] = []
    for seg in segments:
        if not seg:
            return []
        out.extend(seg if not out else seg[1:])
    return out


def _csp_route_path(stage: Stage, order: List[GridPos] | Assignment) -> List[GridPos]:
    positions = _assigned_positions(order) if isinstance(order, dict) else list(order)
    points = [stage.start] + positions + [stage.goal]
    segments = [_shortest_segment(stage, a, b) for a, b in zip(points, points[1:])]
    return _merge_segments(segments)


def _csp_constraint_summary(path: List[GridPos], stage: Stage, required: List[GridPos] | Assignment | None = None, max_cost: float = 230.0) -> str:
    if isinstance(required, dict):
        conflicts, reasons = _assignment_conflicts(stage, required, complete=True)
        return f"Graph coloring conflicts={conflicts}. " + "; ".join(reasons[:3])
    cost = path_cost(path, stage, "normal") if path else float("inf")
    return f"Route minh hoa sau CSP: cost={cost:.1f}, cells={len(path) if path else 0}."


def _csp_conflicts(path: List[GridPos], stage: Stage, required: List[GridPos] | Assignment, max_cost: float = 230.0, min_route_quality: float = 0.0) -> Tuple[int, List[str]]:
    if isinstance(required, dict):
        return _assignment_conflicts(stage, required, complete=True)
    return (0, ["route minh hoa hop le"]) if path else (99, ["khong tao duoc route minh hoa"])


def _csp_checkpoints(stage: Stage) -> List[GridPos]:
    return [BUILDING_DOORS[var] for var in BUILDING_ORDER[:4]]


def _csp_variable_name(index: int) -> str:
    return _building_label(BUILDING_ORDER[index]) if 0 <= index < len(BUILDING_ORDER) else f"X{index + 1}"


def _csp_label(pos: GridPos | CSPValue, stage: Optional[Stage] = None) -> str:
    if isinstance(pos, CSPValue):
        return _value_text(pos)
    if stage:
        for values in _csp_domains(stage).values():
            for value in values:
                if value.pos == pos:
                    return _building_label(value.building_key)
    return str(pos)


def _csp_domain_text(values: List[GridPos] | List[CSPValue], stage: Stage, include_goal: bool = False) -> str:
    labels = [_csp_label(v, stage) for v in values]
    if include_goal:
        labels.append(f"GOAL@{stage.goal}")
    return "{ " + "; ".join(labels) + " }"


def csp_building_for_pos(pos: GridPos) -> Optional[Variable]:
    for key, door in BUILDING_DOORS.items():
        if door == pos:
            return key
    return None


def csp_color_for_value_text(text: str) -> Optional[str]:
    lowered = text.lower()
    for code, label, color_hex in COLORS:
        if code.lower() in lowered or label.lower() in lowered:
            return color_hex
    return None


def csp_color_assignments_from_note(note: str) -> Dict[GridPos, str]:
    out: Dict[GridPos, str] = {}
    for raw in str(note).splitlines():
        line = raw.strip()
        for key in BUILDING_ORDER:
            prefix = f"{key} "
            if line.startswith(prefix) and "=" in line:
                color_hex = csp_color_for_value_text(line.split("=", 1)[1])
                if color_hex:
                    out[BUILDING_DOORS[key]] = color_hex
                continue
            try_token = f"{key} ="
            if try_token in line and any(token in line.lower() for token in ("thử", "thu ", "try")):
                color_hex = csp_color_for_value_text(line.split(try_token, 1)[1])
                if color_hex:
                    out[BUILDING_DOORS[key]] = color_hex
    return out
