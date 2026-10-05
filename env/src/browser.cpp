#include "browser.hpp"
#include <iostream>
#include <fstream>
#include <thread>
#include <ixwebsocket/IXNetSystem.h>
#include <chrono>
#include <filesystem>
#include <stdexcept>
#include <cstdlib>

#ifdef _WIN32
#include <windows.h>
#else
#include <unistd.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <signal.h>
#endif

Browser::Browser() {}

Browser::~Browser() {
    close();
}

std::string Browser::findChromeBinary() {
    if (const char* env_p = std::getenv("CHROME_BIN")) {
        return std::string(env_p);
    }
#ifdef _WIN32
    std::string paths[] = {
        "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
        "C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe",
        "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
        "C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe"
    };
    for (const auto& p : paths) {
        if (std::filesystem::exists(p)) return p;
    }
    throw std::runtime_error("Chrome/Edge not found");
#else
    std::string paths[] = {
        "/usr/bin/chromium",
        "/usr/bin/chromium-browser",
        "/usr/bin/google-chrome"
    };
    for (const auto& p : paths) {
        if (std::filesystem::exists(p)) return p;
    }
    throw std::runtime_error("Chromium not found");
#endif
}

std::string Browser::createTempDir() {
    auto tmp_dir = std::filesystem::temp_directory_path() / ("minishop_" + std::to_string(std::chrono::system_clock::now().time_since_epoch().count()));
    std::filesystem::create_directories(tmp_dir);
    return tmp_dir.string();
}

void Browser::removeTempDir(const std::string& path) {
    try {
        std::filesystem::remove_all(path);
    } catch (...) {}
}

std::string Browser::readWsUrl(const std::string& port_file_path) {
    for (int i = 0; i < 50; ++i) {
        std::ifstream file(port_file_path);
        if (file.is_open()) {
            std::string port_str;
            std::string path_str;
            if (std::getline(file, port_str) && std::getline(file, path_str)) {
                return "ws://127.0.0.1:" + port_str + path_str;
            }
        }
        std::this_thread::sleep_for(std::chrono::milliseconds(100));
    }
    throw std::runtime_error("Failed to read DevToolsActivePort");
}

void Browser::launch(const std::string& start_url) {
    std::string bin = findChromeBinary();
    temp_dir_ = createTempDir();
    
    std::string cmd = "\"" + bin + "\" --headless=new --remote-debugging-port=0 --user-data-dir=\"" + temp_dir_ + "\" " +
                      "--no-sandbox --disable-gpu --disable-dev-shm-usage --window-size=1000,800 \"" + start_url + "\"";

#ifdef _WIN32
    STARTUPINFOA si;
    PROCESS_INFORMATION pi;
    ZeroMemory(&si, sizeof(si));
    si.cb = sizeof(si);
    ZeroMemory(&pi, sizeof(pi));

    std::vector<char> cmd_buf(cmd.begin(), cmd.end());
    cmd_buf.push_back('\0');
    if (!CreateProcessA(NULL, cmd_buf.data(), NULL, NULL, FALSE, CREATE_SUSPENDED, NULL, NULL, &si, &pi)) {
        throw std::runtime_error("Failed to start Chrome, error: " + std::to_string(GetLastError()) + ", cmd: " + cmd);
    }

    job_handle_ = CreateJobObjectA(NULL, NULL);
    if (job_handle_) {
        JOBOBJECT_EXTENDED_LIMIT_INFORMATION jeli = { 0 };
        jeli.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE;
        SetInformationJobObject(job_handle_, JobObjectExtendedLimitInformation, &jeli, sizeof(jeli));
        if (!AssignProcessToJobObject(job_handle_, pi.hProcess)) {
            // Failed to assign (e.g. nested job), continue anyway
            CloseHandle(job_handle_);
            job_handle_ = nullptr;
        }
    }
    ResumeThread(pi.hThread);
    process_handle_ = pi.hProcess;
    CloseHandle(pi.hThread);
#else
    pid_ = fork();
    if (pid_ == 0) {
        setpgid(0, 0);
        execl("/bin/sh", "sh", "-c", cmd.c_str(), NULL);
        exit(1);
    }
#endif

    std::string port_file = (std::filesystem::path(temp_dir_) / "DevToolsActivePort").string();
    ws_url_ = readWsUrl(port_file);

    ix::initNetSystem();
    webSocket_.setUrl(ws_url_);
    
    std::promise<void> connected;
    webSocket_.setOnMessageCallback([this, &connected](const ix::WebSocketMessagePtr& msg) {
        if (msg->type == ix::WebSocketMessageType::Open) {
            connected.set_value();
        } else if (msg->type == ix::WebSocketMessageType::Message) {
            auto j = nlohmann::json::parse(msg->str);
            if (j.contains("id")) {
                int id = j["id"];
                std::lock_guard<std::mutex> lock(ws_mutex_);
                auto it = pending_requests_.find(id);
                if (it != pending_requests_.end()) {
                    it->second.set_value(j);
                    pending_requests_.erase(it);
                }
            }
        }
    });

    webSocket_.start();
    connected.get_future().wait();
}

nlohmann::json Browser::sendCommand(const std::string& method, const nlohmann::json& params) {
    int id;
    std::future<nlohmann::json> fut;
    {
        std::lock_guard<std::mutex> lock(ws_mutex_);
        id = next_id_++;
        fut = pending_requests_[id].get_future();
    }
    
    nlohmann::json req = {
        {"id", id},
        {"method", method},
        {"params", params}
    };
    
    webSocket_.send(req.dump());
    return fut.get();
}

void Browser::close() {
    webSocket_.stop();
#ifdef _WIN32
    if (job_handle_) {
        CloseHandle(job_handle_); // This kills all processes in the job
        job_handle_ = nullptr;
    }
    if (process_handle_) {
        CloseHandle(process_handle_);
        process_handle_ = nullptr;
    }
#else
    if (pid_ > 0) {
        kill(-pid_, SIGKILL);
        waitpid(pid_, nullptr, 0);
        pid_ = -1;
    }
#endif
    if (!temp_dir_.empty()) {
        removeTempDir(temp_dir_);
        temp_dir_.clear();
    }
}
