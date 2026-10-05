"""Reads ONLY the JSON-lines log and writes report.md and PNG charts. Nothing here is typed in by hand:
every number and every sentence is computed from the log."""
import argparse
import json
import math
import os
from collections import Counter, defaultdict

import matplotlib
matplotlib.use("Agg")  # no display needed, also on CI
import matplotlib.pyplot as plt
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_P = 0.15  # the task's own popup setting


def wilson(k, n, z=1.96):
    """95% Wilson score interval for k successes out of n attempts."""
    if n == 0:
        return 0.0, 0.0, 0.0
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    # clamp: rounding can push the bounds a hair past p when p is 0 or 1
    return p, max(0.0, min(p, c - h)), min(1.0, max(p, c + h))


def pct(x):
    return f"{100 * x:.1f}%"


def load(path):
    """Returns list of (parsed record, raw line)."""
    rows = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append((json.loads(line), line))
    return rows


def build_episodes(rows):
    """Group step lines into attempts. The key identifies one attempt uniquely."""
    groups = defaultdict(list)
    for rec, raw in rows:
        key = (rec["phase"], rec["agent"], rec["run"], rec["popup_p"], rec["episode"])
        groups[key].append((rec, raw))
    eps = []
    for key, steps in groups.items():
        steps.sort(key=lambda s: s[0]["step"])
        last, last_raw = steps[-1]
        order = last["info"].get("order")
        eps.append({
            "phase": key[0], "agent": key[1], "run": key[2], "popup_p": key[3], "episode": key[4],
            "goal": last["goal"], "seed": last["seed"], "steps": len(steps),
            "success": bool(order and order.get("success")),
            "order": order, "truncated": last["truncated"], "error": last["info"].get("error"),
            "last_screen": last["observation"]["screen"], "last_raw": last_raw, "last": last,
            "popup_steps": sum(1 for s, _ in steps if s["popup_showing"]),
            "any_popup": any(s["popup_showing"] for s, _ in steps),
            "waits": sum(1 for s, _ in steps if s["action"] == "wait"),
            "reward": sum(s["reward"] for s, _ in steps),
        })
    return eps


def failure_reason(ep):
    """Category of a failed attempt, decided by code from the final log line."""
    if ep["error"]:
        return "environment_error"
    o = ep["order"]
    if o is not None:
        item = ep["goal"].split(" x")[0]
        qty = int(ep["goal"].split(" x")[1])
        if o["item"] is None:
            return "checked_out_empty_cart"
        if o["item"] != item:
            return "wrong_item_ordered"
        if o["qty"] != qty:
            return "wrong_quantity_ordered"
    return f"step_limit_on_{ep['last_screen']}_screen"


