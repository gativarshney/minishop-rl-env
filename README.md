# MiniShop RL environment

A small shopping page, a C++ environment that drives it through raw Chrome DevTools Protocol, and two Python agents (random and tabular Q-learning).

## What was built
- `site/index.html`: plain HTML/JS shop. Goal from the URL (`?item=blue-mug&qty=2&seed=42&popup_p=0.15&delay_p=0.10`). Seeded popups and delayed buttons. Exposes `window.__orderResult` and `window.__state`.
- `env/`: C++17 program (CMake, IXWebSocket with TLS and zlib off, nlohmann/json). Starts headless Chrome or Edge once, talks CDP over a WebSocket, real mouse clicks, observation read live from the page. Speaks JSON lines on stdin/stdout.
- `agents/`: random agent and Q-learning agent.
- `scripts/run_all.py`: build, train 3 runs, evaluate, popup sweep, analyze. `scripts/analyze.py`: reads only the log and writes `report.md` and `charts/`.
- `scripts/parallel_bench.py`: Part 5 extra, several environments (one browser window each) on one Chrome at the same time, with a speedup table in the report.
- `scripts/test_env.py`, `scripts/test_cleanup.py`: smoke test (one full purchase) and a crash test (no browser left behind).
- `scripts/ci_step.sh`: used by CI to put the end of a failing step's output into an annotation.

## Approach
Q-learning with a small goal-relative state, epsilon-greedy with decay, 3 independent training runs, evaluation on unseen seeds. See `DECISIONS.md` for state, actions, reward and when an attempt ends.

## How to run
Needs CMake, a C++17 compiler, Python 3 and Chrome or Edge (set `CHROME_BIN` to override the browser path).

```
pip install -r requirements.txt
.\run.ps1        # Windows
./run.sh         # Linux
```
Everything lands in `logs/run.jsonl`, `logs/parallel.jsonl`, `report.md` and `charts/`. GitHub Actions on ubuntu-latest first runs the smoke test, the cleanup test and a small parallel check, then `./run.sh`.

## Evaluation method
Training attempts use seeds below 100000, evaluation attempts seeds from 100000. Each agent gets 210 evaluation attempts (3 runs x 70) at popup_p=0.15, delay_p=0.10, the Q agent also at popup_p 0 and 0.4. Confidence intervals are 95% Wilson intervals.

## Results (from the committed run, see `report.md` for everything)
- Random agent: 6 of 210 succeeded (2.9%, CI 1.3% to 6.1%).
- Q-learning agent: 210 of 210 succeeded (100%, CI 98.2% to 100%), also at popup_p 0 and 0.4.
- With more popups the agent needs more steps (4.32 at popup_p 0, 5.07 at 0.4) but still stays under the 20 step limit.
- Several environments on one Chrome: 1.49x faster with 2, 1.94x with 4 and 3.80x with 8 (random agent, same 48 attempts each time).
- The full pipeline took about 7.5 minutes on the Windows laptop, including the parallel environments benchmark.

## Limitations
- The task is small, so the learner reaches 100% and the sweep does not show a drop in success, only in steps.
- The state uses page facts (cart, viewed product) that the agent reads from `window.__state` through `info`, not from the buttons alone.
- One hyperparameter setting, no search.
- Timing numbers depend on the machine.

## Part 5 (extra)
I picked the first option: several environments on one Chrome. The numbers are in the last section of `report.md`, computed from `logs/parallel.jsonl`. Each environment needs its own browser window; separate tabs in one window were throttled by Chrome when in the background and got slower, not faster. On Linux the browser must be started from the main thread: Chrome is started with a parent-death signal, which fires when the thread that started it ends, and the env answers each request on its own short-lived thread.

## Pending
- The Harbor task format (the other Part 5 option) was not done.
- Harder pages and a learner without hand built state (see `DECISIONS.md`).
