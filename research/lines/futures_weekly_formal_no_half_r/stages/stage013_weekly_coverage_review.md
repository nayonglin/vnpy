# Stage013 周线因果、就绪覆盖与信号门专项复核

- 复核时间：2026-10-23 16:12（Asia/Shanghai）。
- 研究线：`futures_weekly_formal_no_half_r`。
- 版本：J 四均线/41完成周就绪；H 三均线/21完成周就绪；两者均保留41条周历史缓存，原19池、半R/C2/全部AI关闭，声明日K开盘模型。
- 范围：只读源码和已完成 J_attempt001 / H_attempt001；不修改任何工具、不重跑策略、不下载行情。两臂均 `completed_pending_independent_review`，不是已通过全部独审或生产资格。
- 重要突破：否。本阶段只是实现与覆盖证据复核，不独立判定收益有效性。
- 新增/修改/删除参数：无。本审查人参与过适配器实现，因此本文件是专项复核，不替代另一审查人的金融、原始行情和完整执行审计。

## 结论与因果顺序

本次实际调用路径未发现提前使用未来价格、重复封周或MA40残余决策的P0/P1问题。源码边界和已完成账本支持以下结论：

1. `weekly_adapter.py:6–17` 按ISO年/周及完整交易日历定义每周最后交易日；只使用未来的日历知识，不使用未来价格。`25–47` 要求该合约本周所有期望交易日均有正量且有限正价日bar，才在最后交易日收盘后更新一次周AM。open取周首bar、high/low取周内极值、close/OI取末bar、量和turnover求和。缺日/零量整周拒绝，不前填。本窗口末日2026-10-22为未完成周，最后完成周为10-16。
2. `stage008_three_ma.py:15–25` 强制缓存41条、就绪阈值21；`65–81` 只取实际观察tail，防止21–40周阶段的前置0污染。普通信号需要MA20当前与上一条，共21条完整周bar。21是有效完成周的累计条数，不保证连续21个自然周。
3. `68–159` 只保留MA5/10/20排列、5/10和10/20交叉及原MACD分支，移除了20/40交叉、MA40排列依赖；legacy `ma_extra_long=40` 留在配置作兼容，不进入这些决策。RSI6由真实周close经TA-Lib计算；MACD仍是基类pandas EMA12/26/9（`qmt_roll_portfolio_strategy.py:9972`），没有改用需要额外33条预热的TA-Lib MACD。41条以后周history/MACD/RSI与旧周线逐值一致已有合成测试证据。
4. `fresh=False` 仅抑制新交叉信号，不抹去周线RSI、排列和MA20；原每日风控仍每天运行。普通信号只在本合约完成周的最后交易日产生，原队列下一交易日用真实日K open成交；周一交易日可有周五21点的日历模型时钟，不能解释成分钟报价确认。
5. 换月形态阈值仍按删MA40后的原公式为20周，simple trend为25周，30周期方向风险层31周起生效；H候选中确有41条 `insufficient_history`，说明该层在早期保留中性/不足历史语义，没有永久关闭。原换月可在周中使用此前完成周决定续仓，因此“普通新交叉仅完成周触发”不等于“所有持仓变化均只能在周末”。两臂实际换月历史模式均为 `target_contract_only`，未走可能混入当日日bar的连续复权分支。
6. 原引擎先撮合上一交易日挂单，再调用当日日bar的 `on_bars`；新bar-open context同时拒绝同日与跳交易日撮合、stale日期、非正量或不合法OHLC。普通入场因果顺序是完成周收盘 → 下一个交易日日K open，节假日不会提前到休市日成交。

## 独立计数复核

J/H各有25,223条周bar、550个至少产生一条有效周bar的合约，二者全部周bar逐值完全相同。809个初始化合约中，部分合约没有有效周bar。两者 `(vt_symbol,week_end)` 重复均为0；所有source_days与日历给定的该周期望日期集合完全一致，违反同周/日期顺序/未来日期的记录为0；缺周拒绝记录均677。周source_days条数分布为1天344条、2天544条、3天958条、4天2,004条、5天21,373条，短周来自交易日历，并非缺日补齐。

