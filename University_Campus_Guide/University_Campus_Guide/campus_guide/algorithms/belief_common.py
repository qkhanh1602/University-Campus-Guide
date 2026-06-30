from __future__ import annotations

from collections import deque
from dataclasses import replace
import heapq
from typing import Dict, Iterable, List, Optional, Set, Tuple

from map_data import GridPos, Stage, is_walkable, manhattan, movement_cost, neighbors

from .common import action_name, h as _h, move, reconstruct


Belief = Tuple[GridPos, ...]


def _unique_positions(items: Iterable[GridPos]) -> Belief:
    return tuple(sorted(set(items)))

def _belief_initial(stage: Stage, size: int = 3) -> Belief:
    # Không biết start: nếu chặng khai báo START? thì dùng đúng tập đó.
    if stage.uncertain_starts:
        possible = [p for p in sorted(stage.uncertain_starts) if is_walkable(p, stage)]
        if possible:
            return _unique_positions(possible)

    # Fallback cho các chặng cũ: agent có thể ở start hoặc vài ô đi được gần start.
    result: List[GridPos] = [stage.start]
    for p in neighbors(stage.start, stage):
        if len(result) >= size:
            break
        result.append(p)
    return _unique_positions(result)

def _belief_goal_set(stage: Stage, size: int = 1) -> Set[GridPos]:
    goals = [stage.goal]
    if size > 1:
        for p in neighbors(stage.goal, stage):
            if len(goals) >= size:
                break
            goals.append(p)
    return set(goals)

def _belief_h(belief: Belief, goals: Set[GridPos], aggregate: str = "MAX") -> float:
    vals = [min(_h(s, g) for g in goals) for s in belief]
    if not vals:
        return 0.0
    return sum(vals) / len(vals) if aggregate == "AVG" else float(max(vals))

def _is_goal_belief(belief: Belief, goals: Set[GridPos]) -> bool:
    return all(pos in goals for pos in belief)

def _apply_belief_action(belief: Belief, action: str, stage: Stage, goals: Set[GridPos]) -> Belief:
    out: List[GridPos] = []
    for pos in belief:
        if pos in goals:
            out.append(pos)  # goal hấp thụ
            continue
        nxt = move(pos, action)
        out.append(nxt if is_walkable(nxt, stage) else pos)
    return _unique_positions(out)

def _rep_next_for_action(rep: GridPos, action: str, stage: Stage) -> Optional[GridPos]:
    nxt = move(rep, action)
    return nxt if is_walkable(nxt, stage) else None


def _belief_rep_next(rep: GridPos, action: str, next_belief: Belief, stage: Stage) -> GridPos:
    intended = _rep_next_for_action(rep, action, stage)
    if intended is not None:
        return intended

    choices = neighbors(rep, stage)
    if not choices:
        return rep

    targets = list(next_belief) or [stage.goal]
    return min(
        choices,
        key=lambda p: (
            min(manhattan(p, target) for target in targets),
            manhattan(p, stage.goal),
        ),
    )


def _shortest_path_from(start: GridPos, goal: GridPos, stage: Stage, use_cost: bool = False) -> List[GridPos]:
    if start == goal:
        return [start]

    parent: Dict[GridPos, Optional[GridPos]] = {start: None}

    if use_cost:
        frontier: List[Tuple[float, int, GridPos]] = [(float(_h(start, goal)), 0, start)]
        g_score: Dict[GridPos, float] = {start: 0.0}
        best_f: Dict[GridPos, float] = {start: float(_h(start, goal))}
        order = 1
        reached: Set[GridPos] = set()
        while frontier:
            f, _, current = heapq.heappop(frontier)
            if f != best_f.get(current):
                continue
            best_f.pop(current, None)
            if current in reached:
                continue
            if current == goal:
                return reconstruct(parent, goal)
            reached.add(current)
            for nb in neighbors(current, stage):
                new_g = g_score[current] + movement_cost(nb, stage)
                new_f = new_g + _h(nb, goal)
                if nb in reached and new_g >= g_score.get(nb, float("inf")):
                    continue
                if new_g < g_score.get(nb, float("inf")):
                    g_score[nb] = new_g
                    parent[nb] = current
                    best_f[nb] = new_f
                    heapq.heappush(frontier, (new_f, order, nb))
                    order += 1
        return []

    frontier = deque([start])
    reached = {start}
    while frontier:
        current = frontier.popleft()
        if current == goal:
            return reconstruct(parent, goal)
        for nb in neighbors(current, stage):
            if nb in reached:
                continue
            reached.add(nb)
            parent[nb] = current
            frontier.append(nb)
    return []


