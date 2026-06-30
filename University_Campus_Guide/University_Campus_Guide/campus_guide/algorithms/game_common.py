from __future__ import annotations

from itertools import product
import time
from typing import Dict, List, Tuple

from map_data import GridPos, Stage, is_walkable, manhattan, movement_cost, neighbors


# Stage 5 scoring model.
# MAX controls the agent and wants a high score. MIN controls moving opponents
# and chooses opponent moves that make the agent score as small as possible.
# Bad weather, crowd, mud/flood, high-cost and risk cells are deliberately
# collapsed into one simple penalty for Stage 5.
BAD_ENVIRONMENT_PENALTY = 5.0
GOAL_BONUS = 100.0
PROGRESS_REWARD = 5.0
STEP_COST = 1.0
LOOKAHEAD_DEPTH = 5
EXPECTIMAX_DEPTH = 3
MAX_AGENT_BRANCH = 3
MAX_MIN_BRANCH = 2
MAX_CHANCE_BRANCH = 3
MAX_TREE_NODES = 100
MAX_TRACE_STEPS = 60
MAX_STAGE5_SECONDS = 1.5


def _environment_kind(pos: GridPos, stage: Stage) -> str:
    if pos in stage.covered:
        return "covered"
    if pos in stage.high_cost:
        return "crowd"
    if pos in stage.risk:
        selector = (pos[0] * 7 + pos[1] * 11) % 3
        if selector == 0:
            return "rain"
        if selector == 1:
            return "mud"
        return "risk"
    return "normal"


def _is_bad_environment(pos: GridPos, stage: Stage) -> bool:
    return _environment_kind(pos, stage) in {"crowd", "rain", "mud", "risk"}


def _valid_enemy_cell(pos: GridPos, stage: Stage, agent_pos: GridPos | None = None) -> bool:
    if agent_pos is not None and pos == agent_pos:
        return False
    if pos in {stage.start, stage.goal}:
        return False
    return is_walkable(pos, stage)


def _agent_corridor(agent_pos: GridPos, stage: Stage, limit: int = 6) -> List[GridPos]:
    """Likely near-term cells MAX wants, used by MIN to block intelligently."""
    corridor: List[GridPos] = []
    seen = {agent_pos}
    current = agent_pos

    for _ in range(limit):
        choices = [p for p in neighbors(current, stage) if p not in seen]
        if not choices:
            break
        choices.sort(
            key=lambda p: (
                manhattan(p, stage.goal),
                movement_cost(p, stage),
                manhattan(p, agent_pos),
            )
        )
        nxt = choices[0]
        corridor.append(nxt)
        seen.add(nxt)
        current = nxt
        if current == stage.goal:
            break

    return corridor


def fixed_opponent_starts(stage: Stage, limit: int = 2) -> List[GridPos]:
    if stage.idx == 5:
        preferred = [(23, 35), (29, 32), (26, 35), (23, 31)]
        curated = [pos for pos in preferred if _valid_enemy_cell(pos, stage, stage.start)]
        if len(curated) >= limit:
            return curated[:limit]

    # Static opponent cells are hard blockers, so moving opponents spawn on the
    # nearest legal walkable cells around those blockers.  This is fixed for the
    # whole stage so the opponent does not teleport when the agent moves.
    spawn_cells: List[GridPos] = []
    for anchor in sorted(stage.opponent, key=lambda p: manhattan(p, stage.start)):
        for pos in neighbors(anchor, stage):
            if _valid_enemy_cell(pos, stage, stage.start) and pos not in spawn_cells:
                spawn_cells.append(pos)

    corridor = _agent_corridor(stage.start, stage)
    spawn_cells.sort(
        key=lambda p: (
            min((manhattan(p, cell) for cell in corridor), default=manhattan(p, stage.start)),
            manhattan(p, stage.start),
            manhattan(p, stage.goal),
        )
    )
    return spawn_cells[:limit]


def _initial_opponents(agent_pos: GridPos, stage: Stage, limit: int = 2) -> List[GridPos]:
    return fixed_opponent_starts(stage, limit)


