from __future__ import annotations

import heapq
import time
from typing import Dict, List, Optional, Set, Tuple

from map_data import GridPos, Stage, manhattan, movement_cost, neighbors

from .common import (
    NeighborInfo,
    SearchResult,
    TraceStep,
    action_name,
    finish_search as _finish,
    frontier_from_heap as _frontier_from_heap,
    h as _h,
    reconstruct,
    stopped_search as _stopped,
)
from .game_common import (
    LOOKAHEAD_DEPTH,
    _alpha_beta_reason,
    _fmt_bound,
    _game_static_value,
    _game_value,
    _new_expectimax_context,
    _score_summary,
    opponent_positions_for_route,
)


def alpha_beta(stage: Stage) -> SearchResult:
    start_time = time.perf_counter()
    start, goal = stage.start, stage.goal
    trace: List[TraceStep] = []
    expanded = 0
    parent: Dict[GridPos, Optional[GridPos]] = {start: None}
    best_score: Dict[GridPos, float] = {start: 0.0}
    reached: Set[GridPos] = set()
    frontier: List[Tuple[float, int, GridPos, float]] = [(-_game_static_value(start, stage), 0, start, 0.0)]
    cache = {}
    context = _new_expectimax_context()
    order = 1
    best_partial = [start]
    best_h = manhattan(start, goal)

    while frontier and expanded < 700:
        _, _, current, g = heapq.heappop(frontier)
        if current in reached:
            continue
        reached.add(current)
        expanded += 1

        if manhattan(current, goal) < best_h:
            best_h = manhattan(current, goal)
            best_partial = reconstruct(parent, current)

        infos: List[NeighborInfo] = []
        if current == goal:
            path = reconstruct(parent, goal)
            trace.append(TraceStep(expanded, current, _frontier_from_heap(frontier), list(reached), infos, "Alpha-Beta Pruning", g, _h(current, goal), "TRACE CAY DOI KHANG. Alpha-Beta: agent da toi Goal, cong thuong lon."))
            return _finish("Alpha-Beta Pruning", start_time, path, stage, expanded, trace)

        current_enemies = opponent_positions_for_route(reconstruct(parent, current), stage)
        scored: List[Tuple[float, GridPos]] = []
        for nb in neighbors(current, stage):
            if nb in current_enemies:
                continue
            score = _game_value(nb, stage, LOOKAHEAD_DEPTH, False, use_ab=True, enemies=current_enemies, cache=cache, context=context)
            scored.append((score, nb))

        scored.sort(reverse=True, key=lambda x: x[0])
        selected_nb = scored[0][1] if scored else None
        selected_action = action_name(current, selected_nb) if selected_nb else "NONE"
        alpha_trace = -float("inf")
        beta_trace = float("inf")
        viable_seen = 0

        for score, nb in scored:
            step = movement_cost(nb, stage)
            ng = g + step
            action = action_name(current, nb)

            if nb in reached:
                value_text = f"diem cay={score:.1f}; alpha={_fmt_bound(alpha_trace)}; beta={_fmt_bound(beta_trace)}"
                infos.append(NeighborInfo(nb, f"MAX {action}", value_text, "SKIP", "Da xet state nay, bo qua de tranh lap."))
                continue

            alpha_before, beta_before = alpha_trace, beta_trace
            alpha_trace = max(alpha_trace, score)
            beta_trace = min(beta_trace, score + 6.0 if viable_seen == 0 else score + 1.0)
            value_text = (
                f"diem cay={score:.1f}; state: {_score_summary(nb, stage)}; "
                f"alpha {_fmt_bound(alpha_before)}->{_fmt_bound(alpha_trace)}; "
                f"beta {_fmt_bound(beta_before)}->{_fmt_bound(beta_trace)}"
            )

            pruned_by_bound = beta_trace <= alpha_trace and viable_seen > 0

            viable_seen += 1
            priority = -score + 0.08 * ng
            if priority < best_score.get(nb, float("inf")):
                best_score[nb] = priority
                parent[nb] = current
                heapq.heappush(frontier, (priority, order, nb, ng))
                order += 1
                selected = nb == selected_nb
                status = "SELECTED" if selected else ("PRUNE" if pruned_by_bound else "ADD/UPDATE")
                infos.append(NeighborInfo(nb, f"MAX {action}", value_text, status, _alpha_beta_reason(action, score, alpha_trace, beta_trace, selected_action, status)))
            else:
                infos.append(NeighborInfo(nb, f"MAX {action}", value_text, "SKIP", "Frontier da co cach den state nay voi uu tien tot hon."))

        if len(trace) < 700:
            next_state = selected_nb if selected_nb is not None else current
            trace.append(TraceStep(
                len(trace) + 1,
                current,
                [next_state],
                reconstruct(parent, current),
                infos,
                "Alpha-Beta Pruning",
                g,
                _h(current, goal),
                f"PHASE=MAX. DECISION_SNAPSHOT. Root state={current}. Hanh dong duoc chon={selected_action}. Next state={next_state}. Alpha-Beta: tinh nhu Minimax nhung dung alpha/beta de cat nhanh khong the tot hon lua chon hien tai.",
            ))

    return _stopped("Alpha-Beta Pruning", start_time, stage, best_partial, expanded, trace, "Alpha-Beta khong tim duoc Goal trong gioi han mo rong.")
