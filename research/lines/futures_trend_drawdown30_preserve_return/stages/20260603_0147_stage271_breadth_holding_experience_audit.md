# Stage271 扩池风险壳持有体验与贡献集中度审计

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：`2026-06-03 01:47 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：只读审计；固定读取 Stage526/Stage556/Stage557 既有输出，不重跑交易引擎，不新增交易版本。
- 是否重要突破：否，但进一步明确“低单笔风险+扩池+避高相关”路线的晋级边界。
- 是否触发A/B：否。没有形成可接入正式版本的新策略。

## 外部调研与判断

- 参考资料：
  - managed futures / trend following 资料强调跨市场分散和低相关风险源，但也强调 model risk、over-optimization 和持有期 drawdown 体验。
  - `pysystemtrade` 这类系统化期货框架把 instrument weights、相关性估计、risk target / diversification multiplier 放在组合构造核心。
  - rolling returns / Ulcer Index 资料提示：持有体验不能只看期末收益和最大回撤，还要看任意启动后的滚动收益、负收益率、回撤深度和持续性。
- 我的判断：
  - 扩池方向仍然成立，但必须证明它真的改善任意启动后的 `63/126` 日体验和年度贡献分散。
  - 如果扩池只增加交易次数、卫星腿贡献太小、主组合仍由少数核心产品族主导，就不能晋级。

## 本次变更

- 新增脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage570_breadth_holding_experience_audit.py`
- 修改脚本：无正式策略脚本修改。
- 删除脚本：无。
- 新增输出：
  - `qmt_roll_stage570_breadth_holding_experience_audit_holding_detail_stage570_breadth_holding_experience_audit_v1.csv`
  - `qmt_roll_stage570_breadth_holding_experience_audit_holding_summary_stage570_breadth_holding_experience_audit_v1.csv`
  - `qmt_roll_stage570_breadth_holding_experience_audit_contribution_annual_stage570_breadth_holding_experience_audit_v1.csv`
  - `qmt_roll_stage570_breadth_holding_experience_audit_contribution_product_stage570_breadth_holding_experience_audit_v1.csv`
  - `qmt_roll_stage570_breadth_holding_experience_audit_contribution_family_stage570_breadth_holding_experience_audit_v1.csv`
  - `qmt_roll_stage570_breadth_holding_experience_audit_contribution_summary_stage570_breadth_holding_experience_audit_v1.csv`
  - `qmt_roll_stage570_breadth_holding_experience_audit_crowding_summary_stage570_breadth_holding_experience_audit_v1.csv`
  - `qmt_roll_stage570_breadth_holding_experience_audit_gates_stage570_breadth_holding_experience_audit_v1.csv`
  - `qmt_roll_stage570_breadth_holding_experience_audit_decision_stage570_breadth_holding_experience_audit_v1.json`
  - `qmt_roll_stage570_breadth_holding_experience_audit_report_stage570_breadth_holding_experience_audit_v1.md`
  - `qmt_roll_stage570_breadth_holding_experience_audit_chart_stage570_breadth_holding_experience_audit_v1.png`

## 参数与口径

- 评估版本：
  - `Stage526`：`stage526_r080_pc25_maxpos4`
  - `Stage256 upper`：`dynamic_prevtop6_r050_pc15_maxpos3`，历史白名单/上限，不可直接部署。
  - `All noncore r020`：`breadth_all_noncore_r020_famcap20_corr5075_maxpos8`
  - `Prev+ r020`：`breadth_prevpos_r020_famcap20_corr5075_maxpos8`
  - `Prev+ r015`：`breadth_prevpos_r015_famcap15_corr5075_maxpos10`
- 数据区间：`2020-01-02` 至 `2026-04-30`。
- 持有体验：
  - 任意启动后 `63` 日和 `126` 日 forward return。
  - 指标：p10、p05、最差收益、负收益率、forward 最大不利波动 p05 / min。
- 贡献集中度：
  - 核心腿使用 Stage526 positions 按产品逐年聚合。
  - 扩池/Stage256 叠加对应卫星腿 product harvest。
  - 注意：该贡献表用于解释产品/产品族集中度，不强行和账户期末权益逐元对齐。
- 相关性拥挤：
  - 使用 Stage557 entry snapshots 的 same-direction correlation 字段。
  - 检查 opened 事件中是否仍出现 `corr > 0.75`，以及年度选择中的同族最大数量。

## 结果

- 决策：`hindsight_upper_bound_improves_experience_selector_required`
- 可部署宽池壳通过闸门：
  - `All noncore r020`：`4/9`
  - `Prev+ r020`：`4/9`
  - `Prev+ r015`：`4/9`
- `Stage256 upper`：`7/8`，但失败项是 `deployable_selector`，因为它是历史白名单/上限。

### 总体表现

| 版本 | 期末权益 | 总收益 | 最大回撤 | Ulcer | Sharpe | 总滑点 | 总交易次数 | 胜率/说明 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| Stage526 | `23,369,505` | `3699.9195%` | `-36.2670%` | `14.4691` | `1.6385` | `1,342,190` | `905` | 非零日胜率 `53.6330%` |
| Stage256 upper | `23,423,510` | `3708.7008%` | `-36.0729%` | `14.3808` | `1.6433` | `1,346,430` | `1,109` | 历史上限，不可直接部署 |
| All noncore r020 | `23,378,900` | `3701.4472%` | `-36.3714%` | `14.4902` | `1.6374` | `1,349,620` | `1,354` | 卫星 PnL `9,395` |
| Prev+ r020 | `23,351,260` | `3696.9528%` | `-36.4055%` | `14.5093` | `1.6355` | `1,343,690` | `997` | 卫星 PnL `-18,245` |
| Prev+ r015 | `23,354,530` | `3697.4846%` | `-36.4126%` | `14.5039` | `1.6361` | `1,343,630` | `1,011` | 卫星 PnL `-14,975` |

