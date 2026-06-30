from __future__ import annotations

from typing import Callable, Dict

from map_data import Stage

from algorithms.alpha_beta import alpha_beta
from algorithms.and_or_graph_search import and_or_graph_search
from algorithms.astar import astar
from algorithms.backtracking_csp import backtracking_csp
from algorithms.belief_astar import belief_astar
from algorithms.belief_bfs import belief_bfs
from algorithms.belief_greedy import belief_greedy
from algorithms.belief_ida import belief_ida
from algorithms.belief_local_beam import belief_local_beam
from algorithms.belief_ucs import belief_ucs
from algorithms.bfs import bfs
from algorithms.common import NeighborInfo, SearchResult, TraceStep, is_valid_path, path_cost
from algorithms.dfs import dfs
from algorithms.expectimax import expectimax
from algorithms.forward_checking_csp import forward_checking_csp
from algorithms.greedy_best_first import greedy_best_first
from algorithms.ida_star import ida_star
from algorithms.ids import ids
from algorithms.local_beam import local_beam
from algorithms.minimax import minimax
from algorithms.min_conflicts_csp import min_conflicts_csp
from algorithms.random_restart_hill import random_restart_hill
from algorithms.simple_hill import simple_hill
from algorithms.simulated_annealing import simulated_annealing
from algorithms.steepest_hill import steepest_hill
from algorithms.stochastic_hill import stochastic_hill
from algorithms.ucs import ucs


ALGORITHMS: Dict[str, Callable[[Stage], SearchResult]] = {
    "BFS": bfs,
    "DFS": dfs,
    "IDS": ids,
    "UCS": ucs,

    "Greedy Best First": greedy_best_first,
    "A*": astar,
    "IDA*": ida_star,

    "Hill Climbing": simple_hill,
    "Simple Hill Climbing": simple_hill,
    "Steepest Hill Climbing": steepest_hill,
    "Stochastic Hill Climbing": stochastic_hill,
    "Random Restart Hill Climbing": random_restart_hill,
    "Local Beam Search": local_beam,
    "Simulated Annealing": simulated_annealing,

    "AND-OR Graph Search": and_or_graph_search,
    "Belief BFS": belief_bfs,
    "Belief State BFS": belief_bfs,
    "Belief UCS": belief_ucs,
    "Belief A*": belief_astar,
    "Belief State A*": belief_astar,
    "Belief Greedy": belief_greedy,
    "Belief IDA*": belief_ida,
    "Belief Local Beam": belief_local_beam,

    "Minimax": minimax,
    "Alpha-Beta Pruning": alpha_beta,
    "Expectimax": expectimax,

    "Backtracking": backtracking_csp,
    "Forward Checking": forward_checking_csp,
    "Min-Conflicts": min_conflicts_csp,
}


def run_algorithm(stage: Stage, algorithm: str) -> SearchResult:
    fn = ALGORITHMS.get(algorithm)

    if not fn:
        raise ValueError(f"Không tìm thấy thuật toán: {algorithm}")

    result = fn(stage)
    # Attach stage for UI components that need map context to render rich traces.
    result.stage = stage

    if result.path and result.path[0] == stage.start and result.path[-1] == stage.goal:
        if not is_valid_path(result.path, stage):
            result.status = "Lỗi path - có đoạn đứt hoặc đi vào vật cản"
        elif "Dừng" not in result.status:
            result.status = "Hoàn thành"
    elif result.path:
        if "Dừng" not in result.status and "Lỗi" not in result.status:
            result.status = "Dừng - chưa đến Goal"
    else:
        result.status = result.status or "Dừng - không tìm thấy đường"

    result.fallback_used = False

    return result
