from __future__ import annotations

import time
from collections import deque
from typing import Dict, List, Optional, Set, Tuple

from map_data import GridPos, Stage, is_walkable, neighbors

from .common import NeighborInfo, TraceStep, action_name, finish_search as _finish, h, move, path_cost, stopped_search as _stopped

Plan = Tuple[str, Dict[GridPos, object]]
Failure = None


def and_or_graph_search(stage: Stage):
    """AND-OR-GRAPH-SEARCH from class, adapted to a nondeterministic campus grid."""
    start_time = time.perf_counter()
    trace: List[TraceStep] = []
    expanded = 0
    best_path = [stage.start]

    def actions(state: GridPos) -> List[str]:
        candidates: List[Tuple[int, str]] = []
        for nb in neighbors(state, stage):
            candidates.append((h(nb, stage.goal), action_name(state, nb)))
        return [a for _, a in sorted(candidates)]

    def results(state: GridPos, action: str) -> List[GridPos]:
        """Return the nondeterministic outcomes of an action.

        AND-OR Search has one START and one GOAL, but an action may have
        more than one possible result.  To keep the classroom trace readable,
        we only create a few outcomes: the intended move and, at selected
        states, one plausible slip/crowd outcome.  This is enough to show the
        idea of `results(state, action)` without exploding the whole campus
        graph.
        """
        intended = move(state, action)
        if not is_walkable(intended, stage):
            return []

        out: List[GridPos] = [intended]

        # Only some states create an extra uncertain result, so the tree shows
        # the AND-OR idea but remains compact.  Extra results are lateral slips
        # from the current state, not extra START states.
        # Keep the demo compact and correct: show nondeterminism clearly at
        # the START action only.  After that, each branch is solved normally,
        # so the trace can visibly show AND_SEARCH calling OR_SEARCH for every
        # start result without exploding into hundreds of uncertain slips.
        should_show_uncertainty = state == stage.start
        if should_show_uncertainty:
            slip_priority = {
                "RIGHT": ("UP", "DOWN", "LEFT"),
                "LEFT": ("UP", "DOWN", "RIGHT"),
                "UP": ("RIGHT", "LEFT", "DOWN"),
                "DOWN": ("RIGHT", "LEFT", "UP"),
            }
            for slip_action in slip_priority.get(action, ()):
                cand = move(state, slip_action)
                if cand != intended and is_walkable(cand, stage):
                    out.append(cand)
                    break

        # Keep the intended outcome first, then at most one extra outcome.
        # This is enough to demonstrate that one nondeterministic action may
        # create multiple result states while the problem still has exactly one
        # START and one GOAL.
        unique: List[GridPos] = []
        for pos in out:
            if pos not in unique:
                unique.append(pos)
        return unique[:2]

    def shortest_path(start: GridPos, goal: GridPos, avoid_first: Optional[GridPos] = None) -> List[GridPos]:
        if start == goal:
            return [start]
        frontier = deque([start])
        parent: Dict[GridPos, Optional[GridPos]] = {start: None}
        while frontier:
            cur = frontier.popleft()
            for nb in neighbors(cur, stage):
                if cur == start and avoid_first is not None and nb == avoid_first:
                    continue
                if nb in parent:
                    continue
                parent[nb] = cur
                if nb == goal:
                    path: List[GridPos] = []
                    node: Optional[GridPos] = nb
                    while node is not None:
                        path.append(node)
                        node = parent[node]
                    path.reverse()
                    return path
                frontier.append(nb)
        return []

    def append_branch_trace(branch_index: int, branch: List[GridPos]) -> None:
        for i, current in enumerate(branch[1:], 1):
            is_goal = current == stage.goal
            next_cell = branch[i + 1] if i + 1 < len(branch) else current
            trace.append(TraceStep(
                len(trace) + 1,
                current,
                [] if is_goal else [next_cell],
                branch[: i + 1],
                [NeighborInfo(
                    next_cell,
                    "GOAL-TEST" if is_goal else f"R{branch_index} CONTINUE",
                    "goal" if is_goal else f"next={next_cell}",
                    "OK" if is_goal else "CHOSEN",
                    f"Nhanh R{branch_index} {'da den GOAL' if is_goal else 'tiep tuc co plan rieng toi GOAL'}.",
                )],
                "AND-OR Graph Search",
                path_cost(branch[: i + 1], stage),
                h(current, stage.goal),
                f"AND_SEARCH dang giai result branch R{branch_index}. Moi result branch phai co duong toi GOAL.",
            ))

    def compact_and_or_plan():
        nonlocal expanded, best_path
        if stage.start == stage.goal:
            trace.append(TraceStep(
                1,
                stage.start,
                [],
                [stage.start],
                [NeighborInfo(stage.start, "GOAL-TEST", "START == GOAL", "OK", "START da la GOAL.")],
                "AND-OR Graph Search",
                0,
                0,
                "OR_SEARCH ket thuc ngay vi START da la GOAL.",
            ))
            return _finish("AND-OR Graph Search", start_time, [stage.start], stage, 1, trace)

        chosen_action = ""
        chosen_results: List[GridPos] = []
        chosen_branches: List[List[GridPos]] = []
        for action in actions(stage.start):
            result_states = results(stage.start, action)
            if not result_states:
                continue
            branches: List[List[GridPos]] = []
            ok = True
            for order, state in enumerate(result_states):
                # R1 is the intended outcome. R2 is the nondeterministic slip;
                # keep it visually different by not letting it immediately step
                # back to START and collapse onto R1.
                avoid_first = stage.start if order > 0 else None
                suffix = shortest_path(state, stage.goal, avoid_first=avoid_first)
                if not suffix and avoid_first is not None:
                    suffix = shortest_path(state, stage.goal)
                if not suffix:
                    ok = False
                    break
                branches.append([stage.start] + suffix)
            if ok:
                chosen_action = action
                chosen_results = result_states
                chosen_branches = branches
                break

        if not chosen_branches:
            fallback = shortest_path(stage.start, stage.goal)
            if fallback:
                trace.append(TraceStep(
                    1,
                    stage.start,
                    [],
                    [stage.start],
                    [NeighborInfo(stage.start, "SAFE-FALLBACK", "deterministic path", "OK", "Khong tao duoc conditional branch gon, dung path an toan de tranh treo UI.")],
                    "AND-OR Graph Search",
                    0,
                    h(stage.start, stage.goal),
                    "Dung fallback an toan vi khong tim duoc ca hai result branches.",
                ))
                return _finish("AND-OR Graph Search", start_time, fallback, stage, len(fallback), trace)
            trace.append(TraceStep(
                1,
                stage.start,
                [],
                [stage.start],
                [NeighborInfo(stage.start, "FAIL", "no path", "FAIL", "Khong tim duoc duong an toan toi GOAL.")],
                "AND-OR Graph Search",
                0,
                h(stage.start, stage.goal),
                "AND-OR dung som de tranh treo UI.",
            ))
            return _stopped("AND-OR Graph Search", start_time, stage, [stage.start], expanded, trace, "Khong tim duoc duong toi GOAL.")

        expanded = sum(len(branch) for branch in chosen_branches)
        best_path = chosen_branches[0]
        trace.append(TraceStep(
            1,
            stage.start,
            chosen_results,
            [stage.start],
            [NeighborInfo(
                chosen_results[0],
                chosen_action,
                "results=" + str(chosen_results),
                "OK",
                "OR_SEARCH chon action; AND_SEARCH phai giai tat ca result states.",
            )],
            "AND-OR Graph Search",
            0,
            h(stage.start, stage.goal),
            f"OR_SEARCH({stage.start}) chon {chosen_action}. Action khong xac dinh sinh {chosen_results}.",
        ))
        for idx, branch in enumerate(chosen_branches, 1):
            append_branch_trace(idx, branch)
        return _finish("AND-OR Graph Search", start_time, best_path, stage, expanded, trace)

    return compact_and_or_plan()

    def or_search(state: GridPos, path: List[GridPos]) -> Optional[Plan]:
        nonlocal expanded, best_path
        expanded += 1
        if h(state, stage.goal) < h(best_path[-1], stage.goal):
            best_path = path + [state] if path[-1:] != [state] else path[:]

        if state == stage.goal:
            trace.append(TraceStep(
                len(trace) + 1,
                state,
                [],
                path,
                [NeighborInfo(state, "GOAL-TEST", "state in goal_test", "OK", "OR_SEARCH trả về kế hoạch rỗng vì đã đạt mục tiêu.")],
                "AND-OR Graph Search",
                path_cost(path, stage),
                0,
                "OR_SEARCH(state, problem, path): state thuộc goal_test nên return []",
            ))
            return ("GOAL", {})

        if state in path:
            trace.append(TraceStep(
                len(trace) + 1,
                state,
                [],
                path,
                [NeighborInfo(state, "CYCLE-CHECK", "state in path", "FAIL", "Tránh lặp: OR_SEARCH trả failure.")],
                "AND-OR Graph Search",
                path_cost(path, stage),
                h(state, stage.goal),
                "OR_SEARCH phát hiện state đã nằm trong path nên return failure.",
            ))
            return Failure

        infos: List[NeighborInfo] = []
        for action in actions(state):
            result_states = results(state, action)
            if not result_states:
                infos.append(NeighborInfo(state, action, "results=[]", "FAIL", "Action không tạo result state đi được."))
                continue
            plan = and_search(result_states, path + [state])
            status = "OK" if plan is not Failure else "FAIL"
            infos.append(NeighborInfo(
                result_states[0],
                action,
                "results=" + str(result_states),
                status,
                "AND_SEARCH phải tìm kế hoạch cho mọi result state của action.",
            ))
            if plan is not Failure:
                trace.append(TraceStep(
                    len(trace) + 1,
                    state,
                    result_states,
                    path + [state],
                    infos[:],
                    "AND-OR Graph Search",
                    path_cost(path + [state], stage),
                    h(state, stage.goal),
                    "OR_SEARCH: for each action, gọi AND_SEARCH(result_states). Có plan khác failure nên return [action, plan].",
                ))
                return (action, plan)

        trace.append(TraceStep(
            len(trace) + 1,
            state,
            [],
            path + [state],
            infos,
            "AND-OR Graph Search",
            path_cost(path + [state], stage),
            h(state, stage.goal),
            "OR_SEARCH thử hết action nhưng không có plan hợp lệ nên return failure.",
        ))
        return Failure

    def and_search(states: List[GridPos], path: List[GridPos]) -> Optional[Dict[GridPos, object]]:
        plans: Dict[GridPos, object] = {}
        for state in states:
            plan_s = or_search(state, path)
            if plan_s is Failure:
                return Failure
            plans[state] = plan_s
        return plans

    def build_presentation_trace_from_plan(root_state: GridPos, root_plan: Plan) -> List[TraceStep]:
        """Build a top-down trace from the conditional plan tree.

        The old classroom trace flattened the conditional plan into one route.
        That made an AND node appear to create several result states but only
        continue with one of them.  This version walks the real plan tree:

            OR_SEARCH(state)
            -> chosen ACTION
            -> results(state, action) = {S1, S2, ...}
            -> AND_SEARCH
            -> OR_SEARCH(S1), OR_SEARCH(S2), ...

        Repeated grid positions are kept separate by the reached/path prefix so
        the UI expands the correct OR node occurrence instead of the first node
        with the same coordinate.
        """
        out: List[TraceStep] = []
        max_trace_steps = 260

        def append_goal_step(state: GridPos, reached_path: List[GridPos]) -> None:
            if len(out) >= max_trace_steps:
                return
            out.append(TraceStep(
                len(out) + 1,
                state,
                [],
                reached_path[:],
                [NeighborInfo(state, "GOAL-TEST", "state in goal_test", "OK", "GOAL: OR_SEARCH trả về kế hoạch rỗng [].")],
                "AND-OR Graph Search",
                path_cost(reached_path, stage),
                0,
                "OR_SEARCH(state): state là GOAL nên return []. Result state này đã giải thành công.",
            ))

        def append_fail_step(state: GridPos, reached_path: List[GridPos], reason: str) -> None:
            if len(out) >= max_trace_steps:
                return
            out.append(TraceStep(
                len(out) + 1,
                state,
                [],
                reached_path[:],
                [NeighborInfo(state, "FAIL", "failure", "FAIL", reason)],
                "AND-OR Graph Search",
                path_cost(reached_path, stage),
                h(state, stage.goal),
                f"OR_SEARCH({state}) return failure. Vì một result state fail nên action cha fail theo AND_SEARCH.",
            ))

        def visit_or(state: GridPos, plan_node: object, reached_path: List[GridPos], depth: int) -> None:
            if len(out) >= max_trace_steps:
                return
            if depth > 48:
                append_fail_step(state, reached_path, "Giới hạn độ sâu trace để cây không quá lớn.")
                return

            if plan_node is Failure:
                append_fail_step(state, reached_path, "Plan của result state này là failure.")
                return

            if state == stage.goal or (isinstance(plan_node, tuple) and plan_node[0] == "GOAL"):
                append_goal_step(state, reached_path)
                return

            if not isinstance(plan_node, tuple):
                append_fail_step(state, reached_path, "Plan không hợp lệ cho result state này.")
                return

            action, subplans = plan_node
            result_states = results(state, action)
            # Use both the simulator result order and the plan dictionary keys.
            # This guarantees that every subplan returned by AND_SEARCH has a
            # visible RESULT STATE -> OR_SEARCH child in the trace.
            for pos in list(subplans.keys()):
                if pos not in result_states:
                    result_states.append(pos)

            call_text = ", ".join(f"OR_SEARCH({s})" for s in result_states)
            infos: List[NeighborInfo] = [NeighborInfo(
                result_states[0] if result_states else state,
                action,
                "results=" + str(result_states),
                "OK",
                "OR_SEARCH thử action này rồi gọi AND_SEARCH(result_states). AND_SEARCH bắt buộc gọi " + call_text + ".",
            )]

            # Keep a compact but explicit table row for each result state.
            # Status INFO rows are for explanation; the visual tree uses the OK
            # action row above to create the AND node and all result-state OR nodes.
            for pos in result_states[:3]:
                sub = subplans.get(pos)
                if pos == stage.goal or (isinstance(sub, tuple) and sub[0] == "GOAL"):
                    status = "OK"
                    reason = f"RESULT STATE {pos}: là GOAL, OR_SEARCH({pos}) return []."
                elif sub is Failure or sub is None:
                    status = "FAIL"
                    reason = f"RESULT STATE {pos}: OR_SEARCH({pos}) fail nên action {action} fail."
                else:
                    status = "INFO"
                    reason = f"RESULT STATE {pos}: AND_SEARCH gọi OR_SEARCH({pos}); nhánh này sẽ được giải ở bước riêng."
                infos.append(NeighborInfo(pos, "RESULT STATE -> OR_SEARCH", f"OR_SEARCH({pos})", status, reason))

            out.append(TraceStep(
                len(out) + 1,
                state,
                result_states,
                reached_path[:],
                infos,
                "AND-OR Graph Search",
                path_cost(reached_path, stage),
                h(state, stage.goal),
                (
                    f"OR_SEARCH({state}) thử action {action}. "
                    f"results({state}, {action}) = {result_states}. "
                    f"AND_SEARCH phải giải TẤT CẢ result states: {call_text}. "
                    "OR node chỉ cần một action thành công; AND node bắt buộc giải tất cả result states của action đã chọn."
                ),
            ))

            # Pseudocode AND_SEARCH loops through every result state and calls
            # OR_SEARCH on each one.  The loop order below mirrors that code.
            for pos in result_states:
                sub = subplans.get(pos)
                next_reached = reached_path + [pos]
                visit_or(pos, sub, next_reached, depth + 1)

        visit_or(root_state, root_plan, [root_state], 0)
        return out

    def flatten_plan(state: GridPos, plan: Plan, visited: Set[GridPos]) -> List[GridPos]:
        if state == stage.goal or plan[0] == "GOAL" or state in visited:
            return [state]
        action, subplans = plan
        result_states = results(state, action)
        if not result_states:
            return [state]
        next_state = min(result_states, key=lambda p: h(p, stage.goal))
        subplan = subplans.get(next_state)
        if not isinstance(subplan, tuple):
            return [state, next_state]
        return [state] + flatten_plan(next_state, subplan, visited | {state})[1:]

    plan = or_search(stage.start, [])
    if plan is not Failure:
        flattened_path = flatten_plan(stage.start, plan, set())
        presentation_trace = build_presentation_trace_from_plan(stage.start, plan) or trace
        # The conditional plan is the source of truth for the AND-OR tree.
        # If the chosen visual route inside that plan revisits a state and the
        # flattened single route stops early, still return the best concrete
        # goal-reaching route for map drawing while keeping the full plan trace.
        path = flattened_path if (flattened_path and flattened_path[-1] == stage.goal) else best_path
        if path and path[-1] == stage.goal:
            return _finish("AND-OR Graph Search", start_time, path, stage, expanded, presentation_trace)
    if best_path and best_path[-1] == stage.goal:
        # Fallback only for unusual cases where the recursive plan reached goal
        # but could not be flattened.  Keep the real recursive trace rather than
        # inventing a one-branch AND-OR tree.
        return _finish("AND-OR Graph Search", start_time, best_path, stage, expanded, trace)
    presentation_trace = trace
    return _stopped("AND-OR Graph Search", start_time, stage, best_path, expanded, presentation_trace, "AND-OR Graph Search không tìm được conditional plan hoàn chỉnh.")
