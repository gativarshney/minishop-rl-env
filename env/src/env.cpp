#include "env.hpp"
#include <chrono>
#include <thread>

using json = nlohmann::json;
using Clock = std::chrono::steady_clock;

static long long msSince(Clock::time_point t) {
    return std::chrono::duration_cast<std::chrono::milliseconds>(Clock::now() - t).count();
}

json MinishopEnv::eval(const std::string& js, int timeout_ms) {
    auto t = Clock::now();
    json res = browser_.sendCommand(session_, "Runtime.evaluate",
                                    {{"expression", js}, {"returnByValue", true}}, timeout_ms);
    cdp_ms_ += msSince(t);
    if (res["result"].contains("exceptionDetails"))
        throw std::runtime_error("page script error: " + res["result"]["exceptionDetails"].dump());
    return res["result"]["result"].value("value", json());
}

// Everything the agent may know is read from the live page here, nothing is hard-coded.
json MinishopEnv::observe() {
    static const char* js = R"JS((() => {
        const popup = window.__state.popupShowing;
        const buttons = [];
        document.querySelectorAll('button').forEach((b, i) => {
            const r = b.getBoundingClientRect();
            if (r.width === 0 || r.height === 0) return;  // on a hidden screen
            const visible = getComputedStyle(b).visibility !== 'hidden';
            let clickable = false;
            if (visible && !b.disabled) {
                // clickable only if the topmost element at the centre is this button
                const el = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2);
                clickable = (el === b || b.contains(el));
            }
            // textContent, because innerText is empty for hidden (delayed) buttons
            buttons.push({i: i, text: b.textContent.trim(), data_id: b.dataset.id || '', clickable: clickable});
        });
        const s = window.__state;
        return {screen: s.screen.replace('-screen', ''), popup_showing: popup, buttons: buttons,
                state: {viewing: s.product, qty: s.qty, cart_item: s.cartItem, cart_qty: s.cartQty, delay_pending: s.delayPending},
                order: window.__orderResult};
    })())JS";
    json raw = eval(js);
    last_raw_ = raw;
    return {{"screen", raw["screen"]}, {"goal", goal_}, {"popup_showing", raw["popup_showing"]},
            {"buttons", raw["buttons"]}};
}

json MinishopEnv::reset(const std::string& item, int qty, int seed, double popup_p, double delay_p) {
    steps_ = 0;
    cdp_ms_ = settle_ms_ = 0;
    goal_ = item + " x" + std::to_string(qty);

    // Reuse the browser; relaunch only if it is not running (first call or after a crash).
    browser_.ensureLaunched();
    if (session_.empty() || generation_ != browser_.generation()) {
        generation_ = browser_.generation();
        session_ = browser_.newPage();
    }

    std::string path;
    for (char c : site_path_) {
        if (c == '\\') path += '/';
        else if (c == ' ') path += "%20";
        else path += c;
    }
    if (path.empty() || path[0] != '/') path = "/" + path;  // C:/x -> /C:/x for file:///
    std::string url = "file://" + path + "?item=" + item + "&qty=" + std::to_string(qty) +
                      "&seed=" + std::to_string(seed) + "&popup_p=" + std::to_string(popup_p) +
                      "&delay_p=" + std::to_string(delay_p);
    try {
        // go through about:blank so we can never read the previous attempt's page by mistake
        browser_.sendCommand(session_, "Page.navigate", {{"url", "about:blank"}}, 5000);
        browser_.sendCommand(session_, "Page.navigate", {{"url", url}}, 5000);
        // wait until the new page has run its script (window.__state exists for this URL)
        auto t = Clock::now();
        const std::string check = "!!(window.__state && document.readyState === 'complete')";
        while (!eval(check).get<bool>()) {
            if (msSince(t) > 8000) throw std::runtime_error("page load timeout");
            std::this_thread::sleep_for(std::chrono::milliseconds(10));
        }
    } catch (...) {
        session_.clear();  // a broken tab is replaced by a new one on the next reset
        throw;
    }
    cdp_ms_ = 0;
    json obs = observe();
    return {{"observation", obs}, {"info", infoFromPage()}};
}

