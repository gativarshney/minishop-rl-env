#pragma once
#include <string>
#include <nlohmann/json.hpp>
#include <ixwebsocket/IXWebSocket.h>
#include <future>
#include <unordered_map>
#include <mutex>

// Starts one headless Chrome/Edge and talks raw CDP to it over a WebSocket.
class Browser {
public:
    Browser();
    ~Browser();

    // Starts the browser if it is not running (thread safe). Throws on failure.
    void ensureLaunched();
    // Kills the whole browser process tree and removes the profile dir.
    void close();
    bool alive() const { return launched_; }
    // Increases every time the browser is (re)started; old page sessions are then invalid.
    int generation() const { return generation_; }

    // Opens a new tab in the same browser and returns its CDP session id.
    std::string newPage();

    // Sends a CDP command to one page (session) and waits at most timeout_ms for the reply.
    nlohmann::json sendCommand(const std::string& session, const std::string& method,
                               const nlohmann::json& params = nlohmann::json::object(),
                               int timeout_ms = 5000);

    // Called from signal / console handlers: kill the browser without cleanup.
    static void emergencyKill();

private:
    void launch();
    std::string findChromeBinary();
    std::string readWsUrl(const std::string& port_file_path, int timeout_ms);
    void killProcessTree();
    bool rawSend(const std::string& method, const nlohmann::json& params,
                 const std::string& session, int timeout_ms, nlohmann::json& out);

    ix::WebSocket webSocket_;
    int generation_ = 0;
    std::mutex launch_mutex_;
    int next_id_ = 1;
    bool launched_ = false;

    std::unordered_map<int, std::promise<nlohmann::json>> pending_requests_;
    std::mutex ws_mutex_;

    std::string temp_dir_;
};
