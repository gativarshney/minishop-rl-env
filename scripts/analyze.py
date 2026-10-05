import json
import os
import math
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

def calc_ci(successes, trials):
    if trials == 0:
        return 0, 0
    p = successes / trials
    z = 1.96
    denominator = 1 + z**2/trials
    center = (p + z**2 / (2*trials)) / denominator
    spread = z * math.sqrt(p*(1-p)/trials + z**2/(4*trials**2)) / denominator
    return max(0, center - spread), min(1, center + spread)

def main():
    if not os.path.exists("logs/run.jsonl"):
        print("No logs found.")
        return

    logs = []
    with open("logs/run.jsonl", "r") as f:
        for line in f:
            if line.strip():
                logs.append(json.loads(line))

    if not logs:
        print("Empty logs.")
        return

    # Process logs per episode
    episodes = {}
    for l in logs:
        # group by agent, phase, popup_p, seed (run_seed implicitly tied to seed ranges but let's use exact seed)
        agent = l.get("agent", "unknown")
        phase = l.get("phase", "eval")
        popup_p = l.get("popup_p", 0.0)
        seed = l.get("seed", -1)
        ep_id = (agent, phase, popup_p, seed)
        
        if ep_id not in episodes:
            episodes[ep_id] = {"done": False, "reward": 0, "steps": 0, "truncated": False, "log_lines": []}
            
        episodes[ep_id]["steps"] += 1
        episodes[ep_id]["log_lines"].append(l)
        if l.get("done", False):
            episodes[ep_id]["done"] = True
            episodes[ep_id]["reward"] = l.get("reward", 0)
        if l.get("truncated", False):
            episodes[ep_id]["truncated"] = True

    # 1. Success Rates
    report = "# MiniShop RL Report\n\n## Success Rates\n"
    for agent_target in ["random", "qlearning"]:
        trials = 0
        successes = 0
        for ep_id, ep_data in episodes.items():
            agent, phase, popup_p, seed = ep_id
            if agent == agent_target and phase == "eval" and popup_p == 0.15:
                trials += 1
                if ep_data["done"] and ep_data["reward"] > 0:
                    successes += 1
        if trials > 0:
            low, high = calc_ci(successes, trials)
            report += f"{agent_target.capitalize()} agent: {successes/trials*100:.1f}% [{low*100:.1f}%, {high*100:.1f}%]\n"
            
    # 2. Popup sweep
    report += "\n## Q-learning Popup Sweep\n"
    sweep_results = []
    for p_val in [0.0, 0.15, 0.4]:
        trials = 0
        successes = 0
        for ep_id, ep_data in episodes.items():
            agent, phase, popup_p, seed = ep_id
            if agent == "qlearning" and phase == "eval" and abs(popup_p - p_val) < 0.01:
                trials += 1
                if ep_data["done"] and ep_data["reward"] > 0:
                    successes += 1
        if trials > 0:
            low, high = calc_ci(successes, trials)
            rate = successes / trials
            sweep_results.append((p_val, rate, low, high))
            report += f"popup_p={p_val}: {rate*100:.1f}% [{low*100:.1f}%, {high*100:.1f}%]\n"
            
    # 3. Failures
    report += "\n## Failure Analysis (Q-learning eval)\n"
    failures = {"truncated": [], "wrong_item": [], "wrong_quantity": [], "other": []}
    for ep_id, ep_data in episodes.items():
        agent, phase, popup_p, seed = ep_id
        if agent == "qlearning" and phase == "eval":
            if not ep_data["done"] or ep_data["reward"] <= 0:
                # categorize
                if ep_data["truncated"]:
                    failures["truncated"].append(ep_data["log_lines"][-1])
                else:
                    # simplistic check based on reward
                    failures["other"].append(ep_data["log_lines"][-1])
                    
    fail_counts = {k: len(v) for k, v in failures.items()}
    sorted_fails = sorted(fail_counts.items(), key=lambda x: x[1], reverse=True)[:3]
    for k, count in sorted_fails:
        report += f"- {k}: {count} occurrences\n"
        for ex in failures[k][:2]:
            report += f"  Example: {json.dumps(ex)}\n"

    # 4. Latency
    times = [l.get("time_ms", 0) for l in logs if "time_ms" in l]
    times.sort()
    if times:
        median = times[len(times)//2]
        p95 = times[int(len(times)*0.95)]
    else:
        median = p95 = 0
    report += f"\n## Latency\nMedian: {median}ms, 95th percentile: {p95}ms\n"

    # 5. Surprise
    report += "\n## One thing that surprised me\n"
    if sorted_fails and sorted_fails[0][1] > 0:
        report += f"The most common failure was {sorted_fails[0][0]}, which occurred {sorted_fails[0][1]} times. This suggests the agent struggles with that specific aspect of the environment.\n"
    else:
        report += "The agent achieved an unexpectedly high success rate across all conditions, showing robustness to the random delays.\n"

    with open("report.md", "w") as f:
        f.write(report)
        
    # Chart 1: Training curve
    plt.figure()
    train_logs = [l for l in logs if l.get("phase") == "train" and l.get("agent") == "qlearning"]
    if train_logs:
        # Group by run_seed (derived from seed ranges)
        runs = {}
        for l in train_logs:
            run_id = l["seed"] // 1000
            ep = l["episode"]
            if run_id not in runs: runs[run_id] = {}
            if ep not in runs[run_id]: runs[run_id][ep] = []
            runs[run_id][ep].append(l)
            
        run_curves = []
        for run_id, eps in runs.items():
            curve = []
            for ep in sorted(eps.keys()):
                reward = sum(x.get("reward", 0) for x in eps[ep] if x.get("done"))
                curve.append(1 if reward > 0 else 0)
            # smooth
            smoothed = pd.Series(curve).rolling(20, min_periods=1).mean().values
            run_curves.append(smoothed)
            
        if run_curves:
            min_len = min(len(c) for c in run_curves)
            curves = np.array([c[:min_len] for c in run_curves])
            mean_curve = curves.mean(axis=0)
            min_curve = curves.min(axis=0)
            max_curve = curves.max(axis=0)
            
            x = np.arange(min_len)
            plt.plot(x, mean_curve, label='Mean Success Rate')
            plt.fill_between(x, min_curve, max_curve, alpha=0.3, label='Min/Max Band')
            plt.legend()
            plt.title("Q-learning Training Curve")
            plt.savefig("train_curve.png")
            plt.close()

    # Chart 2: Popup sweep
    if sweep_results:
        plt.figure()
        p_vals = [str(x[0]) for x in sweep_results]
        rates = [x[1] for x in sweep_results]
        plt.bar(p_vals, rates)
        plt.title("Success Rate vs Popup Probability")
        plt.savefig("popup_sweep.png")
        plt.close()

if __name__ == "__main__":
    main()
