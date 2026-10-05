"""Kills the env process hard mid-run and checks no browser with our profile dir survives."""
import subprocess, sys, time, os
sys.path.insert(0, os.path.dirname(__file__))
from env_client import Env


def leftovers():
    if os.name == "nt":
        cmd = ["powershell", "-NoProfile", "-Command",
               "(Get-CimInstance Win32_Process | Where-Object { $_.Name -match 'chrome|msedge' -and $_.CommandLine -like '*minishop_profile_*' } | Measure-Object).Count"]
    else:
        cmd = ["sh", "-c", "pgrep -fc 'chrome.*minishop_profile_' || true"]
    return int(subprocess.run(cmd, capture_output=True, text=True).stdout.strip() or 0)


env = Env()
env.reset("blue-mug", 1, 1, 0.5, 0.5)
print("browser processes while running:", leftovers())
env.proc.kill()  # simulate a crash, no cleanup code can run
time.sleep(2)
n = leftovers()
print("browser processes after crash:", n)
sys.exit(0 if n == 0 else 1)
