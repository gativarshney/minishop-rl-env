#include "browser.hpp"
#include <iostream>

int main() {
    std::cout << "Starting browser launcher test..." << std::endl;
    try {
        Browser b;
        b.launch("about:blank");
        auto res = b.sendCommand("Target.getTargets");
        std::cout << "Connected! Targets: " << res.dump() << std::endl;
        b.close();
    } catch(const std::exception& e) {
        std::cerr << "Error: " << e.what() << std::endl;
        return 1;
    }
    return 0;
}
