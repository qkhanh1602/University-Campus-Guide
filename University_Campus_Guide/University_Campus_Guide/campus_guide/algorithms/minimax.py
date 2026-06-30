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
    _game_reply_summary,
    _game_static_value,
    _game_value,
    _minimax_reason,
    _new_expectimax_context,
    _score_summary,
    opponent_positions_for_route,
)


def minimax(stage: Stage) -> SearchResult:
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
            trace.append(TraceStep(expanded, current, _frontier_from_heap(frontier), list(reached), infos, "Minimax", g, _h(current, goal), "TRACE CAY DOI KHANG. Minimax: agent da toi Goal, cong thuong lon."))
            return _finish("Minimax", start_time, path, stage, expanded, trace)

        current_enemies = opponent_positions_for_route(reconstruct(parent, current), stage)
        scored: List[Tuple[float, GridPos]] = []
        for nb in neighbors(current, stage):
            if nb in current_enemies:
                continue
            score = _game_value(nb, stage, LOOKAHEAD_DEPTH, False, enemies=current_enemies, cache=cache, context=context)
            scored.append((score, nb))

        scored.sort(reverse=True, key=lambda x: x[0])
        selected_nb = scored[0][1] if scored else None
        selected_action = action_name(current, selected_nb) if selected_nb else "NONE"

        for score, nb in scored:
            step = movement_cost(nb, stage)
            ng = g + step
            action = action_name(current, nb)
            reply = _game_reply_summary(nb, stage)
            value_text = f"diem cay={score:.1f}; state: {_score_summary(nb, stage)}"

            if nb in reached:
                infos.append(NeighborInfo(nb, f"MAX {action}", value_text, "SKIP", "Da xet state nay, bo qua de tranh lap."))
                continue

            priority = -score + 0.08 * ng
            if priority < best_score.get(nb, float("inf")):
                best_score[nb] = priority
                parent[nb] = current
                heapq.heappush(frontier, (priority, order, nb, ng))
                order += 1
                selected = nb == selected_nb
                status = "SELECTED" if selected else "ADD/UPDATE"
                infos.append(NeighborInfo(nb, f"MAX {action}", value_text, status, _minimax_reason(action, score, reply, selected_action, selected)))
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
                "Minimax",
                g,
                _h(current, goal),
                f"PHASE=MAX. DECISION_SNAPSHOT. Root state={current}. Hanh dong duoc chon={selected_action}. Next state={next_state}. Minimax: MAX so sanh cac action sau khi MIN ep moi nhanh ve truong hop xau nhat.",
            ))

    return _stopped("Minimax", start_time, stage, best_partial, expanded, trace, "Minimax khong tim duoc Goal trong gioi han mo rong.")
