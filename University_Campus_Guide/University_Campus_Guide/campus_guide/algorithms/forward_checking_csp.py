from __future__ import annotations

import time
from typing import List, Optional

from map_data import Stage

from .common import NeighborInfo, SearchResult, TraceStep, finish_search as _finish, path_cost, stopped_search as _stopped
from .csp_common import (
    Assignment,
    Domains,
    _assignment_conflicts,
    _assignment_text,
    _check_value,
    _csp_domains,
    _csp_representation,
    _csp_route_path,
    _csp_variables,
    _domain_text,
    _domains_text,
    _forward_domains,
    _value_text,
)


def forward_checking_csp(stage: Stage) -> SearchResult:
    start_time = time.perf_counter()
    variables = _csp_variables()
    initial_domains = _csp_domains(stage)
    trace: List[TraceStep] = []
    expanded = 0
    best_assignment: Assignment = {}
    best_path = [stage.start]

    def remember(assignment: Assignment) -> None:
        nonlocal best_assignment, best_path
        if len(assignment) > len(best_assignment):
            best_assignment = dict(assignment)
            best_path = _csp_route_path(stage, best_assignment) or best_path

    def ordered_values(var: str, domains: Domains):
        return list(domains[var])

    def make_step(var: str, assignment: Assignment, domains: Domains, infos: List[NeighborInfo], message: str, heuristic: float = 0.0) -> None:
        current = infos[0].node if infos else (assignment[var].pos if var in assignment else stage.start)
        removed_lines = [
            f"{info.action} | {info.value} | {info.reason}"
            for info in infos
            if str(info.status).upper() == "REMOVE"
        ]
        removed_text = "\nGia tri bi loai / Removed Values:\n" + ("\n".join(removed_lines) if removed_lines else "khong co")
        note = (
            _csp_representation(stage, assignment, domains, variables)
            + f"\nBước {len(trace) + 1}: {message}"
            + f"\nGan hien tai / Current Assignment:\n{_assignment_text(assignment)}"
            + f"\nMien gia tri con lai / Remaining Domains:\n{_domains_text(domains)}"
            + removed_text
        )
        trace.append(
            TraceStep(
                len(trace) + 1,
                current,
                [v.pos for vals in domains.values() for v in vals],
                [assignment[k].pos for k in variables if k in assignment],
                infos,
                "Forward Checking",
                path_cost(_csp_route_path(stage, assignment), stage, "normal") if assignment else 0.0,
                heuristic,
                note,
            )
        )

    def fc(assignment: Assignment, domains: Domains, index: int) -> Optional[Assignment]:
        nonlocal expanded
        expanded += 1
        remember(assignment)

        if index == len(variables):
            conflicts, reasons = _assignment_conflicts(stage, assignment, complete=True)
            infos = [
                NeighborInfo(v.pos, "CHECK FINAL", _value_text(v), "OK" if conflicts == 0 else "FAIL", "; ".join(reasons))
                for v in assignment.values()
            ]
            make_step(variables[-1], assignment, domains, infos, "Da to mau tat ca toa nha, kiem tra assignment cuoi.", float(conflicts))
            return dict(assignment) if conflicts == 0 else None

        var = variables[index]
        make_step(
            var,
            assignment,
            domains,
            [NeighborInfo(domains[var][0].pos if domains.get(var) else stage.start, "CHON BIEN", var, "INFO", f"ORDER-DOMAIN-VALUES({var}) = {_domain_text(domains[var])}")],
            f"Chọn biến {var}, sau mỗi lần gán sẽ lọc domain biến chưa gán.",
        )

        for value in ordered_values(var, domains):
            ok, reasons = _check_value(stage, assignment, var, value)
            if not ok:
                make_step(
                    var,
                    assignment,
                    domains,
                    [NeighborInfo(value.pos, f"LOAI {var}", _value_text(value), "REMOVE", "; ".join(reasons))],
                    f"Loại {var} = {value.name} vì vi phạm constraint hiện tại.",
                    1.0,
                )
                continue

            trial_assignment = dict(assignment)
            trial_assignment[var] = value
            trial_domains, removed = _forward_domains(stage, trial_assignment, domains)
            future_empty = [v for v in variables[index + 1 :] if not trial_domains.get(v)]

            infos: List[NeighborInfo] = [
                NeighborInfo(value.pos, f"GAN {var}", f"{var} = {_value_text(value)}", "SELECTED", "Gán tạm thời rồi forward-check domain còn lại.")
            ]
            for removed_var, removed_value, reason in removed[:12]:
                infos.append(
                    NeighborInfo(
                        removed_value.pos,
                        f"REMOVE {removed_var}",
                        f"{removed_var} = {_value_text(removed_value)}",
                        "REMOVE",
                        reason,
                    )
                )

            if future_empty:
                make_step(
                    var,
                    trial_assignment,
                    trial_domains,
                    infos,
                    f"Forward Checking phát hiện domain rỗng: {', '.join(future_empty)}. Prune nhánh.",
                    1.0,
                )
                continue

            make_step(
                var,
                trial_assignment,
                trial_domains,
                infos,
                f"Gán {var} = {value.name}; loại trước {len(removed)} value không còn hợp lệ khỏi future domains.",
            )
            result = fc(trial_assignment, trial_domains, index + 1)
            if result is not None:
                return result

        make_step(
            var,
            assignment,
            domains,
            [NeighborInfo(domains[var][0].pos if domains.get(var) else stage.start, "PRUNE", var, "PRUNE", "Không còn giá trị nào của biến này dẫn tới nghiệm.")],
            f"Forward Checking quay lui tại {var}.",
            1.0,
        )
        return None

    assignment = fc({}, initial_domains, 0)
    if assignment:
        path = _csp_route_path(stage, assignment)
        return _finish("Forward Checking", start_time, path, stage, expanded, trace, "normal")

    return _stopped(
        "Forward Checking",
        start_time,
        stage,
        best_path,
        expanded,
        trace,
        "Forward Checking khong tim duoc assignment to mau thoa constraints.",
        "normal",
    )
