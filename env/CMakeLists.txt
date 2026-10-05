cmake_minimum_required(VERSION 3.14)
project(MinishopEnv CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

include(FetchContent)

# json
FetchContent_Declare(json
  URL https://github.com/nlohmann/json/releases/download/v3.11.2/json.tar.xz
)
set(JSON_BuildTests OFF CACHE INTERNAL "")
set(CMAKE_POLICY_VERSION_MINIMUM "3.5" CACHE STRING "" FORCE)
FetchContent_MakeAvailable(json)

# ixwebsocket
FetchContent_Declare(ixwebsocket
  GIT_REPOSITORY https://github.com/machinezone/IXWebSocket.git
  GIT_TAG v11.4.4
)
set(USE_TLS OFF CACHE BOOL "" FORCE)
set(USE_ZLIB OFF CACHE BOOL "" FORCE)
set(IXWEBSOCKET_INSTALL OFF CACHE BOOL "" FORCE)
set(USE_TEST OFF CACHE BOOL "" FORCE)
FetchContent_MakeAvailable(ixwebsocket)

add_executable(minishop_env src/main.cpp src/browser.cpp src/env.cpp)
target_link_libraries(minishop_env PRIVATE nlohmann_json::nlohmann_json ixwebsocket)

if(WIN32)
  target_link_libraries(minishop_env PRIVATE ws2_32 crypt32)
endif()
