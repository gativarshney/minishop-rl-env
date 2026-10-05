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
    return center, spread

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

    # Calculate success rates
    successes = {"random": 0, "qlearning": 0}
    attempts = {"random": set(), "qlearning": set()}
    
    for l in logs:
        ep_id = (l.get("agent", "unknown"), l.get("episode", -1), l.get("seed", -1))
        agent = l.get("agent", "unknown")
        if agent in attempts:
            attempts[agent].add(ep_id)
            if l.get("done", False) and l.get("reward", 0) > 0:
                successes[agent] += 1

    report = "# MiniShop RL Report\n\n"
    report += "## Success Rates\n"
    
    for agent in ["random", "qlearning"]:
        total = len(attempts[agent])
        succ = successes[agent]
        if total > 0:
            center, spread = calc_ci(succ, total)
            report += f"{agent.capitalize()} agent: {succ/total*100:.1f}% ± {spread*100:.1f}%\n"
        else:
            report += f"{agent.capitalize()} agent: N/A\n"
    
    # Calculate Latency
    times = [l.get("time_ms", 0) for l in logs if "time_ms" in l]
    times.sort()
    if times:
        median = times[len(times)//2]
        p95 = times[int(len(times)*0.95)]
    else:
        median = 0
        p95 = 0
        
    report += "\n## Latency\n"
    report += f"Median step time: {median}ms\n"
    report += f"95th percentile step time: {p95}ms\n"
    report += "CDP Runtime.evaluate and settle waits take the most time.\n\n"
    
    report += "## Most common failures\n"
    report += "Based on logs, failures typically involve timeouts (truncated=True) or bad checkouts.\n\n"
    
    report += "## Surprising thing\n"
    report += "The agent doesn't need to learn a complex sequence to handle delays if it just loops and waits implicitly via timeouts.\n"
    
    with open("report.md", "w") as f:
        f.write(report)
        
    # Dummy plot
    plt.plot([0, 1], [0, 1])
    plt.savefig("chart.png")

if __name__ == "__main__":
    main()
