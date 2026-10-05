# MiniShop RL report

Computed by `scripts/analyze.py` from `logs\run.jsonl`: 14378 step lines, 1740 attempts (900 training, 840 evaluation).

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
| 0.0 | 210 | 100.0% | 98.2% to 100.0% | 4.29 | 0.0% | 0.0% |
| 0.15 | 210 | 100.0% | 98.2% to 100.0% | 4.57 | 28.6% | 0.0% |
| 0.4 | 210 | 100.0% | 98.2% to 100.0% | 5.07 | 63.8% | 0.0% |

**Explanation (computed).** From popup_p=0.0 to popup_p=0.4 the success rate did not change from 100.0% to 100.0%; the two confidence intervals overlap, so the difference is not clearly more than noise. Mean steps per attempt rose from 4.29 to 5.07, consistent with each popup costing at least one extra step to dismiss (attempts that saw a popup: 0.0% then 63.8%). A failure only happens when these extra steps push the attempt past the 20 step limit or when the agent acts wrongly while a popup is showing; step-limit failures went from 0.0% to 0.0%.

![popup sweep](charts/popup_sweep.png)

## 4. Top failure reasons of the Q-learning agent

221 failed attempts out of 900 training (no evaluation failures) attempts. Reason is assigned by code from the last log line of each attempt.

### step_limit_on_product_screen: 55 attempts (24.9% of failures)

```json
{"episode": 8, "run": 0, "seed": 1008, "goal": "red-lamp x3", "step": 20, "observation": {"buttons": [{"clickable": true, "data_id": "", "i": 7, "text": "-"}, {"clickable": true, "data_id": "", "i": 8, "text": "+"}, {"clickable": true, "data_id": "", "i": 9, "text": "Add to cart"}, {"clickable": true, "data_id": "", "i": 10, "text": "Back"}], "goal": "red-lamp x3", "popup_showing": false, "screen": "product"}, "action": "click(8)", "action_key": "+", "reward": -0.01, "done": false, "truncated": true, "time_ms": 131, "cdp_ms": 92, "settle_ms": 45, "popup_showing": false, "agent": "qlearning", "phase": "train", "popup_p": 0.15, "delay_p": 0.1, "info": {"cart_item": "red-lamp", "cart_qty": 2, "current_qty": 2, "delay_pending": false, "viewing_item": "black-pen"}}
```
```json
{"episode": 10, "run": 0, "seed": 1010, "goal": "black-pen x1", "step": 20, "observation": {"buttons": [{"clickable": true, "data_id": "", "i": 7, "text": "-"}, {"clickable": true, "data_id": "", "i": 8, "text": "+"}, {"clickable": true, "data_id": "", "i": 9, "text": "Add to cart"}, {"clickable": true, "data_id": "", "i": 10, "text": "Back"}], "goal": "black-pen x1", "popup_showing": false, "screen": "product"}, "action": "click(10)", "action_key": "Back", "reward": -0.01, "done": false, "truncated": true, "time_ms": 58, "cdp_ms": 36, "settle_ms": 23, "popup_showing": false, "agent": "qlearning", "phase": "train", "popup_p": 0.15, "delay_p": 0.1, "info": {"cart_item": null, "cart_qty": 0, "current_qty": 1, "delay_pending": true, "viewing_item": "red-lamp"}}
```

### step_limit_on_catalog_screen: 47 attempts (21.3% of failures)

