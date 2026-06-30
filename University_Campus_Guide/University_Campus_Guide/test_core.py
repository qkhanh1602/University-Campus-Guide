from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'campus_guide'))
from map_data import STAGES, LANDMARKS, BUILDINGS, BUILDING_CELLS, validate_path_detail, is_walkable, in_bounds, manhattan, collision_reason
from algorithms.search_algorithms import run_algorithm

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

EXPECTED_ALGORITHM_COUNT = 18
NON_WALKABLE_LANDMARKS = {"HO_NUOC"}


def partial_path_ok(path, stage):
    """A stopped algorithm may return a partial path.
    It still must be continuous and must not enter buildings/collision cells.
    """
    if not path:
        return True, "No path returned"
    if path[0] != stage.start:
        return False, f"Partial path does not start at START {stage.start}"
    for p in path:
        if not is_walkable(p, stage):
            return False, f"Partial path enters blocked cell {p}"
    for a, b in zip(path, path[1:]):
        if manhattan(a, b) != 1:
            return False, f"Partial path jumps from {a} to {b}"
    return True, "Partial path is continuous and collision-safe"


def audit_map_setup():
    errors = []
    for key, (label, pos) in LANDMARKS.items():
        if not in_bounds(pos):
            errors.append(f"Landmark {key}/{label} is outside the map at {pos}")
        elif key not in NON_WALKABLE_LANDMARKS and not is_walkable(pos):
            errors.append(f"Landmark {key}/{label} is not walkable at {pos}: {collision_reason(pos)}")
    for building in BUILDINGS:
        if not building.label.strip():
            errors.append(f"Building {building.key} has an empty label")
    sample_blocked = sorted(BUILDING_CELLS)[:50]
    for pos in sample_blocked:
        if is_walkable(pos):
            errors.append(f"Building collision cell is walkable: {pos}")
    for idx, stage in STAGES.items():
        for role, pos in [("START", stage.start), ("GOAL", stage.goal)]:
            if not is_walkable(pos, stage):
                errors.append(f"Stage {idx} {role} is not walkable at {pos}: {collision_reason(pos, stage)}")
        for label, cells in [("blocked", stage.blocked), ("opponent", stage.opponent), ("high_cost", stage.high_cost), ("risk", stage.risk), ("covered", stage.covered)]:
            for pos in cells:
                if not in_bounds(pos):
                    errors.append(f"Stage {idx} {label} cell is outside map: {pos}")
    return errors


def main():
    configured = sum(len(stage.algorithms) for stage in STAGES.values())
    if configured != EXPECTED_ALGORITHM_COUNT:
        raise SystemExit(f"Expected {EXPECTED_ALGORITHM_COUNT} main algorithms, got {configured}")
    setup_errors = audit_map_setup()
    if setup_errors:
        print("\nMAP SETUP FAILED:")
        for error in setup_errors:
            print(error)
        raise SystemExit(1)

    total = 0
    completed = 0
    stopped = 0
    failed = []
    for idx, stage in STAGES.items():
        for alg in stage.algorithms:
            res = run_algorithm(stage, alg)
            ok_goal, msg_goal = validate_path_detail(res.path, stage)
            ok_partial, msg_partial = partial_path_ok(res.path, stage)
            total += 1
            if ok_goal:
                completed += 1
                verdict = "DONE"
                msg = msg_goal
            elif ok_partial and ("Dừng" in res.status or "Không tìm" in res.status):
                stopped += 1
                verdict = "STOP"
                msg = msg_partial + " | stopped without fallback"
            else:
                verdict = "FAIL"
                msg = msg_goal + " | " + msg_partial
                failed.append((idx, alg, res.status, msg))
            if res.fallback_used:
                failed.append((idx, alg, res.status, "fallback_used must stay False"))
            if not res.trace:
                failed.append((idx, alg, res.status, "Trace is empty; expected step-by-step explanation"))
            print(f"Stage {idx} | {alg:<28} | {verdict:<4} | cost={res.cost:<7} | expanded={res.expanded:<4} | steps={max(0, len(res.path)-1):<3} | {res.status} | {msg}")
    if failed:
        print('\nFAILED:')
        for row in failed:
            print(row)
        raise SystemExit(1)
    print(f"\nOK: {total}/18 algorithms executed. Completed={completed}, stopped_without_fallback={stopped}.")

if __name__ == '__main__':
    main()
