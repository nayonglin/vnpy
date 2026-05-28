#pragma once

#include <algorithm>
#include <cstdlib>
#include <cstring>
#include <dlfcn.h>
#include <stdexcept>
#include <string>
#include <vector>

namespace ctp_native {

struct SystemInfoResult {
    std::vector<char> bytes;
    std::string source;
};

inline std::string env_or_empty(const char *name) {
    const char *value = std::getenv(name);
    return value ? std::string(value) : std::string();
}

inline bool env_flag(const char *name) {
    std::string value = env_or_empty(name);
    return value == "1" || value == "true" || value == "TRUE" ||
           value == "yes" || value == "YES";
}

inline void *open_collector_library() {
    std::string path = env_or_empty("CTP_SYSTEM_INFO_DYLIB");
    if (path.empty()) {
        return RTLD_DEFAULT;
    }
    void *handle = dlopen(path.c_str(), RTLD_NOW | RTLD_LOCAL);
    if (!handle) {
        throw std::runtime_error("dlopen CTP_SYSTEM_INFO_DYLIB failed: " + std::string(dlerror()));
    }
    return handle;
}

inline void *resolve_system_info_symbol(void *handle, std::string &symbol_name) {
    const char *names[] = {
        "CTP_GetSystemInfoUnAesEncode",
        "_CTP_GetSystemInfoUnAesEncode",
        "_Z28CTP_GetSystemInfoUnAesEncodePcRi",
        "__Z28CTP_GetSystemInfoUnAesEncodePcRi",
        "CTP_GetRealSystemInfo",
        "_Z21CTP_GetRealSystemInfoPcRi",
        "__Z21CTP_GetRealSystemInfoPcRi",
    };
    for (const char *name : names) {
        dlerror();
        void *symbol = dlsym(handle, name);
        if (symbol) {
            symbol_name = name;
            return symbol;
        }
    }
    return nullptr;
}

inline SystemInfoResult collect_via_official_function(std::size_t max_len) {
    void *handle = open_collector_library();
    std::string symbol_name;
    void *symbol = resolve_system_info_symbol(handle, symbol_name);
    if (!symbol) {
        throw std::runtime_error("CTP system-info collector symbol not found");
    }

    std::vector<char> buffer(std::max<std::size_t>(max_len, 270), 0);
    int length = 0;
    using CollectorFunc = int (*)(char *, int &);
    auto collect = reinterpret_cast<CollectorFunc>(symbol);
    int collect_code = collect(buffer.data(), length);

    if (collect_code != 0) {
        throw std::runtime_error(
            "CTP system-info collector returned error code=" + std::to_string(collect_code) +
            " length=" + std::to_string(length));
    }
    if (length <= 0 || static_cast<std::size_t>(length) > max_len) {
        throw std::runtime_error("CTP system-info collector returned invalid length=" + std::to_string(length));
    }
    buffer.resize(static_cast<std::size_t>(length));
    return {buffer, "collector_api:" + symbol_name};
}

inline SystemInfoResult load_system_info(std::size_t max_len) {
    std::string source = env_or_empty("CTP_SYSTEM_INFO_SOURCE");
    if (source.empty()) {
        source = "auto";
    }

    if (source == "collector_api" || source == "auto") {
        try {
            return collect_via_official_function(max_len);
        } catch (const std::exception &) {
            if (source == "collector_api" || env_flag("CTP_NATIVE_REQUIRE_SYSTEM_INFO")) {
                throw;
            }
        }
    }

    std::string env_info = env_or_empty("CTP_CLIENT_SYSTEM_INFO");
    if (!env_info.empty()) {
        std::size_t copy_len = std::min<std::size_t>(env_info.size(), max_len);
        return {std::vector<char>(env_info.data(), env_info.data() + copy_len), "env:CTP_CLIENT_SYSTEM_INFO"};
    }

    if (env_flag("CTP_NATIVE_REQUIRE_SYSTEM_INFO")) {
        throw std::runtime_error("CTP native system info is required but no collector bytes were available");
    }
    return {{}, "empty"};
}

}  // namespace ctp_native
