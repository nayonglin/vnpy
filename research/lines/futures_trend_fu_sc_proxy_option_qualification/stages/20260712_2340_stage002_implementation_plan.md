# Stage002 执行数据资格实施计划

- line_id：`futures_trend_fu_sc_proxy_option_qualification`
- 记录时间：`2026-07-12 23:40 CST`
- 阶段性质：预声明后的实现计划；当前不联网
- 回测：否

## 实现顺序

1. 新增独立 semantic preflight，逐事件重算 Stage001 metadata normalization 与 audit，不能复用旧 cache validator 自证。
2. 从 Stage001 SC selection ledger 提取 `selection_date/prior_close/selected_symbol`；从 Stage131 requirements计算FU方向、总量与加权entry price。
3. 用冻结 metadata 做32条 adverse-side nearest-ATM selection，输出所有候选排名而不只保存winner。
4. 计算不使用option价格的 `ideal_option_lots` 粗粒度，先检查核心6和全体门。
5. 运行 line-local tests 与独立 agent preflight review；未批准则停止。
6. 批准后复用已审查 Stage133 entry-session market-data producer，核心6 canary后才允许剩余26。

## 测试

- raw->normalized被篡改必须失败。
- wrong underlying/expired/class/strike必须失败。
- ATM tie按较低strike再symbol固定。
- long/short必须分别映射PUT/CALL。
- 事件日SC价格不得影响selection。
- ideal lots小于2必须被粒度门拦截。
- canary任一失败不得调用剩余26。

## 当前边界

- 默认真实网络关闭。
- 当前只允许实现preflight、selection和fake-fetch测试。
- 独立review批准前，不得调用K线/tick接口。

