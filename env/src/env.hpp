#pragma once
#include "browser.hpp"
#include <string>
#include <nlohmann/json.hpp>
#include <chrono>

struct StepResult {
    nlohmann::json observation;
    double reward;
    bool done;
    bool truncated;
    nlohmann::json info;
    long long time_ms;
    bool popup_showing;
};

class MinishopEnv {
public:
    MinishopEnv();
    ~MinishopEnv();

    nlohmann::json reset(const std::string& item, int qty, int seed, double popup_p, double delay_p, const std::string& html_path);
    StepResult step(int action_i, const std::string& action_type); // action_type: "click" or "wait"

private:
    nlohmann::json getObservation();
    void click(int x, int y);
    void waitForSettle();

    Browser browser_;
    int steps_ = 0;
    std::string current_goal_;
    
    // Last read state
    bool popup_showing_ = false;
};
