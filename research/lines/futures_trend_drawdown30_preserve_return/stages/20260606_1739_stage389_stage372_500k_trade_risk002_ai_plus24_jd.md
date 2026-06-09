# Stage389 Stage372 50万 risk_ratio 0.02 plus24 鸡蛋 AI选品反证

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：2026-06-06 17:39 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：回测/AI选品扩池/反证
- 是否重要突破：否，是重要反证
- 是否触发A/B：已读取 `skills/version-ab-experiment/SKILL.md`；本阶段被拒绝，不进入正式A/B

## 外部调研与判断

- 参考资料：
  - 信易科技鸡蛋 JD 期货业务规则页：https://www.shinnytech.com/articles/business-rules/products/dce.jd
  - 大连商品交易所历史月报中包含 `jd` 鸡蛋合约交易记录：https://www.dce.com.cn/dalianshangpin/resource/cms/2019/05/2019051410181769090.pdf
  - 大连商品交易所合约设计资料中列出鸡蛋交易单位为 `5` 吨/手：https://www.dce.com.cn/dalianshangpin/resource/cms/2016/11/%E7%8E%89%E7%B1%B3%E6%B7%80%E6%B7%80%E7%B2%89%E6%9C%9F%E8%B4%A7%E5%90%88%E7%BA%A6%E8%AE%BE%E8%AE%A1%E8%AF%B4%E6%98%8E.pdf
- 我的判断：鸡蛋 `jd.DCE` 是大商所鲜活农产品/畜禽品种，经济驱动与黑色、金属、能源不同，作为扩池候选有第一性原理价值；但必须与 Stage388 一样走 AI 选品，不应固定追加或因单品种历史表现做黑名单/白名单。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage677_stage372_500k_trade_risk002_ai_plus24_jd.py`
- 修改脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage674_stage372_500k_trade_risk001_ni_ag_sc_p.py`，将图表/variant label 从写死 `plus-ni-ag-sc-p` 改为根据 `EXTRA_PRODUCTS` 自动生成，避免加入 `jd` 后标签误导。
- 删除脚本：无
- 新增参数：
  - `EXTRA_PRODUCTS=(ni.SHFE, ag.SHFE, sc.INE, p.DCE, jd.DCE)`
  - `AI_PLUS24_STRATEGY=stage677_stage372_500k_trade_risk002_ai_plus24_jd_entry_filter`
  - `AI_PLUS24_SCORE_TYPE=stage677_full_market_ai_probability_plus24_jd`
  - `TARGET_TRADE_RISK_RATIO=0.02`
  - `TARGET_VARIANT=stage372_500k_trade_risk002_ai_plus24_jd_maxpos4`
  - `TARGET_NO_MAXPOS_VARIANT=stage372_500k_trade_risk002_ai_plus24_jd_maxpos24`
- 修改参数：plus 宇宙从 Stage388 的 `23` 个产品扩大到 `24` 个产品；AI 仍固定 `top8 + fu.SHFE` 卫星，不扫 topN。
- 删除参数：无
- 新增回测结果：新增 A/C/C2 多周期、成本压力、滚动窗口、资金占用、五个扩展品种贡献和 AI 选中次数。
- 修改回测结果：无
- 删除回测结果：无

## 回测/归因参数

- 数据区间：历史全周期 `2020-01-02` 至 `2026-04-30`，另含多起点、市场阶段、弱窗口和 YTD runner。
- 账户规模：`500,000`
- 成本口径：正常成本、2x成本、3x成本压力。
- 样本过滤：full-market AI predictions 中 `jd.DCE` 有 `50` 行，`eval_date=2022-01-28` 至 `2026-02-27`；Stage677 eligibility 共 `50` 个 eval_date、`24` 个产品、`441` 行。
- 策略/归因口径：
  - A：`stage372_500k_trade_risk004_ai_plus24_jd_maxpos4`
  - C：`stage372_500k_trade_risk002_ai_plus24_jd_maxpos4`
  - C2：`stage372_500k_trade_risk002_ai_plus24_jd_maxpos24`
  - 当前正式实盘版本未改变，仍为 `official_live_stage372_20w_recovery_sleeve`。

## 结果

- A 全周期：期末权益 `2,096,640`，总收益 `319.3280%`，最大回撤 `-51.4022%`，Sharpe `0.8562`，总滑点 `303,070`，总交易次数 `724`，胜率 `50.7042%`，broker10峰值 `74.3386%`，2x/3x成本DD `-57.0357%/-63.0500%`。
- C 全周期：期末权益 `757,270`，总收益 `51.4540%`，最大回撤 `-60.9205%`，Sharpe `0.3988`，总滑点 `122,760`，总交易次数 `659`，胜率 `48.0826%`，broker10峰值 `73.7152%`，2x/3x成本DD `-65.6804%/-70.9004%`。
- C 相对 A：收益少 `267.8740pp`，最大回撤恶化 `9.5183pp`，Sharpe 下降 `0.4574`，滑点减少 `180,310`，broker10峰值仅下降 `0.6234pp`；硬失败是 DD30 和降风险后回撤反而恶化。
- C2 全周期：期末权益 `674,880`，总收益 `34.9760%`，最大回撤 `-61.1486%`，Sharpe `0.3137`，总滑点 `137,740`，总交易次数 `813`，胜率 `48.5224%`，2x/3x成本DD `-67.9049%/-75.3269%`；相对 C 收益少 `16.4780pp`、回撤劣化 `0.2281pp`，放宽并发失败。
- C 多周期：
  - `since_2021`：`460,670/-7.8660%/-58.7992%/Sharpe0.0504`
  - `since_2022`：`370,940/-25.8120%/-34.1809%/Sharpe-0.4692`
  - `since_2023`：`376,220/-24.7560%/-37.3812%/Sharpe-0.6158`
  - `since_2024`：`361,010/-27.7980%/-34.9719%/Sharpe-0.9775`
  - `since_2025`：`523,325/4.6650%/-12.3277%/Sharpe0.3048`
  - `phase_2022_2023`：`501,370/0.2740%/-18.8579%/Sharpe0.0772`
  - `weak_2021_drawdown`：`470,540/-5.8920%/-15.8311%/Sharpe-0.9553`
  - `ytd_2026_latest_ai`：`483,295/-3.3410%/-9.7783%/Sharpe-0.5951`；注意该 YTD 仍是历史 eligibility 复验，不是最新同宇宙 live inference。
