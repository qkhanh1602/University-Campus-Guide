from __future__ import annotations

import time
from typing import List, Optional

from map_data import Stage

from .common import NeighborInfo, SearchResult, TraceStep, finish_search as _finish, path_cost, stopped_search as _stopped
from .csp_common import (
    Assignment,
    CSPValue,
    _assignment_conflicts,
    _assignment_text,
    _check_value,
    _csp_domains,
    _csp_representation,
    _csp_route_path,
    _csp_variables,
    _domain_text,
    _value_text,
)


def backtracking_csp(stage: Stage) -> SearchResult:
    start_time = time.perf_counter()
    variables = _csp_variables()
    domains = _csp_domains(stage)
    trace: List[TraceStep] = []
    expanded = 0
    best_assignment: Assignment = {}
    best_path = [stage.start]

    def remember(assignment: Assignment) -> None:
        nonlocal best_assignment, best_path
        if len(assignment) > len(best_assignment):
            best_assignment = dict(assignment)
            best_path = _csp_route_path(stage, best_assignment) or best_path

    def ordered_values(var: str, assignment: Assignment) -> List[CSPValue]:
        return list(domains[var])

    def make_step(
        var: str,
        assignment: Assignment,
        infos: List[NeighborInfo],
        message: str,
        heuristic: float = 0.0,
    ) -> None:
        current = infos[0].node if infos else (assignment[var].pos if var in assignment else stage.start)
        note = (
            _csp_representation(stage, assignment, domains, variables)
            + f"\nBước {len(trace) + 1}: {message}"
            + f"\nAssignment snapshot:\n{_assignment_text(assignment)}"
        )
        trace.append(
            TraceStep(
                len(trace) + 1,
                current,
                [v.pos for v in domains.get(var, [])],
                [assignment[k].pos for k in variables if k in assignment],
                infos,
                "Backtracking",
                path_cost(_csp_route_path(stage, assignment), stage, "normal") if assignment else 0.0,
                heuristic,
                note,
            )
        )

    def backtrack(assignment: Assignment, index: int) -> Optional[Assignment]:
        nonlocal expanded
        expanded += 1
        remember(assignment)

        if index == len(variables):
            conflicts, reasons = _assignment_conflicts(stage, assignment, complete=True)
            infos = [
                NeighborInfo(
                    assignment[var].pos,
                    f"{var} = {assignment[var].label()}",
                    _value_text(assignment[var]),
                    "OK" if conflicts == 0 else "FAIL",
                    "; ".join(reasons),
                )
                for var in variables
            ]
            make_step(variables[-1], assignment, infos, "Da to mau tat ca toa nha, kiem tra toan bo constraints.", float(conflicts))
            return dict(assignment) if conflicts == 0 else None

        var = variables[index]
        choose_info = [
            NeighborInfo(
                domains[var][0].pos if domains.get(var) else stage.start,
                "CHON BIEN",
                var,
                "INFO",
                f"ORDER-DOMAIN-VALUES({var}) = {_domain_text(domains[var])}",
            )
        ]
        make_step(var, assignment, choose_info, f"Chọn biến chưa gán {var}.")

        for value in ordered_values(var, assignment):
            ok, reasons = _check_value(stage, assignment, var, value)
            status = "ADD" if ok else "FAIL"
            infos = [
                NeighborInfo(
                    value.pos,
                    f"THU {var}",
                    f"{var} = {_value_text(value)}",
                    status,
                    "; ".join(reasons),
                )
            ]
            make_step(var, assignment, infos, f"Thử {var} = {value.name}. Kiểm tra constraint.", 0.0 if ok else 1.0)
            if not ok:
                continue

            assignment[var] = value
            make_step(
                var,
                assignment,
                [
                    NeighborInfo(
                        value.pos,
                        f"GAN {var}",
                        f"{var} = {_value_text(value)}",
                        "SELECTED",
                        "Hợp lệ, tiếp tục gán biến kế tiếp.",
                    )
                ],
                f"{var} = {value.name} hợp lệ, thêm vào Assignment.",
            )
            result = backtrack(assignment, index + 1)
            if result is not None:
                return result

            removed = assignment.pop(var)
            make_step(
                var,
                assignment,
                [
                    NeighborInfo(
                        removed.pos,
                        f"BACKTRACK {var}",
                        f"xoa {var} = {_value_text(removed)}",
                        "FAIL",
                        "Nhánh sâu hơn thất bại, quay lui để thử giá trị khác.",
                    )
                ],
                f"Quay lui: bỏ {var} = {removed.name}.",
                1.0,
            )
        return None

    assignment = backtrack({}, 0)
    if assignment:
        path = _csp_route_path(stage, assignment)
        return _finish("Backtracking", start_time, path, stage, expanded, trace, "normal")

    return _stopped(
        "Backtracking",
        start_time,
        stage,
        best_path,
        expanded,
        trace,
        "Backtracking khong tim duoc assignment to mau thoa constraints.",
        "normal",
    )
