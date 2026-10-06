#include "browser.hpp"
#include <fstream>
#include <thread>
#include <chrono>
#include <filesystem>
#include <stdexcept>
#include <cstdlib>
#include <vector>
#include <ixwebsocket/IXNetSystem.h>

#ifdef _WIN32
#include <windows.h>
#else
#include <unistd.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <sys/prctl.h>
#include <signal.h>
#include <fcntl.h>
#endif

// Process-wide handles so a signal handler can kill the browser too.
#ifdef _WIN32
static HANDLE g_job = nullptr;  // job object: closing it kills Chrome and its children
static DWORD g_pid = 0;
#else
static volatile pid_t g_pgid = -1;  // Chrome is its own process group leader
#endif

Browser::Browser() {}
Browser::~Browser() { close(); }

std::string Browser::findChromeBinary() {
    if (const char* env_p = std::getenv("CHROME_BIN")) return std::string(env_p);
#ifdef _WIN32
    const char* paths[] = {
        "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
        "C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe",
        "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
        "C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe"};
#else
    const char* paths[] = {"/usr/bin/google-chrome", "/usr/bin/chromium",
                           "/usr/bin/chromium-browser"};
#endif
    for (const char* p : paths)
        if (std::filesystem::exists(p)) return p;
    throw std::runtime_error("no Chrome/Edge/Chromium found (set CHROME_BIN)");
}

// Chrome writes the debugging port and browser path here once it is listening.
std::string Browser::readWsUrl(const std::string& port_file, int timeout_ms) {
    auto start = std::chrono::steady_clock::now();
    while (std::chrono::steady_clock::now() - start < std::chrono::milliseconds(timeout_ms)) {
        std::ifstream file(port_file);
        std::string port, path;
        if (file.is_open() && std::getline(file, port) && std::getline(file, path)) {
            // strip a possible trailing \r so the URL stays valid
            while (!port.empty() && (port.back() == '\r' || port.back() == ' ')) port.pop_back();
            while (!path.empty() && (path.back() == '\r' || path.back() == ' ')) path.pop_back();
            return "ws://127.0.0.1:" + port + path;
        }
        std::this_thread::sleep_for(std::chrono::milliseconds(50));
    }
    throw std::runtime_error("timed out waiting for DevToolsActivePort");
}

void Browser::launch() {
    std::string bin = findChromeBinary();
    // unique profile dir per run; it is also how leftover processes are recognised
    temp_dir_ = (std::filesystem::temp_directory_path() /
                 ("minishop_profile_" + std::to_string(std::chrono::system_clock::now().time_since_epoch().count()))).string();
    std::filesystem::create_directories(temp_dir_);

    std::vector<std::string> args = {
        bin, "--headless=new", "--remote-debugging-port=0",
        "--remote-allow-origins=*",  // Chrome rejects the WebSocket handshake without this
        "--user-data-dir=" + temp_dir_,
        "--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage",
        "--no-first-run", "--no-default-browser-check",
        // several tabs share one browser: keep background tabs running at full speed
        "--disable-background-timer-throttling", "--disable-renderer-backgrounding",
        "--disable-backgrounding-occluded-windows",
        "--window-size=1000,800", "about:blank"};

#ifdef _WIN32
    // Build one command line; every argument is quoted so paths with spaces survive.
    std::string cmd;
    for (auto& a : args) cmd += "\"" + a + "\" ";
    int n = MultiByteToWideChar(CP_UTF8, 0, cmd.c_str(), -1, nullptr, 0);
    std::vector<wchar_t> wcmd(n);  // CreateProcessW needs a writable buffer
    MultiByteToWideChar(CP_UTF8, 0, cmd.c_str(), -1, wcmd.data(), n);
    int m = MultiByteToWideChar(CP_UTF8, 0, bin.c_str(), -1, nullptr, 0);
    std::vector<wchar_t> wbin(m);
    MultiByteToWideChar(CP_UTF8, 0, bin.c_str(), -1, wbin.data(), m);

    STARTUPINFOW si;
    PROCESS_INFORMATION pi;
    ZeroMemory(&si, sizeof(si));
    si.cb = sizeof(si);
    ZeroMemory(&pi, sizeof(pi));
    // Suspended so we can put it in the job before it spawns children.
    if (!CreateProcessW(wbin.data(), wcmd.data(), NULL, NULL, FALSE,
                        CREATE_SUSPENDED | CREATE_NO_WINDOW, NULL, NULL, &si, &pi))
        throw std::runtime_error("CreateProcessW failed, error " + std::to_string(GetLastError()));

    HANDLE job = CreateJobObjectW(NULL, NULL);
    if (job) {
        JOBOBJECT_EXTENDED_LIMIT_INFORMATION jeli = {};
        jeli.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE;
        SetInformationJobObject(job, JobObjectExtendedLimitInformation, &jeli, sizeof(jeli));
        if (!AssignProcessToJobObject(job, pi.hProcess)) {
            CloseHandle(job);  // fall back to taskkill in close()
            job = nullptr;
        }
    }
    g_job = job;
    g_pid = pi.dwProcessId;
    ResumeThread(pi.hThread);
    CloseHandle(pi.hThread);
    CloseHandle(pi.hProcess);
#else
    pid_t pid = fork();
    if (pid < 0) throw std::runtime_error("fork failed");
    if (pid == 0) {
        setsid();                          // own process group so kill(-pgid) gets every child
        prctl(PR_SET_PDEATHSIG, SIGKILL);  // die with the env even if it crashes
        int devnull = open("/dev/null", O_RDWR);
        dup2(devnull, 0);
        dup2(devnull, 1);  // stdout is our JSON channel, Chrome must not write to it
        dup2(devnull, 2);
        std::vector<char*> argv;
        for (auto& a : args) argv.push_back(const_cast<char*>(a.c_str()));
        argv.push_back(nullptr);
        execv(bin.c_str(), argv.data());
        _exit(127);
    }
    g_pgid = pid;
#endif
    launched_ = true;
    generation_++;

    try {
        std::string ws_url = readWsUrl((std::filesystem::path(temp_dir_) / "DevToolsActivePort").string(), 15000);

        ix::initNetSystem();
        webSocket_.setUrl(ws_url);
        webSocket_.disableAutomaticReconnection();  // a dead browser must fail fast, not retry forever
        webSocket_.setHandshakeTimeout(10);
        webSocket_.disablePerMessageDeflate();

        auto connected = std::make_shared<std::promise<bool>>();
        auto fut = connected->get_future();
        auto once = std::make_shared<std::once_flag>();
        webSocket_.setOnMessageCallback([this, connected, once](const ix::WebSocketMessagePtr& msg) {
            if (msg->type == ix::WebSocketMessageType::Open) {
                std::call_once(*once, [&] { connected->set_value(true); });
            } else if (msg->type == ix::WebSocketMessageType::Error) {
                std::call_once(*once, [&] { connected->set_value(false); });
            } else if (msg->type == ix::WebSocketMessageType::Message) {
                auto j = nlohmann::json::parse(msg->str, nullptr, false);
                if (j.is_discarded() || !j.contains("id")) return;  // events are ignored
                std::lock_guard<std::mutex> lock(ws_mutex_);
                auto it = pending_requests_.find(j["id"].get<int>());
                if (it != pending_requests_.end()) {
                    it->second.set_value(j);
                    pending_requests_.erase(it);
                }
            }
        });
        webSocket_.start();
        if (fut.wait_for(std::chrono::seconds(10)) != std::future_status::ready || !fut.get())
            throw std::runtime_error("DevTools WebSocket connect failed");

    } catch (...) {
        close();  // never leave a half started browser behind
        throw;
    }
}