def _enemy_move_candidates(enemy_pos: GridPos, agent_pos: GridPos, stage: Stage) -> List[GridPos]:
    # Opponent may stay only when the current cell is legal, then step toward
    # the route MAX is most likely to use.
    candidates = []
    if _valid_enemy_cell(enemy_pos, stage, agent_pos):
        candidates.append(enemy_pos)
    candidates.extend(neighbors(enemy_pos, stage))

    unique: List[GridPos] = []
    for pos in candidates:
        if _valid_enemy_cell(pos, stage, agent_pos) and pos not in unique:
            unique.append(pos)

    corridor = _agent_corridor(agent_pos, stage)
    next_steps = corridor[:3]
    unique.sort(
        key=lambda p: (
            min((manhattan(p, step) for step in next_steps), default=manhattan(p, agent_pos)),
            manhattan(p, agent_pos),
            manhattan(p, stage.goal),
        )
    )
    return unique[:3]


def _opponent_successors(agent_pos: GridPos, enemies: List[GridPos], stage: Stage) -> List[List[GridPos]]:
    if not enemies:
        return []

    groups = [_enemy_move_candidates(enemy, agent_pos, stage) for enemy in enemies]
    outcomes: List[List[GridPos]] = []

    for combo in product(*groups):
        if any(not _valid_enemy_cell(pos, stage, agent_pos) for pos in combo):
            continue
        if len(set(combo)) != len(combo):
            continue
        outcomes.append(list(combo))

    # MIN does not subtract score directly.  It chooses opponent positions that
    # make the next legal MAX move as weak as possible.
    outcomes.sort(key=lambda group: _min_indirect_key(agent_pos, group, stage))
    return outcomes[:8]


def _agent_successors(
    pos: GridPos,
    stage: Stage,
    enemies: List[GridPos] | None = None,
    limit: int = MAX_AGENT_BRANCH,
) -> List[GridPos]:
    blocked = set(enemies or [])
    actions = [nb for nb in neighbors(pos, stage) if nb not in blocked]
    actions.sort(
        key=lambda nb: (
            _game_static_value(nb, stage, enemies=enemies),
            -manhattan(nb, stage.goal),
        ),
        reverse=True,
    )
    return actions[:limit]


def _best_max_reply_value(agent_pos: GridPos, stage: Stage, enemies: List[GridPos]) -> float:
    legal_moves = [nb for nb in neighbors(agent_pos, stage) if nb not in set(enemies)]
    if not legal_moves:
        return -9999.0
    return max(_game_static_value(nb, stage) for nb in legal_moves)


def _min_indirect_key(agent_pos: GridPos, enemies: List[GridPos], stage: Stage) -> Tuple[float, int, int]:
    corridor = _agent_corridor(agent_pos, stage)
    bad_cells = sorted(stage.high_cost | stage.risk)
    best_reply = _best_max_reply_value(agent_pos, stage, enemies)
    corridor_distance = min(
        (manhattan(enemy, cell) for enemy in enemies for cell in corridor[:4]),
        default=99,
    )
    bad_distance = min(
        (manhattan(enemy, cell) for enemy in enemies for cell in bad_cells),
        default=99,
    )
    return (best_reply, corridor_distance, bad_distance)


def moving_opponent_positions(agent_pos: GridPos, stage: Stage, limit: int = 2) -> List[GridPos]:
    """One-turn MIN response from the fixed spawn, kept for simple previews."""
    enemies = _initial_opponents(agent_pos, stage, limit)
    outcomes = _opponent_successors(agent_pos, enemies, stage)
    return outcomes[0] if outcomes else enemies


def advance_opponents(agent_pos: GridPos, stage: Stage, enemies: List[GridPos]) -> List[GridPos]:
    """Move each opponent at most one legal cell after the agent takes a step."""
    outcomes = _opponent_successors(agent_pos, enemies, stage)
    return outcomes[0] if outcomes else list(enemies)


def opponent_positions_for_route(route: List[GridPos] | Tuple[GridPos, ...], stage: Stage, limit: int = 2) -> List[GridPos]:
    """Replay a visible route so opponents move one square per agent step."""
    enemies = fixed_opponent_starts(stage, limit)
    for agent_pos in list(route)[1:]:
        enemies = advance_opponents(agent_pos, stage, enemies)
    return enemies


