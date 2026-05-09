# Stage191 手动品种池特征探针

- line_id：`futures_trend`
- 当前模式：`day`
- 记录时间：2026-05-09 17:30 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：手动初始品种池的解释性统计探针
- 是否重要突破：否
- 是否触发A/B：否，本阶段不提出可晋级版本，只做解释性分析。

## 外部调研与判断

- 参考资料：
  - 趋势跟踪相关研究通常强调跨市场、多品种、交易成本和流动性约束。
  - 期货趋势跟踪交易成本研究指出，波动下降和固定成本占比上升会侵蚀趋势策略表现。
  - 时间序列动量和商品趋势跟踪文献支持多市场趋势效应，但并不意味着每个可交易品种都适合某一套具体策略。
- 我的判断：
  - 手动池不应被视为天然最优，但它可能编码了人的默会知识：数据完整、流动性、合约活跃、趋势地形、保证金可承受、交易经验。
  - 正确方向不是直接扩大池子，而是识别手动池的隐含特征，再找相似品种做小规模候选验证。

## 本次变更

- 新增脚本：无
- 修改脚本：无
- 删除脚本：无
- 新增参数：无
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：沿用全市场可交易池审计产物
- 账户规模：不涉及
- 成本口径：不涉及新增成本模型
- 样本过滤：`qmt_roll_full_market_tradable_universe_eligible_full_market_tradable_universe_v1.csv` 的 50 个可交易品种
- 策略/归因口径：解释性统计，不是交易回测

## 结果

- 可交易品种：50
- 手动静态池：18
- 非静态候选：32
- 手动池中位特征：
  - recent_bar_coverage_ratio：0.9708
  - recent_nonzero_volume_ratio：0.9708
  - recent_median_volume：295,138.75
  - recent_median_open_interest：298,885.75
  - estimated_margin_per_contract：8,391.90
  - market_trend_efficiency_60d_median：0.1110
  - market_realized_vol_60d_median：0.1005
  - market_range_pct_mean_60d_median：0.0178
- 非静态池中位特征：
  - recent_bar_coverage_ratio：0.8542
  - recent_nonzero_volume_ratio：0.8542
  - recent_median_volume：105,093.25
  - recent_median_open_interest：102,367.75
  - estimated_margin_per_contract：8,434.13

## 相似候选

- 按距离手动池中心最近：
  - `UR.CZCE`
  - `pg.DCE`
  - `sn.SHFE`
  - `eb.DCE`
  - `fu.SHFE`
- 按“像手动池”的解释性分类概率最高：
  - `pg.DCE`
  - `UR.CZCE`
  - `sn.SHFE`
  - `SR.CZCE`
  - `br.SHFE`

## 结论

- 本阶段结论：手动池并不一定是最优，但它明显不是随机池，至少在数据完整性、活跃度、趋势地形、持仓/成交规模上与非静态品种不同。
- 是否进入下一步：可以，但只能进入“候选相似品种小规模审计”，不能直接替换正式池。
- 下一步：
  - 用 leave-one/add-one 的方式分别测试 `UR.CZCE`、`pg.DCE`、`sn.SHFE`、`eb.DCE`、`fu.SHFE`。
  - 优先验证单品种增量贡献和弱窗口影响，而不是一次性结构池全量替换。

## 过拟合反思

- 运行前判断：有风险。
- 运行后判断：有风险，但可控。
- 原因：
  - 用模型识别“你选过什么”容易学习你的历史偏好，而不是未来收益。
  - 本阶段没有用结果决定交易规则，只做解释性候选排序。

## 继续价值反思

- 运行前判断：是。
- 运行后判断：是。
- 原因：
  - Stage190 反证了粗暴结构池替换；Stage191 提供了更细的方向：找相似品种逐个 add-one，而不是全池替换。

## 合入建议

- 是否更新本线 `LINE.md`：否。
- 是否更新 `research/registry.md`：否。
- 是否追加根目录 `memory.md/back_log.md`：否，本阶段只是解释性探针。
