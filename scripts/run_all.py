"""Build, train, evaluate, sweep and analyze. Every result comes from running the real environment."""
import argparse
import glob
import json
import multiprocessing as mp
import os
import random
import shutil
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))
from agents.qlearning_agent import QAgent  # noqa: E402
from agents.random_agent import RandomAgent  # noqa: E402
from env_client import Env  # noqa: E402

ITEMS = ["blue-mug", "red-lamp", "green-book", "black-pen"]
GOALS = [(item, qty) for item in ITEMS for qty in (1, 2, 3)]  # the 12 goals
DEFAULT_POPUP, DELAY_P = 0.15, 0.10
SWEEP_POPUPS = [0.0, 0.15, 0.4]
LOG_DIR = os.path.join(ROOT, "logs")
PART_DIR = os.path.join(LOG_DIR, "parts")


def build():
    env_dir = os.path.join(ROOT, "env")
    subprocess.check_call(["cmake", "-S", env_dir, "-B", os.path.join(env_dir, "build"), "-DCMAKE_BUILD_TYPE=Release"])
    subprocess.check_call(["cmake", "--build", os.path.join(env_dir, "build"), "--config", "Release"])


def run_episode(env, agent, goal, seed, popup_p, delay_p, meta, train, out):
    """Plays one attempt, writes one JSON line per step, returns True if the order was correct."""
    item, qty = goal
    obs, info = env.reset(item, qty, seed, popup_p, delay_p)
    if train is not None:
        agent.start_episode(item, qty, meta["episode"], train)
    success = False
    for step in range(1, 21):
        action = agent.act(obs, info)
        key = getattr(agent, "last_key", action[0])
        res = env.step(action)
        done, trunc = res["done"], res["truncated"]
        rec = {"episode": meta["episode"], "run": meta["run"], "seed": seed, "goal": f"{item} x{qty}",
               "step": step, "observation": obs,
               "action": f"click({action[1]})" if action[0] == "click" else "wait",
               "action_key": key, "reward": res["reward"], "done": done, "truncated": trunc,
               "time_ms": res["time_ms"], "cdp_ms": res["cdp_ms"], "settle_ms": res["settle_ms"],
               "popup_showing": obs["popup_showing"], "agent": agent.name, "phase": meta["phase"],
               "popup_p": popup_p, "delay_p": delay_p, "info": res["info"]}
        out.write(json.dumps(rec) + "\n")
        errored = "error" in res["info"]
        if meta["phase"] == "train" and not errored:
            agent.learn(obs, info, key, res["reward"], res["observation"], res["info"], done)
        success = bool(res["info"].get("order", {}).get("success", False))
        obs, info = res["observation"], res["info"]
        if done or trunc:
            break
    return success


def safe_episode(holder, agent, *rest):
    """If the env process or browser dies mid-attempt, restart it once and replay the attempt."""
    try:
        return run_episode(holder[0], agent, *rest)
    except RuntimeError as e:
        print(f"env problem ({e}), restarting environment", flush=True)
        holder[0].close()
        holder[0] = Env()
        return run_episode(holder[0], agent, *rest)


def job(args):
    """One independent worker: trains one Q agent, then evaluates it and the random baseline."""
    run, n_train, n_eval, popups = args
    os.makedirs(PART_DIR, exist_ok=True)
    out = open(os.path.join(PART_DIR, f"job{run}.jsonl"), "w")
    holder = [Env()]  # list so safe_episode can swap in a fresh env
    try:
        # ----- training: popup/delay as in the task, goals cycle through all 12 in shuffled blocks
        agent = QAgent(seed=run)
        order_rng = random.Random(run)
        order = []
        for ep in range(n_train):
            if not order:
                order = GOALS[:]
                order_rng.shuffle(order)
            goal = order.pop()
            meta = {"episode": ep, "run": run, "phase": "train"}
            safe_episode(holder, agent, goal, 1000 * (run + 1) + ep, DEFAULT_POPUP, DELAY_P, meta, True, out)
        # ----- evaluation: seeds >= 100000 never appear in training (training seeds are < 100000)
        for popup_p in popups:
            for who in (agent, RandomAgent(seed=10_000 + run)):
                if who is agent and popup_p not in SWEEP_POPUPS:
                    continue
                if who is not agent and popup_p != DEFAULT_POPUP:
                    continue  # random baseline only needs the default setting
                for ep in range(n_eval):
                    # same seeds and goals for both agents so the comparison is paired
                    goal = GOALS[ep % 12]
                    meta = {"episode": ep, "run": run, "phase": "eval"}
                    if who is agent:
                        agent.start_episode(goal[0], goal[1], ep, False)
                    safe_episode(holder, who, goal, 100_000 + 1000 * run + ep, popup_p, DELAY_P, meta, None, out)
    finally:
        holder[0].close()
        out.close()
    return run


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--train-episodes", type=int, default=300)
    ap.add_argument("--eval-per-run", type=int, default=70)  # 3 runs x 70 = 210 attempts per condition
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--skip-build", action="store_true")
    ap.add_argument("--out", default=os.path.join(LOG_DIR, "run.jsonl"))
    a = ap.parse_args()
    t0 = time.time()
    if not a.skip_build:
        build()
    shutil.rmtree(PART_DIR, ignore_errors=True)
    jobs = [(r, a.train_episodes, a.eval_per_run, SWEEP_POPUPS) for r in range(a.runs)]
    with mp.Pool(a.runs) as pool:  # runs are independent, so they use separate browsers in parallel
        pool.map(job, jobs)
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    with open(a.out, "w") as merged:
        for part in sorted(glob.glob(os.path.join(PART_DIR, "job*.jsonl"))):
            with open(part) as f:
                shutil.copyfileobj(f, merged)
    shutil.rmtree(PART_DIR, ignore_errors=True)
    print(f"logs written to {a.out} in {time.time() - t0:.0f}s (including build)")
    subprocess.check_call([sys.executable, os.path.join(ROOT, "scripts", "analyze.py"), "--log", a.out])
    print(f"total {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
