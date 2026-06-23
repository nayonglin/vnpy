# Stage061 - 产品 OI 参与度确认只读审计

## 基本信息

- 时间：2026-06-20 06:07 CST
- 当前模式：day
- 研究线：`futures_trend_c9_minrisk_highquality`
- 当前官方正式版：`official_live_stage847_c9_15w_stage819_05r_stop_retry_once` / `Stage847-C9-15w`
- 阶段性质：只读外生参与度审计；不是真实组合引擎，不新增交易规则，不触发 A/B，不修改正式配置，不连接 CTP，不调用订单 API
- 是否重要突破：否；这是对“价格顺向但持仓量收缩是否低质量”的反证
- 是否触发 A/B：否。目标桶是大额正贡献，且乐观跳过后收益保留低于 `80%`、回撤恶化

## 开始前反思

- 是否在过拟合：否。规则在运行前固定为一个低自由度经济假设：产品价格在官方方向上已经走顺，但 `open_interest` 没有扩张，可能只是平仓/回补而不是新增参与。没有按年份、产品、方向、阈值或最终盈亏调参。
- 是否有继续价值：是。Stage060 已经证明相对基差 headwind 会切断右尾；OI 是更基础的市场参与度变量，值得用只读上界验证它是否能解释 C9 的低质量信号。

## 外部调研和我的判断

- CME 对 open interest 的定义是期末未平仓合约数量，并把它作为判断市场情绪和价格趋势背后强度的指标之一。我的判断：这支持把 OI 用作“参与度确认”，但不能直接当作方向预测器。资料：https://www.cmegroup.com/education/courses/introduction-to-futures/open-interest
- CFTC/CME COT 框架把 open interest 拆成不同交易者类别，说明 OI 的有效信息来自“谁在持仓”和“持仓结构”，不是单纯总量。我的判断：本阶段只用产品总 OI，所以只能做粗确认，不能直接晋级交易规则。资料：https://www.cftc.gov/MarketReports/CommitmentsofTraders/AbouttheCOTReports/index.htm ，https://www.cmegroup.com/tools-information/quikstrike/commitment-of-traders.html
- Hong and Yogo 的 NBER 论文认为 futures market open interest 在存在套保需求和需求曲线向下时可能比价格更有宏观/资产信息。我的判断：OI 有研究价值，但必须用资金曲线和跨产品图验证，不能用“价格涨、OI降=趋势弱”这个教科书句式直接下结论。资料：https://www.nber.org/system/files/working_papers/w16712/revisions/w16712.rev1.pdf
- GitHub/AKShare futures 文档显示交易所、品种、交易时间和期货数据接口是开放路线，但 Stage029 已证明会员持仓接口历史覆盖仍不稳定。本阶段因此不继续修会员排名，而使用本仓已有 Stage496 synthetic full-preclose bar 中点时化 `synthetic_open_interest`。资料：https://github.com/akfamily/akshare/blob/main/docs/data/futures/futures.md

## 本阶段版本变更

- 新增脚本：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage061_product_oi_confirmation_audit.py`
- 新增输出目录：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage061_product_oi_confirmation_audit/`
- 新增参数：
  - `WINDOW = 63`
  - `MAX_SIGNAL_AGE_DAYS = 7`
  - `TARGET_BUCKET = price_aligned_oi_contracting`
- 修改参数：无
- 删除参数：无
- 数据源：
  - 输入 closed lots：Stage060 features，`399` 笔官方 closed lots
  - 输入资金曲线：Stage060 official curve
  - OI 源：Stage496 synthetic full-preclose bar，`2020-01-02` 至 `2026-04-30`，`19` 个产品，`26,380` 行
- 固定规则：
  - `directional_price_change_63 = direction_sign * log(close_t / close_t-63)`
  - `oi_log_change_63 = log(open_interest_t / open_interest_t-63)`
  - 目标桶：`directional_price_change_63 > 0` 且 `oi_log_change_63 <= 0`
  - 解释：官方方向的价格已经顺向，但产品持仓量未扩张，直觉上可能代表趋势缺少新增资金确认

## 回测/审计结果

### 官方 C9/15w 基准

- 期末权益：`39,176,437.60`
- 总收益：`26,017.6251%`
- 最大回撤：`-45.0827%`
- Sharpe：`1.6339`
- 总滑点：`2,730,130`
- 总交易次数：`787`
- 胜率：`53.2560%`

### Stage061 只读覆盖

- official lots：`399`
- OI-ready：`299/399 = 74.9373%`
- `2018/2019` ready 为 `0`，因为 Stage496 OI 从 `2020-01-02` 开始
- `2020` ready `69/84 = 82.1429%`
- `2021-2025` ready 均接近或等于 `100%`
- `2026` ready `14/15 = 93.3333%`

### 分桶结果

