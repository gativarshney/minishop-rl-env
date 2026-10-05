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

    // Starts the browser and attaches to its first page. Throws on failure.
    void launch();
    // Kills the whole browser process tree and removes the profile dir.
    void close();
    bool alive() const { return launched_; }

    // Sends a CDP command to the page and waits at most timeout_ms for the reply.
    nlohmann::json sendCommand(const std::string& method,
                               const nlohmann::json& params = nlohmann::json::object(),
                               int timeout_ms = 5000);

    // Called from signal / console handlers: kill the browser without cleanup.
    static void emergencyKill();

private:
    std::string findChromeBinary();
    std::string readWsUrl(const std::string& port_file_path, int timeout_ms);
    void killProcessTree();
    bool rawSend(const std::string& method, const nlohmann::json& params,
                 const std::string& session, int timeout_ms, nlohmann::json& out);

    ix::WebSocket webSocket_;
    std::string session_id_;  // CDP session of the page target
    int next_id_ = 1;
    bool launched_ = false;

    std::unordered_map<int, std::promise<nlohmann::json>> pending_requests_;
    std::mutex ws_mutex_;

    std::string temp_dir_;
};