使用同一原19池mapping，以及每个合约截至当日的已完成周bar数，重新构造每日目标合约就绪数；J/H各1,647日与保存的weekly_readiness完全一致，0处不符。该重算仅计数，不计算或回放策略信号。

| 项目 | J 四MA/41周 | H 三MA/21周 |
|---|---:|---:|
| 账户/就绪记录日数 | 1,647 | 1,647 |
| 映射合约日总数（分母） | 28,565 | 28,565 |
| 有效就绪合约日（分子） | 9,834 | 27,929 |
| 合约日就绪比例 | 34.426746% | 97.773499% |
| 每日映射品种均值/中位数 | 17.343655 / 17 | 17.343655 / 17 |
| 每日就绪目标均值/中位数 | 5.970856 / 3 | 16.957498 / 16 |
| 0就绪目标日数 | 58 | 0 |
| 本账户窗口首个有就绪目标日 | 2020-03-20 | 2020-01-02 |
| 首个全部当日映射目标均就绪日 | 2021-10-29 | 2020-05-08 |
| 全历史曾就绪初始化合约 | 453 / 809 | 526 / 809 |
| 最大累计有效周数 | 56 | 56 |

H在2020-01-02已有14/15映射目标就绪，是2019年预热形成的周历史，不是2020账户窗口后见数据；当日没有新完成周，首条候选是2020-01-03。

## 候选、信号标签与模型成交

候选账本都是 `flat_entry` 决策行，既包括opened也包括skipped，并非所有潜在原始信号或完整逐合约信号面板。J/H候选均覆盖19个池内品种。所有候选的日期均能命中其自身合约weekly_bars的week_end，未发生周中重复沿用交叉生成候选；按日期/品种/entry_context/信号的候选重复均为0。

| 项目 | J | H |
|---|---:|---:|
| 候选行数 | 89 | 351 |
| opened / skipped | 52 / 37 | 197 / 154 |
| 首/末候选日期 | 2020-03-20 / 2026-09-30 | 2020-01-03 / 2026-10-16 |
| long_case1a / short_case1a | 14 / 7 | 59 / 51 |
| long_case2 / short_case2 | 28 / 20 | 106 / 90 |
| long_case3 / short_case3 | 12 / 8 | 26 / 19 |
| 声明模型成交笔数（开+平） | 108（54+54） | 408（203+205） |
| 声明模型成交数量合计 | 486 | 3,876 |
| 模型实际成交品种 | 17 / 19 | 19 / 19 |
| 换月形态诊断 targeted / skipped | 2 / 7 | 10 / 2 |
| 换月形态所需周数 | 40 | 20 |

J未产生模型成交的池内品种为lc.GFEX与si.GFEX；H的19个品种均有模型成交。零成交不等于零原始信号，不能据此直接给品种alpha贴失败标签。

skipped细分：J为short_signal_rejected 28、sizing_zero_volume 8、concurrent_limit 1；H为109、41、4。保留的正式空头入口限制仍可拒绝case2/case3候选。opened候选行不是成交笔数，换月、平仓、拆分及末端未完成订单等属于不同事件口径，应由完整会计/执行审计解释，不能互相等同。

就绪比例提高63.346753个百分点，说明原41周门槛在单真实合约历史上确实压低了参与机会。候选与模型交易增多同时受21周门槛、三线排列/交叉、组合持仓/资金/风险路径影响；本实验同时更改两项条件，没有额外固定门槛对照，不能把变化拆分归因给其中一个。不能由候选多、交易多或覆盖高直接认定三MA更有效。

## 边界、置信度与后续

