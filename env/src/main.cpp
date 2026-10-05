// JSON-lines front end: one request per stdin line, one reply per stdout line.
#include "env.hpp"
#include <iostream>
#include <string>
#include <csignal>
#ifdef _WIN32
#include <windows.h>
#endif

using json = nlohmann::json;

// If we are interrupted or the console closes, take the browser down with us.
#ifdef _WIN32
static BOOL WINAPI onConsole(DWORD) {
    Browser::emergencyKill();
    return FALSE;  // let the default handler end the process
}
#else
static void onSignal(int sig) {
    Browser::emergencyKill();
    std::signal(sig, SIG_DFL);
    std::raise(sig);
}
#endif

int main(int argc, char** argv) {
    std::string site;
    for (int i = 1; i + 1 < argc; ++i)
        if (std::string(argv[i]) == "--site") site = argv[i + 1];
    if (site.empty()) {
        std::cerr << "usage: minishop_env --site <absolute path to index.html>\n";
        return 2;
    }

#ifdef _WIN32
    SetConsoleCtrlHandler(onConsole, TRUE);
#else
    std::signal(SIGINT, onSignal);
    std::signal(SIGTERM, onSignal);
    std::signal(SIGHUP, onSignal);
    std::signal(SIGPIPE, SIG_IGN);
#endif

    MinishopEnv env(site);  // its destructor closes the browser on normal exit
    std::string line;
    while (std::getline(std::cin, line)) {
        if (line.empty()) continue;
        json res;
        try {
            json req = json::parse(line);
            std::string cmd = req.value("cmd", "");
            if (cmd == "reset") {
                json obs = env.reset(req.value("item", "blue-mug"), req.value("qty", 1), req.value("seed", 42),
                                     req.value("popup_p", 0.0), req.value("delay_p", 0.0));
                res = {{"status", "ok"}, {"observation", obs}};
            } else if (cmd == "step") {
                StepResult r = env.step(req.value("action", "wait"), req.value("i", -1));
                res = {{"status", "ok"}, {"observation", r.observation}, {"reward", r.reward},
                       {"done", r.done}, {"truncated", r.truncated}, {"info", r.info},
                       {"time_ms", r.time_ms}, {"cdp_ms", r.cdp_ms}, {"settle_ms", r.settle_ms},
                       {"popup_showing", r.popup_showing}};
            } else if (cmd == "close") {
                break;
            } else {
                res = {{"status", "error"}, {"error", "unknown command"}};
            }
        } catch (const std::exception& e) {
            res = {{"status", "error"}, {"error", e.what()}};
        }
        std::cout << res.dump() << std::endl;  // endl flushes so Python never waits on a buffer
    }
    env.close();
    return 0;
}
