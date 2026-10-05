#include "env.hpp"
#include <iostream>
#include <chrono>
#include <thread>
#include <filesystem>

MinishopEnv::MinishopEnv() {}
MinishopEnv::~MinishopEnv() {}

nlohmann::json MinishopEnv::reset(const std::string& item, int qty, int seed, double popup_p, double delay_p, const std::string& html_path) {
    steps_ = 0;
    current_goal_ = item + " x" + std::to_string(qty);
    
    std::string path_str = html_path;
    for (char& c : path_str) { if (c == '\\') c = '/'; }
    if (path_str.length() > 0 && path_str[0] != '/') path_str = "/" + path_str;
    
    std::string url = "file://" + path_str + "?item=" + item + "&qty=" + std::to_string(qty) + 
                      "&seed=" + std::to_string(seed) + "&popup_p=" + std::to_string(popup_p) + 
                      "&delay_p=" + std::to_string(delay_p);
    
    // Launch/restart browser
    browser_.close();
    browser_.launch(url);
    
    waitForSettle();
    
    return getObservation();
}

StepResult MinishopEnv::step(int action_i, const std::string& action_type) {
    auto start = std::chrono::steady_clock::now();
    
    if (action_type == "click" && action_i >= 0) {
        // get button coordinates
        std::string script = R"(
            (function(i) {
                let buttons = Array.from(document.querySelectorAll('button'));
                let b = buttons[i];
                if (!b) return null;
                let rect = b.getBoundingClientRect();
                return {x: rect.left + rect.width/2, y: rect.top + rect.height/2};
            })()
        )";
        script.insert(script.find("()"), "(" + std::to_string(action_i) + ")");
        
        nlohmann::json params = {
            {"expression", script},
            {"returnByValue", true}
        };
        auto res = browser_.sendCommand("Runtime.evaluate", params);
        if (res.contains("result") && res["result"].contains("result") && res["result"]["result"].contains("value") && res["result"]["result"]["value"].is_object()) {
            auto val = res["result"]["result"]["value"];
            click(val["x"].get<int>(), val["y"].get<int>());
        }
    }
    
    waitForSettle();
    
    steps_++;
    auto obs = getObservation();
    
    // Check if done
    bool done = false;
    double reward = -0.01;
    nlohmann::json info = {{"current_qty", 1}, {"cart_item", "None"}};
    
    nlohmann::json eval_params = {{"expression", "window.__orderResult"}, {"returnByValue", true}};
    auto res = browser_.sendCommand("Runtime.evaluate", eval_params);
    if (res.contains("result") && res["result"].contains("result") && res["result"]["result"].contains("value") && res["result"]["result"]["value"].is_object()) {
        auto val = res["result"]["result"]["value"];
        done = true;
        if (val.value("success", false)) {
            reward = 1.0;
        } else {
            reward = -1.0;
        }
    }
    
    // Extract info
    eval_params["expression"] = "(() => { return {qty: typeof quantity !== 'undefined' ? quantity : 1, cartItem: typeof cartItem !== 'undefined' && cartItem ? cartItem : 'None'}; })()";
    res = browser_.sendCommand("Runtime.evaluate", eval_params);
    if (res.contains("result") && res["result"].contains("result") && res["result"]["result"].contains("value") && res["result"]["result"]["value"].is_object()) {
        auto val = res["result"]["result"]["value"];
        info["current_qty"] = val.value("qty", 1);
        info["cart_item"] = val.value("cartItem", "None");
    }
    
    bool truncated = steps_ >= 20;
    if (truncated) done = true;
    
    auto end = std::chrono::steady_clock::now();
    long long time_ms = std::chrono::duration_cast<std::chrono::milliseconds>(end - start).count();
    
    return {obs, reward, done, truncated, info, time_ms, popup_showing_};
}

nlohmann::json MinishopEnv::getObservation() {
    std::string script = R"(
        (() => {
            let screen = "unknown";
            let active = document.querySelector('.screen.active');
            if (active) screen = active.id.replace('-screen', '');
            
            let popup = document.getElementById('popup-overlay');
            let popupShowing = popup && popup.style.display === 'block';
            
            let buttons = Array.from(document.querySelectorAll('button'));
            let btnList = [];
            for (let i = 0; i < buttons.length; i++) {
                let b = buttons[i];
                let rect = b.getBoundingClientRect();
                let visible = rect.width > 0 && rect.height > 0 && window.getComputedStyle(b).visibility !== 'hidden';
                let clickable = false;
                if (visible) {
                    let centerX = rect.left + rect.width / 2;
                    let centerY = rect.top + rect.height / 2;
                    let el = document.elementFromPoint(centerX, centerY);
                    clickable = (el === b || b.contains(el));
                }
                btnList.push({
                    i: i,
                    text: b.innerText,
                    id: b.getAttribute('data-id') || '',
                    clickable: clickable
                });
            }
            return {
                screen: screen,
                popup_showing: popupShowing,
                buttons: btnList
            };
        })()
    )";
    nlohmann::json params = {{"expression", script}, {"returnByValue", true}};
    auto res = browser_.sendCommand("Runtime.evaluate", params);
    
    nlohmann::json obs = {{"screen", "unknown"}, {"goal", current_goal_}, {"buttons", nlohmann::json::array()}};
    if (res.contains("result") && res["result"].contains("result") && res["result"]["result"].contains("value")) {
        auto val = res["result"]["result"]["value"];
        obs["screen"] = val.value("screen", "unknown");
        obs["buttons"] = val.value("buttons", nlohmann::json::array());
        popup_showing_ = val.value("popup_showing", false);
        obs["popup_showing"] = popup_showing_;
    }
    return obs;
}

void MinishopEnv::click(int x, int y) {
    browser_.sendCommand("Input.dispatchMouseEvent", {
        {"type", "mouseMoved"}, {"x", x}, {"y", y}
    });
    browser_.sendCommand("Input.dispatchMouseEvent", {
        {"type", "mousePressed"}, {"x", x}, {"y", y}, {"button", "left"}, {"clickCount", 1}
    });
    browser_.sendCommand("Input.dispatchMouseEvent", {
        {"type", "mouseReleased"}, {"x", x}, {"y", y}, {"button", "left"}, {"clickCount", 1}
    });
}

void MinishopEnv::waitForSettle() {
    // Basic polling to wait for buttons to become visible (in case of delay)
    for (int i=0; i<10; i++) {
        std::this_thread::sleep_for(std::chrono::milliseconds(50));
        auto obs = getObservation();
        bool any_visible = false;
        for (auto& b : obs["buttons"]) {
            if (b["clickable"] == true) {
                any_visible = true; break;
            }
        }
        if (any_visible) break;
    }
}
