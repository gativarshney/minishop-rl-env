#pragma once
#include "browser.hpp"
#include <string>
#include <nlohmann/json.hpp>

struct StepResult {
    nlohmann::json observation;
    double reward;
    bool done;       // an order was placed (right or wrong)
    bool truncated;  // stopped for taking too long (step limit or error)
    nlohmann::json info;
    long long time_ms;    // whole step, wall clock
    long long cdp_ms;     // time spent waiting on CDP replies
    long long settle_ms;  // time spent waiting for the page to stop changing
    bool popup_showing;
};

class MinishopEnv {
public:
    // Several environments can share one browser; each one drives its own window.
    MinishopEnv(Browser& browser, const std::string& site_path) : browser_(browser), site_path_(site_path) {}

    // Opens the page fresh for one attempt. The browser itself is reused.
    // Returns {observation, info}; both are read from the live page.
    nlohmann::json reset(const std::string& item, int qty, int seed, double popup_p, double delay_p);
    // action_type is "click" (uses action_i) or "wait".
    StepResult step(const std::string& action_type, int action_i);

    static constexpr int kMaxSteps = 20;

private:
    // One CDP Runtime.evaluate that returns a JSON value.
    nlohmann::json eval(const std::string& js, int timeout_ms = 3000);
    nlohmann::json observe();  // live read of screen, popup, buttons, page state
    nlohmann::json infoFromPage() const;  // extra facts from window.__state / __orderResult
    void realClick(double x, double y);
    void settle();

    Browser& browser_;
    std::string session_;  // CDP session of this environment's window
    int generation_ = -1;  // browser generation the session belongs to
    std::string site_path_;
    std::string goal_;
    int steps_ = 0;
    long long cdp_ms_ = 0;
    long long settle_ms_ = 0;
    nlohmann::json last_raw_;  // last page read (screen, popup, buttons, state)
};
