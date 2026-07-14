# Stage001 AI 排名年度 Jackknife 资格审计完成并闭线

- line_id：`futures_trend_ai_rank_year_jackknife_qualification`
- 当前模式：`day`
- 记录时间：`2026-07-13 01:48 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `codex/stage130-option-probe`
- 阶段性质：固定 full-market Top8 年度历史敏感性、future60 换入/换出资格审计、独立复算、机械闭线
- 是否重要突破：否；明确反证年度 jackknife 共识榜
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：Meinshausen/Bühlmann stability selection、Inoue/Kilian time-series bagging、Petropoulos/Hyndman/Bergmeir time-series bagging uncertainty、AAAI rank aggregation。
- 调研结论：选择稳定性审计有理论价值，但 IID stability-selection 定理不能直接套时序；moving-block bootstrap 又会引入块边界和非平稳风险。当前 full-market “AI” 是固定权重评分，不是待重训模型，因此采用逐月删除每个过去完整自然年的确定性 jackknife，而非随机 bootstrap。
- 我的判断：该规格能隔离评分中 `24%` 全历史累计策略 PnL 的单年依赖；future60 只用于资格标签，不证明组合因果。结果为跨时期负 edge，因此不能进入真引擎。

## 本次变更

- 新增脚本：`tools/stage001_year_jackknife_qualification.py`。
- 新增测试：`tests/test_stage001_year_jackknife_qualification.py`。
- 新增输出：输入审计、daily manifest、年度 PnL、13,265条 variant rank、共识 rank、3,078条 future60 label、月/年比较、gate、decision、report、manifest。
- 修改脚本：无正式策略、AI月池、回测引擎或实盘脚本修改。
- 删除脚本：无。
- 新增参数：研究固定 `TopN=8`、`all_cycle_weight=0.24`、`horizon=60 global trade dates`、`MIN_COMPLETE_MONTHS=42`、`MIN_SWAP_MONTHS=24`、`MIN_SWAPS_PER_ACTIVE_YEAR=3`、`MIN_POSITIVE_YEARS=4`、`MAX_BEST_YEAR_SHARE=0.60`。
- 修改参数：无正式参数修改。
- 删除参数：无。

## 回测/归因参数

- 数据区间：eval `2022-01-28 -> 2026-06-30`，可完整比较至 `2025-11-28`；严格 future60 最晚数据到 `2026-06-30`。
- 账户规模：不适用；单品种 Stage124 PnL 只作为横截面资格标签。
- 成本口径：沿用冻结 Stage124 单品种 C9 daily 中已含 net PnL；本阶段不产生新增成交或成本。
- 样本过滤：每月 baseline 加逐个删除 `2020 -> eval_year-1` 完整自然年；只替换 score 中 `0.24*rank_all_cycle_profit`，其余特征、权重、history gate 不变。
- 共识：所有 variant 平均 ordinal rank 升序、product_vt_symbol 升序 tie-break，固定 Top8。
- 标签：eval 日严格排除，下一60个 global dates 必须逐日完整；缺一日即 incomplete，不缩短窗口。

## 测试与输入闭合

- TDD 首轮目标模块不存在按预期为红；实现首轮 `5/8`，修复 Series 日期归一化 `.dt`；同时更正测试对四个并列平均百分位的错误期望，不改变研究口径。
- 最终 `unittest 8/8`、py_compile、`git diff --check` 通过。
- 五个冻结源 SHA 与 Stage124 daily manifest SHA 全匹配。
- daily `57` 文件、`73,251` 行、重复日期 `0`、非有限 PnL `0`。
- base panel `4,446` 行、`78` 月、`57` 品种、重复键 `0`；累计 PnL `4,446/4,446` 重算通过，独立复算最大浮点误差约 `1.82e-11`。
- 资格期 baseline Top8 `54/54` 月完全重现；独立复算 score 最大误差 `3.33e-16`。
- variant `13,265` 行，`omitted_year < eval_year` 违规 `0`，非 all-cycle 复制特征差异 `0`，重复键 `0`。
- future60 `54×57=3,078` 标签独立复算一致；eval 日泄漏 `0`，缺日严格不合格。

## 结果

- decision：`CLOSE_LINE_YEAR_JACKKNIFE_RANK_INELIGIBLE`。
- gate：`2/12` 通过、`10/12` 失败；通过项仅 upstream integrity 与完整比较月数量。
- 完整比较月：`47 >= 42`；实际换仓月：`21 < 24`。
- 21个换仓月全部是一进一出，守恒错误 `0`；共同 Top8 为 `7/8`，Jaccard `7/9=0.777778`。
- total raw edge：`-54,520`；月度 raw edge 中位：`-1,550`；月度 percentile edge 中位：`-0.0943396`。
- 年度 raw edge：2022 `-25,590`（6月）、2023 `-17,905`（7月）、2024 `-885`（6月）、2025 `-10,140`（2月）。
- 有效年份正/负：`0/3`；2025只有2个换仓月，不满足每年最少3月。
- early `2022-2023=-43,495`；late `2024-2026=-11,025`，两段均为负。
- 最新7个月 `2025-12 -> 2026-06` 不完整：2025-12至2026-03主要是个别产品 Stage124 daily 缺完整60日；2026-04/05/06全局未来日仅 `39/21/0`，按预声明 fail-close 排除。
- 期末权益/总收益/最大回撤/Sharpe/总滑点/胜率：均不适用，未运行策略回测。
- 总交易次数：`0`。

## 独立审查

- reviewer：独立 agent `Hooke`（`019f576a-1acb-7302-97ba-aa424b7545fc`），只读全量复算冻结 SHA、daily、base panel、累计 PnL、54月 baseline、13,265 variant、3,078 label、共识、21次交换、年度汇总和12个 gate。
- 终审：`P0=0 / P1=0 / P2=3 / P3=2`；数字置信度 `99%`、语义置信度 `97%`，没有问题会改变闭线。
- P2-1：future60 月度窗口高度重叠，21个月不能视为独立样本；削弱统计显著性表述，但总 edge、early/late 与三个有效年均负，不影响机械闭线。
- P2-2：最新7个月因产品缺日或全局未来不足60日排除，限制最新时期覆盖；符合预声明 fail-close，不影响既有负 edge 闭线。
- P2-3：LINE/registry 在终审时仍写“已预声明”；本次已更新为完成并关闭。
- P3-1：无正 edge 年时 `best_year_positive_edge_share=inf` 在 CSV 为 `inf`、JSON 序列化为 `null`；对应 gate 明确失败，不影响 decision，暂不为展示重跑。
- P3-2：8个单测以合成数据为主，未直接覆盖全输出；独立 agent 的全量复算已补足，不影响结果。

## 输出文件

- report：`outputs/stage001_year_jackknife_qualification/report.md`。
- decision：`outputs/stage001_year_jackknife_qualification/decision.json`。
- monthly/yearly：`outputs/stage001_year_jackknife_qualification/monthly_comparison.csv`、`yearly_comparison.csv`。
- rankings/labels：`outputs/stage001_year_jackknife_qualification/variant_rankings.csv.gz`、`consensus_rankings.csv`、`future60_labels.csv`。
- gates：`outputs/stage001_year_jackknife_qualification/gates.csv`。
- input evidence：`outputs/stage001_year_jackknife_qualification/input_audit.json`、`daily_source_manifest.csv`、`daily_source_audit.csv`。
- manifest：`outputs/stage001_year_jackknife_qualification/manifest.csv`、`manifest.sha256`。

## 结论

- 本阶段结论：删除单一历史年度后做平均名次共识，没有提高未来60日单品种表现，反而跨2022-2025总体为负；年度 jackknife 共识榜不具备进入四锚点真引擎 canary 的资格。
- 是否进入下一步：否；不读取 `version-ab-experiment`、不创建月池、不跑资金曲线、不做A/B或实盘。
- 下一步：本线关闭。禁止修改24%权重、TopN、年度块、平均名次、60日标签、年份门或只挑正月份救参；后续必须换真正新外生信息或独立收益源。

## 过拟合反思

- 运行前判断：中等；研究动机来自当前评分使用历史盈利且用户关注2022，存在研究序列后验风险。
- 运行后判断：没有新增参数过拟合；单规格、全过去年度、固定Top8/权重/标签/gate，失败后未救参。
- 原因：结果为否定性且跨期同向为负，不存在挑选局部正结果晋级。

## 继续价值反思

- 运行前判断：有；它直接检验当前 full-market score 最明显的历史依赖。
- 运行后判断：当前形状无继续价值。
- 原因：机制轻微改变榜单但换入持续弱于换出，参数救援只会围绕历史结果拟合。

## 合入建议

- 是否更新本线 `LINE.md`：是，标记完成并关闭。
- 是否更新 `research/registry.md`：是，记录负 edge 与禁止救参。
- 是否追加根目录 `memory.md/back_log.md`：只追加 `back_log.md` 跨线闭线摘要；不修改 `memory.md`。

