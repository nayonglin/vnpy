#include <chrono>
#include <condition_variable>
#include <cstdlib>
#include <cstring>
#include <filesystem>
#include <iostream>
#include <mutex>
#include <stdexcept>
#include <string>
#include <thread>
#include <vector>

#include "ctp_native_system_info.hpp"
#include "ThostFtdcTraderApi.h"

namespace {

std::string env_required(const char *name) {
    const char *value = std::getenv(name);
    if (!value || std::strlen(value) == 0) {
        std::cerr << "Missing required env: " << name << std::endl;
        std::exit(2);
    }
    return std::string(value);
}

template <std::size_t N>
void copy_field(char (&dst)[N], const std::string &src) {
    std::memset(dst, 0, N);
    std::strncpy(dst, src.c_str(), N - 1);
}

std::string rsp_info(CThostFtdcRspInfoField *info) {
    if (!info) {
        return "ErrorID=0 ErrorMsg=";
    }
    return "ErrorID=" + std::to_string(info->ErrorID) + " ErrorMsg=" + std::string(info->ErrorMsg);
}

bool rsp_ok(CThostFtdcRspInfoField *info) {
    return !info || info->ErrorID == 0;
}

class NativeTdProbe final : public CThostFtdcTraderSpi {
public:
    NativeTdProbe(CThostFtdcTraderApi *api, int wait_seconds)
        : api_(api), wait_seconds_(wait_seconds) {
        broker_id_ = env_required("CTP_BROKERID");
        user_id_ = env_required("CTP_USERID");
        password_ = env_required("CTP_PASSWORD");
        td_address_ = env_required("CTP_TD_ADDRESS");
        app_id_ = env_required("CTP_APPID");
        auth_code_ = env_required("CTP_AUTH_CODE");

        const char *product = std::getenv("CTP_PRODUCT_INFO");
        if (product) {
            product_info_ = product;
        }

        try {
            system_info_ = ctp_native::load_system_info(sizeof(TThostFtdcClientSystemInfoType));
        } catch (const std::exception &exc) {
            std::cerr << "Failed to load CTP native system info: " << exc.what() << std::endl;
            std::exit(3);
        }

        const char *register_user_system_info = std::getenv("CTP_NATIVE_REGISTER_USER_SYSTEM_INFO");
        if (register_user_system_info && std::string(register_user_system_info) == "1") {
            register_user_system_info_ = true;
        }

        const char *submit_user_system_info = std::getenv("CTP_NATIVE_SUBMIT_USER_SYSTEM_INFO");
        if (submit_user_system_info && std::string(submit_user_system_info) == "1") {
            submit_user_system_info_ = true;
        }
    }

    void log(const std::string &message) {
        auto elapsed = std::chrono::duration<double>(std::chrono::steady_clock::now() - start_).count();
        std::cout << "[" << elapsed << "s] " << message << std::endl;
    }

    void start() {
        start_ = std::chrono::steady_clock::now();
        log("native C++ TD-only probe starting");
        log("api_version=" + std::string(CThostFtdcTraderApi::GetApiVersion()));
        log("CTP_BROKERID=" + broker_id_);
        log("CTP_TD_ADDRESS=" + td_address_);
        log("CTP_USERID=set(len=" + std::to_string(user_id_.size()) + ")");
        log("CTP_PASSWORD=set(len=" + std::to_string(password_.size()) + ")");
        log("CTP_APPID=set(len=" + std::to_string(app_id_.size()) + ")");
        log("CTP_AUTH_CODE=set(len=" + std::to_string(auth_code_.size()) + ")");
        log("CTP_SYSTEM_INFO_SOURCE=" + system_info_.source);
        log("CTP_CLIENT_SYSTEM_INFO=" + std::string(system_info_.bytes.empty() ? "empty" : "set(len=" + std::to_string(system_info_.bytes.size()) + ")"));
        log("CTP_NATIVE_REGISTER_USER_SYSTEM_INFO=" + std::string(register_user_system_info_ ? "1" : "0"));
        log("CTP_NATIVE_SUBMIT_USER_SYSTEM_INFO=" + std::string(submit_user_system_info_ ? "1" : "0"));

        api_->RegisterSpi(this);
        api_->SubscribePrivateTopic(THOST_TERT_QUICK);
        api_->SubscribePublicTopic(THOST_TERT_QUICK);

        std::vector<char> front(td_address_.begin(), td_address_.end());
        front.push_back('\0');
        api_->RegisterFront(front.data());
        api_->Init();

        std::unique_lock<std::mutex> lock(mutex_);
        cv_.wait_for(lock, std::chrono::seconds(wait_seconds_), [this] { return done_; });

        log(
            "summary front_connected=" + std::string(front_connected_ ? "true" : "false") +
            " auth_ok=" + std::string(auth_ok_ ? "true" : "false") +
            " login_ok=" + std::string(login_ok_ ? "true" : "false") +
            " settlement_ok=" + std::string(settlement_ok_ ? "true" : "false") +
            " account_count=" + std::to_string(account_count_) +
            " position_count=" + std::to_string(position_count_));
    }

