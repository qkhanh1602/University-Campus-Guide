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
    EXPECTIMAX_DEPTH,
    MAX_AGENT_BRANCH,
    MAX_STAGE5_SECONDS,
    MAX_TRACE_STEPS,
    _expectimax_reply_summary,
    _expectimax_value,
    _expectimax_reason,
    _game_static_value,
    _new_expectimax_context,
    _score_summary,
    opponent_positions_for_route,
)


def _expectimax_actions(pos: GridPos, stage: Stage, enemies: List[GridPos]) -> List[GridPos]:
    actions = [nb for nb in neighbors(pos, stage) if nb not in enemies]
    actions.sort(key=lambda nb: _game_static_value(nb, stage, "expectimax"), reverse=True)
    return actions[:MAX_AGENT_BRANCH]


def expectimax(stage: Stage) -> SearchResult:
    start_time = time.perf_counter()
    start, goal = stage.start, stage.goal
    trace: List[TraceStep] = []
    expanded = 0
    parent: Dict[GridPos, Optional[GridPos]] = {start: None}
    best_score: Dict[GridPos, float] = {start: 0.0}
    reached: Set[GridPos] = set()
    frontier: List[Tuple[float, int, GridPos, float]] = [
        (-_game_static_value(start, stage, "expectimax"), 0, start, 0.0)
    ]
    cache = {}
    context = _new_expectimax_context()
    order = 1
    best_partial = [start]
    best_h = manhattan(start, goal)

    while frontier and expanded < 300 and time.perf_counter() - start_time <= MAX_STAGE5_SECONDS:
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
            if len(trace) < MAX_TRACE_STEPS:
                trace.append(TraceStep(expanded, current, _frontier_from_heap(frontier), list(reached), infos, "Expectimax", g, _h(current, goal), "TRACE CAY DOI KHANG. Expectimax: agent da toi Goal, cong thuong lon."))
            return _finish("Expectimax", start_time, path, stage, expanded, trace)

        current_enemies = opponent_positions_for_route(reconstruct(parent, current), stage)
        scored: List[Tuple[float, GridPos]] = []
        for nb in _expectimax_actions(current, stage, current_enemies):
            score = _expectimax_value(
                nb,
                stage,
                EXPECTIMAX_DEPTH,
                False,
                enemies=current_enemies,
                cache=cache,
                context=context,
            )
            scored.append((score, nb))

        scored.sort(reverse=True, key=lambda x: x[0])
        selected_nb = scored[0][1] if scored else None
        selected_action = action_name(current, selected_nb) if selected_nb else "NONE"

        for score, nb in scored:
            step = movement_cost(nb, stage, "expected")
            ng = g + step
            action = action_name(current, nb)
            chance_text = _expectimax_reply_summary(nb, stage)
            value_text = f"EV={score:.1f}; state: {_score_summary(nb, stage)}; nodes={int(context.get('nodes', 0))}"

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
                reason = _expectimax_reason(action, score, selected_action, selected)
                infos.append(NeighborInfo(nb, f"MAX {action}", value_text, status, f"{chance_text}. {reason}"))
            else:
                infos.append(NeighborInfo(nb, f"MAX {action}", value_text, "SKIP", "Frontier da co cach den state nay voi uu tien tot hon."))

        if len(trace) < MAX_TRACE_STEPS:
            limited_note = " Da dung mo rong CHANCE de tranh treo UI, dung diem hien tai." if context.get("limited") else ""
            next_state = selected_nb if selected_nb is not None else current
            trace.append(TraceStep(
                len(trace) + 1,
                current,
                [next_state],
                reconstruct(parent, current),
                infos,
                "Expectimax",
                g,
                _h(current, goal),
                f"PHASE=MAX. DECISION_SNAPSHOT. Root state={current}. Hanh dong duoc chon={selected_action}. Next state={next_state}. Expectimax: MAX chon action co EV cao nhat; CHANCE tinh diem trung binh co trong so theo xac suat.{limited_note}",
            ))

    if best_partial and best_partial[-1] == goal:
        return _finish("Expectimax", start_time, best_partial, stage, expanded, trace)

    return _stopped("Expectimax", start_time, stage, best_partial, expanded, trace, "Expectimax dung som theo budget thoi gian/node de tranh treo UI.")
