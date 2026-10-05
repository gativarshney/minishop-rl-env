import json
import random
import math

class QLearningAgent:
    def __init__(self, alpha=0.1, gamma=0.9, epsilon_start=1.0, epsilon_min=0.05, epsilon_decay=0.995, seed=42):
        self.q_table = {}
        self.alpha = alpha
        self.gamma = gamma
        self.epsilon = epsilon_start
        self.epsilon_min = epsilon_min
        self.epsilon_decay = epsilon_decay
        self.rng = random.Random(seed)

    def extract_state(self, obs, info):
        # Extract small, goal-relative state
        screen = obs.get("screen", "unknown")
        popup = obs.get("popup_showing", False)
        
        # Buttons ready or not (are there any clickable buttons besides Dismiss?)
        buttons = obs.get("buttons", [])
        clickable_buttons = [b for b in buttons if b.get("clickable", False)]
        buttons_ready = any(b.get("text") != "Dismiss" for b in clickable_buttons)

        # Quantity relative to target
        goal = obs.get("goal", "") # e.g. "blue-mug x2"
        target_qty = 1
        goal_item = ""
        if " x" in goal:
            goal_item, qty_str = goal.split(" x")
            target_qty = int(qty_str)
            
        current_qty = info.get("current_qty", 1)
        if current_qty < target_qty:
            qty_rel = "below"
        elif current_qty == target_qty:
            qty_rel = "equal"
        else:
            qty_rel = "above"
            
        cart_item = info.get("cart_item", "None")
        cart_match = (cart_item == goal_item)
        
        # Is there a View button for the goal item?
        view_goal = False
        for b in clickable_buttons:
            if b.get("text") == "View" and b.get("id") == goal_item:
                view_goal = True
                
        state = (screen, popup, buttons_ready, qty_rel, cart_match, view_goal)
        return state

    def extract_actions(self, obs):
        # Actions: button text, and for View buttons, which product it opens. Plus wait.
        actions = []
        buttons = obs.get("buttons", [])
        for b in buttons:
            if b.get("clickable", False):
                action_name = b.get("text", "")
                if action_name == "View":
                    action_name = f"View {b.get('id', '')}"
                actions.append({"type": "click", "i": b["i"], "name": action_name})
        actions.append({"type": "wait", "i": -1, "name": "wait"})
        return actions

    def get_q(self, state, action_name):
        return self.q_table.get((state, action_name), 0.0)

    def get_action(self, obs, info, eval_mode=False):
        state = self.extract_state(obs, info)
        actions = self.extract_actions(obs)
        
        if not eval_mode and self.rng.random() < self.epsilon:
            # Random exploration
            return self.rng.choice(actions)
        
        # Greedy choice with random tie breaks
        best_val = -float('inf')
        best_acts = []
        for a in actions:
            val = self.get_q(state, a["name"])
            if val > best_val:
                best_val = val
                best_acts = [a]
            elif val == best_val:
                best_acts.append(a)
                
        return self.rng.choice(best_acts)

    def update(self, obs, info, action, reward, next_obs, next_info, done):
        state = self.extract_state(obs, info)
        next_state = self.extract_state(next_obs, next_info)
        action_name = action["name"]
        
        old_q = self.get_q(state, action_name)
        
        next_actions = self.extract_actions(next_obs)
        if done:
            max_next_q = 0.0
        else:
            max_next_q = max([self.get_q(next_state, a["name"]) for a in next_actions]) if next_actions else 0.0
            
        new_q = old_q + self.alpha * (reward + self.gamma * max_next_q - old_q)
        self.q_table[(state, action_name)] = new_q

    def decay_epsilon(self):
        self.epsilon = max(self.epsilon_min, self.epsilon * self.epsilon_decay)