def rate_row(eps):
    k = sum(e["success"] for e in eps)
    p, lo, hi = wilson(k, len(eps))
    return k, len(eps), p, lo, hi


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--log", default=os.path.join(ROOT, "logs", "run.jsonl"))
    ap.add_argument("--report", default=os.path.join(ROOT, "report.md"))
    ap.add_argument("--charts", default=os.path.join(ROOT, "charts"))
    a = ap.parse_args()
    os.makedirs(a.charts, exist_ok=True)

    rows = load(a.log)
    eps = build_episodes(rows)
    steps = [r for r, _ in rows]
    ev = [e for e in eps if e["phase"] == "eval"]
    tr = [e for e in eps if e["phase"] == "train"]
    md = []

    md.append("# MiniShop RL report\n")
    md.append(f"Computed by `scripts/analyze.py` from `{os.path.relpath(a.log, ROOT)}`: "
              f"{len(rows)} step lines, {len(eps)} attempts ({len(tr)} training, {len(ev)} evaluation).\n")

    # ---------- 1. success rates ----------
    md.append("## 1. Success rate of both agents\n")
    md.append(f"Evaluation attempts on unseen seeds, popup_p={DEFAULT_P}, "
              f"delay_p={ev[0]['last']['delay_p'] if ev else 'n/a'}. 95% Wilson confidence interval.\n")
    md.append("| agent | successes | attempts | success rate | 95% CI |\n|---|---|---|---|---|")
    main_rows = {}
    for ag in ("random", "qlearning"):
        sub = [e for e in ev if e["agent"] == ag and e["popup_p"] == DEFAULT_P]
        if not sub:
            continue
        k, n, p, lo, hi = rate_row(sub)
        main_rows[ag] = (p, lo, hi)
        md.append(f"| {ag} | {k} | {n} | {pct(p)} | {pct(lo)} to {pct(hi)} |")
    md.append("")
    if len(main_rows) == 2:
        r, q = main_rows["random"], main_rows["qlearning"]
        verdict = ("do not overlap" if q[1] > r[2] or r[1] > q[2] else "overlap")
        md.append(f"The two confidence intervals {verdict}.\n")
        fig, ax = plt.subplots(figsize=(4.5, 3.5))
        names = list(main_rows)
        vals = [main_rows[n][0] for n in names]
        err = [[main_rows[n][0] - main_rows[n][1] for n in names], [main_rows[n][2] - main_rows[n][0] for n in names]]
        ax.bar(names, vals, yerr=err, capsize=5, color=["#9aa5b1", "#2b7a78"])
        ax.set_ylim(0, 1)
        ax.set_ylabel("success rate")
        ax.set_title("Success rate (95% Wilson CI)")
        fig.tight_layout()
        fig.savefig(os.path.join(a.charts, "success_rates.png"), dpi=120)
        plt.close(fig)
        md.append("![success rates](charts/success_rates.png)\n")

    # ---------- 2. training curve ----------
    md.append("## 2. Training curve\n")
    q_tr = [e for e in tr if e["agent"] == "qlearning"]
    runs = sorted({e["run"] for e in q_tr})
    if q_tr:
        n_ep = max(e["episode"] for e in q_tr) + 1
        bin_size = max(1, n_ep // 20)  # about 20 points on the curve
        curves = []
        for r in runs:
            by_ep = {e["episode"]: e["success"] for e in q_tr if e["run"] == r}
            curves.append([np.mean([by_ep[i] for i in range(b, min(b + bin_size, n_ep)) if i in by_ep])
                           for b in range(0, n_ep, bin_size)])
        arr = np.array(curves)
        xs = [b + bin_size for b in range(0, n_ep, bin_size)]
        fig, ax = plt.subplots(figsize=(6, 3.5))
        ax.plot(xs, arr.mean(axis=0), color="#2b7a78", label=f"mean of {len(runs)} runs")
        ax.fill_between(xs, arr.min(axis=0), arr.max(axis=0), alpha=0.25, color="#2b7a78", label="min to max")
        ax.set_xlabel("training episode")
        ax.set_ylabel(f"success rate (bins of {bin_size})")
        ax.set_ylim(0, 1)
        ax.legend()
        ax.set_title("Q-learning training curve (exploring, popup_p=0.15)")
        fig.tight_layout()
        fig.savefig(os.path.join(a.charts, "training_curve.png"), dpi=120)
        plt.close(fig)
        m = arr.mean(axis=0)
        md.append(f"{len(runs)} independent training runs with different seeds, {n_ep} episodes each, "
                  f"success averaged over bins of {bin_size} episodes (training includes exploration).\n")
        md.append(f"Mean success in the first bin: {pct(m[0])}; in the last bin: {pct(m[-1])} "
                  f"(last bin range over runs: {pct(arr[:, -1].min())} to {pct(arr[:, -1].max())}).\n")
        md.append("![training curve](charts/training_curve.png)\n")

    # ---------- 3. popup sweep ----------
    md.append("## 3. Popup probability sweep (Q-learning agent)\n")
    sweep = {}
    for p in sorted({e["popup_p"] for e in ev if e["agent"] == "qlearning"}):
        sub = [e for e in ev if e["agent"] == "qlearning" and e["popup_p"] == p]
        k, n, rate, lo, hi = rate_row(sub)
        sweep[p] = {"n": n, "rate": rate, "lo": lo, "hi": hi,
                    "mean_steps": np.mean([e["steps"] for e in sub]),
                    "mean_waits": np.mean([e["waits"] for e in sub]),
                    "popup_share": np.mean([e["any_popup"] for e in sub]),
                    "limit_share": np.mean([e["truncated"] and not e["order"] for e in sub]),
                    "mean_popup_steps": np.mean([e["popup_steps"] for e in sub])}
    md.append("| popup_p | attempts | success rate | 95% CI | mean steps | attempts that saw a popup | step-limit failures |\n|---|---|---|---|---|---|---|")
    for p, s in sweep.items():
        md.append(f"| {p} | {s['n']} | {pct(s['rate'])} | {pct(s['lo'])} to {pct(s['hi'])} | "
                  f"{s['mean_steps']:.2f} | {pct(s['popup_share'])} | {pct(s['limit_share'])} |")
    md.append("")
    if len(sweep) >= 2:
        ps = list(sweep)
        lo_p, hi_p = ps[0], ps[-1]
        s0, s1 = sweep[lo_p], sweep[hi_p]
        change = s1["rate"] - s0["rate"]
        overlap = not (s1["hi"] < s0["lo"] or s0["hi"] < s1["lo"])
        word = "fell" if change < 0 else "rose" if change > 0 else "did not change"
        steps_word = "rose" if s1["mean_steps"] > s0["mean_steps"] else "did not rise"
        md.append(f"**Explanation (computed).** From popup_p={lo_p} to popup_p={hi_p} the success rate {word} "
                  f"from {pct(s0['rate'])} to {pct(s1['rate'])}; the two confidence intervals "
                  f"{'overlap, so the difference is not clearly more than noise' if overlap else 'do not overlap'}. "
                  f"Mean steps per attempt {steps_word} from {s0['mean_steps']:.2f} to {s1['mean_steps']:.2f}"
                  f"{', consistent with each popup costing at least one extra step to dismiss' if s1['mean_steps'] > s0['mean_steps'] else ''} "
                  f"(attempts that saw a popup: {pct(s0['popup_share'])} then {pct(s1['popup_share'])}). "
                  f"A failure only happens when these extra steps push the attempt past the 20 step limit "
                  f"or when the agent acts wrongly while a popup is showing; step-limit failures went from "
                  f"{pct(s0['limit_share'])} to {pct(s1['limit_share'])}.\n")
        fig, ax = plt.subplots(figsize=(5, 3.5))
        x = list(sweep)
        y = [sweep[p]["rate"] for p in x]
        err = [[sweep[p]["rate"] - sweep[p]["lo"] for p in x], [sweep[p]["hi"] - sweep[p]["rate"] for p in x]]
        ax.errorbar(x, y, yerr=err, marker="o", capsize=5, color="#2b7a78")
        ax.set_ylim(0, 1.05)
        ax.set_xlabel("popup_p")
        ax.set_ylabel("success rate")
        ax.set_title("Q-learning success vs popup probability")
        fig.tight_layout()
        fig.savefig(os.path.join(a.charts, "popup_sweep.png"), dpi=120)
        plt.close(fig)
        md.append("![popup sweep](charts/popup_sweep.png)\n")

    # ---------- 4. failures ----------
    md.append("## 4. Top failure reasons of the Q-learning agent\n")
    # all evaluation attempts of the learning agent, every popup_p; if it never failed, fall back
    # to its training attempts (clearly labelled) so there is still something to study
    pool, label = [e for e in ev if e["agent"] == "qlearning"], "evaluation"
    fails = [e for e in pool if not e["success"]]
    if not fails:
        pool, label = [e for e in tr if e["agent"] == "qlearning"], "training (no evaluation failures)"
        fails = [e for e in pool if not e["success"]]
    md.append(f"{len(fails)} failed attempts out of {len(pool)} {label} attempts. "
              "Reason is assigned by code from the last log line of each attempt.\n")
    cats = Counter(failure_reason(e) for e in fails)
    for reason, count in cats.most_common(3):
        md.append(f"### {reason}: {count} attempts ({pct(count / max(1, len(fails)))} of failures)\n")
        ex = [e for e in fails if failure_reason(e) == reason][:2]
        for e in ex:
            md.append("```json\n" + e["last_raw"] + "\n```")
        md.append("")
    if not fails:
        md.append("No failed attempts in this log.\n")

    # ---------- 5. latency ----------
    md.append("## 5. Step latency\n")
    t = np.array([s["time_ms"] for s in steps], dtype=float)
    cdp = np.array([s["cdp_ms"] for s in steps], dtype=float)
    settle = np.array([s["settle_ms"] for s in steps], dtype=float)
    other = t - cdp - settle  # time outside CDP calls and settling: process pipe, python side of the pause, wait sleeps
    md.append(f"All {len(steps)} steps: median {np.median(t):.0f} ms, p95 {np.percentile(t, 95):.0f} ms.\n")
    md.append("| part | median ms | p95 ms | share of total time |\n|---|---|---|---|")
    for name, arr in (("CDP calls", cdp), ("settle polling", settle), ("other (wait sleep, overhead)", other)):
        md.append(f"| {name} | {np.median(arr):.0f} | {np.percentile(arr, 95):.0f} | {pct(arr.sum() / t.sum())} |")
    md.append("")
    kinds = {"click": [s for s in steps if s["action"].startswith("click")],
             "wait": [s for s in steps if s["action"] == "wait"]}
    md.append("| action | steps | median ms | p95 ms |\n|---|---|---|---|")
    for k, v in kinds.items():
        if v:
            tt = np.array([s["time_ms"] for s in v])
            md.append(f"| {k} | {len(v)} | {np.median(tt):.0f} | {np.percentile(tt, 95):.0f} |")
    md.append("")
    fig, ax = plt.subplots(figsize=(5, 3.5))
    parts = [cdp.mean(), settle.mean(), other.mean()]
    ax.bar(["CDP calls", "settle polling", "other"], parts, color=["#2b7a78", "#9aa5b1", "#d9a441"])
    ax.set_ylabel("mean ms per step")
    ax.set_title("Where step time goes")
    fig.tight_layout()
    fig.savefig(os.path.join(a.charts, "latency.png"), dpi=120)
    plt.close(fig)
    md.append("![latency](charts/latency.png)\n")

    # ---------- 6. surprise (computed observations, to be rewritten by hand) ----------
    md.append("## One thing that surprised me\n")
    md.append("> Placeholder generated from the data by `scripts/analyze.py`. To be rewritten in my own words.\n")
    q_ev = [e for e in ev if e["agent"] == "qlearning" and e["popup_p"] == DEFAULT_P]
    r_ev = [e for e in ev if e["agent"] == "random" and e["popup_p"] == DEFAULT_P]
    if q_ev:
        wait_steps = [s for s in steps if s["action"] == "wait"]
        wait_share_steps = len(wait_steps) / len(steps)
        wait_share_time = sum(s["time_ms"] for s in wait_steps) / t.sum()
        md.append(f"- Wait actions are {pct(wait_share_steps)} of all steps but {pct(wait_share_time)} of all step time.")
        q_waits = np.mean([e["waits"] for e in q_ev])
        md.append(f"- A trained Q-learning attempt uses {q_waits:.2f} wait actions on average.")
    if q_ev and r_ev:
        succ_q = [e["steps"] for e in q_ev if e["success"]]
        succ_r = [e["steps"] for e in r_ev if e["success"]]
        if succ_q:
            md.append(f"- Successful Q-learning attempts took {np.mean(succ_q):.2f} steps on average"
                      + (f"; successful random attempts took {np.mean(succ_r):.2f}." if succ_r else "; the random agent never succeeded."))
        if r_ev:
            r_wrong = Counter(failure_reason(e) for e in r_ev if not e["success"])
            if r_wrong:
                name, c = r_wrong.most_common(1)[0]
                md.append(f"- The random agent's most common failure was `{name}` ({c} of {len(r_ev)} attempts).")
    md.append("")

    with open(a.report, "w") as f:
        f.write("\n".join(md) + "\n")
    print(f"wrote {a.report}")


if __name__ == "__main__":
    main()
