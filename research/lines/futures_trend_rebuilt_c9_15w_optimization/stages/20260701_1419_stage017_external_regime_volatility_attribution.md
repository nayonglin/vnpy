# Stage017 外生 regime/volatility 只读归因

- line_id：`futures_trend_rebuilt_c9_15w_optimization`
- 当前模式：`day`
- 记录时间：`2026-07-01 14:19 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：只读外生/市场状态归因；不改策略、不连接 CTP、不调用下单 API
- 是否重要突破：否，但提供 Stage018 冻结真实引擎验证线索
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：
  - Hurst、Ooi、Pedersen《A Century of Evidence on Trend-Following Investing》：长期趋势跟随右尾来自跨市场/跨周期，但无清晰趋势阶段会产生显著回撤。
  - CME《When Do Trend Followers Make Money?》：趋势跟随收益受波动率、相关性和趋势状态共同影响，不应只看单一收益或单一波动指标。
  - CME《Demystifying Time-Series Momentum Strategies》：趋势检测和波动状态会影响换手与风险压力，但应避免用事后最差窗口调参。
  - Hood/Raughtigan《Volatility Targeting Is Trendy》与 PyTrendFollow / mlm-trend-following GitHub 示例：波动率归一化和 realized-vol 过滤是常见研究形状，但不能直接复制为商品期货 alpha。
- 我的判断：
  - 本阶段只采纳“低自由度市场状态”这个形状：`60d realized vol`、`60d trend efficiency`、`MA20>MA60` 广度、close-position 极端度。
  - 不采纳外部资料里的具体窗口、阈值、仓位倍数；本阶段只做归因证据，不写交易规则。
  - 修正过程中发现 `market_ma20_over_ma60_60d` 是连续强弱值，不是 0/1；最终用 `>0` 统计广度，并修正 joint regime 优先级，避免 `high_vol_low_eff` 被其他标签覆盖。

## 本次变更

- 新增脚本：`research/lines/futures_trend_rebuilt_c9_15w_optimization/tools/stage017_external_regime_volatility_attribution.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：无交易参数；新增只读诊断分桶 `vol60_bucket`、`trend_eff60_bucket`、`trend_breadth_bucket`、`close_extreme_bucket`、`joint_regime`
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：
  - Stage013 曲线：继承 `stage013_account_state_pilot_gate_engine_v1`，本阶段只取 `requested_start_month >= 2020-01`
  - market daily：`2020-01-02` 到 `2026-04-30`，中位品种数 `18`
  - full-market AI monthly predictions：`2022-01-28` 到 `2026-02-27`，每月 `57` 个产品
  - entry outcome：Stage015 closed lots
- 账户规模：继承 Stage013 C9/15w，`150,000`
- 成本口径：继承 Stage013 已回放曲线与 Stage015 closed lots；本阶段不重新撮合、不改成本
- 样本过滤：曲线 forward 只保留能匹配 market daily 的日期；focus entry 为 `2022-01-01` 到 `2023-12-31`
- 策略/归因口径：只读；按市场状态分桶后看曲线未来 `63/126/252/366` 交易日收益、Top100 最差窗口前段状态、entry cash PnL、AI top8 未来 `60d` PnL

## 结果

- 期末权益：不适用，本阶段不产生新回测曲线
- 总收益：不适用
- 最大回撤：不适用
- Sharpe：不适用
- 总滑点：不适用
- 总交易次数：不适用
- 胜率：不适用
- 其他关键指标：
  - 曲线日 `all_market_days` 后续 `252` 交易日负收益率 `14.6258%`，最小收益 `-39.7595%`，中位收益 `51.1698%`
  - `high_vol_low_eff` 后续 `252` 交易日负收益率 `31.5021%`，最小收益 `-26.7794%`，中位收益 `20.7372%`
  - `trend_clean` 后续 `252` 交易日负收益率 `1.6034%`，最小收益 `-11.1037%`，中位收益 `55.9681%`
  - `high_vol_high_eff` 后续 `252` 交易日负收益率 `71.1462%`，但 `2022-2023` entry cash PnL 为正，说明不能简单写成“高波动全禁”
  - Top100 最差窗口前 `63` 个交易日，`high_vol_low_eff` 天数占比中位数 `44.4444%`，`trend_clean` 为 `0%`
  - `2022-2023` focus entry：`high_vol_low_eff` 共 `149` 笔、`12` 产品、cash PnL `-3,727,166`；`broad_trend` cash PnL `+1,868,380`；`high_vol_high_eff` cash PnL `+6,145,270`
  - `2022-2023` AI top8：`high_vol_low_eff` 共 `12` 个产品月，未来 `60d` 平均 PnL `-1,351.25`、中位 `-475`；`broad_trend` 平均 `+2,090.88`
  - 决策：`stage017_regime_signal_has_engine_test_value`

