#include "env.hpp"
#include <iostream>
#include <string>
#include <nlohmann/json.hpp>

using json = nlohmann::json;

int main() {
    MinishopEnv env;

    std::string line;
    while (std::getline(std::cin, line)) {
        if (line.empty()) continue;
        try {
            json req = json::parse(line);
            std::string cmd = req.value("cmd", "");
            
            if (cmd == "reset") {
                std::string item = req.value("item", "blue-mug");
                int qty = req.value("qty", 1);
                int seed = req.value("seed", 42);
                double popup_p = req.value("popup_p", 0.0);
                double delay_p = req.value("delay_p", 0.0);
                
                json obs = env.reset(item, qty, seed, popup_p, delay_p);
                json res = {
                    {"status", "ok"},
                    {"observation", obs}
                };
                std::cout << res.dump() << std::endl;
            } else if (cmd == "step") {
                int action_i = req.value("action_i", -1);
                std::string action_type = req.value("action_type", "wait");
                
                StepResult step_res = env.step(action_i, action_type);
                
                json res = {
                    {"status", "ok"},
                    {"observation", step_res.observation},
                    {"reward", step_res.reward},
                    {"done", step_res.done},
                    {"truncated", step_res.truncated},
                    {"info", step_res.info},
                    {"time_ms", step_res.time_ms},
                    {"popup_showing", step_res.popup_showing}
                };
                std::cout << res.dump() << std::endl;
            } else if (cmd == "close") {
                break;
            } else {
                json res = {{"status", "error"}, {"error", "unknown command"}};
                std::cout << res.dump() << std::endl;
            }
        } catch (const std::exception& e) {
            json res = {{"status", "error"}, {"error", e.what()}};
            std::cout << res.dump() << std::endl;
        }
    }
    return 0;
}
