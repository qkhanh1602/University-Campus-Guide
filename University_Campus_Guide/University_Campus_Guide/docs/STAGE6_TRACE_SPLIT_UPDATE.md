# Stage 6 CSP Trace Layout Update

Updated Stage 6 trace presentation to match the classroom CSP layout.

## New 3-box layout

1. **CSP REPRESENTATION**
   - Variables
   - Domain
   - Constraints

2. **CURRENT ASSIGNMENT**
   - Shows only the compact current assignment, for example:
     `{checkpoint_1 = Khối E.1, checkpoint_2 = Khoa Công nghệ Thông tin}`

3. **SEARCH TRACE / SOLVING STEPS**
   - Shows step-by-step solving logs:
     - choose variable
     - try value
     - check constraints
     - forward checking domain pruning
     - Min-Conflicts chọn biến xung đột và đổi sang màu ít xung đột nhất

## Files changed

- `campus_guide/trace_dialog.py`
- `campus_guide/app_window.py`
- `campus_guide/algorithms/csp_common.py`

## Test

`python test_core.py` passes with 18/18 algorithms executed.
