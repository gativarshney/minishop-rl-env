# Decisions

## State (Q-learning agent)
A tuple relative to the goal, so one table serves all 12 goals: screen, popup showing, any button ready (clickable), quantity below/equal/above the goal (the cart quantity on the cart screen, the selector quantity elsewhere), cart item empty/matches/other, viewed product is the goal item or not, and whether a clickable "View" button belongs to the goal item. The quantity, cart and viewed product come from the page's `window.__state`, returned in `info`. The goal itself is not in the state, only how the page compares to it.

## Actions
Click or wait. For the learner, an action is named by button text ("Add to cart", "+", "Dismiss" ...). "View" buttons are named `View:goal` or `View:other` (by product, relative to the goal) so the knowledge transfers between goals. Only clickable buttons plus `wait` are offered. The random agent picks uniformly from the clickable buttons plus wait.

## Reward
-0.01 per step (shorter paths are better), +1 when the page reports the right item and quantity, -1 when an order is placed with the wrong content. The page's own `window.__orderResult` is the only truth. No other shaping.

## When an attempt ends
`done` when an order is placed (right or wrong). `truncated` after 20 steps, or when a CDP call times out or the browser dies (the browser is then relaunched on the next reset). A truncated attempt still bootstraps in Q-learning, a done attempt does not.

## Environment choices
- One browser is reused across attempts; each reset goes to about:blank and then to the goal URL.
- After every action the env polls the page until two reads in a row match (at most 150 ms). Delayed buttons (up to 300 ms) can still be hidden, so the agent must `wait`.
- Clicks are real `Input.dispatchMouseEvent` events at the button centre. A click on a covered or hidden button is still sent and simply does nothing, like for a user.
- Cleanup: Linux uses its own process group and parent-death signal, Windows uses a Job Object with kill-on-close (taskkill as fallback). Verified by killing the env process hard and counting browsers with our profile dir.

## Evaluation
Training: 3 runs with different seeds, 300 attempts each, popup_p 0.15, delay_p 0.10, goals in shuffled blocks of 12. Evaluation seeds start at 100000, training seeds are below that. The Q agent is evaluated greedily (no learning) with 70 attempts per run, 210 total per condition. The random agent gets the same seeds and goals.

## Skipped
- Part 5 (optional).
- No hyperparameter search; one setting was used.
- No test that Chrome versions other than the installed one work.

## What next
- Harder pages (more popup kinds, moving buttons) so the agent is not at 100%.
- A learner that does not need hand built state (small neural network over the button list).
- Run attempts in parallel inside one process with several tabs.