## 输出文件

- report：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage017_external_regime_volatility_attribution/rebuilt_c9_stage017_external_regime_volatility_attribution_report_stage017_external_regime_volatility_attribution_v1.md`
- summary：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage017_external_regime_volatility_attribution/rebuilt_c9_stage017_external_regime_volatility_attribution_decision_stage017_external_regime_volatility_attribution_v1.json`
- orders：不适用
- daily：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage017_external_regime_volatility_attribution/rebuilt_c9_stage017_external_regime_volatility_attribution_daily_forward_regime_summary_stage017_external_regime_volatility_attribution_v1.csv`
- quality：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage017_external_regime_volatility_attribution/rebuilt_c9_stage017_external_regime_volatility_attribution_entry_regime_summary_stage017_external_regime_volatility_attribution_v1.csv`
- chart：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage017_external_regime_volatility_attribution/rebuilt_c9_stage017_external_regime_volatility_attribution_chart_stage017_external_regime_volatility_attribution_v1.png`
- ai：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage017_external_regime_volatility_attribution/rebuilt_c9_stage017_external_regime_volatility_attribution_ai_monthly_regime_summary_stage017_external_regime_volatility_attribution_v1.csv`
- worst：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage017_external_regime_volatility_attribution/rebuilt_c9_stage017_external_regime_volatility_attribution_worst_window_regime_summary_stage017_external_regime_volatility_attribution_v1.csv`

## 结论

- 本阶段结论：`high_vol_low_eff` 是比单纯 broker10、active4 更接近“剩余左尾环境”的低自由度状态标签；它在曲线 forward、Top100 最差窗口前段、focus entry cash PnL、AI top8 未来 `60d` 四张表里同时偏弱。
- 但它不是直接上线规则：`high_vol_high_eff` 在曲线 forward 上很差、在 focus entry cash PnL 上却很强，说明市场状态必须和账户状态/入场形态结合，不能简单按高波动禁开。
- 是否进入下一步：是，进入 Stage018 冻结真实引擎验证。
- 下一步：只写一个预声明 Stage018，不扫阈值；候选形状是“当市场处于 high-vol/low-efficiency 时，对风险释放/AI top8 排名做保守处理”，并必须保留 Stage013 真实成交、保证金、broker10、AI 审计口径。

## 过拟合反思

- 运行前判断：否。阶段只读、低自由度、外部研究支持，且不按日期/品种/方向/source_start/horizon 补丁化。
- 运行后判断：仍然否，但有过拟合风险需要控制。
- 原因：`high_vol_low_eff` 与剩余左尾一致，但当前分桶仍来自样本分位数，不能直接作为真实交易阈值；Stage018 必须冻结一个形状，不继续扫 `0.33/0.67`、窗口、倍数或组合条件。

## 继续价值反思

- 运行前判断：是。Stage016 已反证纯账户压力规则，需要能区分“右尾趋势”和“假突破拥挤”的市场状态信息。
- 运行后判断：是。
- 原因：`high_vol_low_eff` 已经在多张独立表中呈现同向弱化，足够值得写一个真实引擎验证；但不够直接上线，下一步必须用严格多起点/任意结束日目标来反证。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage017 结论和 Stage018 建议
- 是否更新 `research/registry.md`：是，把当前线最新关键阶段更新为 Stage017
- 是否追加根目录 `memory.md/back_log.md`：否，本阶段不是正式候选或跨线合入
