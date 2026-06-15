# Stage026 Stage850 产品方向敞口生存线规则设计草案

- line_id：`futures_trend_stage819_intraday_rules`
- 当前模式：`day`
- 记录时间：`2026-06-14 23:59 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：规则设计冻结；不接引擎、不跑回测、不连接 CTP、不调用下单。
- 是否重要突破：否。只是把 Stage024/025 的机制判断转成低自由度候选规则边界。
- 是否触发A/B：否。本阶段不产生新策略版本，不进入官方候选，不与正式版做 A/B。

## 外部调研与判断

- 参考资料：
  - CME futures order types：https://www.cmegroup.com/education/courses/things-to-know-before-trading-cme-futures/futures-order-types
  - CME position and risk management：https://www.cmegroup.com/education/courses/things-to-know-before-trading-cme-futures/position-and-risk-management
  - CFTC stop-loss order education：https://www.cftc.gov/sites/default/files/Stoploss_final_ada.pdf
  - vn.py GitHub：https://github.com/vnpy/vnpy
- 我的判断：
  - 外部资料继续支持“止损”和“仓位/保证金风险管理”是两层问题。Stage023 的 C9 已经证明实时止损+一次重试有进攻价值，但 Stage024/025 说明左尾不是靠继续调止损倍数能解决。
  - vn.py/VeighNa 只是组合策略回测和实盘框架；本阶段不能从框架文档复制一个规则，而应在本仓库已验证的资金联动问题上抽象低自由度规则。
  - Stage025 的核心证据是 `8/8` paired lots 同路径但 C9 更大仓；这不是 K 线形态分类问题，而是产品方向风险预算在账户回撤状态下继续放大的问题。

## 本次变更

- 新增脚本：无。
- 修改脚本：无。
- 删除脚本：无。
- 新增参数：无。本阶段不新增可跑参数，只冻结规则形状。
- 修改参数：无。
- 删除参数：无。

## 回测/归因参数

- 数据区间：不新增回测；沿用 Stage024/025 对 `2022-03-09 -> 2022-06-29` 压力段和 C9/C4 paired lots 的证据。
- 账户规模：沿用 Stage819 候选 `300,000` 口径。
- 成本口径：不新增成本压力；沿用 Stage847/849 已记录结果。
- 样本过滤：无新增筛选。禁止按 `fu/AP/FG`、年份、方向、`1.3549` 手数比或单个 episode 反推规则。
- 策略/归因口径：
  - 参考 A：Stage819 baseline。
  - 参考 C4：`stage830_stage819_c2_broker10_100_cap`。
  - 参考 C9：`stage847_stage819_c4_05r_stop_retry_once`。
  - 本阶段只做设计，不生成 C10/C11/C850 引擎。

## 结果

- 期末权益：未新增；沿用 Stage847 C9 `37,395,131.2`，C4 `30,523,910.8`。
- 总收益：未新增；沿用 Stage847 C9 `12365.0437%`，C4 `10074.6369%`。
- 最大回撤：未新增；沿用 Stage847 C9 `-53.2418%`，C4 `-50.7900%`。
- Sharpe：未新增；沿用 Stage847 C9 `1.4910`，C4 `1.4519`。
- 总滑点：未新增；沿用 Stage847 C9 `2,610,040`，C4 `2,079,430`。
- 总交易次数：未新增；沿用 Stage847 C9 `730`，C4 `677`。
- 胜率：未新增；沿用 Stage847 C9 `53.3156%`，C4 `53.6294%`。
- 其他关键指标：
  - 决策标签：`stage850_product_direction_exposure_guard_design_only`。
  - 直接否决的规则形状：
    - 不做产品名、年份、方向黑名单。
    - 不做 `0.4R/0.6R`、开盘分钟窗、OR 长度、重试次数等入场日小参数救参。
    - 不复刻 C5 的单纯 broker10 `>100%` 全局 forced deleverage；Stage833 已反证。
    - 不复刻 C6 的 top3/direction share 阈值生存线；Stage838 已反证。
    - 不做止损后 blanket cooldown；Stage836/845 已反证。
    - 不使用 C4 路径、A 路径、未来收益、事后最大亏损、`1.3549` 手数比作为 live 规则输入。

### 冻结候选形状：PDEG-v0 drawdown budget freeze

- 名称：`stage850_pdeg_v0_drawdown_budget_freeze_design_only`。
- 目标：只在账户已经进入回撤状态时，阻止同一产品方向风险预算继续按高权益路径放大；如果必须减仓，只减“预算外增量”，不把正常趋势底仓直接砍掉。
- 实时可见状态：
  - 当前账户估算权益 `estimated_equity`。
  - 当前账户权益高水位 `account_high_water_equity`。
  - 当前 broker10 保证金/权益 `broker10_margin_to_equity`。
  - 当前持仓，按 `product + direction` 聚合为产品方向 key。
  - 每个产品方向 key 的当前合约手数、名义敞口、保证金贡献和最近一次 key-flat 时记录的预算权益。
  - 即将发出的 entry/add/retry/rollover reopen 目标手数和预估保证金。
- 状态定义：
  - `drawdown_mode = estimated_equity < account_high_water_equity`。不设 `-10%/-20%` 小阈值；只要离开权益高水位，就进入预算冻结语义。
  - `product_direction_key = product + direction`，不区分具体合约月份，换月仍属于同一 key。
  - `key_budget_equity = min(estimated_equity, last_key_flat_equity)`；若该 key 无历史 flat 记录，则用当前 `estimated_equity`，不追溯未来样本。
  - `key_budget_risk_cash` 和 `key_budget_margin_cash` 由现有 sizing/margin 函数基于 `key_budget_equity` 计算；不引入新的小数倍率。
- 触发条件：
  - 只在 `drawdown_mode = true` 时评估。
  - 只评估当前或下单后将成为最大产品方向保证金贡献的 key；不处理非主导小仓。
  - 只在新 entry/add/retry/rollover reopen 会让该 key 的风险现金或保证金现金超过 `key_budget_*` 时拦截。
  - 若总 broker10 已经或将要超过既有硬生存线 `100%`，允许对最大 key 做“预算外增量”减仓；否则优先只冻结新增/加仓，不强行平底仓。
- 动作：
  - 对新开/加仓/重试/换月重开：把目标手数压到不超过该 key 的冻结预算；压到 `0` 时跳过本次增加暴露。
  - 对持仓后 broker10 超过 `100%` 的情形：只减最大 key 中超过冻结预算的手数，不能直接把整笔趋势仓平掉。
  - 每次动作必须记录 `key`、`drawdown_mode`、`estimated_equity`、`account_high_water_equity`、`last_key_flat_equity`、`before/after volume`、`before/after broker10`、`reason`。
- 与 C5/C6 的区别：
  - C5/C6 是“看到 broker10 压力后按保证金/集中度强制砍仓”，容易砍错簇并释放新风险。
  - PDEG-v0 是“账户回撤中不允许主导产品方向继续按更高权益预算扩张”，先管预算膨胀，再有限处理预算外增量。
  - 它不需要 top3 share、direction share、产品名或年份阈值。
- 失败条件：
  - 如果 Stage027 只读反事实显示该规则无法命中 Stage849 的 paired pressure lots，则停止该分支。
  - 如果命中只能依赖新增小数阈值、产品名、方向、年份或 `1.35x` 手数比，则停止该分支。
  - 如果规则会覆盖大多数普通右尾持仓，说明它不是生存线而是机械降杠杆，应停止。

## 输出文件

- report：本文件。
- summary：无。
- orders：无。
- daily：无。
- quality：
  - 本阶段无代码改动，无 `py_compile`。
  - 质量检查只要求本 stage 记录完整、LINE 同步、无 CTP/下单触发。

## 结论

- 本阶段结论：
  - 可以保留一个低自由度后续候选：`PDEG-v0 drawdown budget freeze`。
  - 但它现在只是规则设计，不是有效策略；不能进入官方候选、不能触发 A/B、不能替代 C4/C9 或 Stage819。
  - Stage850 的本质不是“分钟 K 线形态”，而是“分钟/日内可实时执行的持仓后预算冻结”。它仍服务于用户要求的实时止损/不能死扛，但它不是继续改入场日 stop/retry。
- 是否进入下一步：可以，但只允许 Stage027 做只读反事实审计，不允许直接写真实引擎。
- 下一步：
  - Stage027 先从现有 C9/C4 lots、daily equity、broker10 和持仓事件中重建 PDEG-v0 在 Stage849 episode 上会不会触发。
  - 重点检查：是否能事前命中 `8/8` 同路径更大仓；是否误伤 Stage847 右尾；是否需要新阈值才能有效。
  - 若 Stage027 证据弱，停止持仓后生存线分支，回到更完整分钟K数据覆盖或结束本研究线。

## 过拟合反思

- 运行前判断：中等风险。
- 运行后判断：仍是中等风险，但已把风险约束住。
- 原因：
  - 风险来自 Stage024/025 后才设计规则，天然容易围绕 `2022` 压力段倒推。
  - 本阶段没有引入产品名、年份、方向黑名单、`1.35x` 手数比或 R 倍数阈值，降低了过拟合。
  - PDEG-v0 仍可能变成隐形降杠杆或隐形 2022 补丁；所以下一步必须先做只读反事实，不直接接引擎。

## 继续价值反思

- 运行前判断：有价值，但必须限制范围。
- 运行后判断：有价值，且只剩一个窄路径。
- 原因：
  - Stage025 已经排除了继续调入场日 stop/retry 小参数；如果还想从 C9 提取价值，只能处理“回撤中主导产品方向预算继续膨胀”的状态问题。
  - PDEG-v0 使用实时可见账户/持仓状态，理论上可实盘逐分钟或逐日检查。
  - 如果 Stage027 证明它不命中关键 paired lots 或明显误伤右尾，就应果断停止，避免把研究线拖成阈值补丁。

## 合入建议

- 是否更新本线 `LINE.md`：是，记录 Stage026 设计冻结与 Stage027 只读反事实下一步。
- 是否更新 `research/registry.md`：否。本阶段不是正式候选、重要突破、路线废弃或跨线合并。
- 是否追加根目录 `memory.md/back_log.md`：否。本阶段只是研究线内部设计草案。
