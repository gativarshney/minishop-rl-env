#pragma once
#include <string>
#include <nlohmann/json.hpp>
#include <ixwebsocket/IXWebSocket.h>
#include <future>
#include <unordered_map>
#include <mutex>

class Browser {
public:
    Browser();
    ~Browser();

    void launch(const std::string& start_url = "about:blank");
    void close();

    nlohmann::json sendCommand(const std::string& method, const nlohmann::json& params = nlohmann::json::object());

private:
    std::string findChromeBinary();
    std::string createTempDir();
    void removeTempDir(const std::string& path);
    std::string readWsUrl(const std::string& port_file_path);

    std::string ws_url_;
    ix::WebSocket webSocket_;
    int next_id_ = 1;

    std::unordered_map<int, std::promise<nlohmann::json>> pending_requests_;
    std::mutex ws_mutex_;

#ifdef _WIN32
    void* process_handle_ = nullptr;
    void* job_handle_ = nullptr;
#else
    int pid_ = -1;
#endif
    std::string temp_dir_;
};
