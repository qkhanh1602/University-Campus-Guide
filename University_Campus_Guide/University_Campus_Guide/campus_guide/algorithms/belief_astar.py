from __future__ import annotations

import heapq
import time
from typing import Dict, List, Set, Tuple

from map_data import GridPos, Stage, movement_cost

from .belief_common import (
    Belief,
    _apply_belief_action,
    _belief_frontier_view,
    _belief_goal_set,
    _belief_h,
    _belief_initial,
    _belief_note,
    _belief_paths_from_actions,
    _belief_rep_next,
    _is_goal_belief,
    _representative_path_to_goal,
)
from .common import NeighborInfo, SearchResult, TraceStep, finish_search as _finish


ACTIONS = ["UP", "DOWN", "LEFT", "RIGHT"]
MAX_EXPANSIONS = 10000
MAX_TRACE_STEPS = 140


def _belief_text(belief: Belief) -> str:
    return "{" + "; ".join(f"({r},{c})" for r, c in belief) + "}"


def _belief_step_cost(stage: Stage, belief: Belief, next_belief: Belief) -> float:
    return max((float(movement_cost(pos, stage)) for pos in next_belief), default=1.0)


def belief_astar(stage: Stage) -> SearchResult:
    name = "Belief State A*"
    aggregate = "MAX"
    goal_size = 1
    start_time = time.perf_counter()
    start_b = _belief_initial(stage)
    goals = _belief_goal_set(stage, goal_size)
    h0 = _belief_h(start_b, goals, aggregate)

    frontier: List[Tuple[float, int, Belief, List[GridPos], List[str], float]] = [(h0, 0, start_b, [stage.start], [], 0.0)]
    best_g: Dict[Belief, float] = {start_b: 0.0}
    reached: Set[Belief] = set()
    reached_order: List[Belief] = []
    trace: List[TraceStep] = []
    expanded = 0
    order = 1
    best_path: List[GridPos] = [stage.start]
    best_actions: List[str] = []
    best_belief: Belief = start_b
    best_h = h0

    while frontier and expanded < MAX_EXPANSIONS:
        _f, _, belief, rep_path, actions, g_b = heapq.heappop(frontier)
        if belief in reached:
            continue
        rep = rep_path[-1]
        h_b = _belief_h(belief, goals, aggregate)
        reached.add(belief)
        reached_order.append(belief)
        expanded += 1

        if h_b < best_h:
            best_h = h_b
            best_path = rep_path[:]
            best_actions = actions[:]
            best_belief = belief

        infos: List[NeighborInfo] = []
        if _is_goal_belief(belief, goals):
            if len(trace) < MAX_TRACE_STEPS:
                trace.append(
                    TraceStep(
                        expanded,
                        rep,
                        _belief_frontier_view([item[2] for item in frontier]),
                        _belief_frontier_view(reached_order),
                        infos,
                        name,
                        g_b,
                        h_b,
                        _belief_note(name, aggregate, goal_size, belief)
                        + f"\nA* dừng: f(B)=g(B)+h(B)={g_b:.1f}+{h_b:.1f}; mọi trạng thái trong belief đều ở Goal.",
                    )
                )
            result_path = _representative_path_to_goal(rep_path, stage, use_cost=True)
            result = _finish(name, start_time, result_path, stage, expanded, trace)
            result.belief_paths = _belief_paths_from_actions(stage, actions, goals)
            return result

        for action in ACTIONS:
            next_belief = _apply_belief_action(belief, action, stage, goals)
            rep_next = _belief_rep_next(rep, action, next_belief, stage)
            step_cost = _belief_step_cost(stage, belief, next_belief)
            next_g = g_b + step_cost
            next_h = _belief_h(next_belief, goals, aggregate)
            next_f = next_g + next_h
            value = f"g={next_g:.1f}, h(B)={next_h:.1f}, f={next_f:.1f}; B'={_belief_text(next_belief)}"

            if next_belief in reached and next_g >= best_g.get(next_belief, float("inf")):
                infos.append(NeighborInfo(rep_next, action, value, "SKIP", "Reached đã có belief này với g(B) tốt hơn."))
                continue

            if next_g < best_g.get(next_belief, float("inf")):
                best_g[next_belief] = next_g
                heapq.heappush(frontier, (next_f, order, next_belief, rep_path + [rep_next], actions + [action], next_g))
                order += 1
                infos.append(NeighborInfo(rep_next, action, value, "ADD/UPDATE", "Thêm/cập nhật Priority Queue theo f(B)=g(B)+h(B)."))
            else:
                infos.append(NeighborInfo(rep_next, action, value, "SKIP", "Frontier đã có belief này với g(B) tốt hơn."))

        if len(trace) < MAX_TRACE_STEPS:
            trace.append(
                TraceStep(
                    expanded,
                    rep,
                    _belief_frontier_view([item[2] for item in frontier]),
                    _belief_frontier_view(reached_order),
                    infos,
                    name,
                    g_b,
                    h_b,
                    _belief_note(name, aggregate, goal_size, belief)
                    + "\nA* trên belief state: chọn belief có f(B)=g(B)+h(B) nhỏ nhất, rồi áp dụng cùng action cho mọi START?.",
                )
            )

    if len(trace) < MAX_TRACE_STEPS:
        trace.append(
            TraceStep(
                expanded + 1,
                best_path[-1],
                [],
                _belief_frontier_view(reached_order),
                [],
                name,
                float(len(best_actions)),
                best_h,
                _belief_note(name, aggregate, goal_size, best_belief)
                + "\nA* đã duyệt hết belief reachable theo f(B)=g(B)+h(B): không có chuỗi action chung đưa toàn bộ START? về đúng Goal.",
            )
        )
    result = _finish(
        name,
        start_time,
        best_path,
        stage,
        expanded,
        trace,
        status="Dừng - chưa đạt Goal",
    )
    result.belief_paths = _belief_paths_from_actions(stage, best_actions, goals)
    return result
