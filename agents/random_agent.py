"""Baseline: picks uniformly among every clickable button plus wait."""
import random


class RandomAgent:
    name = "random"

    def __init__(self, seed):
        self.rng = random.Random(seed)  # seeded so runs are reproducible

    def act(self, obs, info):
        options = [("click", b["i"]) for b in obs["buttons"] if b["clickable"]]
        options.append(("wait", None))
        return self.rng.choice(options)

    def learn(self, *args, **kwargs):
        pass  # the baseline never learns
