# MiniShop RL report

Computed by `scripts/analyze.py` from `logs\run.jsonl`: 14278 step lines, 1740 attempts (900 training, 840 evaluation).

## 1. Success rate of both agents

Evaluation attempts on unseen seeds, popup_p=0.15, delay_p=0.1. 95% Wilson confidence interval.

| agent | successes | attempts | success rate | 95% CI |
|---|---|---|---|---|
| random | 6 | 210 | 2.9% | 1.3% to 6.1% |
| qlearning | 210 | 210 | 100.0% | 98.2% to 100.0% |

The two confidence intervals do not overlap.

![success rates](charts/success_rates.png)

## 2. Training curve

3 independent training runs with different seeds, 300 episodes each, success averaged over bins of 15 episodes (training includes exploration).

Mean success in the first bin: 2.2%; in the last bin: 100.0% (last bin range over runs: 100.0% to 100.0%).

![training curve](charts/training_curve.png)

## 3. Popup probability sweep (Q-learning agent)

| popup_p | attempts | success rate | 95% CI | mean steps | attempts that saw a popup | step-limit failures |
|---|---|---|---|---|---|---|
| 0.0 | 210 | 100.0% | 98.2% to 100.0% | 4.31 | 0.0% | 0.0% |
| 0.15 | 210 | 100.0% | 98.2% to 100.0% | 4.58 | 28.6% | 0.0% |
| 0.4 | 210 | 100.0% | 98.2% to 100.0% | 5.11 | 63.8% | 0.0% |

**Explanation (computed).** From popup_p=0.0 to popup_p=0.4 the success rate did not change from 100.0% to 100.0%; the two confidence intervals overlap, so the difference is not clearly more than noise. Mean steps per attempt rose from 4.31 to 5.11, consistent with each popup costing at least one extra step to dismiss (attempts that saw a popup: 0.0% then 63.8%). A failure only happens when these extra steps push the attempt past the 20 step limit or when the agent acts wrongly while a popup is showing; step-limit failures went from 0.0% to 0.0%.

![popup sweep](charts/popup_sweep.png)

## 4. Top failure reasons of the Q-learning agent

240 failed attempts out of 900 training (no evaluation failures) attempts. Reason is assigned by code from the last log line of each attempt.

### step_limit_on_product_screen: 65 attempts (27.1% of failures)

```json
{"episode": 8, "run": 0, "seed": 1008, "goal": "red-lamp x3", "step": 20, "observation": {"buttons": [{"clickable": true, "data_id": "", "i": 7, "text": "-"}, {"clickable": true, "data_id": "", "i": 8, "text": "+"}, {"clickable": true, "data_id": "", "i": 9, "text": "Add to cart"}, {"clickable": true, "data_id": "", "i": 10, "text": "Back"}], "goal": "red-lamp x3", "popup_showing": false, "screen": "product"}, "action": "click(8)", "action_key": "+", "reward": -0.01, "done": false, "truncated": true, "time_ms": 47, "cdp_ms": 15, "settle_ms": 31, "popup_showing": false, "agent": "qlearning", "phase": "train", "popup_p": 0.15, "delay_p": 0.1, "info": {"cart_item": "red-lamp", "cart_qty": 2, "current_qty": 2, "delay_pending": false, "viewing_item": "black-pen"}}
```
```json
{"episode": 10, "run": 0, "seed": 1010, "goal": "black-pen x1", "step": 20, "observation": {"buttons": [{"clickable": true, "data_id": "", "i": 7, "text": "-"}, {"clickable": true, "data_id": "", "i": 8, "text": "+"}, {"clickable": true, "data_id": "", "i": 9, "text": "Add to cart"}, {"clickable": true, "data_id": "", "i": 10, "text": "Back"}], "goal": "black-pen x1", "popup_showing": false, "screen": "product"}, "action": "click(10)", "action_key": "Back", "reward": -0.01, "done": false, "truncated": true, "time_ms": 50, "cdp_ms": 19, "settle_ms": 30, "popup_showing": false, "agent": "qlearning", "phase": "train", "popup_p": 0.15, "delay_p": 0.1, "info": {"cart_item": null, "cart_qty": 0, "current_qty": 1, "delay_pending": true, "viewing_item": "red-lamp"}}
```

### step_limit_on_catalog_screen: 44 attempts (18.3% of failures)

