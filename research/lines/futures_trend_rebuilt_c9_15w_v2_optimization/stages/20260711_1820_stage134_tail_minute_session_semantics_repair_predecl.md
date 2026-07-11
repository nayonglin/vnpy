# Stage134 tail minute session semantics repair predecl

- line_id：`futures_trend_rebuilt_c9_15w_v2_optimization`
- 当前模式：day
- 预声明时间：2026-07-11 18:20 CST
- 阶段性质：修复 Stage120 对夜盘自然日/交易日的错误验收语义并重新补齐固定 6 个尾部分钟文件；不回测收益、不改策略、不连接 CTP、不调用订单 API。
- 是否重要突破：否
- 是否触发 A/B：否

## 已观察事实

- Stage120 固定 6 个合约全部下载完成，但只有 `lh2609.DCE/SM609.CZCE/SH609.CZCE` 通过旧 Stage112；`cu2607.SHFE/au2608.SHFE/cu2608.SHFE` 因 `unique_trade_dates_match` 失败被隔离。
- 三个 SHFE 文件的日盘日期数分别严格等于 Stage020 预期交易日数 `22/25/5`，失败来自夜盘跨午夜增加自然日，不是行情行缺失。
- 旧下载边界为首日 `00:00` 到末日次日 `00:00`，会漏掉首个交易日对应的前一交易日 `21:00` 夜盘，并可能混入末日 `21:00` 后属于下一交易日的分钟。

## 冻结范围

- 合约固定为：`cu2607.SHFE`、`au2608.SHFE`、`lh2609.DCE`、`SM609.CZCE`、`SH609.CZCE`、`cu2608.SHFE`。
- 每个合约的预期交易日集合固定来自 Stage020 `product_returns` 中 `main_contract_vt == contract_vt` 的实际日期，不使用自然日数量代理。
- 全市场交易日固定来自同一 Stage020 `product_returns.date` 去重集合；首个预期交易日的 `signal_date` 是该集合中的前一交易日。
- 下载窗口固定为：首个 `signal_date 20:55:00` 到最后预期交易日 `15:15:00`。
- 成交窗口固定为 Stage208 既有语义：优先 `signal_date 21:00-21:05`，若该夜盘不存在则要求 `fill_date 09:00-09:05` 可用。

## 严格验收

- 日盘 `09:00-15:00` 观察到的日期集合必须与预期交易日集合完全一致。
- 每个预期交易日至少存在夜盘优先窗口或日盘回退窗口，缺任一交易日即失败。
- 必须同时通过：单一 `vt_symbol`、必需列、非空、时间有序、无重复键、OHLC 关系、volume/OI 非空且非负、下载边界内无越界行。
- 旧文件不直接删除；先复制到本阶段 `quarantine/replaced_previous`，再在同一文件系统用 `os.replace` 原子替换。
- 任一新文件失败时只隔离临时文件，不覆盖既有正式文件。

## 停止规则

- 若固定 6 个合约未全部通过，不进入 no-JD Stage208。
- 若全部通过，也只说明分钟数据阻塞清零；`jd_contract_daily_margin_history` 仍阻塞含 JD 的正式 Stage208 真账本。
- 不得通过修改合约、日期、成交窗口、允许 fallback 或删除失败行来救结果。

## 运行前反思

- 过拟合：否。修复的是交易日/session 数据语义，完全不读取收益结果。
- 继续价值：有。Stage120 已证明下载通路可用，当前阻塞是可复现的数据验收 bug；修复后才能公平证伪 Stage208。
