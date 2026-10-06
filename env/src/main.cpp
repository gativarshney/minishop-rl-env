// JSON-lines front end: one request per stdin line, one reply per stdout line.
#include "env.hpp"
#include <iostream>
#include <string>
#include <csignal>
#include <map>
#include <memory>
#include <mutex>
#include <thread>
#include <vector>
#include <atomic>
#include <chrono>
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

    Browser browser;  // one browser, declared first so it is destroyed last
    // Environment slots, picked by the optional "env" field of a request (default 0).
    // Each slot drives its own window. The client sends one request per slot at a time.
    std::map<int, std::unique_ptr<MinishopEnv>> slots;
    std::atomic<int> running{0};  // requests still being handled
    std::mutex out_mutex;

    // Runs one request and prints one reply line. Runs in its own thread so that
    // requests for different slots are handled at the same time.
    auto handle = [&](MinishopEnv* env, int slot, json req) {
        json res;
        try {
            std::string cmd = req.value("cmd", "");
            if (cmd == "reset") {
                json r = env->reset(req.value("item", "blue-mug"), req.value("qty", 1), req.value("seed", 42),
                                    req.value("popup_p", 0.0), req.value("delay_p", 0.0));
                res = {{"status", "ok"}, {"observation", r["observation"]}, {"info", r["info"]}};
            } else {
                StepResult r = env->step(req.value("action", "wait"), req.value("i", -1));
                res = {{"status", "ok"}, {"observation", r.observation}, {"reward", r.reward},
                       {"done", r.done}, {"truncated", r.truncated}, {"info", r.info},
                       {"time_ms", r.time_ms}, {"cdp_ms", r.cdp_ms}, {"settle_ms", r.settle_ms},
                       {"popup_showing", r.popup_showing}};
            }
        } catch (const std::exception& e) {
            res = {{"status", "error"}, {"error", e.what()}};
        }
        res["env"] = slot;
        {
            std::lock_guard<std::mutex> lock(out_mutex);
            std::cout << res.dump() << std::endl;  // endl flushes so Python never waits on a buffer
        }
        running--;
    };

    std::string line;
    while (std::getline(std::cin, line)) {
        if (line.empty()) continue;
        json req = json::parse(line, nullptr, false);
        if (req.is_discarded()) {
            std::lock_guard<std::mutex> lock(out_mutex);
            std::cout << json{{"status", "error"}, {"error", "bad json"}}.dump() << std::endl;
            continue;
        }
        std::string cmd = req.value("cmd", "");
        if (cmd == "close") break;
        if (cmd != "reset" && cmd != "step") {
            std::lock_guard<std::mutex> lock(out_mutex);
            std::cout << json{{"status", "error"}, {"error", "unknown command"}}.dump() << std::endl;
            continue;
        }
        if (cmd == "reset") {
            // Start (or restart) the browser here on the main thread: on Linux the browser is
            // tied to the thread that started it, and worker threads end after every request.
            try { browser.ensureLaunched(); } catch (...) {}  // the worker reports the error
        }
        int slot = req.value("env", 0);
        auto& env = slots[slot];
        if (!env) env = std::make_unique<MinishopEnv>(browser, site);
        running++;
        std::thread(handle, env.get(), slot, req).detach();  // detached so finished threads are freed
    }
    while (running > 0) std::this_thread::sleep_for(std::chrono::milliseconds(5));  // let running requests finish before the browser goes away
    browser.close();
    return 0;
}
