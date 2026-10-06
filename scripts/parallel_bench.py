"""Part 5 extra: run several environments (tabs) on ONE Chrome at the same time and time it."""
import argparse
import json
import os
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from agents.random_agent import RandomAgent  # noqa: E402
from env_client import Env, EnvProcess  # noqa: E402
from run_all import GOALS, DEFAULT_POPUP, DELAY_P  # noqa: E402


def episode(env, ep):
    """One attempt of the random agent. Seeds depend only on the episode number, so every
    setting of N plays exactly the same set of attempts."""
    item, qty = GOALS[ep % 12]
    agent = RandomAgent(seed=ep)
    obs, info = env.reset(item, qty, 200_000 + ep, DEFAULT_POPUP, DELAY_P)
    steps, ok = 0, False
    for _ in range(20):
        res = env.step(agent.act(obs, info))
        steps += 1
        obs, info = res["observation"], res["info"]
        if res["done"] or res["truncated"]:
            ok = bool(info.get("order", {}).get("success"))
            break
    return steps, ok


def run(n_envs, episodes):
    proc = EnvProcess()  # one browser for all tabs
    envs = [Env(proc, w) for w in range(n_envs)]
    for e in envs:  # warm up: opens every window before the clock starts
        e.reset("blue-mug", 1, 0, 0.0, 0.0)
    results = [None] * episodes

    def worker(w):
        for ep in range(w, episodes, n_envs):  # worker w plays episodes w, w+N, ...
            results[ep] = episode(envs[w], ep)

    t0 = time.time()
    threads = [threading.Thread(target=worker, args=(w,)) for w in range(n_envs)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    wall = time.time() - t0
    proc.close()
    return {"n_envs": n_envs, "episodes": episodes, "steps": sum(r[0] for r in results),
            "successes": sum(r[1] for r in results), "wall_s": round(wall, 3)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--episodes", type=int, default=48)
    ap.add_argument("--envs", type=int, nargs="+", default=[1, 2, 4, 8])
    ap.add_argument("--out", default=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                                  "logs", "parallel.jsonl"))
    a = ap.parse_args()
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    with open(a.out, "w") as f:
        for n in a.envs:
            r = run(n, a.episodes)
            print(r, flush=True)
            f.write(json.dumps(r) + "\n")


if __name__ == "__main__":
    main()