json MinishopEnv::infoFromPage() const {
    json info = {{"current_qty", last_raw_["state"]["qty"]},
                 {"viewing_item", last_raw_["state"]["viewing"]},
                 {"cart_item", last_raw_["state"]["cart_item"]},
                 {"cart_qty", last_raw_["state"]["cart_qty"]},
                 {"delay_pending", last_raw_["state"]["delay_pending"]}};
    if (!last_raw_["order"].is_null()) info["order"] = last_raw_["order"];
    return info;
}

// A real mouse click: move, press, release at the button centre through CDP.
void MinishopEnv::realClick(double x, double y) {
    auto t = Clock::now();
    browser_.sendCommand(session_, "Input.dispatchMouseEvent", {{"type", "mouseMoved"}, {"x", x}, {"y", y}});
    browser_.sendCommand(session_, "Input.dispatchMouseEvent",
                         {{"type", "mousePressed"}, {"x", x}, {"y", y}, {"button", "left"}, {"clickCount", 1}});
    browser_.sendCommand(session_, "Input.dispatchMouseEvent",
                         {{"type", "mouseReleased"}, {"x", x}, {"y", y}, {"button", "left"}, {"clickCount", 1}});
    cdp_ms_ += msSince(t);
}

// Poll until two reads in a row are identical, but give up after 150 ms. Delayed
// buttons (up to 300 ms) can still be hidden afterwards: the agent then has to wait.
void MinishopEnv::settle() {
    auto t = Clock::now();
    json prev = last_raw_;
    // brief pause so the click handler's DOM changes have landed
    std::this_thread::sleep_for(std::chrono::milliseconds(15));
    while (msSince(t) < 150) {
        observe();
        if (last_raw_ == prev) break;
        prev = last_raw_;
        std::this_thread::sleep_for(std::chrono::milliseconds(15));
    }
    settle_ms_ += msSince(t);
}

StepResult MinishopEnv::step(const std::string& action_type, int action_i) {
    auto start = Clock::now();
    cdp_ms_ = settle_ms_ = 0;
    json info = json::object();
    steps_++;
    try {
        if (action_type == "click") {
            // fresh position lookup; the button may have moved or vanished since the last read
            std::string js = "(() => { const b = document.querySelectorAll('button')[" + std::to_string(action_i) +
                             "]; if (!b) return null; const r = b.getBoundingClientRect();"
                             " return {x: r.left + r.width / 2, y: r.top + r.height / 2, w: r.width}; })()";
            json pos = eval(js);
            if (pos.is_null() || pos["w"].get<double>() == 0) {
                info["invalid_action"] = "no such visible button";  // wasted step, nothing is clicked
            } else {
                // Click even if covered or hidden: the page decides, like for a real user.
                bool was_clickable = false;
                for (auto& b : last_raw_["buttons"])
                    if (b["i"] == action_i) was_clickable = b["clickable"];
                if (!was_clickable) info["click_blocked"] = true;
                realClick(pos["x"].get<double>(), pos["y"].get<double>());
            }
        } else if (action_type == "wait") {
            // short pause; a delayed button (50 to 300 ms) needs one to a few waits
            std::this_thread::sleep_for(std::chrono::milliseconds(60));
        } else {
            info["invalid_action"] = "unknown action type";
        }
        // settle() needs a baseline read taken before it starts comparing
        observe();
        settle();
    } catch (const std::exception& e) {
        // Timeouts or a dead browser end the attempt cleanly; the next reset relaunches.
        session_.clear();  // the next reset opens a fresh tab (and a fresh browser if it died)
        info["error"] = e.what();
        return {json{{"screen", "unknown"}, {"goal", goal_}, {"popup_showing", false},
                     {"buttons", json::array()}},
                -0.01, false, true, info, msSince(start), cdp_ms_, settle_ms_, false};
    }

    json obs = observe();
    json page_info = infoFromPage();  // keep it alive while iterating
    for (auto& kv : page_info.items()) info[kv.key()] = kv.value();

    bool done = !last_raw_["order"].is_null();
    double reward = -0.01;  // small cost per step so shorter paths are better
    if (done) {
        reward = last_raw_["order"].value("success", false) ? 1.0 : -1.0;  // page's own verdict
    }
    bool truncated = !done && steps_ >= kMaxSteps;
    return {obs, reward, done, truncated, info, msSince(start), cdp_ms_, settle_ms_,
            last_raw_["popup_showing"].get<bool>()};
}
