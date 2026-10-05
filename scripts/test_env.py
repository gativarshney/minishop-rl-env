"""Smoke test: one full correct purchase through real clicks, read from the live page."""
import sys
sys.path.insert(0, __import__("os").path.dirname(__file__))
from env_client import Env

env = Env()
obs = env.reset("blue-mug", 2, 42, 0.0, 0.0)
print("reset:", obs["screen"], [b["text"] for b in obs["buttons"]])


def click_text(obs, text, nth=0):
    hits = [b for b in obs["buttons"] if b["text"] == text and b["clickable"]]
    return env.step(("click", hits[nth]["i"]))


r = env.step(("click", next(b["i"] for b in obs["buttons"] if b["data_id"] == "blue-mug")))
for text in ["+", "Add to cart", "Checkout"]:
    r = click_text(r["observation"], text)
    print(text, "->", r["observation"]["screen"], r["reward"], r["done"], r["info"], r["time_ms"], "ms")
assert r["done"] and r["reward"] == 1.0 and r["info"]["order"]["success"], "purchase should succeed"
obs = env.reset("red-lamp", 3, 7, 0.0, 0.0)  # browser reuse
print("second reset ok:", obs["screen"])
env.close()
print("OK")
