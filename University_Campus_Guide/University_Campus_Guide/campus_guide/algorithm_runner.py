
from __future__ import annotations

from algorithms.search_algorithms import run_algorithm, SearchResult
from map_data import Stage


def run_selected_algorithm(stage: Stage, algorithm_name: str) -> SearchResult:
    return run_algorithm(stage, algorithm_name)