- P0/P1：本专项实际路径未发现。结论局限于周线因果、就绪与候选覆盖；不宣称整项研究已接受。
- P2工程边界：WeeklyArrayManager没有对外部重复update同一合约周末bar的幂等保护；重复调用可能重复封周。本次引擎按唯一(dt,symbol)执行，实际两臂重复封周均0，故没有影响本次输出。保留冻结代码，未为此更改实现。
- 周线统计的有效性依赖原日历与原日bar真实性；本文件复核source_days集合，不独立重新审计25,223条周bar的全部原始OHLC。原始数据/完整财务核对另由独立审查完成。
- 两臂bar_open_acceptance均为PASS_DECLARED_BAR_OPEN_MODEL、minute/proxy读次数0；这表示声明K线模型对齐，不是价差、深度、队列、容量或实盘执行资格。postflight inputs_unchanged均true。
- 过拟合反思：本次只是冻结输出核对，没有拟合或绩效选样；但同一历史窗口已被反复研究，现有结果仍不是新增PIT/OOS证据。继续价值：有，明确了覆盖瓶颈和实际参与规模；本阶段不建议新增调参或为改善收益救援搜索。
- 后续：等待完整独立会计/数据审计和最终研究报告；保持NO_PROMOTION，不将模型成交笔数称作qualified executable counts。

## 源文件SHA256

以下为本次只读输出源的即时SHA；写入前再次逐一复核未变。冻结tools亦与J input_manifest匹配。