- C 滚动收益左尾：63日 p05 `-17.7945%`，126日 p05 `-24.4493%`，252日 p05 `-36.9631%`，最差252日 `-46.4110%`。
- C 资金占用：active days `936`，active rate `61.0966%`，平均占用 `10.7513%`，active day平均占用 `17.5972%`，p95 `34.2689%`，峰值 `73.7152%`，`>30%` `147` 天，`>50%` `10` 天，`>70%` `1` 天，`>90%/>100%` 均 `0`。
- C 扩展品种贡献：
  - `ag`：`+34,725`，滑点 `2,820`，交易 `22`
  - `jd`：`-82,330`，滑点 `3,340`，交易 `22`
  - `ni`：`-51,730`，滑点 `2,420`，交易 `44`
  - `p`：`-184,200`，滑点 `4,880`，交易 `44`
  - `sc`：`-9,600`，滑点 `5,000`，交易 `36`
  - 合计：`-293,135`，滑点 `18,460`，交易 `168`
- AI 选中证据：
  - `jd.DCE` 被选 `13` 次，平均 rank `5.5385`，最好 rank `1`，最差 rank `8`。
  - `ag/ni/p/sc/jd` 分别被选 `13/16/21/20/13` 次。
- 与 Stage388 对照：Stage388 C 为 `1,118,385/123.6770%/-50.9778%/Sharpe0.6544`；Stage389 C 为 `757,270/51.4540%/-60.9205%/Sharpe0.3988`，加入鸡蛋后更差。
- 与 Stage387 对照：Stage387 固定全加 C 为 `4,634,210/826.8420%/-25.3045%/Sharpe1.3707`，Stage389 真 AI plus24 明显不能替代。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage677_stage372_500k_trade_risk002_ai_plus24_jd_report_stage677_stage372_500k_trade_risk002_ai_plus24_jd_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage677_stage372_500k_trade_risk002_ai_plus24_jd_summary_stage677_stage372_500k_trade_risk002_ai_plus24_jd_v1.csv`
- comparison：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage677_stage372_500k_trade_risk002_ai_plus24_jd_comparison_stage677_stage372_500k_trade_risk002_ai_plus24_jd_v1.csv`
- rolling：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage677_stage372_500k_trade_risk002_ai_plus24_jd_rolling_stage677_stage372_500k_trade_risk002_ai_plus24_jd_v1.csv`
- margin：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage677_stage372_500k_trade_risk002_ai_plus24_jd_margin_usage_stage677_stage372_500k_trade_risk002_ai_plus24_jd_v1.csv`
- activity：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage677_stage372_500k_trade_risk002_ai_plus24_jd_extra_activity_stage677_stage372_500k_trade_risk002_ai_plus24_jd_v1.csv`
- eligibility：`examples/portfolio_backtesting/backtest_outputs/stage677_generated_inputs/qmt_roll_stage677_stage372_500k_trade_risk002_ai_plus24_jd_historical_ai_plus24_jd_eligibility_stage677_stage372_500k_trade_risk002_ai_plus24_jd_v1.csv`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage677_stage372_500k_trade_risk002_ai_plus24_jd_decision_stage677_stage372_500k_trade_risk002_ai_plus24_jd_v1.json`

## 结论

- 本阶段结论：`stage372_500k_trade_risk002_ai_plus24_jd_rejected`。鸡蛋已经进入同一套 AI 选品逻辑，并被 AI 选中 `13` 次，但组合结果比 Stage388 更差，且 `jd` 自身贡献为负。
- 是否进入下一步：不进入正式配置、不 A/B、不改当前实盘产品池。
- 下一步：继续保留“畜禽/鲜活农产品有独立经济驱动”的研究价值，但不能基于当前 AI selector 接入；若继续，必须先重训同宇宙账户级 selector，而不是给 `jd` 调月份、rank 或单品种过滤。

## 过拟合反思

- 运行前判断：不是典型过拟合，因为 `jd.DCE` 是新的独立经济驱动候选，且用户明确要求使用 AI 选品。
- 运行后判断：继续救这个结果会过拟合。
- 原因：`jd` 被 AI top8 选中后，组合全周期、滚动左尾和多起点都更弱；继续调 topN、排除 p/sc/jd 或只选特定月份，就是用失败结果反向拟合历史。

## 继续价值反思

- 运行前判断：有价值，可以检验鸡蛋是否能修复 Stage388 的 AI plus23 失败路径。
- 运行后判断：当前 plus24_jd 候选无推广价值；AI selector 重构仍有价值。
- 原因：结果说明问题不在“少了鸡蛋”，而在现有 AI 目标与 Stage372 账户级目标错配。鸡蛋作为 future source/selector 重训样本可保留，但不进交易池。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage389 当前状态。
- 是否更新 `research/registry.md`：否，本阶段是同线反证，非合入者不改 registry。
- 是否追加根目录 `memory.md/back_log.md`：是，作为“鸡蛋 AI plus24 反证、不要推广现有 selector”的重要记忆追加。
