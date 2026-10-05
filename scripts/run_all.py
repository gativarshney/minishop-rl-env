import subprocess
import json
import os
import sys

# Hack to load agents
sys.path.append(os.path.abspath("agents"))
from random_agent import RandomAgent
from qlearning_agent import QLearningAgent

def main():
    if sys.platform == "win32":
        env_bin = os.path.join("env", "build", "Release", "minishop_env.exe")
    else:
        env_bin = os.path.join("env", "build", "minishop_env")
        
    if not os.path.exists(env_bin):
        print(f"Error: {env_bin} not found. Please build first.")
        sys.exit(1)
        
    print("Starting env process...")
    proc = subprocess.Popen([env_bin], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
    
    logs = []
    html_path = os.path.abspath(os.path.join("site", "index.html"))
    
    # Train QLearning agent quickly (10 episodes)
    # Then Eval QLearning (10 episodes) and Random (10 episodes) to save time,
    # but wait, the instructions demand at least 200 attempts for each.
    # To run 200 attempts quickly, we need to do it.

    agents = [
        ("random", RandomAgent()),
        ("qlearning", QLearningAgent())
    ]
    
    episodes_per_agent = 200
    
    for agent_name, agent in agents:
        for ep in range(episodes_per_agent):
            # 4 items x 3 quantities
            items = ["blue-mug", "red-lamp", "green-book", "black-pen"]
            item = items[ep % 4]
            qty = (ep % 3) + 1
            seed = 42 + ep
            
            req = {"cmd": "reset", "item": item, "qty": qty, "seed": seed, "popup_p": 0.15, "delay_p": 0.1, "html_path": html_path}
            proc.stdin.write(json.dumps(req) + "\n")
            proc.stdin.flush()
            
            res_str = proc.stdout.readline()
            if not res_str: break
            res = json.loads(res_str)
            if "observation" not in res:
                print(f"Error from env: {res}")
                break
            obs = res["observation"]
            info = {"current_qty": 1, "cart_item": "None"}
            
            step_idx = 0
            done = False
            while not done and step_idx < 20:
                if agent_name == "random":
                    action = agent.get_action(obs)
                else:
                    action = agent.get_action(obs, info, eval_mode=True)
                    
                req = {"cmd": "step", "action_i": action["i"], "action_type": action["type"]}
                proc.stdin.write(json.dumps(req) + "\n")
                proc.stdin.flush()
                
                res = json.loads(proc.stdout.readline())
                next_obs = res["observation"]
                done = res["done"]
                info = res.get("info", {"current_qty": 1, "cart_item": "None"})
                
                logs.append(json.dumps({
                    "episode": ep, "seed": seed, "goal": f"{item} x{qty}", "step": step_idx,
                    "action": action.get("name", "wait") if "name" in action else action["type"],
                    "reward": res["reward"], "done": done, "truncated": res["truncated"],
                    "time_ms": res["time_ms"], "popup_showing": res["popup_showing"], "agent": agent_name
                }))
                
                if agent_name == "qlearning":
                    agent.update(obs, info, action, res["reward"], next_obs, info, done)
                    
                obs = next_obs
                step_idx += 1
                
    proc.stdin.write(json.dumps({"cmd": "close"}) + "\n")
    proc.stdin.flush()
    proc.wait()
    
    os.makedirs("logs", exist_ok=True)
    with open("logs/run.jsonl", "w") as f:
        for l in logs:
            f.write(l + "\n")
            
if __name__ == "__main__":
    main()
