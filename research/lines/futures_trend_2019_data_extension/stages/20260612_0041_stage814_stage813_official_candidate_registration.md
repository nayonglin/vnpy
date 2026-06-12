# Stage814 Stage813 登记为正式候选版本

- line_id：`futures_trend_2019_data_extension`
- 当前模式：day
- 记录时间：2026-06-12 00:41 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：正式候选登记/配置固化，不是回测
- 是否重要突破：否。属于用户指定的候选升级动作
- 是否触发A/B：否。本阶段复用 Stage813 已完成的纠错 A/B 结果

## 外部调研与判断

- 参考资料：本阶段不新增外部 alpha 资料；执行纪律参考本仓库 `skills/futures-live-execution-sop/SKILL.md` 与 `skills/version-ab-experiment/SKILL.md`，结果依据 Stage813 本地纠错 A/B 报告。
- 我的判断：可以登记为“正式候选/影子盘观察版本”，但不能替换当前实盘默认。原因是 Stage813 的 RSI 锁盈确实改变交易路径并改善部分收益/Sharpe，但没有改善 DD40/DD50 风险失败；它仍是进攻候选而非防守正式替代。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/qmt_roll_official_candidate_stage813_config.py`
- 修改脚本：`examples/portfolio_backtesting/qmt_roll_official_live_config.py`
- 删除脚本：无
- 新增参数：
  - `long_tighter_initial_stop=True`
  - `enable_rsi_partial_exit=True`
  - `rsi_partial_exit_threshold=95.0`
  - `rsi_partial_exit_ratio=0.5`
  - `trailing_stop_enabled=True`
  - `trailing_stop_pct=0.0`
  - `profit_lock_tiers=""`，显式使用策略默认分层锁盈 stop
- 修改参数：将 Stage813 登记为 `official_candidate_stage813_50w_am41_oi08_old_ai_long_tighter_stop_rsi95_v1`
- 删除参数：无

## 回测/归因参数

- 数据区间：本阶段不新增回测；引用 Stage813 年度起点 `2018-01 -> 2026-01`，统一终点 `2026-05-29`
- 账户规模：`500,000`
- 成本口径：沿用 Stage813 年度 A/B 输出
- 样本过滤：全部 `9` 个年度起点，成熟样本为 `2018-2025` 共 `8` 个起点
- 策略/归因口径：Stage813 = Stage804 多头更紧初始止损 + RSI95 半平锁盈；继承 Stage777 `AM41/OI0.8/旧正式AI/maxpos4/关闭连败缩放和 recovery sleeve`

## 结果

- 期末权益：本阶段不新增单一回测结果；代表 `2020-01` 起点 Stage813 ON 为 `27,577,760`
- 总收益：代表 `2020-01` 起点 `5415.5520%`
- 最大回撤：代表 `2020-01` 起点 `-56.0975%`
- Sharpe：代表 `2020-01` 起点 `1.5525`
- 总滑点：代表 `2020-01` 起点 `2,296,860`
- 总交易次数：代表 `2020-01` 起点 `525`
- 胜率：本阶段不新增统计
- 其他关键指标：
  - Stage813 ON vs OFF 全部 `9` 个起点：收益胜出 `5/9`、回撤胜出 `3/9`、Sharpe 胜出 `6/9`、收益+回撤双胜 `2/9`
  - 成熟 `8` 个起点：收益胜出 `5/8`、回撤胜出 `3/8`、Sharpe 胜出 `6/8`
  - 成熟收益中位差 `+13.692pp`、回撤中位差 `0`、Sharpe 中位差 `+0.0311`
  - DD40 失败 OFF `4`、ON `4`；DD50 失败 OFF `2`、ON `2`
  - RSI 半平锁盈触发 `31` 次，合计 `1,520` 手

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage813_stage804_rsi_partial_exit_ablation_yearly_report_stage813_stage804_rsi_partial_exit_ablation_yearly_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage813_stage804_rsi_partial_exit_ablation_yearly_on_summary_stage813_stage804_rsi_partial_exit_ablation_yearly_v1.csv`
- orders：无新增
- daily：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage813_stage804_rsi_partial_exit_ablation_yearly_on_curves_stage813_stage804_rsi_partial_exit_ablation_yearly_v1.csv`
- quality：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage813_stage804_rsi_partial_exit_ablation_yearly_decision_stage813_stage804_rsi_partial_exit_ablation_yearly_v1.json`

## 结论

- 本阶段结论：Stage813 已按用户要求登记为正式候选版本，并显式开启 RSI95 半平锁盈开关；当前实盘默认仍是 Stage372 20万 `official_live_stage372_20w_recovery_sleeve`。
- 是否进入下一步：可以进入候选 shadow/影子盘观察；不能直接进入 live default。
- 下一步：用候选 manifest 跑最新交易日 shadow，对比 Stage372 当前实盘默认和 Stage777 旧候选；若考虑实盘，必须先做 dry-run、经纪商持仓对账和 DD40/DD50 风险复核。

## 过拟合反思

- 运行前判断：有过拟合风险。
- 运行后判断：仍有过拟合风险，但本次通过“不改 live default、显式风险边界、只登记候选”控制了风险。
- 原因：Stage813 的收益/Sharpe 改善不是全局风险改善，DD40/DD50 失败没有下降；若直接因部分收益路径胜出而切正式，就是把候选晋级建立在进攻收益偏好上。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：有价值，但价值在于候选影子盘观察和执行治理，不在于继续扫 RSI 阈值。
- 原因：Stage813 解决了 Stage812 对照污染后的真实开关效果确认，也把 RSI 锁盈口径显式固化，能避免后续再踩隐式默认坑；但继续优化 `90/92/95/97` 这类阈值会过拟合。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage814 候选登记摘要
- 是否更新 `research/registry.md`：是，把当前候选状态从 Stage777 更新为 Stage813 已登记，Stage372 live default 不变
- 是否追加根目录 `memory.md/back_log.md`：是，属于正式候选登记事件