def _environment_penalty(pos: GridPos, stage: Stage, enemies: List[GridPos] | None = None) -> float:
    return BAD_ENVIRONMENT_PENALTY if _is_bad_environment(pos, stage) else 0.0


def _environment_label(pos: GridPos, stage: Stage) -> str:
    labels = {
        "normal": "binh thuong",
        "covered": "mai che/an toan",
        "crowd": "dam dong",
        "rain": "mua",
        "mud": "bun/ngap",
        "risk": "vung rui ro",
    }
    return labels.get(_environment_kind(pos, stage), "binh thuong")


def _game_static_value(
    pos: GridPos,
    stage: Stage,
    mode: str = "minimax",
    enemies: List[GridPos] | None = None,
) -> float:
    initial_distance = manhattan(stage.start, stage.goal)
    current_distance = manhattan(pos, stage.goal)
    progress_score = (initial_distance - current_distance) * PROGRESS_REWARD
    env_penalty = _environment_penalty(pos, stage, enemies)
    goal_bonus = GOAL_BONUS if pos == stage.goal else 0.0
    return progress_score - STEP_COST - env_penalty + goal_bonus


def _score_breakdown(pos: GridPos, stage: Stage) -> str:
    initial_distance = manhattan(stage.start, stage.goal)
    current_distance = manhattan(pos, stage.goal)
    progress_score = (initial_distance - current_distance) * PROGRESS_REWARD
    env_penalty = _environment_penalty(pos, stage)
    goal_bonus = GOAL_BONUS if pos == stage.goal else 0.0
    return (
        f"tien gan Goal={progress_score:+.0f}; "
        f"buoc di=-{STEP_COST:.0f}; "
        f"moi truong {_environment_label(pos, stage)}: -{env_penalty:.0f}; "
        f"thuong Goal={goal_bonus:+.0f}"
    )


def _score_summary(pos: GridPos, stage: Stage, enemies: List[GridPos] | None = None) -> str:
    initial_distance = manhattan(stage.start, stage.goal)
    current_distance = manhattan(pos, stage.goal)
    progress_score = (initial_distance - current_distance) * PROGRESS_REWARD
    env_penalty = _environment_penalty(pos, stage)
    goal_bonus = GOAL_BONUS if pos == stage.goal else 0.0
    return (
        f"gan Goal {progress_score:+.0f}; "
        f"buoc -1; "
        f"moi truong -{env_penalty:.0f}; "
        f"goal {goal_bonus:+.0f}"
    )


def _minimax_reason(action: str, score: float, reply: str, selected_action: str, selected: bool) -> str:
    if selected:
        return (
            f"MAX chon {action} vi sau khi MIN di chuyen doi thu gay bat loi gian tiep, "
            f"nhanh nay con diem cao nhat ({score:.1f})."
        )
    return (
        f"Sau phan ung cua MIN, nhanh nay con {score:.1f}; "
        f"khong tot bang lua chon hien tai cua MAX ({selected_action})."
    )


def _alpha_beta_reason(
    action: str,
    score: float,
    alpha: float,
    beta: float,
    selected_action: str,
    status: str,
) -> str:
    if status == "PRUNE":
        return (
            "Trong cay lookahead, cat phan mo rong tiep vi beta <= alpha: "
            f"nhanh nay khong vuot duoc lua chon hien tai cua MAX ({_fmt_bound(beta)} <= {_fmt_bound(alpha)})."
        )
    if status == "SELECTED":
        return (
            f"Tam chon {action}: diem {score:.1f} cap nhat alpha, "
            f"day la lua chon tot nhat cua MAX hien tai."
        )
    return (
        f"Xet {action}: cap nhat bien alpha/beta de biet nhanh sau co can mo rong tiep hay khong. "
        f"Hanh dong dang tot nhat la {selected_action}."
    )


