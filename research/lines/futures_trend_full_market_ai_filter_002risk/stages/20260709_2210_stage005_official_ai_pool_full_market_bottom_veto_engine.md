# Stage005 正式 AI 池 + 全市场底部四分位 veto 真实引擎

- line_id：`futures_trend_full_market_ai_filter_002risk`
- 当前模式：`day`
- 记录时间：`2026-07-09 22:27 CST`
- 阶段性质：独立研究线最小 A/C 真实引擎回测
- 是否重要突破：待独立 review；本阶段先验证结构角色切换
- 是否触发A/B：是，A=官方 C9/15w；C=官方 C9/15w + 正式 AI 池内 full-market bottom25 veto

## 外部调研与判断

- 参考资料：Hudson & Thames meta-labeling、AQR managed futures、QuantInsti cross-sectional momentum ML。
- 我的判断：AI 不应在当前特征质量下替代趋势策略的产品池；更合理的是作为低权限 veto 或 sizing overlay。

## 本次变更

- 新增脚本：`research/lines/futures_trend_full_market_ai_filter_002risk/tools/stage005_official_ai_pool_full_market_bottom_veto_engine.py`
- 新增参数：`BOTTOM_VETO_QUANTILE=0.25`、`MIN_ACTIVE_PRODUCTS_FOR_VETO=12`
- 修改参数：候选 C 的 AI eligibility 从正式文件改为“正式文件减去全市场分数底部四分位”。
- 删除参数：本阶段不删除正式风险参数，不关闭 OI restore，不改 product_universe。

## 回测参数

- 数据区间：`2020-01-01` 到 `2026-06-30`
- 账户规模：`150,000`
- 成本口径：沿用 C9 真实引擎原成本/slippage 配置。
- 风险口径：官方 C9 风险原样保留；本阶段不测试 `0.02` 风险。

## 结果

- A 期末权益：`5,979,281.00`；总收益 `3886.1873%`；最大回撤 `-55.3701%`；Sharpe `1.3959`
- C 期末权益：`4,407,585.30`
- C 总收益：`2838.3902%`
- C 最大回撤：`-46.1580%`
- C Sharpe：`1.3541`
- C 总滑点：`524,860.00`
- C 总交易次数：`585`
- C 胜率：`52.2876%`，口径为非零交易日胜率，不是逐笔胜率。
- 收益保留率：`0.7304`
- C 相对 A 收益差：`-1047.7971` 百分点；回撤差：`9.2121` 百分点。

## 输出文件

- report：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_full_market_ai_filter_002risk/outputs/stage005_official_ai_pool_full_market_bottom_veto_engine/full_market_ai002_stage005_official_ai_pool_full_market_bottom_veto_engine_report_stage005_official_ai_pool_full_market_bottom_veto_engine_v1.md`
- summary：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_full_market_ai_filter_002risk/outputs/stage005_official_ai_pool_full_market_bottom_veto_engine/full_market_ai002_stage005_official_ai_pool_full_market_bottom_veto_engine_ac_summary_stage005_official_ai_pool_full_market_bottom_veto_engine_v1.csv`
- eligibility：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_full_market_ai_filter_002risk/outputs/stage005_official_ai_pool_full_market_bottom_veto_engine/full_market_ai002_stage005_official_ai_pool_full_market_bottom_veto_engine_eligibility_stage005_official_ai_pool_full_market_bottom_veto_engine_v1.csv`
- overlay_audit：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_full_market_ai_filter_002risk/outputs/stage005_official_ai_pool_full_market_bottom_veto_engine/full_market_ai002_stage005_official_ai_pool_full_market_bottom_veto_engine_official_overlay_audit_stage005_official_ai_pool_full_market_bottom_veto_engine_v1.csv`
- risk_restore_audit：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_full_market_ai_filter_002risk/outputs/stage005_official_ai_pool_full_market_bottom_veto_engine/full_market_ai002_stage005_official_ai_pool_full_market_bottom_veto_engine_risk_restore_audit_stage005_official_ai_pool_full_market_bottom_veto_engine_v1.csv`
- chart：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_full_market_ai_filter_002risk/outputs/stage005_official_ai_pool_full_market_bottom_veto_engine/full_market_ai002_stage005_official_ai_pool_full_market_bottom_veto_engine_equity_drawdown_stage005_official_ai_pool_full_market_bottom_veto_engine_v1.png`

## 结论

- 本阶段结论：`stage005_continue_to_halfyear_if_independent_review_passes`
- 是否进入下一步：等待独立 agent review 后决定。
- 下一步：若 C 在保持 50%+ 收益的同时改善回撤，再跑逐半年多周期；否则停止该 veto 形状。

## 过拟合反思

- 运行前判断：低到中等。结构角色从 selector 降为 veto，不按坏窗口和单品种救参。
- 运行后判断：等待独立 review。

## 继续价值反思

- 运行前判断：有价值。它验证 full-market 特征能否作为低权限 overlay，而不是替代正式 AI 池。
- 运行后判断：等待独立 review。
