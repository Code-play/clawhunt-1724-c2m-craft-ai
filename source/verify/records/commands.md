# Verification commands

| Command | Exit | Expected last line |
|---|---|---|
| `python -m c2m_craft demo` | 0 | artifacts written: 33 |
| `python tests/test_runner.py` | 0 | N/N tests passed |
| `python -m c2m_craft demo (second run)` | 0 | identical hash manifest |
| `python verify/run_verification.py` | 0 | N/N assertions passed |

Generated at the logical as-of time recorded in `out/hash_manifest.json`; no wall clock is read.

Group results:

| Group | Assertions | Passed |
|---|---|---|
| A | 14 | 14 |
| B | 12 | 12 |
| C | 25 | 25 |
| D | 33 | 33 |
| E | 9 | 9 |
| F | 38 | 38 |
| G | 51 | 51 |
| H | 12 | 12 |
| I | 22 | 22 |
| J | 35 | 35 |
| K | 38 | 38 |
