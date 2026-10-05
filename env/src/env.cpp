#include "env.hpp"

MinishopEnv::MinishopEnv() {}
MinishopEnv::~MinishopEnv() {}

nlohmann::json MinishopEnv::reset(const std::string& item, int qty, int seed, double popup_p, double delay_p) {
    return nlohmann::json::object();
}

StepResult MinishopEnv::step(int action_i, const std::string& action_type) {
    return {};
}

nlohmann::json MinishopEnv::getObservation() {
    return nlohmann::json::object();
}

void MinishopEnv::click(int x, int y) {}
void MinishopEnv::waitForSettle() {}