```json
{"episode": 0, "run": 0, "seed": 1000, "goal": "green-book x1", "step": 20, "observation": {"buttons": [{"clickable": true, "data_id": "blue-mug", "i": 1, "text": "View"}, {"clickable": true, "data_id": "red-lamp", "i": 2, "text": "View"}, {"clickable": true, "data_id": "green-book", "i": 3, "text": "View"}, {"clickable": true, "data_id": "black-pen", "i": 4, "text": "View"}, {"clickable": true, "data_id": "", "i": 5, "text": "Newsletter"}], "goal": "green-book x1", "popup_showing": false, "screen": "catalog"}, "action": "click(3)", "action_key": "View:goal", "reward": -0.01, "done": false, "truncated": true, "time_ms": 32, "cdp_ms": 9, "settle_ms": 22, "popup_showing": false, "agent": "qlearning", "phase": "train", "popup_p": 0.15, "delay_p": 0.1, "info": {"cart_item": null, "cart_qty": 0, "current_qty": 1, "delay_pending": false, "viewing_item": "green-book"}}
```
```json
{"episode": 7, "run": 0, "seed": 1007, "goal": "black-pen x2", "step": 20, "observation": {"buttons": [{"clickable": true, "data_id": "blue-mug", "i": 1, "text": "View"}, {"clickable": true, "data_id": "red-lamp", "i": 2, "text": "View"}, {"clickable": true, "data_id": "green-book", "i": 3, "text": "View"}, {"clickable": true, "data_id": "black-pen", "i": 4, "text": "View"}, {"clickable": true, "data_id": "", "i": 5, "text": "Newsletter"}], "goal": "black-pen x2", "popup_showing": false, "screen": "catalog"}, "action": "click(1)", "action_key": "View:other", "reward": -0.01, "done": false, "truncated": true, "time_ms": 51, "cdp_ms": 33, "settle_ms": 19, "popup_showing": false, "agent": "qlearning", "phase": "train", "popup_p": 0.15, "delay_p": 0.1, "info": {"cart_item": null, "cart_qty": 0, "current_qty": 1, "delay_pending": true, "viewing_item": "blue-mug"}}
```

### checked_out_empty_cart: 36 attempts (16.3% of failures)

```json
{"episode": 1, "run": 0, "seed": 1001, "goal": "black-pen x3", "step": 6, "observation": {"buttons": [{"clickable": true, "data_id": "", "i": 11, "text": "Checkout"}, {"clickable": true, "data_id": "", "i": 12, "text": "Clear cart"}, {"clickable": true, "data_id": "", "i": 13, "text": "Back"}], "goal": "black-pen x3", "popup_showing": false, "screen": "cart"}, "action": "click(11)", "action_key": "Checkout", "reward": -1.0, "done": true, "truncated": false, "time_ms": 30, "cdp_ms": 8, "settle_ms": 22, "popup_showing": false, "agent": "qlearning", "phase": "train", "popup_p": 0.15, "delay_p": 0.1, "info": {"cart_item": null, "cart_qty": 0, "current_qty": 1, "delay_pending": false, "order": {"item": null, "qty": 0, "success": false}, "viewing_item": "black-pen"}}
```
```json
{"episode": 2, "run": 0, "seed": 1002, "goal": "blue-mug x1", "step": 14, "observation": {"buttons": [{"clickable": true, "data_id": "", "i": 11, "text": "Checkout"}, {"clickable": true, "data_id": "", "i": 12, "text": "Clear cart"}, {"clickable": true, "data_id": "", "i": 13, "text": "Back"}], "goal": "blue-mug x1", "popup_showing": false, "screen": "cart"}, "action": "click(11)", "action_key": "Checkout", "reward": -1.0, "done": true, "truncated": false, "time_ms": 33, "cdp_ms": 12, "settle_ms": 22, "popup_showing": false, "agent": "qlearning", "phase": "train", "popup_p": 0.15, "delay_p": 0.1, "info": {"cart_item": null, "cart_qty": 0, "current_qty": 1, "delay_pending": false, "order": {"item": null, "qty": 0, "success": false}, "viewing_item": "black-pen"}}
```

## 5. Step latency

All 14378 steps: median 44 ms, p95 130 ms.

| part | median ms | p95 ms | share of total time |
|---|---|---|---|
| CDP calls | 12 | 73 | 34.8% |
| settle polling | 25 | 50 | 46.1% |
| other (wait sleep, overhead) | 1 | 69 | 19.0% |

| action | steps | median ms | p95 ms |
|---|---|---|---|
| click | 11428 | 40 | 112 |
| wait | 2950 | 99 | 150 |

![latency](charts/latency.png)

## One thing that surprised me

> Placeholder generated from the data by `scripts/analyze.py`. To be rewritten in my own words.

- Wait actions are 20.5% of all steps but 35.8% of all step time.
- A trained Q-learning attempt uses 0.29 wait actions on average.
- Successful Q-learning attempts took 4.57 steps on average; successful random attempts took 10.67.
- The random agent's most common failure was `wrong_item_ordered` (64 of 210 attempts).

