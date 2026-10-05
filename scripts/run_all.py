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
    try:
        proc = subprocess.Popen([env_bin], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
    except Exception as e:
        print(f"Failed to start {env_bin}: {e}")
        sys.exit(1)
    
    logs = []
    html_path = os.path.abspath(os.path.join("site", "index.html"))
    
    episodes_per_agent = 200
    
    # Train QLearning agent (3 seeds, 144 episodes each = 432)
    # Then Eval QLearning at popup 0, 0.15, 0.4
    # Then Eval Random at popup 0.15
    
    # Run loop function
    def run_episodes(agent_name, agent, num_episodes, phase, popup_p, seed_offset, do_update=False):
        for ep in range(num_episodes):
            items = ["blue-mug", "red-lamp", "green-book", "black-pen"]
            item = items[ep % 4]
            qty = (ep % 3) + 1
            seed = seed_offset + ep
            
            req = {"cmd": "reset", "item": item, "qty": qty, "seed": seed, "popup_p": popup_p, "delay_p": 0.1, "html_path": html_path}
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
                    action = agent.get_action(obs, info, eval_mode=not do_update)
                    
                req = {"cmd": "step", "action_i": action["i"], "action_type": action["type"]}
                proc.stdin.write(json.dumps(req) + "\n")
                proc.stdin.flush()
                
                res = json.loads(proc.stdout.readline())
                next_obs = res["observation"]
                done = res["done"]
                next_info = res.get("info", {"current_qty": 1, "cart_item": "None"})
                
                logs.append(json.dumps({
                    "episode": ep, "seed": seed, "goal": f"{item} x{qty}", "step": step_idx,
                    "observation": obs, "phase": phase, "popup_p": popup_p, "delay_p": 0.1,
                    "action": action.get("name", "wait") if "name" in action else action["type"],
                    "reward": res["reward"], "done": done, "truncated": res["truncated"],
                    "time_ms": res["time_ms"], "popup_showing": res["popup_showing"], "agent": agent_name
                }))
                
                if do_update:
                    agent.update(obs, info, action, res["reward"], next_obs, next_info, done)
                    
                obs = next_obs
                info = next_info
                step_idx += 1
            if do_update and hasattr(agent, "decay_epsilon"):
                agent.decay_epsilon()

    for run_seed in range(3):
        agent = QLearningAgent(seed=run_seed)
        run_episodes("qlearning", agent, 144, "train", 0.15, run_seed*1000, do_update=True)
        # eval on 3 sweeps for this seed
        run_episodes("qlearning", agent, 200, "eval", 0.0, run_seed*1000 + 2000, do_update=False)
        run_episodes("qlearning", agent, 200, "eval", 0.15, run_seed*1000 + 3000, do_update=False)
        run_episodes("qlearning", agent, 200, "eval", 0.4, run_seed*1000 + 4000, do_update=False)

    random_agent = RandomAgent()
    run_episodes("random", random_agent, 200, "eval", 0.15, 10000, do_update=False)
                
    proc.stdin.write(json.dumps({"cmd": "close"}) + "\n")
    proc.stdin.flush()
    proc.wait()
    
    os.makedirs("logs", exist_ok=True)
    with open("logs/run.jsonl", "w") as f:
        for l in logs:
            f.write(l + "\n")
            
if __name__ == "__main__":
    main()
