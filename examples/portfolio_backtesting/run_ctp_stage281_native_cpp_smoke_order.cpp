#include <chrono>
#include <condition_variable>
#include <cstdlib>
#include <cstring>
#include <filesystem>
#include <iomanip>
#include <iostream>
#include <mutex>
#include <sstream>
#include <string>
#include <thread>
#include <vector>

#include "ThostFtdcTraderApi.h"

namespace {

constexpr const char *kConfirmText = "I_UNDERSTAND_THIS_SENDS_CTP_TEST_ORDERS";

std::string env_value(const char *name, const std::string &fallback = "") {
    const char *value = std::getenv(name);
    if (!value || std::strlen(value) == 0) {
        return fallback;
    }
    return std::string(value);
}

std::string env_required(const char *name) {
    std::string value = env_value(name);
    if (value.empty()) {
        std::cerr << "Missing required env: " << name << std::endl;
        std::exit(2);
    }
    return value;
}

bool env_flag(const char *name) {
    std::string value = env_value(name);
    return value == "1" || value == "true" || value == "TRUE" || value == "yes" || value == "YES";
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

bool is_active_order_status(char status) {
    return status == THOST_FTDC_OST_NoTradeQueueing ||
           status == THOST_FTDC_OST_PartTradedQueueing ||
           status == THOST_FTDC_OST_Unknown;
}

std::string order_status_text(char status) {
    switch (status) {
        case THOST_FTDC_OST_AllTraded: return "AllTraded";
        case THOST_FTDC_OST_PartTradedQueueing: return "PartTradedQueueing";
        case THOST_FTDC_OST_PartTradedNotQueueing: return "PartTradedNotQueueing";
        case THOST_FTDC_OST_NoTradeQueueing: return "NoTradeQueueing";
        case THOST_FTDC_OST_NoTradeNotQueueing: return "NoTradeNotQueueing";
        case THOST_FTDC_OST_Canceled: return "Canceled";
        case THOST_FTDC_OST_Unknown: return "Unknown";
        default: return std::string("status_") + status;
    }
}

class NativeSmokeOrder final : public CThostFtdcTraderSpi {
public:
    explicit NativeSmokeOrder(CThostFtdcTraderApi *api, int wait_seconds)
        : api_(api), wait_seconds_(wait_seconds) {
        broker_id_ = env_required("CTP_BROKERID");
        user_id_ = env_required("CTP_USERID");
        password_ = env_required("CTP_PASSWORD");
        td_address_ = env_required("CTP_TD_ADDRESS");
        app_id_ = env_required("CTP_APPID");
        auth_code_ = env_required("CTP_AUTH_CODE");

        mode_ = env_value("CTP_NATIVE_SMOKE_MODE", "dry-run");
        instrument_id_ = env_value("CTP_NATIVE_SMOKE_INSTRUMENT", "MA609");
        exchange_id_ = env_value("CTP_NATIVE_SMOKE_EXCHANGE", "CZCE");
        direction_ = env_value("CTP_NATIVE_SMOKE_DIRECTION", "buy") == "sell" ? THOST_FTDC_D_Sell : THOST_FTDC_D_Buy;
        price_ = std::stod(env_value("CTP_NATIVE_SMOKE_PRICE", "1.0"));
        volume_ = std::stoi(env_value("CTP_NATIVE_SMOKE_VOLUME", "1"));
        confirm_text_ = env_value("CTP_NATIVE_SMOKE_CONFIRM", "");
        enabled_ = env_flag("CTP_NATIVE_SMOKE_ORDER_ENABLED");

        const char *product = std::getenv("CTP_PRODUCT_INFO");
        if (product) {
            product_info_ = product;
        }

        const char *client_system_info = std::getenv("CTP_CLIENT_SYSTEM_INFO");
        if (client_system_info) {
            client_system_info_ = client_system_info;
        }
    }

    void log(const std::string &message) {
        auto elapsed = std::chrono::duration<double>(std::chrono::steady_clock::now() - start_).count();
        std::cout << "[" << elapsed << "s] " << message << std::endl;
    }

    void start() {
        start_ = std::chrono::steady_clock::now();
        order_ref_ = make_order_ref();

        log("native C++ smoke-order probe starting");
        log("api_version=" + std::string(CThostFtdcTraderApi::GetApiVersion()));
        log("CTP_BROKERID=" + broker_id_);
        log("CTP_TD_ADDRESS=" + td_address_);
        log("CTP_USERID=set(len=" + std::to_string(user_id_.size()) + ")");
        log("CTP_PASSWORD=set(len=" + std::to_string(password_.size()) + ")");
        log("CTP_APPID=set(len=" + std::to_string(app_id_.size()) + ")");
        log("CTP_AUTH_CODE=set(len=" + std::to_string(auth_code_.size()) + ")");
        log("CTP_CLIENT_SYSTEM_INFO=" + std::string(client_system_info_.empty() ? "empty" : "set(len=" + std::to_string(client_system_info_.size()) + ")"));
        log("mode=" + mode_ +
            " enabled=" + std::string(enabled_ ? "true" : "false") +
            " confirm_ok=" + std::string(confirm_text_ == kConfirmText ? "true" : "false") +
            " instrument=" + instrument_id_ +
            " exchange=" + exchange_id_ +
            " direction=" + std::string(direction_ == THOST_FTDC_D_Buy ? "buy" : "sell") +
            " price=" + double_to_string(price_) +
            " volume=" + std::to_string(volume_) +
            " order_ref=" + order_ref_);

        api_->RegisterSpi(this);
        api_->SubscribePrivateTopic(THOST_TERT_QUICK);
        api_->SubscribePublicTopic(THOST_TERT_QUICK);

        std::vector<char> front(td_address_.begin(), td_address_.end());
        front.push_back('\0');
        api_->RegisterFront(front.data());
        api_->Init();

        std::unique_lock<std::mutex> lock(mutex_);
        cv_.wait_for(lock, std::chrono::seconds(wait_seconds_), [this] { return done_; });

        log("summary front_connected=" + std::string(front_connected_ ? "true" : "false") +
            " auth_ok=" + std::string(auth_ok_ ? "true" : "false") +
            " login_ok=" + std::string(login_ok_ ? "true" : "false") +
            " settlement_ok=" + std::string(settlement_ok_ ? "true" : "false") +
            " send_order_api_called_count=" + std::to_string(send_order_api_called_count_) +
            " cancel_order_api_called_count=" + std::to_string(cancel_order_api_called_count_) +
            " rsp_order_insert_count=" + std::to_string(rsp_order_insert_count_) +
            " err_order_insert_count=" + std::to_string(err_order_insert_count_) +
            " rtn_order_count=" + std::to_string(rtn_order_count_) +
            " rtn_trade_count=" + std::to_string(rtn_trade_count_) +
            " final_order_status=" + final_order_status_ +
            " order_ref=" + order_ref_);
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
        login();
    }

    void OnRspUserLogin(CThostFtdcRspUserLoginField *login_rsp, CThostFtdcRspInfoField *info, int reqid, bool last) override {
        std::string extra;
        if (login_rsp) {
            front_id_ = login_rsp->FrontID;
            session_id_ = login_rsp->SessionID;
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
        maybe_send_order();
    }

    void OnRspOrderInsert(CThostFtdcInputOrderField *order, CThostFtdcRspInfoField *info, int reqid, bool last) override {
        ++rsp_order_insert_count_;
        std::string ref = order ? std::string(order->OrderRef) : "";
        log("OnRspOrderInsert reqid=" + std::to_string(reqid) + " last=" + (last ? "true " : "false ") +
            rsp_info(info) + " OrderRef=" + ref);
        final_order_status_ = "RspOrderInsert";
        done();
    }

    void OnErrRtnOrderInsert(CThostFtdcInputOrderField *order, CThostFtdcRspInfoField *info) override {
        ++err_order_insert_count_;
        std::string ref = order ? std::string(order->OrderRef) : "";
        log("OnErrRtnOrderInsert " + rsp_info(info) + " OrderRef=" + ref);
        final_order_status_ = "ErrRtnOrderInsert";
        done();
    }

    void OnRtnOrder(CThostFtdcOrderField *order) override {
        if (!order) {
            return;
        }
        ++rtn_order_count_;
        final_order_status_ = order_status_text(order->OrderStatus);
        order_sys_id_ = order->OrderSysID;
        exchange_id_from_order_ = order->ExchangeID;
        log("OnRtnOrder OrderRef=" + std::string(order->OrderRef) +
            " OrderSysID=" + order_sys_id_ +
            " ExchangeID=" + exchange_id_from_order_ +
            " Status=" + final_order_status_ +
            " VolumeTotalOriginal=" + std::to_string(order->VolumeTotalOriginal) +
            " VolumeTraded=" + std::to_string(order->VolumeTraded) +
            " VolumeTotal=" + std::to_string(order->VolumeTotal));

        if (mode_ == "submit-cancel" && !cancel_sent_ && is_active_order_status(order->OrderStatus)) {
            cancel_order();
        }
        if (order->OrderStatus == THOST_FTDC_OST_AllTraded ||
            order->OrderStatus == THOST_FTDC_OST_Canceled ||
            order->OrderStatus == THOST_FTDC_OST_NoTradeNotQueueing ||
            order->OrderStatus == THOST_FTDC_OST_PartTradedNotQueueing) {
            done();
        }
    }

    void OnRtnTrade(CThostFtdcTradeField *trade) override {
        if (!trade) {
            return;
        }
        ++rtn_trade_count_;
        log("OnRtnTrade InstrumentID=" + std::string(trade->InstrumentID) +
            " Direction=" + std::string(1, trade->Direction) +
            " OffsetFlag=" + std::string(1, trade->OffsetFlag) +
            " Price=" + double_to_string(trade->Price) +
            " Volume=" + std::to_string(trade->Volume));
    }

    void OnRspOrderAction(CThostFtdcInputOrderActionField *action, CThostFtdcRspInfoField *info, int reqid, bool last) override {
        log("OnRspOrderAction reqid=" + std::to_string(reqid) + " last=" + (last ? "true " : "false ") +
            rsp_info(info) + " OrderRef=" + (action ? std::string(action->OrderRef) : ""));
        if (!rsp_ok(info)) {
            done();
        }
    }

    void OnErrRtnOrderAction(CThostFtdcOrderActionField *action, CThostFtdcRspInfoField *info) override {
        log("OnErrRtnOrderAction " + rsp_info(info) + " OrderRef=" + (action ? std::string(action->OrderRef) : ""));
        done();
    }

    void OnRspError(CThostFtdcRspInfoField *info, int reqid, bool last) override {
        log("OnRspError reqid=" + std::to_string(reqid) + " last=" + (last ? "true " : "false ") + rsp_info(info));
    }

private:
    int next_reqid() {
        return ++reqid_;
    }

    std::string make_order_ref() const {
        auto now = std::chrono::system_clock::now().time_since_epoch();
        auto millis = std::chrono::duration_cast<std::chrono::milliseconds>(now).count();
        return std::to_string(millis % 1000000000000LL);
    }

    std::string double_to_string(double value) const {
        std::ostringstream oss;
        oss << std::fixed << std::setprecision(4) << value;
        return oss.str();
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
        if (client_system_info_.empty()) {
            return 0;
        }
        std::memset(system_info, 0, sizeof(TThostFtdcClientSystemInfoType));
        std::size_t copy_len = std::min(client_system_info_.size(), sizeof(TThostFtdcClientSystemInfoType));
        std::memcpy(system_info, client_system_info_.data(), copy_len);
        return static_cast<int>(copy_len);
    }

    void maybe_send_order() {
        if (mode_ == "dry-run") {
            log("dry-run ready: order API not called");
            done();
            return;
        }
        if (mode_ != "submit-cancel") {
            log("blocked: unknown mode=" + mode_);
            done();
            return;
        }
        if (!enabled_ || confirm_text_ != kConfirmText) {
            log("blocked: submit-cancel requires CTP_NATIVE_SMOKE_ORDER_ENABLED=1 and exact confirm text");
            done();
            return;
        }
        if (volume_ != 1) {
            log("blocked: smoke test volume must be 1");
            done();
            return;
        }
        if (price_ <= 0) {
            log("blocked: smoke test price must be positive");
            done();
            return;
        }

        CThostFtdcInputOrderField req{};
        copy_field(req.BrokerID, broker_id_);
        copy_field(req.InvestorID, user_id_);
        copy_field(req.UserID, user_id_);
        copy_field(req.InstrumentID, instrument_id_);
        copy_field(req.ExchangeID, exchange_id_);
        copy_field(req.OrderRef, order_ref_);
        req.OrderPriceType = THOST_FTDC_OPT_LimitPrice;
        req.Direction = direction_;
        req.CombOffsetFlag[0] = THOST_FTDC_OF_Open;
        req.CombHedgeFlag[0] = THOST_FTDC_HF_Speculation;
        req.LimitPrice = price_;
        req.VolumeTotalOriginal = volume_;
        req.TimeCondition = THOST_FTDC_TC_GFD;
        req.VolumeCondition = THOST_FTDC_VC_AV;
        req.MinVolume = 1;
        req.ContingentCondition = THOST_FTDC_CC_Immediately;
        req.StopPrice = 0;
        req.ForceCloseReason = THOST_FTDC_FCC_NotForceClose;
        req.IsAutoSuspend = 0;
        req.UserForceClose = 0;
        req.IsSwapOrder = 0;

        ++send_order_api_called_count_;
        int ret = api_->ReqOrderInsert(&req, next_reqid());
        log("ReqOrderInsert OrderRef=" + order_ref_ + " ret=" + std::to_string(ret));
        if (ret != 0) {
            done();
        }
    }

    void cancel_order() {
        CThostFtdcInputOrderActionField req{};
        copy_field(req.BrokerID, broker_id_);
        copy_field(req.InvestorID, user_id_);
        copy_field(req.UserID, user_id_);
        copy_field(req.InstrumentID, instrument_id_);
        copy_field(req.ExchangeID, exchange_id_from_order_.empty() ? exchange_id_ : exchange_id_from_order_);
        copy_field(req.OrderRef, order_ref_);
        if (!order_sys_id_.empty()) {
            copy_field(req.OrderSysID, order_sys_id_);
        }
        req.FrontID = front_id_;
        req.SessionID = session_id_;
        req.ActionFlag = THOST_FTDC_AF_Delete;

        cancel_sent_ = true;
        ++cancel_order_api_called_count_;
        int ret = api_->ReqOrderAction(&req, next_reqid());
        log("ReqOrderAction(cancel) OrderRef=" + order_ref_ +
            " OrderSysID=" + order_sys_id_ +
            " ret=" + std::to_string(ret));
        if (ret != 0) {
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
    std::string client_system_info_;

    std::string mode_;
    bool enabled_ = false;
    std::string confirm_text_;
    std::string instrument_id_;
    std::string exchange_id_;
    char direction_;
    double price_ = 0;
    int volume_ = 1;
    std::string order_ref_;
    std::string order_sys_id_;
    std::string exchange_id_from_order_;
    int front_id_ = 0;
    int session_id_ = 0;
    bool cancel_sent_ = false;

    bool front_connected_ = false;
    bool auth_ok_ = false;
    bool login_ok_ = false;
    bool settlement_ok_ = false;
    int send_order_api_called_count_ = 0;
    int cancel_order_api_called_count_ = 0;
    int rsp_order_insert_count_ = 0;
    int err_order_insert_count_ = 0;
    int rtn_order_count_ = 0;
    int rtn_trade_count_ = 0;
    std::string final_order_status_ = "-";
};

}  // namespace

int main() {
    std::string wait_raw = env_value("CTP_NATIVE_SMOKE_WAIT_SECONDS", "75");
    int wait_seconds = std::stoi(wait_raw);

    std::filesystem::path flow_dir("/private/tmp/stage281_native_cpp_smoke_order_flow/Td");
    std::filesystem::create_directories(flow_dir);
    std::string flow_path = flow_dir.string() + "/";

    CThostFtdcTraderApi *api = CThostFtdcTraderApi::CreateFtdcTraderApi(flow_path.c_str());
    if (!api) {
        std::cerr << "CreateFtdcTraderApi returned null" << std::endl;
        return 5;
    }

    NativeSmokeOrder probe(api, wait_seconds);
    probe.start();

    api->RegisterSpi(nullptr);
    api->Release();
    return 0;
}
