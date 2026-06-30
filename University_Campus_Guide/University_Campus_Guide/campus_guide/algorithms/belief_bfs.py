from __future__ import annotations

import time
from collections import deque
from typing import Dict, List, Set, Tuple

from map_data import GridPos, Stage

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


def belief_bfs(stage: Stage) -> SearchResult:
    name = "Belief State BFS"
    aggregate = "MAX"
    goal_size = 1
    start_time = time.perf_counter()
    start_b = _belief_initial(stage)
    goals = _belief_goal_set(stage, goal_size)

    frontier = deque([(start_b, [stage.start], [])])
    reached: Set[Belief] = {start_b}
    reached_order: List[Belief] = []
    trace: List[TraceStep] = []
    expanded = 0
    best_path: List[GridPos] = [stage.start]
    best_h = _belief_h(start_b, goals, aggregate)
    best_actions: List[str] = []
    best_belief: Belief = start_b

    while frontier and expanded < MAX_EXPANSIONS:
        belief, rep_path, actions = frontier.popleft()
        rep = rep_path[-1]
        h_b = _belief_h(belief, goals, aggregate)
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
                        _belief_frontier_view([item[0] for item in frontier]),
                        _belief_frontier_view(reached_order),
                        infos,
                        name,
                        len(actions),
                        h_b,
                        _belief_note(name, aggregate, goal_size, belief)
                        + "\nBFS dừng: mọi trạng thái trong belief đều đã ở Goal.",
                    )
                )
            result_path = _representative_path_to_goal(rep_path, stage, use_cost=False)
            result = _finish(name, start_time, result_path, stage, expanded, trace)
            result.belief_paths = _belief_paths_from_actions(stage, actions, goals)
            return result

        for action in ACTIONS:
            next_belief = _apply_belief_action(belief, action, stage, goals)
            rep_next = _belief_rep_next(rep, action, next_belief, stage)
            value = f"B'={_belief_text(next_belief)}"
            if next_belief in reached:
                infos.append(NeighborInfo(rep_next, action, value, "SKIP", "Belief này đã có trong reached nên BFS không thêm lại."))
                continue
            reached.add(next_belief)
            frontier.append((next_belief, rep_path + [rep_next], actions + [action]))
            infos.append(NeighborInfo(rep_next, action, value, "ADD", "Thêm belief mới vào cuối Queue FIFO."))

        if len(trace) < MAX_TRACE_STEPS:
            trace.append(
                TraceStep(
                    expanded,
                    rep,
                    _belief_frontier_view([item[0] for item in frontier]),
                    _belief_frontier_view(reached_order),
                    infos,
                    name,
                    len(actions),
                    h_b,
                    _belief_note(name, aggregate, goal_size, belief)
                    + "\nBFS trên belief state: pop Queue FIFO, áp dụng cùng một action cho tất cả START? trong belief.",
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
                len(best_actions),
                best_h,
                _belief_note(name, aggregate, goal_size, best_belief)
                + "\nBFS đã duyệt hết belief reachable: không có chuỗi action chung đưa toàn bộ START? về đúng Goal.",
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
