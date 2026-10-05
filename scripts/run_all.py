import subprocess
import json
import os
import sys

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
    
    # Run 2 episodes of random agent
    for ep in range(2):
        print(f"Episode {ep}")
        req = {"cmd": "reset", "item": "blue-mug", "qty": 1, "seed": 42 + ep, "popup_p": 0.0, "delay_p": 0.0}
        proc.stdin.write(json.dumps(req) + "\n")
        proc.stdin.flush()
        
        res = json.loads(proc.stdout.readline())
        obs = res["observation"]
        
        step_idx = 0
        done = False
        while not done and step_idx < 10:
            # Random action
            buttons = obs.get("buttons", [])
            clickable = [b for b in buttons if b.get("clickable", False)]
            if clickable:
                a = clickable[0]
                action = {"type": "click", "i": a["i"]}
                act_str = f"click({a['i']})"
            else:
                action = {"type": "wait", "i": -1}
                act_str = "wait"
                
            req = {"cmd": "step", "action_i": action["i"], "action_type": action["type"]}
            proc.stdin.write(json.dumps(req) + "\n")
            proc.stdin.flush()
            
            res = json.loads(proc.stdout.readline())
            next_obs = res["observation"]
            done = res["done"]
            
            logs.append(json.dumps({
                "episode": ep, "seed": 42 + ep, "goal": "blue-mug x1", "step": step_idx,
                "action": act_str, "reward": res["reward"], "done": done, "truncated": res["truncated"],
                "time_ms": res["time_ms"], "popup_showing": res["popup_showing"], "agent": "random"
            }))
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
