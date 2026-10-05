"""Python side of the environment: talks JSON lines to the C++ minishop_env process."""
import atexit
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = os.path.join(ROOT, "site", "index.html")  # absolute, the C++ side turns it into a file:// URL


def find_exe():
    # MSVC puts the binary in build/Release, Makefiles directly in build/
    name = "minishop_env.exe" if os.name == "nt" else "minishop_env"
    for sub in ("Release", ""):
        p = os.path.join(ROOT, "env", "build", sub, name)
        if os.path.exists(p):
            return p
    raise FileNotFoundError("minishop_env not built; run the build first")


class Env:
    def __init__(self):
        self.proc = subprocess.Popen([find_exe(), "--site", SITE], stdin=subprocess.PIPE,
                                     stdout=subprocess.PIPE, text=True, bufsize=1)
        atexit.register(self.close)  # the env's own cleanup then kills Chrome

    def _call(self, req):
        self.proc.stdin.write(json.dumps(req) + "\n")
        self.proc.stdin.flush()
        line = self.proc.stdout.readline()
        if not line:
            raise RuntimeError("environment process died")
        res = json.loads(line)
        if res.get("status") != "ok":
            raise RuntimeError(res.get("error", "unknown env error"))
        return res

    def reset(self, item, qty, seed, popup_p, delay_p):
        return self._call({"cmd": "reset", "item": item, "qty": qty, "seed": seed,
                           "popup_p": popup_p, "delay_p": delay_p})["observation"]

    def step(self, action):
        """action is ('click', i) or ('wait', None)."""
        kind, i = action
        return self._call({"cmd": "step", "action": kind, "i": -1 if i is None else i})

    def close(self):
        if self.proc.poll() is None:
            try:
                self.proc.stdin.write('{"cmd":"close"}\n')
                self.proc.stdin.flush()
                self.proc.wait(timeout=10)
            except Exception:
                self.proc.kill()