    void OnFrontConnected() override {
        front_connected_ = true;
        log("OnFrontConnected: trading front connected");

        CThostFtdcReqAuthenticateField req{};
        copy_field(req.BrokerID, broker_id_);
        copy_field(req.UserID, user_id_);
        copy_field(req.AuthCode, auth_code_);
        copy_field(req.AppID, app_id_);
        if (!product_info_.empty()) {
            copy_field(req.UserProductInfo, product_info_);
        }

        int ret = api_->ReqAuthenticate(&req, next_reqid());
        log("ReqAuthenticate ret=" + std::to_string(ret));
    }

    void OnFrontDisconnected(int reason) override {
        log("OnFrontDisconnected reason=" + std::to_string(reason));
        done();
    }

    void OnRspAuthenticate(CThostFtdcRspAuthenticateField *, CThostFtdcRspInfoField *info, int reqid, bool last) override {
        log("OnRspAuthenticate reqid=" + std::to_string(reqid) + " last=" + (last ? "true " : "false ") + rsp_info(info));
        if (!rsp_ok(info)) {
            done();
            return;
        }
        auth_ok_ = true;
        if (register_user_system_info_) {
            register_user_system_info();
        }
        login();
    }

    void OnRspUserLogin(CThostFtdcRspUserLoginField *login_rsp, CThostFtdcRspInfoField *info, int reqid, bool last) override {
        std::string extra;
        if (login_rsp) {
            extra = " FrontID=" + std::to_string(login_rsp->FrontID) +
                    " SessionID=" + std::to_string(login_rsp->SessionID) +
                    " TradingDay=" + std::string(login_rsp->TradingDay) +
                    " LoginTime=" + std::string(login_rsp->LoginTime);
        }
        log("OnRspUserLogin reqid=" + std::to_string(reqid) + " last=" + (last ? "true " : "false ") + rsp_info(info) + extra);
        if (!rsp_ok(info)) {
            done();
            return;
        }
        login_ok_ = true;
        if (submit_user_system_info_) {
            submit_user_system_info(login_rsp);
        }

        CThostFtdcSettlementInfoConfirmField req{};
        copy_field(req.BrokerID, broker_id_);
        copy_field(req.InvestorID, user_id_);
        int ret = api_->ReqSettlementInfoConfirm(&req, next_reqid());
        log("ReqSettlementInfoConfirm ret=" + std::to_string(ret));
    }

    void OnRspSettlementInfoConfirm(CThostFtdcSettlementInfoConfirmField *, CThostFtdcRspInfoField *info, int reqid, bool last) override {
        log("OnRspSettlementInfoConfirm reqid=" + std::to_string(reqid) + " last=" + (last ? "true " : "false ") + rsp_info(info));
        if (!rsp_ok(info)) {
            done();
            return;
        }
        settlement_ok_ = true;

        query_account();
    }

    void OnRspQryTradingAccount(CThostFtdcTradingAccountField *account, CThostFtdcRspInfoField *info, int reqid, bool last) override {
        if (account) {
            ++account_count_;
            log("OnRspQryTradingAccount reqid=" + std::to_string(reqid) +
                " last=" + (last ? "true " : "false ") +
                rsp_info(info) +
                " Balance=" + std::to_string(account->Balance) +
                " Available=" + std::to_string(account->Available));
        } else {
            log("OnRspQryTradingAccount reqid=" + std::to_string(reqid) + " last=" + (last ? "true " : "false ") + rsp_info(info));
        }
        if (last) {
            std::thread([this] {
                std::this_thread::sleep_for(std::chrono::milliseconds(1200));
                query_position();
            }).detach();
        }
    }

    void OnRspQryInvestorPosition(CThostFtdcInvestorPositionField *pos, CThostFtdcRspInfoField *info, int reqid, bool last) override {
        if (pos) {
            ++position_count_;
            if (position_count_ <= 5) {
                log("OnRspQryInvestorPosition reqid=" + std::to_string(reqid) +
                    " last=" + (last ? "true " : "false ") +
                    rsp_info(info) +
                    " InstrumentID=" + std::string(pos->InstrumentID) +
                    " PosiDirection=" + std::string(1, pos->PosiDirection) +
                    " Position=" + std::to_string(pos->Position));
            }
        }
        if (last) {
            log("OnRspQryInvestorPosition last=true total_position_count=" + std::to_string(position_count_));
            done();
        }
    }

    void OnRspError(CThostFtdcRspInfoField *info, int reqid, bool last) override {
        log("OnRspError reqid=" + std::to_string(reqid) + " last=" + (last ? "true " : "false ") + rsp_info(info));
    }

private:
    int next_reqid() {
        return ++reqid_;
    }

    void login() {
        CThostFtdcReqUserLoginField req{};
        copy_field(req.BrokerID, broker_id_);
        copy_field(req.UserID, user_id_);
        copy_field(req.Password, password_);
        if (!product_info_.empty()) {
            copy_field(req.UserProductInfo, product_info_);
        }
        TThostFtdcClientSystemInfoType system_info{};
        int system_info_len = copy_client_system_info(system_info);
        int ret = api_->ReqUserLogin(&req, next_reqid(), system_info_len, system_info);
        log("ReqUserLogin system_info_len=" + std::to_string(system_info_len) + " ret=" + std::to_string(ret));
    }

