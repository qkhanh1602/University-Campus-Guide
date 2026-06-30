from __future__ import annotations

import random
import time
from typing import List, Tuple

from map_data import Stage

from .common import NeighborInfo, SearchResult, TraceStep, finish_search as _finish, path_cost, stopped_search as _stopped
from .csp_common import (
    Assignment,
    CSPValue,
    Variable,
    _adjacent,
    _assignment_conflicts,
    _assignment_text,
    _building_label,
    _csp_domains,
    _csp_representation,
    _csp_route_path,
    _csp_variables,
    _value_text,
)


def min_conflicts_csp(stage: Stage, max_steps: int = 80, seed: int = 13) -> SearchResult:
    name = "Min-Conflicts"
    start_time = time.perf_counter()
    rng = random.Random(seed)
    variables = _csp_variables()
    domains = _csp_domains(stage)
    trace: List[TraceStep] = []
    expanded = 0

    def initial_assignment() -> Assignment:
        assignment: Assignment = {}
        for var in variables:
            assignment[var] = rng.choice(domains[var])
        conflicts, _ = _assignment_conflicts(stage, assignment, complete=True)
        if conflicts == 0 and variables:
            first = variables[0]
            for other in _adjacent(first):
                same_color = next((value for value in domains[other] if value.name == assignment[first].name), None)
                if same_color:
                    assignment[other] = same_color
                break
        return assignment

    def conflict_count(assignment: Assignment) -> int:
        return _assignment_conflicts(stage, assignment, complete=True)[0]

    def conflicted_variables(assignment: Assignment) -> List[Variable]:
        out: List[Variable] = []
        for var in variables:
            value = assignment.get(var)
            if not value:
                out.append(var)
                continue
            for other in _adjacent(var):
                other_value = assignment.get(other)
                if other_value and other_value.name == value.name:
                    out.append(var)
                    break
        return out

    def candidate_rows(var: Variable, assignment: Assignment) -> List[Tuple[int, CSPValue]]:
        rows: List[Tuple[int, CSPValue]] = []
        for value in domains[var]:
            trial = dict(assignment)
            trial[var] = value
            rows.append((conflict_count(trial), value))
        rows.sort(key=lambda item: (item[0], item[1].name))
        return rows

    def make_note(assignment: Assignment, message: str, extra: str = "") -> str:
        note = (
            _csp_representation(stage, assignment, domains, variables)
            + f"\nBước {len(trace) + 1} - Min-Conflicts: {message}"
            + f"\nAssignment hiện tại:\n{_assignment_text(assignment)}"
        )
        if extra:
            note += "\n" + extra
        return note

    def add_trace(var: Variable, assignment: Assignment, infos: List[NeighborInfo], message: str, conflicts: int, extra: str = "") -> None:
        route = _csp_route_path(stage, assignment)
        current = assignment[var].pos if var in assignment else (infos[0].node if infos else stage.start)
        trace.append(
            TraceStep(
                len(trace) + 1,
                current,
                [v.pos for v in domains[var]] if var in domains else [],
                [assignment[k].pos for k in variables if k in assignment],
                infos,
                name,
                path_cost(route, stage, "normal") if route else 0.0,
                float(conflicts),
                make_note(assignment, message, extra),
            )
        )

    assignment = initial_assignment()
    best_assignment = dict(assignment)
    best_conflicts = conflict_count(assignment)
    init_infos = [
        NeighborInfo(
            assignment[var].pos,
            f"{var} = {assignment[var].label()}",
            _value_text(assignment[var]),
            "OK" if var not in conflicted_variables(assignment) else "FAIL",
            "Khởi tạo assignment đầy đủ; biến xung đột sẽ được sửa ở các bước sau.",
        )
        for var in variables[:12]
    ]
    add_trace(
        variables[0],
        assignment,
        init_infos,
        "Khởi tạo assignment màu đầy đủ cho tất cả tòa nhà.",
        best_conflicts,
        f"Số xung đột ban đầu = {best_conflicts}.",
    )

    for _ in range(1, max_steps + 1):
        expanded += 1
        conflicts, reasons = _assignment_conflicts(stage, assignment, complete=True)
        if conflicts < best_conflicts:
            best_conflicts = conflicts
            best_assignment = dict(assignment)

        if conflicts == 0:
            final_path = _csp_route_path(stage, assignment)
            infos = [
                NeighborInfo(value.pos, f"{var} = {value.label()}", _value_text(value), "OK", "Không còn xung đột với các tòa kề nhau.")
                for var, value in assignment.items()
            ]
            add_trace(
                variables[-1],
                assignment,
                infos,
                "Tất cả ràng buộc kề nhau khác màu đều thỏa mãn.",
                0,
                "Min-Conflicts kết thúc vì conflicts = 0.",
            )
            return _finish(name, start_time, final_path, stage, expanded, trace, "normal")

        conflicted = conflicted_variables(assignment)
        var = rng.choice(conflicted)
        rows = candidate_rows(var, assignment)
        best_value = rows[0][1]
        assignment[var] = best_value

        infos: List[NeighborInfo] = []
        for count_value, value in rows:
            status = "SELECTED" if value.name == best_value.name else "TRY"
            infos.append(
                NeighborInfo(
                    value.pos,
                    f"THU {var} = {value.label()}",
                    f"conflicts={count_value}",
                    status,
                    (
                        f"Chọn màu này vì làm số xung đột của {_building_label(var)} nhỏ nhất."
                        if status == "SELECTED"
                        else f"Thử màu {value.label()} để đếm số cặp kề nhau bị trùng màu."
                    ),
                )
            )
        add_trace(
            var,
            assignment,
            infos,
            f"Chọn biến đang xung đột {var}; thử tất cả màu và gán màu có conflicts nhỏ nhất.",
            conflict_count(assignment),
            "Lý do xung đột trước khi sửa: " + "; ".join(reasons[:4]),
        )

    final_path = _csp_route_path(stage, best_assignment) or [stage.start]
    return _stopped(
        name,
        start_time,
        stage,
        final_path,
        expanded,
        trace,
        f"Min-Conflicts hết {max_steps} bước, kết quả tốt nhất còn {best_conflicts} xung đột.",
        "normal",
    )