bool Browser::rawSend(const std::string& method, const nlohmann::json& params,
                      const std::string& session, int timeout_ms, nlohmann::json& out) {
    int id;
    std::future<nlohmann::json> fut;
    {
        std::lock_guard<std::mutex> lock(ws_mutex_);
        id = next_id_++;
        fut = pending_requests_[id].get_future();
    }
    nlohmann::json req = {{"id", id}, {"method", method}, {"params", params}};
    if (!session.empty()) req["sessionId"] = session;
    webSocket_.send(req.dump());
    if (fut.wait_for(std::chrono::milliseconds(timeout_ms)) != std::future_status::ready) {
        std::lock_guard<std::mutex> lock(ws_mutex_);
        pending_requests_.erase(id);
        return false;
    }
    out = fut.get();
    return true;
}

void Browser::ensureLaunched() {
    std::lock_guard<std::mutex> lock(launch_mutex_);
    if (launched_ && webSocket_.getReadyState() == ix::ReadyState::Open) return;
    if (launched_) close();  // browser died: clean up before starting a new one
    launch();
}

// Each environment gets its own tab. Flatten mode lets one WebSocket carry all tab sessions.
std::string Browser::newPage() {
    nlohmann::json out;
    if (!rawSend("Target.createTarget", {{"url", "about:blank"}, {"newWindow", true}, {"width", 1000}, {"height", 800}}, "", 5000, out) || out.contains("error"))
        throw std::runtime_error("createTarget failed");
    std::string target_id = out["result"]["targetId"];
    if (!rawSend("Target.attachToTarget", {{"targetId", target_id}, {"flatten", true}}, "", 5000, out) ||
        out.contains("error"))
        throw std::runtime_error("attachToTarget failed");
    std::string session = out["result"]["sessionId"];
    return session;
}

nlohmann::json Browser::sendCommand(const std::string& session, const std::string& method,
                                    const nlohmann::json& params, int timeout_ms) {
    nlohmann::json out;
    if (!rawSend(method, params, session, timeout_ms, out))
        throw std::runtime_error("CDP timeout: " + method);
    if (out.contains("error"))
        throw std::runtime_error("CDP error in " + method + ": " + out["error"].dump());
    return out;
}

void Browser::killProcessTree() {
#ifdef _WIN32
    if (g_job) {
        TerminateJobObject(g_job, 1);
        CloseHandle(g_job);
        g_job = nullptr;
    } else if (g_pid) {
        // no job (assignment failed): taskkill /T walks the child tree
        std::string cmd = "taskkill /T /F /PID " + std::to_string(g_pid) + " >nul 2>&1";
        std::system(cmd.c_str());
    }
    g_pid = 0;
#else
    if (g_pgid > 0) {
        kill(-g_pgid, SIGKILL);
        waitpid(g_pgid, nullptr, 0);
        g_pgid = -1;
    }
#endif
}

void Browser::close() {
    if (launched_) {
        webSocket_.stop();
        killProcessTree();
        launched_ = false;
    }
    if (!temp_dir_.empty()) {
        // Chrome may hold files for a moment after dying, so retry a few times
        for (int i = 0; i < 20; ++i) {
            std::error_code ec;
            std::filesystem::remove_all(temp_dir_, ec);
            if (!ec) break;
            std::this_thread::sleep_for(std::chrono::milliseconds(100));
        }
        temp_dir_.clear();
    }
}

void Browser::emergencyKill() {
#ifdef _WIN32
    if (g_job) {
        TerminateJobObject(g_job, 1);
    } else if (g_pid) {
        std::string cmd = "taskkill /T /F /PID " + std::to_string(g_pid) + " >nul 2>&1";
        std::system(cmd.c_str());
    }
#else
    if (g_pgid > 0) kill(-g_pgid, SIGKILL);
#endif
}