def _expectimax_reason(action: str, score: float, selected_action: str, selected: bool) -> str:
    if selected:
        return (
            f"MAX chon {action} vi diem ky vong EV={score:.1f} lon nhat "
            "sau khi tinh xac suat moi truong xau va doi thu doi vi tri."
        )
    return (
        f"EV cua {action} = {score:.1f}; thap hon lua chon hien tai ({selected_action})."
    )


def _fmt_bound(value: float) -> str:
    if value == float("inf"):
        return "+inf"
    if value == -float("inf"):
        return "-inf"
    return f"{value:.1f}"


def _game_reply_summary(pos: GridPos, stage: Stage, expectimax_mode: bool = False) -> str:
    enemies = _initial_opponents(pos, stage)
    outcomes = _opponent_successors(pos, enemies, stage)
    if not outcomes:
        return "MIN khong co nuoc di doi thu hop le"

    if expectimax_mode:
        return (
            "CHANCE: moi truong/doi thu co the sinh nhieu ket qua; "
            f"outcomes={outcomes[:3]}, EV lay trung binh co trong so."
        )

    worst = outcomes[0]
    return (
        "MIN: doi thu di 1 o hop le, chon vi tri lam luot MAX tiep theo bat loi nhat; "
        f"chon {worst}"
    )


def _new_expectimax_context() -> Dict[str, float | bool]:
    return {
        "nodes": 0,
        "deadline": time.perf_counter() + MAX_STAGE5_SECONDS,
        "limited": False,
    }


def _expectimax_risk_penalty(pos: GridPos, stage: Stage) -> float:
    if _is_bad_environment(pos, stage):
        return BAD_ENVIRONMENT_PENALTY
    if any(_is_bad_environment(nb, stage) for nb in neighbors(pos, stage)):
        return BAD_ENVIRONMENT_PENALTY
    return 0.0


def _expectimax_chance_outcomes(
    pos: GridPos,
    stage: Stage,
    enemies: List[GridPos],
) -> List[Tuple[float, str, List[GridPos], float]]:
    outcomes: List[Tuple[float, str, List[GridPos], float]] = [
        (0.70, "binh thuong", list(enemies), 0.0),
        (0.20, "moi truong xau", list(enemies), _expectimax_risk_penalty(pos, stage)),
    ]

    enemy_outcomes = _opponent_successors(pos, enemies, stage)[:1]
    if enemy_outcomes:
        outcomes.append((0.10, "doi thu doi vi tri", enemy_outcomes[0], 0.0))

    compact: List[Tuple[float, str, List[GridPos], float]] = []
    for prob, label, next_enemies, extra_penalty in outcomes[:MAX_CHANCE_BRANCH]:
        if prob <= 0:
            continue
        compact.append((prob, label, next_enemies, extra_penalty))

    total = sum(prob for prob, _, _, _ in compact)
    if total <= 0:
        return [(1.0, "100% leaf score", list(enemies), 0.0)]

    return [(prob / total, label, next_enemies, extra_penalty) for prob, label, next_enemies, extra_penalty in compact]


def _expectimax_reply_summary(pos: GridPos, stage: Stage) -> str:
    enemies = _initial_opponents(pos, stage)
    outcomes = _expectimax_chance_outcomes(pos, stage, enemies)
    parts = [f"{prob * 100:.0f}% {label}" for prob, label, _, _ in outcomes]
    return "CHANCE outcomes: " + "; ".join(parts)