### 63/126日持有体验

| 版本 | 63日p10 | 63日负收益率 | 63日最差 | 126日p10 | 126日负收益率 | 126日最差 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Stage526 | `-9.5763%` | `23.2131%` | `-31.1143%` | `-4.1865%` | `13.6558%` | `-33.1790%` |
| Stage256 upper | `-9.5385%` | `23.0769%` | `-30.6535%` | `-4.0601%` | `13.1579%` | `-33.0183%` |
| All noncore r020 | `-9.5905%` | `23.2811%` | `-31.1444%` | `-4.3071%` | `13.6558%` | `-33.2771%` |
| Prev+ r020 | `-9.5938%` | `23.2811%` | `-31.1583%` | `-4.2919%` | `13.6558%` | `-33.2935%` |
| Prev+ r015 | `-9.5904%` | `23.2811%` | `-31.1398%` | `-4.3226%` | `13.6558%` | `-33.2755%` |

### 年度贡献集中度

| 版本 | 年均top1产品占正收益 | 年均top1产品族占正收益 | top1产品>35%年份 | top1产品族>50%年份 | 年均正贡献产品数 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Stage526 | `40.1918%` | `48.3859%` | `4` | `4` | `8.1429` |
| Stage256 upper | `40.0291%` | `48.3107%` | `4` | `4` | `10.2857` |
| All noncore r020 | `40.0789%` | `48.3746%` | `4` | `4` | `14.1429` |
| Prev+ r020 | `40.1687%` | `48.4228%` | `4` | `4` | `9.5714` |
| Prev+ r015 | `40.1735%` | `48.4107%` | `4` | `4` | `9.5714` |

## 图表视觉复盘

- 图表：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage570_breadth_holding_experience_audit_chart_stage570_breadth_holding_experience_audit_v1.png`
- 左上/中上：`Stage256 upper` 的 `63/126` 日 p10 相对 Stage526 有小幅正改善；三个可部署宽池壳均为负值，说明宽池没有抬高持有左尾。
- 右上：`Stage256 upper` 负收益率下降，尤其 `126` 日下降约 `0.50pp`；宽池壳 `63` 日负收益率反而略高，`126` 日基本没有改善。
- 左下：扩池后年均 top1 产品占正收益仍约 `40%`，top1 产品族约 `48%`，并且 `4/7` 年 top1 产品超过 `35%`，`4/7` 年 top1 产品族超过 `50%`。说明卫星腿虽然增加了正贡献产品数量，但没有改变主风险来源。
- 中下：收益/回撤散点显示 `Stage256 upper` 在右上且回撤更浅；`All noncore r020` 总收益略高但最大回撤更深；两个 `Prev+` 版本收益和回撤都差于 Stage526。
- 右下：`All noncore r020` 仍有 `1` 个 opened 事件同向相关超过 `0.75`；`Prev+` 两个版本没有 opened 高相关事件，但仍没改善路径。

## 结论

- 当前可部署宽池壳不能晋级。
- `Stage256 upper` 提供了有价值上限：如果有真正 point-in-time selector，确实可能改善 3/6 个月体验和路径质量。
- 但现在的全宽池、上一年为正宽池都没有做到：
  - 63/126日体验不改善；
  - 最大回撤和 Ulcer 劣化；
  - 年度贡献集中度几乎不变；
  - 卫星收益太小或为负，不能改变主组合风险来源。
- 下一步不应继续扫宽池 risk/cap/corr/maxpos 小数；应转向 selector 证据本身：基差、库存/仓单、成交/OI结构、产业链价差、新闻/政策事件接收时间戳，先做固定预测力审计。

## 过拟合反思

- 运行前判断：不是过拟合。固定读取既有结果，用预先定义的持有体验、贡献集中度和相关性拥挤指标审计。
- 运行后判断：不是过拟合。审计没有把历史赢家写成规则，反而明确把 Stage256 标记为不可部署上限。
- 风险：如果下一步直接把 `jm/OI/lh/ru/FG` 或 Stage256 白名单固化为实盘池，就是过拟合。

## 继续价值反思

- 运行前判断：有价值。它回答用户关心的“任意时候启动、持有多久”的体验问题，并检验扩池是否真分散。
- 运行后判断：有价值，但继续方向收窄。
- 下一步：停止宽池壳参数优化；继续做 point-in-time selector 的数据资格和预测力验证。若 selector 不能证明能接近 Stage256 上限，则扩池路线只保留为风险预算经验，不进入候选。

## 验证

- `.py311/bin/python examples/portfolio_backtesting/analyze_qmt_roll_stage570_breadth_holding_experience_audit.py`：通过。
- `.py311/bin/python -m py_compile examples/portfolio_backtesting/analyze_qmt_roll_stage570_breadth_holding_experience_audit.py`：通过。
- `.py311/bin/python -m json.tool ...decision...json`：通过。
- 图表已视觉检查。

## 合入建议

- 是否更新本线 `LINE.md`：是。
- 是否更新 `research/registry.md`：否。本阶段不是新候选或正式突破。
- 是否追加根目录 `memory.md/back_log.md`：否。本阶段延续 Stage270/Stage264 边界。
