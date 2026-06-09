# Stage393 Stage391 C2 加 PVC 回测

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：`2026-06-06 20:10 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：按用户要求，在 Stage391 C2 的 `50万 + risk_ratio_*=0.02 + plus24 鸡蛋 + no-AI + short_case1a/2/3 + maxpos24` 形态上新增 PVC `v.DCE`，形成 plus25 后重跑 A/C/C2。
- 是否重要突破：否。该阶段是反证，PVC 加入后 C2 明显弱于 Stage391 C2。
- 是否触发A/B：是。新增 PVC 后构造 A/C/C2 预声明对照，但结果不进入正式 A/B。

## 外部调研与判断

- 参考资料：
  - 本地历史 Stage241/Stage292/Stage295 已把 `v.DCE` 记录为 PVC/聚氯乙烯相关候选或 P0 监控对象，说明符号映射在仓库内已有历史依据。
  - 在线核验只用于确认 PVC 对应大商所聚氯乙烯期货、交易代码 `V`；未把外部行情、新闻或品种热度用于收益筛选。
  - 沿用 Stage390/Stage391 对 AQR 趋势跟踪和 `pysystemtrade` 的判断：多市场分散必须看账户级路径、成本、保证金和任意启动窗口，不能只看单品种独立表现。
- 我的判断：PVC 从品类上有独立经济驱动，值得按用户要求执行一次同规则回测；但 Stage391 C2 已经是高并发、成本敏感的边界形态，新增一个品种可能不是简单增加机会，而是改变持仓排序、保证金占用、恢复仓和强制减仓路径。运行后结果支持后一种解释：PVC 自身净亏损不大，但对组合路径的挤占很大。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage680_stage372_500k_trade_risk002_no_ai_plus25_jd_v_short_cases123.py`
- 修改脚本：无。
- 删除脚本：无。
- 新增参数：
  - `EXTRA_PRODUCTS=("ni.SHFE","ag.SHFE","sc.INE","p.DCE","jd.DCE","v.DCE")`
  - `ALLOWED_SHORT_SIGNALS={"short_case1a","short_case2","short_case3"}`
  - `TARGET_NO_MAXPOS_VARIANT=stage372_500k_trade_risk002_no_ai_plus25_jd_v_short_cases123_maxpos25`
- 修改参数：
  - plus 宇宙从 Stage391 的 `24` 个产品扩为 `25` 个产品。
  - `enable_ai_product_pool_filter=False`，继续关闭 AI product pool filter。
  - C/C2 继续使用 `risk_ratio_*=0.02`；A 使用 `risk_ratio_*=0.04`。
  - C2 的 `max_concurrent_positions` 从 `24` 跟随宇宙规模改为 `25`。
- 删除参数：无。

## 回测/归因参数

- 数据区间：主历史全周期 `2020-01-02` 至 `2026-04-30`；另包含 start-year、market phase、weak window、YTD latest-ai 标签窗口。
- 账户规模：`500,000`。
- 成本口径：正常滑点成本为主，并输出 `1x/2x/3x` 成本压力。
- 样本过滤：关闭 AI product pool filter；所有 plus25 产品只受原趋势逻辑、风险资金、恢复仓 sleeve、强制保证金减仓和并发上限约束。
- 策略/归因口径：
  - A：`stage372_500k_trade_risk004_no_ai_plus25_jd_v_short_cases123_maxpos4`
  - C：`stage372_500k_trade_risk002_no_ai_plus25_jd_v_short_cases123_maxpos4`
  - C2：`stage372_500k_trade_risk002_no_ai_plus25_jd_v_short_cases123_maxpos25`

## 结果

- 期末权益：
  - A：`1,394,775`
  - C：`634,835`
  - C2：`1,528,705`
- 总收益：
  - A：`178.9550%`
  - C：`26.9670%`
  - C2：`205.7410%`
- 最大回撤：
  - A：`-59.8813%`
  - C：`-45.4458%`
  - C2：`-42.8712%`
- Sharpe：
  - A：`0.6257`
  - C：`0.2900`
  - C2：`0.7136`
- 总滑点：
  - A：`307,860`
  - C：`199,830`
  - C2：`273,780`
- 总交易次数：
  - A：`1,517`
  - C：`1,378`
  - C2：`2,012`
- 胜率：
  - A：`50.0997%`
  - C：`48.4154%`
  - C2：`51.3351%`