    int copy_client_system_info(TThostFtdcClientSystemInfoType &system_info) {
        if (system_info_.bytes.empty()) {
            return 0;
        }
        std::memset(system_info, 0, sizeof(TThostFtdcClientSystemInfoType));
        std::size_t copy_len = std::min(system_info_.bytes.size(), sizeof(TThostFtdcClientSystemInfoType));
        std::memcpy(system_info, system_info_.bytes.data(), copy_len);
        if (copy_len < system_info_.bytes.size()) {
            log("CTP_CLIENT_SYSTEM_INFO truncated from len=" + std::to_string(system_info_.bytes.size()) +
                " to len=" + std::to_string(copy_len));
        }
        return static_cast<int>(copy_len);
    }

    void register_user_system_info() {
        if (system_info_.bytes.empty()) {
            log("RegisterUserSystemInfo skipped: empty client system info");
            return;
        }

        CThostFtdcUserSystemInfoField req{};
        copy_field(req.BrokerID, broker_id_);
        copy_field(req.UserID, user_id_);
        copy_field(req.ClientAppID, app_id_);
        req.ClientSystemInfoLen = copy_client_system_info(req.ClientSystemInfo);
        int ret = api_->RegisterUserSystemInfo(&req);
        log("RegisterUserSystemInfo client_system_info_len=" + std::to_string(req.ClientSystemInfoLen) +
            " ret=" + std::to_string(ret));
    }

    void submit_user_system_info(CThostFtdcRspUserLoginField *login_rsp) {
        if (system_info_.bytes.empty()) {
            log("SubmitUserSystemInfo skipped: empty client system info");
            return;
        }

        CThostFtdcUserSystemInfoField req{};
        copy_field(req.BrokerID, broker_id_);
        copy_field(req.UserID, user_id_);
        copy_field(req.ClientAppID, app_id_);
        if (login_rsp) {
            copy_field(req.ClientLoginTime, login_rsp->LoginTime);
        }
        req.ClientIPPort = 0;
        req.ClientSystemInfoLen = copy_client_system_info(req.ClientSystemInfo);
        int ret = api_->SubmitUserSystemInfo(&req);
        log("SubmitUserSystemInfo client_system_info_len=" + std::to_string(req.ClientSystemInfoLen) +
            " ret=" + std::to_string(ret));
    }

    void query_account() {
        CThostFtdcQryTradingAccountField account_req{};
        copy_field(account_req.BrokerID, broker_id_);
        copy_field(account_req.InvestorID, user_id_);
        int ret_account = api_->ReqQryTradingAccount(&account_req, next_reqid());
        log("ReqQryTradingAccount ret=" + std::to_string(ret_account));
    }

    void query_position() {
        CThostFtdcQryInvestorPositionField pos_req{};
        copy_field(pos_req.BrokerID, broker_id_);
        copy_field(pos_req.InvestorID, user_id_);
        int ret_pos = api_->ReqQryInvestorPosition(&pos_req, next_reqid());
        log("ReqQryInvestorPosition ret=" + std::to_string(ret_pos));
        if (ret_pos != 0) {
            done();
        }
    }

    void done() {
        {
            std::lock_guard<std::mutex> lock(mutex_);
            done_ = true;
        }
        cv_.notify_all();
    }

    CThostFtdcTraderApi *api_;
    int wait_seconds_;
    int reqid_ = 0;
    std::chrono::steady_clock::time_point start_;
    std::mutex mutex_;
    std::condition_variable cv_;
    bool done_ = false;

    std::string broker_id_;
    std::string user_id_;
    std::string password_;
    std::string td_address_;
    std::string app_id_;
    std::string auth_code_;
    std::string product_info_;
    ctp_native::SystemInfoResult system_info_;
    bool register_user_system_info_ = false;
    bool submit_user_system_info_ = false;

    bool front_connected_ = false;
    bool auth_ok_ = false;
    bool login_ok_ = false;
    bool settlement_ok_ = false;
    int account_count_ = 0;
    int position_count_ = 0;
};

}  // namespace

int main() {
    std::string sdk_dir = env_required("CTP_MAC_CP_SDK_DIR");
    std::string wait_raw = std::getenv("CTP_NATIVE_TD_WAIT_SECONDS") ? std::getenv("CTP_NATIVE_TD_WAIT_SECONDS") : "75";
    int wait_seconds = std::stoi(wait_raw);

    std::filesystem::path flow_dir("/private/tmp/stage278_native_cpp_td_flow/Td");
    std::filesystem::create_directories(flow_dir);
    std::string flow_path = flow_dir.string() + "/";

    CThostFtdcTraderApi *api = CThostFtdcTraderApi::CreateFtdcTraderApi(flow_path.c_str());
    if (!api) {
        std::cerr << "CreateFtdcTraderApi returned null" << std::endl;
        return 5;
    }

    NativeTdProbe probe(api, wait_seconds);
    probe.start();

    api->RegisterSpi(nullptr);
    api->Release();
    return 0;
}
