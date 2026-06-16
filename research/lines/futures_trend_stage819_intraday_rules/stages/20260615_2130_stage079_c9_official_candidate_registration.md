# Stage079 C9登记为官方 primary candidate 与晋升闸门

- line_id：`futures_trend_stage819_intraday_rules`
- 当前模式：`day`
- 记录时间：`2026-06-15 21:30 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：正式候选注册 + 晋升闸门；不新增交易规则、不新增回测。
- 是否重要突破：是。C9 从研究线版本登记为官方 primary official candidate，但仍非 live default。
- 是否触发A/B：触发候选晋升纪律；本阶段只做 registry/manifest 静态验证，未运行新的 A/C 回测。

## 外部调研与判断

- 参考资料：
  - FCA algorithmic trading controls：https://www.fca.org.uk/publications/multi-firm-reviews/algorithmic-trading-controls-high-level-observations
  - FIA automated trading risk controls：https://www.fia.org/sites/default/files/2024-07/FIA_WP_AUTOMATED%20TRADING%20RISK%20CONTROLS_FINAL_0.pdf
  - vn.py GitHub README：https://github.com/vnpy/vnpy/blob/master/README_ENG.md
  - Interactive Brokers walk-forward analysis：https://www.interactivebrokers.com/campus/ibkr-quant-news/the-future-of-backtesting-a-deep-dive-into-walk-forward-analysis/
- 我的判断：
  - 正式候选晋升不是“收益更高就切默认”，而是先冻结版本、审计参数、建立 kill gate、再做 shadow/dry-run 与风险接受。
  - vn.py 的组合回测/策略配置可以作为 C9 registry 的工程入口；但 C9 仍引用 Stage847 研究 wrapper，后续 live default 前必须工程化或显式批准该边界。
  - walk-forward/rolling validation 的价值是暴露路径依赖和起点风险。C9 的右尾很强，但 Stage896/899 的回撤和 broker10 尾部仍是正式切换前的核心阻力。

## 本次变更

- 新增脚本：
  - `examples/portfolio_backtesting/qmt_roll_official_candidate_stage847_c9_config.py`
- 修改脚本：
  - `examples/portfolio_backtesting/qmt_roll_official_live_config.py`
    - 新增 C9 候选版本登记。
    - `OFFICIAL_CANDIDATE_PRIMARY_VERSION` 从 Stage819 30w 切到 C9。
    - `OFFICIAL_LIVE_VERSION` 保持 `official_live_stage372_20w_recovery_sleeve`，不改实盘默认。
- 新增记录：
  - `research/lines/futures_trend_stage819_intraday_rules/C9_OFFICIAL_PROMOTION_GATE.md`
- 删除脚本：无。
- 新增参数：
  - `enable_stage827_intraday_c2_stop=True`
  - `enable_stage830_broker10_margin_cap=True`
  - `enable_stage847_half_r_stop_retry=True`
  - `stage847_stop_retry_r=0.5`
  - `stage847_max_retries=1`
- 修改参数：
  - 官方候选 primary 指向 `official_candidate_stage847_c9_30w_stage819_05r_stop_retry_once_v1`。
- 删除参数：无。

## 回测/归因参数

- 数据区间：本阶段不新增回测；引用 Stage078 冻结结果 `2018-01-02 -> 2026-05-29` 及 Stage896/897/899 多起点结果。
- 账户规模：C9 候选 `300,000`；当前 live default Stage372 `200,000`。
- 成本口径：沿用 Stage078/Stage863/896/897/899 既有 vn.py 组合回测成本、手续费、滑点设置。
- 样本过滤：无新增样本过滤；不按品种、方向、年份、窗口好坏调整。
- 策略/归因口径：
  - C9 官方候选冻结为 Stage819 30w + C2 intraday stop + broker10 cap + `0.5R` stop/retry once。
  - 当前正式默认仍为 Stage372 20w。

## 结果

- 静态验证：
  - `py_compile` 通过：`qmt_roll_official_candidate_stage847_c9_config.py`、`qmt_roll_official_live_config.py`。
  - C9 manifest 可导入，版本为 `official_candidate_stage847_c9_30w_stage819_05r_stop_retry_once_v1`。
  - C9 状态为 `official_candidate_not_live_default_high_risk_watch`，`live_default=False`，资金 `300000`，stop/retry 参数为 `0.5R / 1`。
  - 官方 manifest 当前 live version 仍为 `official_live_stage372_20w_recovery_sleeve`。
  - 官方 manifest primary candidate 已指向 C9，候选清单共 `4` 个。
- 引用 Stage078 冻结指标：
  - C9 全周期：期末权益 `51,297,786.20`，总收益 `16,999.2621%`，最大回撤 `-41.6664%`，Sharpe `1.6404`，总滑点 `3,646,200`，总交易次数 `790`，胜率 `53.5299%`，max broker10 `115.0507%`。
  - Stage896 完整 3 年窗口：C9 `7/7` 正收益，收益中位 `562.2128%`，最差回撤 `-56.1208%`，DD40/DD50 `4/1`，broker100 `2`；相对 Stage372 收益胜 `7/7`、Sharpe 胜 `6/7`、回撤胜 `1/7`、broker10 胜 `0/7`。
  - Stage897 完整 1 年窗口：`12/15` 正收益，负窗口为 `2018-01/2018-06/2022-01`，最差回撤 `-35.0696%`。
  - Stage898：`metric_fail_count=0`、`p0_fail_count=0`、`c9_open_missing_full_minute_entry_day_count=0`。
  - Stage899：月度起点 `101` 个中 `99` 个曾转正；成熟 1 年以上 `89/89` 曾转正且当前全部正收益；全月度最差回撤 `-58.0872%`。

## 输出文件

- report：`research/lines/futures_trend_stage819_intraday_rules/C9_OFFICIAL_PROMOTION_GATE.md`
- summary：`examples/portfolio_backtesting/qmt_roll_official_candidate_stage847_c9_config.py`
- orders：无；未连接 CTP，未调用下单。
- daily：无新增。
- quality：官方 manifest 静态验证输出。

## 结论

- 本阶段结论：C9 已正式登记为 primary official candidate；这只是“官方候选晋升”，不是“实盘默认切换”。
- 是否进入下一步：是。
- 下一步：
  1. 用官方候选入口做 Stage372 vs C9 的注册后同窗口 A/C 复核。
  2. 跑最新完成交易日 C9 official-candidate shadow，只读信号、pending、diagnostics。
  3. 建立 dry-run 和 broker-state reconciliation；任何真实报单必须另行显式确认。
  4. 处理 Stage847 研究 wrapper 的工程化边界，或形成明确审批记录。

## 过拟合反思

- 运行前判断：不是新增过拟合，但有选择性晋升风险。
- 运行后判断：本阶段没有新增参数和回测筛选，不构成新的过拟合；但 C9 若因高收益直接切 live default，会忽视 Stage896/899 已暴露的风险尾。
- 原因：本次只冻结已有 C9 规则并登记候选，没有扫 R 倍数、重试次数、月份、品种、方向或窗口；真正风险来自决策层面是否接受 `-56%/-58%` 回撤和 broker10 over-100。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：仍有价值，但价值已经从“继续调策略”转为“执行治理、shadow、dry-run、风险接受、工程化”。
- 原因：数据 P0 已清零，C9 收益材料性足够；剩余问题不是继续找更好参数，而是确认风险尾能否被操作纪律接受。

## 合入建议

- 是否更新本线 `LINE.md`：是，记录 C9 已成为官方 primary candidate。
- 是否更新 `research/registry.md`：本阶段不直接修改，由合入者统一更新；当前 registry 仍可保留 Stage819 历史状态直到统一整理。
- 是否追加根目录 `memory.md/back_log.md`：是。C9 登记为正式候选属于重要候选状态变更。
