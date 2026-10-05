import json
import random
import sys

class RandomAgent:
    def __init__(self, action_space_fn=None):
        self.action_space_fn = action_space_fn

    def get_action(self, obs):
        buttons = obs.get("buttons", [])
        clickable_buttons = [b for b in buttons if b.get("clickable", False)]
        
        # We can either click a random button, or wait
        actions = []
        for b in clickable_buttons:
            actions.append({"type": "click", "i": b["i"]})
        actions.append({"type": "wait", "i": -1})
        
        # Exact choice documented here: Randomly pick from clickable buttons or wait.
        action = random.choice(actions)
        return action
