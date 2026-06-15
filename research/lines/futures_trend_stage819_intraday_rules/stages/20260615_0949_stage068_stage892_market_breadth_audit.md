# Stage068 - Stage892 全市场 first60 广度可行性审计

- 时间：2026-06-15 09:49 CST
- 当前模式：day
- line_id：`futures_trend_stage819_intraday_rules`
- model_tag：`stage892_stage891_market_breadth_audit_v1`
- 源候选：`official_candidate_stage819_30w_am41_oi08_old_ai_long_tighter_stop_rsi95_v1`
- 阶段性质：只读外生参与度数据可行性审计；不新增交易规则、不接真实组合引擎、不改 Stage372 官方正式版、不改官方候选配置、不连接 CTP、不调用下单、不触发 A/B。
- 是否重要突破：否。它不是 alpha 结果，而是确认当前 Stage861 分钟源不能直接支持“全市场广度”规则。

## 外部调研和判断

- 参考资料：CME 关于 market participation、volume/OI 与风险管理/止损纪律的资料支持把全市场广度当作外生参与度信息源；vn.py 官方仓库用于确认本地回测和数据处理技术栈背景。
- 我的判断：市场广度是和单合约 first60、OR15、成交量三元不同的一类信息，值得做一次低自由度可行性审计；但必须先证明数据面板真的是“同一交易日全市场多合约”，否则不能写规则。

## 本次版本改动

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage892_stage891_market_breadth_audit.py`
- 新增记录：`research/lines/futures_trend_stage819_intraday_rules/stages/20260615_0949_stage068_stage892_market_breadth_audit.md`
- 固定审计定义：
  - 对每个 C9 lot 的 `entry_date`，读取 Stage861 `full_minute_bars` 中同日所有合约最早 `60` 根分钟K。
  - 计算全市场上涨/下跌比例，再按信号方向得到 `market_same_direction_share`。
  - 最少合约数固定为 `20`，广度中轴固定为 `50%`。
  - 不扫描分钟窗口、广度阈值、品种族群、方向或年份。
- 新增参数：无交易参数；只读审计常量 `EARLY_BARS=60`、`MIN_MARKET_SYMBOLS=20`、`BREATH_MIDPOINT=0.50`。
- 修改参数：无。
- 删除参数：无。
- 官方正式版 Stage372：未修改。
- 官方候选配置：未修改。

## 数据与输出

- 输入：Stage889 C9 features、Stage861 full minute bars。
- C9 closed lots：`401`
- market daily rows：`1,408`
- market breadth missing lot pct：`100.0%`
- summary chart 尺寸：`2700x2100`
- atlas page001 尺寸：`2700x1950`
- atlas 页数：`3`
- 输出：
  - report：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage892_stage891_market_breadth_audit_report_stage892_stage891_market_breadth_audit_v1.md`
  - features：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage892_stage891_market_breadth_audit_features_stage892_stage891_market_breadth_audit_v1.csv`
  - market daily：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage892_stage891_market_breadth_audit_market_daily_stage892_stage891_market_breadth_audit_v1.csv`
  - state summary：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage892_stage891_market_breadth_audit_state_summary_stage892_stage891_market_breadth_audit_v1.csv`
  - proxy summary：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage892_stage891_market_breadth_audit_proxy_summary_stage892_stage891_market_breadth_audit_v1.csv`
  - proxy yearly：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage892_stage891_market_breadth_audit_proxy_yearly_stage892_stage891_market_breadth_audit_v1.csv`
  - summary chart：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage892_stage891_market_breadth_audit_summary_chart_stage892_stage891_market_breadth_audit_v1.png`
  - atlas manifest：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage892_stage891_market_breadth_audit_atlas_manifest_stage892_stage891_market_breadth_audit_v1.csv`
  - decision：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage892_stage891_market_breadth_audit_decision_stage892_stage891_market_breadth_audit_v1.json`

## 新增回测/代理结果

本阶段不新增真实回测。固定代理全部无触发，因为 `market_breadth_state` 全部为 `market_breadth_missing`：

- `MB1_exit60_market_breadth_adverse`：触发 `0` 笔，delta `0`
- `MB2_exit60_market_and_own_price_adverse`：触发 `0` 笔，delta `0`
- `MB3_exit60_market_adverse_and_05r_adverse_first`：触发 `0` 笔，delta `0`
- `MB4_exit60_market_adverse_own_price_favorable`：触发 `0` 笔，delta `0`

状态层面显示当前数据源不是广度面板：

- `market_breadth_missing__own_price_adverse`：`171` 笔，PnL `-2,558,048.70`，loser PnL 覆盖 `53.0324%`。
- `market_breadth_missing__own_price_favorable`：`215` 笔，PnL `55,467,848.30`，big winner `22`。
- `market_breadth_missing__own_price_missing`：`15` 笔，PnL `1,040,465.00`。

## K线视觉检查

- atlas page001 代表性样本标题里显示 market breadth 的实际合约数只有 `n=1/3/5` 等，无法达到 `MIN_MARKET_SYMBOLS=20`。
- K线本身可视化正常，但它只能证明单合约路径；不能证明全市场广度。
- 这说明 Stage861 的 full minute bars 对目标交易是完整的，但本质是事件覆盖面板，不是同日全市场连续面板。

## 决策

- decision：`stage892_market_breadth_data_scope_not_broad_enough_no_engine`
- 结论：当前 Stage861 分钟源不能直接支持市场广度规则；不能把 `market_same_direction_share` 当成可交易信号，也不能因为缺失而扫描更低 `MIN_MARKET_SYMBOLS` 或按品种/年份救参。
- 操作：不接真实引擎、不触发 A/B、不改官方正式版、不改官方候选配置。

## 反过拟合反思

- 运行前：否。只用固定 `60` 根和 `50%` 广度中轴，先做数据面板可行性审计。
- 运行后：如果为了让当前数据源产生信号而把最少合约数从 `20` 降到 `1/3/5`，或者按品种族群、年份、方向去拼广度，就是过拟合并且概念上错误。

## 继续价值反思

- 运行前：有价值。市场广度是真正不同于单合约 K线的小变体的信息源。
- 运行后：当前 Stage861 数据面板下没有继续价值；市场广度路线只有在另建“全市场连续分钟面板”后才有研究价值。若不能补这个面板，本线下一步应转账户级非交易层生存线或暂停。

## 后续规划和 TODO

- 不使用当前 Stage861 full minute bars 继续做市场广度交易规则。
- 不扫描 `MIN_MARKET_SYMBOLS`、广度阈值、分钟窗口、品种族群、方向或年份。
- 若未来继续市场广度方向，先独立构建全市场连续分钟面板，并在进入规则审计前验证每个 entry_date 的合约覆盖数分布。
- 本阶段不是正式候选、不是重要突破，不更新 `registry.md`、不追加根目录 `memory.md` / `back_log.md`。
