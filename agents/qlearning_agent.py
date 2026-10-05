"""Tabular Q-learning with a small, goal-relative state so one table serves all 12 goals."""
import random
from collections import defaultdict


def rel(a, target):
    """Compare a quantity with the goal quantity."""
    return "below" if a < target else "equal" if a == target else "above"


class QAgent:
    name = "qlearning"

    def __init__(self, seed, alpha=0.3, gamma=0.95, eps_start=1.0, eps_min=0.05, eps_decay=0.99):
        self.rng = random.Random(seed)
        self.q = defaultdict(float)  # (state, action_key) -> value
        self.alpha, self.gamma = alpha, gamma
        self.eps_start, self.eps_min, self.eps_decay = eps_start, eps_min, eps_decay
        self.eps = eps_start
        self.goal_item = None
        self.goal_qty = None

    def start_episode(self, goal_item, goal_qty, episode, train):
        self.goal_item, self.goal_qty = goal_item, goal_qty
        # epsilon shrinks with episodes; evaluation is fully greedy
        self.eps = max(self.eps_min, self.eps_start * self.eps_decay ** episode) if train else 0.0

    # ----- state and actions -------------------------------------------------
    def state(self, obs, info):
        """Small tuple, relative to the goal. Built from the observation and info of ONE moment."""
        buttons = obs["buttons"]
        ready = any(b["clickable"] for b in buttons)
        screen = obs["screen"]
        # on the cart screen the quantity that matters is the cart's, otherwise the selector's
        qty = info["cart_qty"] if screen in ("cart", "done") else info["current_qty"]
        cart = info["cart_item"]
        cart_match = "empty" if cart is None else "yes" if cart == self.goal_item else "no"
        viewing = info["viewing_item"]
        viewing_goal = "none" if viewing is None else "yes" if viewing == self.goal_item else "no"
        goal_view = any(b["text"] == "View" and b["data_id"] == self.goal_item and b["clickable"]
                        for b in buttons)
        return (screen, obs["popup_showing"], ready, rel(qty, self.goal_qty), cart_match,
                viewing_goal, goal_view)

    def action_key(self, button):
        """Actions are named by button text; View buttons by whether the product is the goal."""
        if button["text"] == "View":
            return "View:goal" if button["data_id"] == self.goal_item else "View:other"
        return button["text"]

    def options(self, obs):
        """Map action key -> list of clickable button indices with that key."""
        opts = {"wait": []}
        for b in obs["buttons"]:
            if b["clickable"]:
                opts.setdefault(self.action_key(b), []).append(b["i"])
        return opts

    # ----- acting and learning ----------------------------------------------
    def act(self, obs, info):
        s = self.state(obs, info)
        opts = self.options(obs)
        keys = list(opts)
        if self.rng.random() < self.eps:
            key = self.rng.choice(keys)
        else:
            best = max(self.q[(s, k)] for k in keys)
            key = self.rng.choice([k for k in keys if self.q[(s, k)] == best])  # random tie-break
        self.last_key = key
        i = self.rng.choice(opts[key]) if opts[key] else None
        return ("click", i) if key != "wait" else ("wait", None)

    def learn(self, obs, info, key, reward, next_obs, next_info, terminal):
        """Q-learning update. obs/info are from BEFORE the action, next_* from AFTER it."""
        s = self.state(obs, info)
        s2 = self.state(next_obs, next_info)
        future = 0.0
        if not terminal:  # a truncated attempt is not a real end, so it still bootstraps
            future = max(self.q[(s2, k)] for k in self.options(next_obs))
        target = reward + self.gamma * future
        self.q[(s, key)] += self.alpha * (target - self.q[(s, key)])