def _parallel_belief_paths(stage: Stage, use_cost: bool = False) -> List[List[GridPos]]:
    starts = list(_belief_initial(stage))
    relaxed_stage = replace(stage, blocked=set())
    paths: List[List[GridPos]] = []
    for start in starts:
        path = _shortest_path_from(start, stage.goal, stage, use_cost)
        if not path:
            path = _shortest_path_from(start, stage.goal, relaxed_stage, use_cost)
        if path:
            paths.append(path)
    return paths


def _belief_at(paths: List[List[GridPos]], index: int) -> Belief:
    cells = [path[min(index, len(path) - 1)] for path in paths if path]
    return _unique_positions(cells)


def _belief_move_infos(paths: List[List[GridPos]], index: int):
    from .common import NeighborInfo

    infos: List[NeighborInfo] = []
    for i, path in enumerate(paths, start=1):
        prev = path[min(max(index - 1, 0), len(path) - 1)]
        cur = path[min(index, len(path) - 1)]
        status = "GOAL" if cur == path[-1] else "MOVE"
        if cur == prev:
            status = "WAIT" if cur != path[-1] else "GOAL"
        value = f"agent={i}"
        reason = "Nhan vat belief di theo duong rieng toi Goal." if status != "GOAL" else "Nhan vat belief da toi Goal va dung lai."
        infos.append(NeighborInfo(cur, action_name(prev, cur), value, status, reason))
    return infos

def _belief_frontier_view(items: Iterable[Belief]) -> List[GridPos]:
    # UI map highlight được nhiều ô, nên trải phẳng vài belief đầu để thấy tập trạng thái.
    out: List[GridPos] = []
    for b in items:
        for pos in b:
            if pos not in out:
                out.append(pos)
            if len(out) >= 16:
                return out
    return out[:16]

def _belief_trace_note(name: str, aggregate: str, goal_size: int) -> str:
    extra = "Goal set có nhiều khả năng." if goal_size > 1 else "Goal là trạng thái hấp thụ."
    return f"{name}: biết Goal nhưng không biết chắc Start; node là belief state = tập START? / vị trí có thể. h(B) dùng {aggregate}. {extra} Thuật toán chỉ hoàn thành khi mọi trạng thái trong belief đều đạt Goal."


def _belief_note(name: str, aggregate: str, goal_size: int, belief: Belief) -> str:
    cells = ";".join(f"({r},{c})" for r, c in belief)
    return _belief_trace_note(name, aggregate, goal_size) + f" CURRENT_BELIEF={cells}"


def _belief_paths_from_actions(stage: Stage, actions: List[str], goals: Set[GridPos]) -> List[List[GridPos]]:
    paths: List[List[GridPos]] = [[start] for start in _belief_initial(stage)]
    for action in actions:
        for path in paths:
            pos = path[-1]
            if pos in goals:
                path.append(pos)
                continue
            nxt = move(pos, action)
            path.append(nxt if is_walkable(nxt, stage) else pos)
    return paths


def _representative_path_to_goal(rep_path: List[GridPos], stage: Stage, use_cost: bool = False) -> List[GridPos]:
    if not rep_path:
        rep_path = [stage.start]
    if rep_path[-1] == stage.goal:
        return rep_path
    tail = _shortest_path_from(rep_path[-1], stage.goal, stage, use_cost)
    if tail:
        return rep_path + tail[1:]
    return rep_path