```json
{
  "/Users/mac/.codex/worktrees/weekly-no-half-r-20261022/fian/research/lines/futures_weekly_formal_no_half_r/outputs/J_attempt001/terminal.json": "ec10fb9e9b8bcdaf7b3bda02870f51ff08cb805c81d7d576aa8308475e7a804a",
  "/Users/mac/.codex/worktrees/weekly-no-half-r-20261022/fian/research/lines/futures_weekly_formal_no_half_r/outputs/J_attempt001/weekly_bars.csv": "9b698f74051c149dd46a60452d55ba1325c83f937c093421cc08d2e9a7c38650",
  "/Users/mac/.codex/worktrees/weekly-no-half-r-20261022/fian/research/lines/futures_weekly_formal_no_half_r/outputs/J_attempt001/weekly_readiness.csv": "c141da25f23ba14c500ce99ca98f1cb58ddc0c41e32b49e34402c0bf4d9b4492",
  "/Users/mac/.codex/worktrees/weekly-no-half-r-20261022/fian/research/lines/futures_weekly_formal_no_half_r/outputs/J_attempt001/entry_candidates.csv": "97552ac78be5ba574d8d46081b714e6796169ec12c3b6fbe5fa6985b25cd2607",
  "/Users/mac/.codex/worktrees/weekly-no-half-r-20261022/fian/research/lines/futures_weekly_formal_no_half_r/outputs/J_attempt001/trades.csv": "174c07064ec9241e0c33a6f2c84f7a38a4f190101855756810cd44363edd7ea2",
  "/Users/mac/.codex/worktrees/weekly-no-half-r-20261022/fian/research/lines/futures_weekly_formal_no_half_r/outputs/J_attempt001/execution_clock.csv": "f4129b9882e3db5d61652f1f30f4627af616afcfd2c6fb29fdd97b33818d4254",
  "/Users/mac/.codex/worktrees/weekly-no-half-r-20261022/fian/research/lines/futures_weekly_formal_no_half_r/outputs/J_attempt001/weekly_coverage.json": "559a0fd118f7a29087fd482a1ffc062492ac1c2c527b75ad838bcea732e1590f",
  "/Users/mac/.codex/worktrees/weekly-no-half-r-20261022/fian/research/lines/futures_weekly_formal_no_half_r/outputs/J_attempt001/rollover_shape_same_volume.csv": "ec44118598423fac56b0b04fc999945ff909842a457ce274f9473e71171fb2f7",
  "/Users/mac/.codex/worktrees/weekly-no-half-r-20261022/fian/research/lines/futures_weekly_formal_no_half_r/outputs/J_attempt001/actual_strategy_settings.json": "f04787010e748e962830c0f9a7b9a4929eda6c7aaf39f7f05f4fb3b06dd5e90a",
  "/Users/mac/.codex/worktrees/weekly-no-half-r-20261022/fian/research/lines/futures_weekly_formal_no_half_r/outputs/J_attempt001/postflight.json": "2d86d527910b748046132992651a414784708e04c45d564e843e66734bc24ca9",
  "/Users/mac/.codex/worktrees/weekly-no-half-r-20261022/fian/research/lines/futures_weekly_formal_no_half_r/outputs/J_attempt001/bar_open_acceptance.json": "e149296f970ada4e0f5e3f519f906c385f764cb84ee5a98e170703e0b2f1881c",
  "/Users/mac/.codex/worktrees/weekly-no-half-r-20261022/fian/research/lines/futures_weekly_formal_no_half_r/outputs/J_attempt001/ai_selection_acceptance.json": "cc7da481cc0b3afb3b09bafed3c3f5a1e4aaa58e8d2e37b240e966102ce7cc5a",
  "/Users/mac/.codex/worktrees/weekly-no-half-r-20261022/fian/research/lines/futures_weekly_formal_no_half_r/outputs/H_attempt001/terminal.json": "5735f6e169092907592d941ac44c91dbba821f03c25cbd2ac051c066b4da384e",
  "/Users/mac/.codex/worktrees/weekly-no-half-r-20261022/fian/research/lines/futures_weekly_formal_no_half_r/outputs/H_attempt001/weekly_bars.csv": "9b698f74051c149dd46a60452d55ba1325c83f937c093421cc08d2e9a7c38650",
  "/Users/mac/.codex/worktrees/weekly-no-half-r-20261022/fian/research/lines/futures_weekly_formal_no_half_r/outputs/H_attempt001/weekly_readiness.csv": "f4b727209728191acfaf97bb71f54d6c386cb260f3f46dd92c24c64724d86e3a",
  "/Users/mac/.codex/worktrees/weekly-no-half-r-20261022/fian/research/lines/futures_weekly_formal_no_half_r/outputs/H_attempt001/entry_candidates.csv": "9cbf14d91627c5aab85fbd769fb516e682d9b0dccfb596504fed1f8d7c9af9bf",
  "/Users/mac/.codex/worktrees/weekly-no-half-r-20261022/fian/research/lines/futures_weekly_formal_no_half_r/outputs/H_attempt001/trades.csv": "d0b1b33eed0052aca52d55973650988b82394f799404de5231202f97a8daecc4",
  "/Users/mac/.codex/worktrees/weekly-no-half-r-20261022/fian/research/lines/futures_weekly_formal_no_half_r/outputs/H_attempt001/execution_clock.csv": "6cabb3e10f5e9ccea23419459a26cac29bb3541ca57aca84370857c69e83b192",
  "/Users/mac/.codex/worktrees/weekly-no-half-r-20261022/fian/research/lines/futures_weekly_formal_no_half_r/outputs/H_attempt001/weekly_coverage.json": "52d707882969cc6cd97a4be2c727032d423857ae164799164af94026b9193910",
  "/Users/mac/.codex/worktrees/weekly-no-half-r-20261022/fian/research/lines/futures_weekly_formal_no_half_r/outputs/H_attempt001/rollover_shape_same_volume.csv": "7df2573dc501676d43ac29f4e2fe92437a589faccf3676677126a49257caf77c",
  "/Users/mac/.codex/worktrees/weekly-no-half-r-20261022/fian/research/lines/futures_weekly_formal_no_half_r/outputs/H_attempt001/actual_strategy_settings.json": "425d7010b151ffe676b8469e4cdea4c1d8655137f40229e464723de9d726fc91",
  "/Users/mac/.codex/worktrees/weekly-no-half-r-20261022/fian/research/lines/futures_weekly_formal_no_half_r/outputs/H_attempt001/postflight.json": "2d86d527910b748046132992651a414784708e04c45d564e843e66734bc24ca9",
  "/Users/mac/.codex/worktrees/weekly-no-half-r-20261022/fian/research/lines/futures_weekly_formal_no_half_r/outputs/H_attempt001/bar_open_acceptance.json": "752bb426847ee5ec245c0111cae0571ef04ba6ba0f59a3209dc0b9137dc2bf98",
  "/Users/mac/.codex/worktrees/weekly-no-half-r-20261022/fian/research/lines/futures_weekly_formal_no_half_r/outputs/H_attempt001/ai_selection_acceptance.json": "cc7da481cc0b3afb3b09bafed3c3f5a1e4aaa58e8d2e37b240e966102ce7cc5a"
}
```
