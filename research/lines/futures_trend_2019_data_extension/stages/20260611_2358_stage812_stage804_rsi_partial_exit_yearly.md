# Stage812 Stage804 开启 RSI>95 半平年度多起点回测

> 2026-06-12 00:26 CST 纠错：本阶段对照口径无效。Stage804 虽然没有在自身 profile 显式写 `enable_rsi_partial_exit=True`，但 `run_qmt_roll_backtest.build_roll_setting()` 默认开启了 `enable_rsi_partial_exit=True`，Stage804 未显式覆盖为 `False`，因此 Stage812 实际是在“已开启 RSI 半平的 Stage804”上再次开启同一开关。`0` 差异来自对照污染，不应作为策略结论引用。修正版见 Stage813。

- line_id：`futures_trend_2019_data_extension`
- 当前模式：`day`
- 记录时间：2026-06-11 23:58 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：年度多起点 A/B 回测，验证 Stage804 上开启已有 RSI 极端半平开关的实际影响
- 是否重要突破：否
- 是否触发A/B：是。A=`official_candidate_stage777_50w_am41_oi08_old_ai_v1`，B=Stage804，C=Stage812

## 外部调研与判断

- 参考资料：本阶段是用户指定的已有开关验证，核心依据为本仓库 `version-ab-experiment` 纪律、Stage804 年度缓存、Stage812 回测输出，以及策略代码中 `enable_rsi_partial_exit` 的实现语义；未新增外部 alpha 资料。
- 我的判断：RSI>95 半平属于极端超买获利保护，理论上能削弱单边过热后的回吐，但如果它不能改变实际成交/权益路径，就不能当作真实保护层。趋势策略最忌为某个右尾或某个回撤窗口做阈值追参，本阶段只测一个既有默认阈值，不扫阈值。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage812_stage804_rsi_partial_exit_yearly.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：运行期启用 `enable_rsi_partial_exit=True`、`rsi_partial_exit_threshold=95.0`、`rsi_partial_exit_ratio=0.5`
- 修改参数：相对 Stage804 仅开启 RSI 半平开关
- 删除参数：无

## 回测/归因参数

- 数据区间：年度起点 `2018-01` 到 `2026-01`，统一终点 `2026-05-29`
- 账户规模：50万
- 成本口径：沿用 Stage804/Stage777 组合回测成本口径
- 样本过滤：全部年度起点 9 个；成熟样本排除 `2026-01` 后 8 个
- 策略/归因口径：Stage812 = Stage804 + RSI>95 半平；保持 AM41、旧正式 AI 老师、OI 命中恢复风险资金到 `0.8`、基础等效 `0.4`、maxpos4、关闭连败缩放和 recovery sleeve、多头更紧初始止损不变

## 结果

- 期末权益：代表 `2020-01` 起点 `27,577,760`；`2018-01` 起点 `26,293,495`；`2019-01` 起点 `30,146,230`
- 总收益：代表 `2020-01` 起点 `5415.552%`；`2018-01` 起点 `5158.699%`；`2019-01` 起点 `5929.246%`
- 最大回撤：代表 `2020-01` 起点 `-56.0975%`；`2018-01` 起点 `-46.5025%`；`2019-01` 起点 `-53.9421%`
- Sharpe：代表 `2020-01` 起点 `1.5525`；`2018-01` 起点 `1.3618`；`2019-01` 起点 `1.4465`
- 总滑点：代表 `2020-01` 起点 `2,296,860`；`2018-01` 起点 `2,029,740`；`2019-01` 起点 `2,445,290`
- 总交易次数：代表 `2020-01` 起点 `525`；`2018-01` 起点 `673`；`2019-01` 起点 `620`
- 胜率：本脚本未汇总输出胜率；沿用交易/滑点/收益回撤作为本轮主判据
- 其他关键指标：相对 Stage804，全部 9 个起点收益、最大回撤、Sharpe、交易次数、滑点差异全部为 `0`；成熟 8 个起点同样全部为 `0`。RSI 半平诊断事件实际触发 `31` 次、合计 `1520` 手，其中 long `29` 次、short `2` 次，但没有改变最终成交与权益路径。相对 Stage777，成熟样本收益胜出 `4/8`、回撤胜出 `4/8`、Sharpe 胜出 `1/8`、收益中位差 `+25.003pp`、回撤中位差 `-0.6193pp`，DD50 失败从 Stage777 的 `0` 增至 Stage812 的 `2`。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage812_stage804_rsi_partial_exit_yearly_report_stage812_stage804_rsi_partial_exit_yearly_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage812_stage804_rsi_partial_exit_yearly_summary_stage812_stage804_rsi_partial_exit_yearly_v1.csv`
- orders：无单独 orders 文件；本阶段输出 `rsi_partial_events` 与对比表
- daily：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage812_stage804_rsi_partial_exit_yearly_curves_stage812_stage804_rsi_partial_exit_yearly_v1.csv`
- quality：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage812_stage804_rsi_partial_exit_yearly_decision_stage812_stage804_rsi_partial_exit_yearly_v1.json`

## 结论

- 本阶段结论：`stage812_stage804_rsi_partial_exit_yearly_not_promoted`。开启 RSI>95 半平后，诊断层有事件，但实际绩效相对 Stage804 完全无差异；因此不能把该开关视为 Stage804 的有效保护层。
- 是否进入下一步：不进入参数优化或候选合入。
- 下一步：若继续，只做执行语义法证，解释为什么诊断事件未改变成交/权益路径；不扫 RSI 阈值、不按品种或年份补丁化。

## 过拟合反思

- 运行前判断：不是典型过拟合。理由是只开启一个既有、固定、语义明确的开关，没有按历史结果选择阈值。
- 运行后判断：当前结果不支持继续调参；若为了让 RSI 半平产生效果去扫 `90/92/95/97` 或按品种设置阈值，会变成过拟合。
- 原因：真正的问题不是阈值优劣，而是当前执行路径下该诊断事件没有改变年度多起点的实际交易结果。

## 继续价值反思

- 运行前判断：有有限价值。用户关心 Stage804 是否开启该保护层，年度多起点能回答实际影响。
- 运行后判断：策略推进价值低，法证价值中等。
- 原因：结论已经清楚地否定了“打开现有 RSI 半平即可改善 Stage804”的假设；但事件触发而绩效无差异，值得在需要时单独查执行语义。

## 合入建议

- 是否更新本线 `LINE.md`：否，本阶段不改变路线状态。
- 是否更新 `research/registry.md`：否。
- 是否追加根目录 `memory.md/back_log.md`：追加 `back_log.md` 简要摘要，不追加 `memory.md`。