def _expectimax_value(
    pos: GridPos,
    stage: Stage,
    depth: int = EXPECTIMAX_DEPTH,
    maximizing: bool = True,
    enemies: List[GridPos] | None = None,
    cache: Dict[Tuple[GridPos, Tuple[GridPos, ...], int, str, str], float] | None = None,
    context: Dict[str, float | bool] | None = None,
) -> float:
    if enemies is None:
        enemies = _initial_opponents(pos, stage)
    if cache is None:
        cache = {}
    if context is None:
        context = _new_expectimax_context()

    role = "MAX" if maximizing else "CHANCE"
    key = (pos, tuple(sorted(enemies)), max(0, depth), role, "expectimax")
    if key in cache:
        return cache[key]

    context["nodes"] = float(context.get("nodes", 0)) + 1
    if (
        depth <= 0
        or pos == stage.goal
        or float(context.get("nodes", 0)) > MAX_TREE_NODES
        or time.perf_counter() >= float(context.get("deadline", 0))
    ):
        if depth > 0 and pos != stage.goal:
            context["limited"] = True
        value = _game_static_value(pos, stage, "expectimax", enemies)
        cache[key] = value
        return value

    if maximizing:
        actions = _agent_successors(pos, stage, enemies, MAX_AGENT_BRANCH)
        if not actions:
            value = _game_static_value(pos, stage, "expectimax", enemies)
        else:
            value = max(
                _expectimax_value(nb, stage, depth - 1, False, enemies, cache, context)
                for nb in actions
            )
        cache[key] = value
        return value

    outcomes = _expectimax_chance_outcomes(pos, stage, enemies)
    if not outcomes:
        value = _game_static_value(pos, stage, "expectimax", enemies)
        cache[key] = value
        return value

    expected = 0.0
    for prob, _, next_enemies, extra_penalty in outcomes:
        child = _expectimax_value(pos, stage, depth - 1, True, next_enemies, cache, context)
        expected += prob * (child - extra_penalty)

    cache[key] = expected
    return expected


def _game_value(
    pos: GridPos,
    stage: Stage,
    depth: int,
    maximizing: bool,
    alpha: float = -float("inf"),
    beta: float = float("inf"),
    use_ab: bool = False,
    expectimax_mode: bool = False,
    enemies: List[GridPos] | None = None,
    cache: Dict[Tuple[GridPos, Tuple[GridPos, ...], int, str, str], float] | None = None,
    context: Dict[str, float | bool] | None = None,
) -> float:
    if enemies is None:
        enemies = _initial_opponents(pos, stage)
    if cache is None:
        cache = {}
    if context is None:
        context = _new_expectimax_context()

    mode = "expectimax" if expectimax_mode else ("alpha_beta" if use_ab else "minimax")
    role = "MAX" if maximizing else ("CHANCE" if expectimax_mode else "MIN")
    key = (pos, tuple(sorted(enemies)), max(0, depth), role, mode)
    if key in cache:
        return cache[key]

    context["nodes"] = float(context.get("nodes", 0)) + 1
    if (
        depth <= 0
        or pos == stage.goal
        or float(context.get("nodes", 0)) > MAX_TREE_NODES
        or time.perf_counter() >= float(context.get("deadline", 0))
    ):
        if depth > 0 and pos != stage.goal:
            context["limited"] = True
        value = _game_static_value(pos, stage, "expectimax" if expectimax_mode else "minimax", enemies)
        cache[key] = value
        return value

    if maximizing:
        nbs = _agent_successors(pos, stage, enemies, MAX_AGENT_BRANCH)
        if not nbs:
            value = _game_static_value(pos, stage, enemies=enemies)
            cache[key] = value
            return value

        value = -float("inf")
        ordered = sorted(nbs, key=lambda nb: _game_static_value(nb, stage, enemies=enemies), reverse=True)
        for nb in ordered:
            value = max(
                value,
                _game_value(nb, stage, depth - 1, False, alpha, beta, use_ab, expectimax_mode, enemies, cache, context),
            )
            if use_ab:
                alpha = max(alpha, value)
                if alpha >= beta:
                    break
        cache[key] = value
        return value

    outcomes = _opponent_successors(pos, enemies, stage)[:MAX_CHANCE_BRANCH if expectimax_mode else MAX_MIN_BRANCH]
    if not outcomes:
        value = _game_static_value(pos, stage, enemies=enemies)
        cache[key] = value
        return value

    if expectimax_mode:
        vals = [
            _game_value(pos, stage, depth - 1, True, alpha, beta, False, True, next_enemies, cache, context)
            for next_enemies in outcomes
        ]
        value = sum(vals) / len(vals)
        cache[key] = value
        return value

    value = float("inf")
    for next_enemies in outcomes:
        value = min(
            value,
            _game_value(pos, stage, depth - 1, True, alpha, beta, use_ab, False, next_enemies, cache, context),
        )
        if use_ab:
            beta = min(beta, value)
            if alpha >= beta:
                break
    cache[key] = value
    return value
