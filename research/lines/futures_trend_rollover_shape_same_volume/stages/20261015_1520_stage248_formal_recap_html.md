# Stage248 正式物料历史回测全量逐笔复盘 HTML

- line_id：`futures_trend_rollover_shape_same_volume`
- 当前模式：day；用户要求生成当前正式策略复盘HTML，并确认既有skill与历史产物。
- 记录时间：2026-10-15 15:20 Asia/Shanghai；生成时间以summary.json的generated_at为准。
- 工作区：`/Users/mac/Desktop/fian`；原有Stage246/247未提交工作不修改。
- 阶段性质：已验收Stage246冻结结果的纯展示；不是新回测，不是重要突破，不触发A/B。

## Skill与历史检索

- Git提交`51888d7c013ac501b2379e9c89c4be237b9bbca7`保留了`skills/futures-recap-html/SKILL.md`及`references/recap-contract.md`；当前checkout缺失，已将原字节复制到本线`references/futures-recap-html/`供本次读取和后续查阅。
- 同时应用`.trae/skills/qmt-roll-review/SKILL.md`的账务一致性要求与`skills/futures-live-execution-sop/SKILL.md`的只读身份规则。旧skill中的bytedance路径按本机仓库映射；没有调用历史默认回测入口。
- canonical renderer为`research/lines/futures_trend_winner_trade_forensics/tools/stage038_c9_15w_big_winner_multiscale_html.py`，SHA256 `613672a4cc91493ba17dc055542e4b4172349de210ff932530caf04ce36bb93a`。
- 旧代码保留Stage038尾部、Stage042 C9全量、Stage045 Stage037C、Stage049 Stage061 Top10+fu全量HTML入口；股票Stage014记录也明确此前复用同一renderer生成过HTML。
- 当前checkout及现有`formal-2020-replay`工作区均未发现旧复盘HTML实体（只有docs模板）。不能把旧路径存在于代码中说成旧文件当前仍可打开。

## 外部调研与判断

- Plotly官方HTML导出：https://plotly.com/python/interactive-html-export/
- VeighNa官方组合回测源码：https://github.com/vnpy/vnpy_portfoliostrategy
- 判断：使用原canonical多周期图表与内嵌Plotly，适配冻结成交账；不换引擎、不升级库、不把线上实现替代冻结版本。HTML无外部script依赖，可离线打开。

## 冻结来源与身份

- 唯一源：`/Users/mac/.codex/worktrees/formal-2020-replay/fian/research/lines/futures_trend_rollover_shape_same_volume/outputs/stage246_2020_20261014/replay_round3`。
- 窗口：2020-01-01至2026-10-14；初始资金150000；正式Stage037/C9与Top10非fu+固定fu政策，物料`m0008_20261008T204054+0800_2a7420a9f955`。
- 两个checkout均通过`assert_official_checkout_matches_active_material()`且身份完全相同；CURRENT、数据库、主力映射SHA与Stage246输入manifest相同。
- 本机没有SOP指定stable production目录及production-live运行回执；未把本机正式物料等同于当前实际生产运行状态。
- 页首明确：2020年至2022-01-28沿用static18边界，之后才启用月池；并非全区间始终11品种。

## 本次改动

- 新增本线`tools/stage248_recap_html.py`、`tools/test_stage248_recap_html.py`，原样保存skill参考；不修改其他研究线。
- 窄适配器只AST加载SHA固定的12个纯展示函数，不执行canonical模块顶层策略、TqSdk或CTP导入；不复制图表模板。
- 本线输出位置覆盖skill历史默认赢家线位置，遵循AGENTS研究线隔离要求。
- 先写缺失证据、残余持仓、输出越界/覆盖、renderer隔离4项测试，适配器缺失时报预期错误；实现后4项通过。
- 新增/修改/删除策略参数：均无。新增/修改/删除回测结果：均无；以下全为引用Stage246已有结果。

## 冻结指标

| 指标 | 数值 |
|---|---:|
| 期末权益 | 9,468,247.25元 |
| 总收益 | 6212.164833% |
| 最大回撤 | -53.304183% |
| Sharpe | 1.471422798 |
| 总滑点 | 2,513,280元 |
| 手续费 | 0元（非真实全成本） |
| 总成交 | 800笔 |
| 完整周期 | 395（119盈利/274亏损/2持平） |
| 完整周期净胜率 | 30.126582% |
| 盈利日/非零盈亏日 | 54.310345%，不是交易胜率 |
| 期末持仓 | 0 |
| broker10保证金代理峰值 | 149.529773%，17天超过100% |

## 输出与验收

- 输出目录：`research/lines/futures_trend_rollover_shape_same_volume/outputs/stage248_formal_m0008_20200101_20261014_recap_v1/`。
- `index.html`：34,307,475字节，含全周期权益/回撤、年度原表、395周期逐笔图。
- 附件：`summary.json`、`chart_manifest.csv`、`episodes.csv`、`records.json`、`verification.json`、`independent_review.json`。
- 每个周期有30日、10日、月、周、日K，默认30日+日K；395组都保留原开仓和最终平仓标记，部分平仓净损益累计，价格变化按成交量加权平仓价计算。
- 390周期存在显式标注的主力背景代理；可见背景缺口0。MA使用已有历史预热，历史不足不填充，代理接缝不复权，图表MA不等于策略信号MA。
- 本次无完整15分钟复盘窗口；不把选定日期分钟补丁拼成完整K线，页面如实提示；R未唯一绑定风险快照，显示N/A。
- JavaScript三个内嵌脚本均经Node语法解析通过；外部script数量0。
- 浏览器实测：全部395、盈利119、亏损274、持平2；2026筛选43；fu筛选34；上一笔/下一笔0→1→0；五周期共10个价量面板；缺分钟提示正常。
- 真鼠标拖拽后，30日K与日K同步缩放，日轴可见首个标签从2023-04-13变为2023-09-21；随后Reset axes并恢复默认周期。浏览器error日志为空。
- 冻结metrics整个字典与源完全相等；所有渲染开/平价、净Pnl、手数再次核对；git diff --check通过。
- 独立review：PASS，未解决P0/P1/P2=0/0/0。源6230个输入全量hash、275物料文件、原始800成交FIFO、395周期、日账和绩效均闭合；395条图表记录逐项对账通过，59,499个唯一合约日OHLCV与源DB差值0，875,218个可复算MA值最大差2.27e-13。HTML内嵌records/summary与JSON相同，详见独立文件。

## 边界与结论

- 沿用源回测的零手续费、训练覆盖2020–2022、自然日整天扫描及夜盘时序边界；非严格样本外、非无前视证明、部署门未通过。不能把946.82万元当作可兑现实盘收益。
- 12个最终退出价落在同自然日日K高低之外；保留原账本日期和价格，明确说明不代表该日K内可成交，不通过移动标记或改价掩盖问题。
- 策略重跑0，行情下载0，生产目录内容访问0，CTP/订单调用0；仅探测指定生产路径是否存在，并读取本地checkout正式物料。
- 过拟合反思（前/后）：否，本次全量展示固定账本，不挑选盈利样本、不调参；原策略已有的训练/时序风险仍在。
- 继续价值（前/后）：是，页面便于查每笔交易与既有数据问题；本次不形成新alpha或晋升证据。
- TODO：交付离线HTML；若后续需要分钟窗口或逐信号/R归因，按独立数据/证据任务处理，不据页面形状寻找阈值。
- 同线有其他任务并行，按AGENTS只写本次唯一stage，不修改LINE、registry、memory或back_log。
