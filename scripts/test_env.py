"""Smoke test: one full correct purchase through real clicks, read from the live page."""
import sys
sys.path.insert(0, __import__("os").path.dirname(__file__))
from env_client import Env

env = Env()
obs, info = env.reset("blue-mug", 2, 42, 0.0, 0.0)
print("reset:", obs["screen"], [b["text"] for b in obs["buttons"]])


def click_text(obs, text, nth=0):
    hits = [b for b in obs["buttons"] if b["text"] == text and b["clickable"]]
    if len(hits) <= nth:  # say what the page looked like, so a failure is easy to understand
        raise AssertionError(f"no clickable {text!r}: screen={obs['screen']} popup={obs['popup_showing']} buttons={obs['buttons']}")
    return env.step(("click", hits[nth]["i"]))


r = env.step(("click", next(b["i"] for b in obs["buttons"] if b["data_id"] == "blue-mug")))
print("after View:", r["observation"]["screen"], r["info"], r["time_ms"], "ms")
for text in ["+", "Add to cart", "Checkout"]:
    r = click_text(r["observation"], text)
    print(text, "->", r["observation"]["screen"], r["reward"], r["done"], r["info"], r["time_ms"], "ms")
assert r["done"] and r["reward"] == 1.0 and r["info"]["order"]["success"], "purchase should succeed"
obs, info = env.reset("red-lamp", 3, 7, 0.0, 0.0)  # browser reuse
print("second reset ok:", obs["screen"])
env.close()
print("OK")