| bucket | lots | products | years | net_pnl |
| --- | ---: | ---: | ---: | ---: |
| `price_aligned_oi_expanding` | 146 | 18 | 7 | `19,175,245.40` |
| `price_not_aligned` | 77 | 18 | 7 | `12,399,427.80` |
| `price_aligned_oi_contracting` | 76 | 18 | 7 | `10,928,717.00` |
| `oi_confirm_missing` | 100 | 15 | 5 | `551,222.40` |

### 目标桶乐观跳过上界

- 目标桶：`price_aligned_oi_contracting`
- 目标桶笔数：`76`
- 目标桶产品数：`18`
- 目标桶年份数：`7`
- 目标桶 realized PnL：`+10,928,717.00`
- 乐观跳过后期末权益：`28,247,720.60`
- 乐观跳过后总收益：`18,731.8137%`
- 收益保留：`71.9966%`
- 乐观跳过后最大回撤：`-52.2733%`
- 乐观跳过后 Sharpe：`1.3818`
- 结论：目标桶不是坏桶。即使按最乐观上界直接跳过，也会明显砍掉右尾，收益保留低于 `80%`，最大回撤比官方恶化约 `7.1906pp`。

## 视觉分析

- 资金曲线图：`qmt_roll_stage061_c9_minrisk_product_oi_confirmation_audit_upper_bound_path_chart_stage061_product_oi_confirmation_audit_v1.png`
  - 蓝线官方曲线长期高于红线。跳过目标桶后，红线在 `2022` 主回撤区更深，之后持续低于官方。
  - 中间的 skipped target PnL 累计线最终上行到约 `1,092.9万`，说明目标桶是正贡献集合。
- 分桶贡献图：`qmt_roll_stage061_c9_minrisk_product_oi_confirmation_audit_bucket_contribution_chart_stage061_product_oi_confirmation_audit_v1.png`
  - `price_aligned_oi_expanding` 是最强右尾桶，但 `price_aligned_oi_contracting` 也稳步贡献正收益，并不是系统性坏质量集合。
  - `price_not_aligned` 也能在 `2025` 大幅跃升，说明产品级 63 日价格/OI 状态不是 C9 单笔质量的充分条件。
- 年度热图：`qmt_roll_stage061_c9_minrisk_product_oi_confirmation_audit_bucket_year_heatmap_stage061_product_oi_confirmation_audit_v1.png`
  - 目标桶在 `2021`、`2024`、`2025` 有明显正贡献，尤其 `2024` 约 `591.5万`，`2025` 约 `287.8万`。
  - 这不是单一年份的噪声，也不是全周期负向桶。
- 产品热图：`qmt_roll_stage061_c9_minrisk_product_oi_confirmation_audit_product_bucket_heatmap_stage061_product_oi_confirmation_audit_v1.png`
  - 目标桶正贡献来自 `ru.SHFE`、`au.SHFE`、`SH.CZCE`、`jm.DCE`、`fu.SHFE` 等多个产品。
  - `ru.SHFE` 在 expanding 桶为负、contracting 桶为正，直接反证“价格顺向但 OI 收缩必然低质量”。
- 散点图：`qmt_roll_stage061_c9_minrisk_product_oi_confirmation_audit_oi_confirmation_scatter_stage061_product_oi_confirmation_audit_v1.png`
  - OI 变化和 realized PnL、前 30 分钟 R、Stage052 趋势 t-stat 没有干净线性/单调分界。
  - 红色目标桶里既有亏损，也有多个大额正收益点；不能据此写最小风险或跳过规则。

## 决策

- 决策：`stage061_product_oi_contracting_no_candidate_right_tail_dominant`
- 不进入 true engine。
- 不触发 `version-ab-experiment`。
- 不修改官方 C9/15w 配置。
- 关闭“产品价格顺向但 OI 收缩就削仓/跳过”的直接规则。

## 过拟合与价值反思

- 运行后是否在过拟合：否。本阶段没有因为结果不好去调 `63` 日窗口、改 `<=0` 阈值、分产品或分年份救参；结果直接反证自然假设。
- 运行后是否有继续价值：有，但不在这条直接规则上继续。价值在于确认：粗粒度产品总 OI 不足以识别 C9 的低质量信号，C9 右尾也可能来自 OI 收缩阶段的价格趋势。下一步如果继续 OI，必须升级到更细的点时化结构，例如会员持仓类别、主力合约/次主力换月中的 OI 迁移、或真正订单簿/成交结构；否则应转向新的独立外生源。

## TODO

- 不扫 `63/126/252`、`0/正负阈值`、产品、方向、年份或月份。
- OI 总量只保留为解释/forward-watch 特征，不进入削仓/跳过规则。
- 下一步优先方向：
  - 若做外生数据工程：重新评估会员持仓/仓单/库存的点时化覆盖，而不是在总 OI 上救参。
  - 若回到分钟级目标：使用已校准 replay 账本，提出新的第一性、开仓时可见、不会切断右尾的分钟执行候选。
