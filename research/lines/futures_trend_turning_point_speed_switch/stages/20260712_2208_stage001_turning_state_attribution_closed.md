# Stage001 严格 T-1 转折状态归因结果与关线

- line_id：`futures_trend_turning_point_speed_switch`
- 当前模式：`day`
- 记录时间：`2026-07-12 22:08 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `codex/stage130-option-probe`
- 阶段性质：冻结口径只读归因、问题修复、独立复核和路线关闭；未运行策略回测
- 是否重要突破：否；属于明确负结论和路线止损
- 是否触发A/B：否；全部归因硬门未通过，不允许实现 canary

## 外部调研与判断

- `Momentum Turning Points` 支持把慢趋势与快趋势的 correction/rebound 分开，但不支持直接迁移为本地商品减仓动作。
- `Dynamic Momentum Learning` 和 `pysystemtrade` 支持多速度/多规则框架，但权重、分类器和相关性估计自由度高，本线未复制这些参数化方法。
- 重叠事件窗研究支持产品与 20 交易日日期块聚类，而不是普通 iid t 检验；本轮因主事件为零，统计 bootstrap 按 fail-close 不运行。
- 我的最终判断：理论上存在的 turning-state 在当前 C9 真实持仓样本中没有出现，不能靠放宽周期、确认天数或方向制造样本。

## 本次变更

- 新增脚本：`tools/stage001_turning_state_attribution.py`。
- 新增测试：`tests/test_turning_point_speed_switch_stage001.py`，最终专属测试 `13/13` 通过；与 MRC 上游联合回归 `39/39` 通过。
- 新增参数：固定 slow `5/10/20/40`、fast `3/6/12/24`、T-1 `40` 日完整窗口、1/5/20 日 outcome、20交易日聚类块、bootstrap seed `20260712` 和 `20,000` 次；这些参数均在结果前预声明。
- 修改参数：无正式策略参数修改。
- 删除参数：无。
- 正式实盘、CTP、邮件、launchd、AI 月池和其他研究线：均未修改。

## 问题修复

- 首轮单测发现 MA 相邻比较误用 `zip(strict=True)`，会阻断全部状态计算；在真实结果前修复并原测试通过。
- 首轮真实执行发现空事件表缺 outcome schema；只补零样本 fail-close，不放宽事件定义。
- 首轮独立 review 为 `P0=0/P1=1/P2=5`：P1 是预声明终点 `2026-06-29`，工具却保留冻结源中的 `2026-06-30` 全零尾行。
- 修复 P1：增加 `FREEZE_END=2026-06-29`，五类 analysis frame 在进入状态、episode、风险和 outcome 前统一截断；原口径重跑。
- 同轮补齐跨日仓位守恒硬断言、空样本 top5 gate fail-close、空 event summary 表头和多笔平仓成交量加权均价。
- 非结果影响语义已显式记录：`269/269` 表示风险字段有唯一候选和真实 Open，不表示手数完全一致；候选量等于 entry-end 为 `265/269`，等于当日 Open flow 为 `257/269`，差异来自止损重试和实际缩量，不影响零事件结论。

## 回测/归因参数

- 冻结源输入：daily `1,571`、trades `641`、positions `470,965`、candidates `839`、actual-contract panel `116,445` 行；五份 SHA 前后全匹配。
- 归因区间：`2020-01-02 -> 2026-06-29`；冻结尾日后数据不得进入状态或 outcome。
- 账户规模：`150,000`，仅用于 current C9 A 身份核对。
- 成本口径：基准 positions 已含成本；本轮无主事件，静态减仓经济门按空样本 fail-close。
- 样本过滤：真实 `positions + trades`；候选只提供入场风险字段，`candidate_status=opened` 不作为成交证据。
- 因果口径：actual contract 严格 `asof_date < action_date`，连续 40 个全市场交易日，不拼主力/连续合约、不补零、不缩短窗口。

## 结果

- 归因状态：`1,529/1,529=100%` 可用。
- 逻辑持仓 episode：`269`；风险字段匹配 `269/269`；换月 `8` 次。
- 状态交叉表：slow 不同向 + fast concordant `24`，slow 不同向 + fast neutral `22`，slow 同向 + fast concordant `1,313`，slow 同向 + fast neutral `170`，任意 fast opposite `0`。
- Concordant references：`304`；严格 slow-aligned + fast-opposite 主事件：`0`。
- 跨日仓位守恒：检查 `470,460` 行，值不连续 `0`、缺前序 `0`、缺后序 `0`；成交 signed-volume、成交笔数、daily/positions PnL 均守恒。
- Gate：仅 feature coverage 通过，其余包括样本、三段、统计、经济性和集中度均 fail-close；`canary_allowed=false`，决策 `CLOSE_LINE`。
- 独立最终复核：`P0=0/P1=0/P2=1`，P2 仅为本结果记录和 registry 尚未收口；结果置信度 `99%`，允许归档关闭。
- 期末权益：N/A（只读归因，不是新策略回测）。
- 总收益：N/A。
- 最大回撤：N/A。
- Sharpe：N/A。
- 总滑点：N/A；冻结 A 输入有历史滑点，但本阶段未新增成交。
- 总交易次数：新增 `0`；冻结 A 输入 `641` 笔仅用于真实持仓归因。
- 胜率：N/A。

## 输出文件

- report：`outputs/stage001_turning_state_attribution/stage001_turning_state_attribution_v1_report.md`。
- decision：`..._decision.json`，SHA256 `d7e7ea3b44ef7dbfc0dd280b2a7b3baca43ea70016da4a40b909e0a7ad55b71e`。
- gate matrix：`..._gate_matrix.csv`，SHA256 `44351672997edf92324637b0b519dde255c306f116fd22acb093866a903feab5`。
- state rows：`..._position_state_rows.csv.gz`，SHA256 `4198ebca0bb731d343eec72577219a05b21ad57c88a0bbc62ef129d3d6a39ea2`。
- source/code manifest、data audit、product days、opposite events、concordant references、state/event summary：均在同一输出目录。

## 结论

- 本阶段结论：严格 turning-opposite 在真实持仓样本中不存在；不是数据缺口、未来函数、换月或去重造成。
- 是否进入下一步：否；本线关闭。
- 下一步：不得写真引擎、不得跑 canary、不得改 MA/确认天数/方向/产品/年份救参。后续优化必须另开结构不同的新线。

## 过拟合反思

- 运行前判断：否；信号、事件、样本门、统计门和唯一动作均在结果前冻结。
- 运行后判断：否；修复仅针对实现 bug、截止日合同和审计完整性，核心结果始终为零事件，未按结果改参数。
- 原因：继续放宽快慢周期或筛选 2022/方向/产品才会成为结果驱动过拟合，因此明确禁止。

## 继续价值反思

- 运行前判断：有，但仅值得一次 Stage001 只读归因。
- 运行后判断：本信号无继续研究价值。
- 原因：连候选状态都没有，写真引擎无法验证任何预声明动作；正确决策是关线而不是制造样本。

## 合入建议

- 更新本线 `LINE.md`：是，标记关闭并写入最终证据。
- 更新 `research/registry.md`：是，更新当前状态和禁止事项。
- 追加根目录 `back_log.md`：是，记录路线废弃和独立复核结论。

## 资料

- https://people.duke.edu/~charvey/Research/Published_Papers/P158_Momentum_turning_points.pdf
- https://arxiv.org/abs/2106.08420
- https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3167271
- https://github.com/pst-group/pysystemtrade/blob/develop/docs/backtesting.md