- 其他关键指标：
  - C2 broker10 资金占用峰值 `76.4689%`、p95 `50.8281%`、`>30%/>50%/>70%/>90%/>100%` 天数 `588/86/3/0/0`。
  - C2 成本压力：`1x` 为 `1,528,705/205.7410%/-42.8712%/Sharpe0.7136`；`2x` 为 `1,254,925/150.9850%/-48.2339%/Sharpe0.5893`；`3x` 为 `981,145/96.2290%/-54.4592%/Sharpe0.4729`。
  - C2 年度：2020 `+232,805`，2021 `+65,680`，2022 `-153,310`，2023 `+90,800`，2024 `+356,035`，2025 `+491,335`，2026截至4月 `-54,640`；不是每年正收益。
  - C2 新增/扩展品种贡献：`ag +257,730`、`jd +64,920`、`ni -195,230`、`p +102,060`、`sc -47,600`、`v -51,410`，合计 `+130,470`。
  - 相对 Stage391 C2：Stage391 C2 为 `3,465,220/593.0440%/-33.5078%/Sharpe1.0047`，本阶段 C2 期末权益少 `1,936,515`，收益少 `387.303pp`，回撤劣化 `9.3635pp`，Sharpe 少 `0.2911`；虽然 broker10 峰值从 `83.0646%` 降到 `76.4689%`，但收益和稳定性都明显变差。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage680_stage372_500k_trade_risk002_no_ai_plus25_jd_v_short_cases123_report_stage680_stage372_500k_trade_risk002_no_ai_plus25_jd_v_short_cases123_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage680_stage372_500k_trade_risk002_no_ai_plus25_jd_v_short_cases123_summary_stage680_stage372_500k_trade_risk002_no_ai_plus25_jd_v_short_cases123_v1.csv`
- orders：未单独输出订单明细。
- daily：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage680_stage372_500k_trade_risk002_no_ai_plus25_jd_v_short_cases123_curves_stage680_stage372_500k_trade_risk002_no_ai_plus25_jd_v_short_cases123_v1.csv`
- quality：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage680_stage372_500k_trade_risk002_no_ai_plus25_jd_v_short_cases123_checks_stage680_stage372_500k_trade_risk002_no_ai_plus25_jd_v_short_cases123_v1.csv`

## 结论

- 本阶段结论：`stage372_500k_trade_risk002_no_ai_plus25_jd_v_short_cases123_rejected`。
- 是否进入下一步：不进入正式、不 A/B、不改官方配置。
- 下一步：PVC 不应作为救 Stage391 C2 的手工追加品种。若继续，只做只读归因：拆 `v.DCE` 对 ag/ni/p/sc/jd 的持仓挤占、强制减仓触发、short_case2/3 入场顺序和 2022/2026 弱窗口贡献；不做 PVC 月份、方向、rank、年份过滤或并发整数救援。

## 过拟合反思

- 运行前判断：不是典型过拟合，但有明显风险。PVC 是本地历史候选且用户明确要求加入，执行一次全规则回测有研究价值；但 Stage391 C2 已经过多轮失败后出现后段抬升，继续一个品种一个品种追加，容易滑向历史救援。
- 运行后判断：继续追加单品种救 C2 会过拟合。
- 原因：PVC 加入后不是简单贡献一个独立 alpha，而是大幅改变组合路径；交易数还减少 `102`、滑点减少 `222,930`，结果仍显著变差，说明问题不是成本多一点，而是机会排序和风险槽被挤占。再按品种筛掉 PVC 或筛年份只会拟合本次失败样本。

## 继续价值反思

- 运行前判断：有价值。它能回答“C2 加 PVC 是否还能保持 Stage391 后段优势”。
- 运行后判断：直接路线无继续价值；只读归因有价值。
- 原因：C2 加 PVC 后收益从 Stage391 的 `593.0440%` 降到 `205.7410%`，回撤从 `-33.5078%` 扩到 `-42.8712%`，Sharpe 从 `1.0047` 降到 `0.7136`。这不是可接受的小幅波动，而是结构性破坏；但它能帮助理解高并发 C2 的有效风险槽很脆弱。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage393 反证状态。
- 是否更新 `research/registry.md`：否。
- 是否追加根目录 `memory.md/back_log.md`：是，作为后续避免手工追加 PVC 救 Stage391 C2 的重要负结论。
