"""Python side of the environment: talks JSON lines to the C++ minishop_env process."""
import atexit
import json
import os
import queue
import subprocess
import sys
import threading
from collections import defaultdict

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


class EnvProcess:
    """One minishop_env process (one Chrome). Several Env objects can share it, one tab each."""

    def __init__(self):
        self.proc = subprocess.Popen([find_exe(), "--site", SITE], stdin=subprocess.PIPE,
                                     stdout=subprocess.PIPE, text=True, bufsize=1)
        self.write_lock = threading.Lock()
        self.replies = defaultdict(queue.Queue)  # env id -> replies for that env
        self.dead = False
        # replies of different envs arrive in any order, so one thread sorts them by env id
        threading.Thread(target=self._reader, daemon=True).start()
        atexit.register(self.close)  # the env's own cleanup then kills Chrome

    def _reader(self):
        for line in self.proc.stdout:
            res = json.loads(line)
            self.replies[res.get("env", 0)].put(res)
        self.dead = True
        for q in list(self.replies.values()):
            q.put(None)  # wake up anyone waiting

    def call(self, env_id, req):
        req = dict(req, env=env_id)
        with self.write_lock:
            self.proc.stdin.write(json.dumps(req) + "\n")
            self.proc.stdin.flush()
        res = self.replies[env_id].get()
        if res is None:
            raise RuntimeError("environment process died")
        if res.get("status") != "ok":
            raise RuntimeError(res.get("error", "unknown env error"))
        return res

    def close(self):
        if self.proc.poll() is None:
            try:
                with self.write_lock:
                    self.proc.stdin.write('{"cmd":"close"}\n')
                    self.proc.stdin.flush()
                self.proc.wait(timeout=15)
            except Exception:
                self.proc.kill()


class Env:
    def __init__(self, process=None, env_id=0):
        self.owns = process is None
        self.process = process or EnvProcess()
        self.env_id = env_id

    def reset(self, item, qty, seed, popup_p, delay_p):
        """Returns (observation, info), both read from the live page."""
        r = self.process.call(self.env_id, {"cmd": "reset", "item": item, "qty": qty, "seed": seed,
                                            "popup_p": popup_p, "delay_p": delay_p})
        return r["observation"], r["info"]

    def step(self, action):
        """action is ('click', i) or ('wait', None)."""
        kind, i = action
        return self.process.call(self.env_id, {"cmd": "step", "action": kind, "i": -1 if i is None else i})

    def close(self):
        if self.owns:
            self.process.close()