```json
{"episode": 0, "run": 0, "seed": 1000, "goal": "green-book x1", "step": 20, "observation": {"buttons": [{"clickable": true, "data_id": "blue-mug", "i": 1, "text": "View"}, {"clickable": true, "data_id": "red-lamp", "i": 2, "text": "View"}, {"clickable": true, "data_id": "green-book", "i": 3, "text": "View"}, {"clickable": true, "data_id": "black-pen", "i": 4, "text": "View"}, {"clickable": true, "data_id": "", "i": 5, "text": "Newsletter"}], "goal": "green-book x1", "popup_showing": false, "screen": "catalog"}, "action": "click(3)", "action_key": "View:goal", "reward": -0.01, "done": false, "truncated": true, "time_ms": 45, "cdp_ms": 14, "settle_ms": 29, "popup_showing": false, "agent": "qlearning", "phase": "train", "popup_p": 0.15, "delay_p": 0.1, "info": {"cart_item": null, "cart_qty": 0, "current_qty": 1, "delay_pending": false, "viewing_item": "green-book"}}
```
```json
{"episode": 7, "run": 0, "seed": 1007, "goal": "black-pen x2", "step": 20, "observation": {"buttons": [{"clickable": true, "data_id": "blue-mug", "i": 1, "text": "View"}, {"clickable": true, "data_id": "red-lamp", "i": 2, "text": "View"}, {"clickable": true, "data_id": "green-book", "i": 3, "text": "View"}, {"clickable": true, "data_id": "black-pen", "i": 4, "text": "View"}, {"clickable": true, "data_id": "", "i": 5, "text": "Newsletter"}], "goal": "black-pen x2", "popup_showing": false, "screen": "catalog"}, "action": "click(1)", "action_key": "View:other", "reward": -0.01, "done": false, "truncated": true, "time_ms": 29, "cdp_ms": 4, "settle_ms": 24, "popup_showing": false, "agent": "qlearning", "phase": "train", "popup_p": 0.15, "delay_p": 0.1, "info": {"cart_item": null, "cart_qty": 0, "current_qty": 1, "delay_pending": true, "viewing_item": "blue-mug"}}
```

### checked_out_empty_cart: 34 attempts (14.2% of failures)

```json
{"episode": 1, "run": 0, "seed": 1001, "goal": "black-pen x3", "step": 6, "observation": {"buttons": [{"clickable": true, "data_id": "", "i": 11, "text": "Checkout"}, {"clickable": true, "data_id": "", "i": 12, "text": "Clear cart"}, {"clickable": true, "data_id": "", "i": 13, "text": "Back"}], "goal": "black-pen x3", "popup_showing": false, "screen": "cart"}, "action": "click(11)", "action_key": "Checkout", "reward": -1.0, "done": true, "truncated": false, "time_ms": 31, "cdp_ms": 9, "settle_ms": 21, "popup_showing": false, "agent": "qlearning", "phase": "train", "popup_p": 0.15, "delay_p": 0.1, "info": {"cart_item": null, "cart_qty": 0, "current_qty": 1, "delay_pending": false, "order": {"item": null, "qty": 0, "success": false}, "viewing_item": "black-pen"}}
```
```json
{"episode": 2, "run": 0, "seed": 1002, "goal": "blue-mug x1", "step": 14, "observation": {"buttons": [{"clickable": true, "data_id": "", "i": 11, "text": "Checkout"}, {"clickable": true, "data_id": "", "i": 12, "text": "Clear cart"}, {"clickable": true, "data_id": "", "i": 13, "text": "Back"}], "goal": "blue-mug x1", "popup_showing": false, "screen": "cart"}, "action": "click(11)", "action_key": "Checkout", "reward": -1.0, "done": true, "truncated": false, "time_ms": 29, "cdp_ms": 9, "settle_ms": 19, "popup_showing": false, "agent": "qlearning", "phase": "train", "popup_p": 0.15, "delay_p": 0.1, "info": {"cart_item": null, "cart_qty": 0, "current_qty": 1, "delay_pending": false, "order": {"item": null, "qty": 0, "success": false}, "viewing_item": "black-pen"}}
```

## 5. Step latency

All 14278 steps: median 43 ms, p95 115 ms.

| part | median ms | p95 ms | share of total time |
|---|---|---|---|
| CDP calls | 11 | 57 | 30.7% |
| settle polling | 25 | 40 | 46.7% |
| other (wait sleep, overhead) | 1 | 70 | 22.6% |

| action | steps | median ms | p95 ms |
|---|---|---|---|
| click | 11321 | 39 | 88 |
| wait | 2957 | 99 | 142 |

![latency](charts/latency.png)

## One thing that surprised me

> Placeholder generated from the data by `scripts/analyze.py`. To be rewritten in my own words.

- Wait actions are 20.7% of all steps but 37.9% of all step time.
- A trained Q-learning attempt uses 0.30 wait actions on average.
- Successful Q-learning attempts took 4.58 steps on average; successful random attempts took 13.00.
- The random agent's most common failure was `wrong_item_ordered` (66 of 210 attempts).

