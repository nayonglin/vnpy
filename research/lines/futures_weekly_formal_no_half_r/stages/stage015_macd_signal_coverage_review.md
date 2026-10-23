# Stage015 H/K MACD消融信号与覆盖专项审查

- 时间：2026-10-23 16:38，Asia/Shanghai。
- 研究线：`futures_weekly_formal_no_half_r`。本次核心冻结提交：`d773af1ed`。
- 比较：既有H_attempt001（三MA+MACD）与新增K_attempt001（三MA、完整关闭MACD）。原19、15万元、2020-01-01至2026-10-22、日K次交易日open模型不变。
- 重要突破：否。本文件只解释信号门、周覆盖与模型成交结构；收益/回撤/Sharpe/FIFO等完整财务结果由另一独立审查人负责，不能以本文件替代总审。
- 操作：只读已完整结束的两臂账本与冻结代码；未运行任何策略或金融回测、未下载行情，未更改tools/LINE/registry/合同。
- 完整终态：H于16:09:37结束，K于16:35:07结束；两者均 `completed_pending_independent_review`、error=null、production_qualified=false。K的执行/MACD专项接受不等于最终研究接受或生产资格。

## 完整关闭MACD的代码与运行证据

`stage014_no_macd.py` 仅基于原三均线包装一次，再覆盖普通信号、shape换月、非shape换月三个MACD消费方法；未再包装ArrayManager，也未修改三均线就绪或缓存初始化。

- `_generate_signal`（17–99）：保留MA5/10与10/20交叉、三线排列、真实周close计算RSI、Donchian、原过滤与量仓风险分支；去掉MACD计算/finite要求/hist方向门，`allow_long/short=True`后仍保留原可选RSI门；删除case3，不改成无交叉常驻排列信号；fresh门保留。
- `_rollover_shape_continuation_snapshot`（101–137）：保留20条历史门、MA5/10/20排列与原方向启用开关，去掉hist计算、finite要求及方向门。`macd_hist=NaN`仅为旧诊断schema兼容，允许/拒绝不读取它。
- `_rollover_reopen_allowed`（139–148）：覆盖继承的非shape重开MACD门，仍调用原 `_passes_entry_filters`，防止遗留隐含消费。
- `_calculate_macd`（13–15）设为Forbidden：任何漏调用先增加计数再抛错，而不是用全0或NaN伪造“关闭”。
- 此前对H实际MRO逐方法扫描，中间Stage847/830/827/804/772层无额外MACD风险/退出消费；旧基类剩余 `macd_hist` 记录器只是诊断字段。K仍未发现新的启用MACD依赖。
- 运行输出 `macd_acceptance.json`：accepted=true，macd_disabled=true，实际类 `NoMacdThreeMaWeeklyIndicatorsStrategy`；MACD计算尝试0、候选case3 0、未知候选信号0、换月hist非空0。四类删除消费清单完整。
- H/K实际setting逐值完全相等；effective_parameters完整相等，包括合约尺寸、滑点、零手续费与全部风险参数。RSI入场过滤原False保持；RSI95半仓退出、MA20止损、其他每日风控保持。21周就绪/41条缓存、25条simple trend、31条方向风险历史语义均未变。
- 新MACD模块、旧三MA模块、周聚合器和bar-open模块的当前SHA均与K input_manifest匹配；两臂postflight inputs_unchanged=true、mismatches=[]。

## 周覆盖完全相等

H/K的 `weekly_bars.csv` 逐值完全一致，`weekly_readiness.csv` 也逐值完全一致；因此此次变化没有来自新增行情、换周算法、就绪门槛或缓存容量。

| 覆盖项 | H | K |
|---|---:|---:|
| 周bar条数 / 有效合约数 | 25,223 / 550 | 25,223 / 550 |
| 同合约同week_end重复 | 0 | 0 |
| 最后完成周 | 2026-10-16 | 2026-10-16 |
| 初始化合约数 / 曾就绪合约数 | 809 / 526 | 809 / 526 |
| ready_need / storage | 21 / 41 | 21 / 41 |
| 缺日/不完整周拒绝数 | 677 | 677 |
| 就绪日记录数 | 1,647 | 1,647 |
| 映射合约日总数 | 28,565 | 28,565 |
| 有效就绪合约日 | 27,929 | 27,929 |
| 就绪覆盖率 | 97.773499% | 97.773499% |
| 零就绪目标日 | 0 | 0 |

截至2026-10-22的末尾未完成周仍未封存。2020开始前已有2019年周线预热，未以账户起点截断真实历史。

## 候选变化可以精确对账

全部候选仍是flat_entry决策记录，包含opened和skipped；它们不是所有合约/所有日期的完整原始信号面板。两臂候选各覆盖19个池内品种，首候选2020-01-03、末候选2026-10-16。两臂所有候选日期都命中自身合约的已完成week_end，按日期/品种/entry_context/信号的重复数均0。

| 信号标签 | H候选数 | K候选数 | 变化 |
|---|---:|---:|---:|
| long_case1a | 59 | 91 | +32 |
| short_case1a | 51 | 65 | +14 |
| long_case2 | 106 | 111 | +5 |
| short_case2 | 90 | 96 | +6 |
| long_case3 | 26 | 0 | -26 |
| short_case3 | 19 | 0 | -19 |
| 合计 | 351 | 363 | +12 |
| opened / skipped | 197 / 154 | 211 / 152 | +14 / -2 |

按 `(date, product_vt_symbol, contract_vt_symbol, signal)` 精确匹配：共同306条，H独有45条且全部case3，K独有57条且全部MA交叉。H的原306条case1/2候选在K中全部保留。

为区分“去掉MACD触发”与“去掉MACD过滤”，对K冻结周bar仅做静态指标算术检查：每条候选取当时该合约已完成周close最后41条，使用旧H的EMA12/26/9公式复算原hist方向。没有实例化策略、调用策略方法或重跑金融。K新增57条候选全部恰好违反H原hist方向门：long_case1a 32、short_case1a 14、long_case2 5、short_case2 6；其中39条opened、18条skipped。由此本次候选行变化可精确写为 **351 − 45 MACD-only + 57 MA交叉放行 = 363**。

关闭MACD不是单纯减少信号：它一方面删去MACD金死叉独立触发，另一方面解除了MA交叉的MACD方向门。这里有固定数据和配对候选证据支持，两种作用不能混成一个“过滤器松/紧”的说法。

共同306条候选中，有3条opened/skipped状态发生变化，全部是组合并发上限路径差异：2020-11-20 sp long_case1a由concurrent_limit跳过变opened；2023-09-01 ru long_case2及2025-03-21 ru short_case1a由opened变concurrent_limit跳过。共同候选的opened数净-1；H被删的case3有24条opened，新增57条中39条opened，所以 **197 − 24 + 39 − 1 = 211**。这证明候选可精确配对，但资金/持仓路径仍会改变最终开仓；不能将57条新增候选直接等同57笔新增成交。

skipped明细：H为short_signal_rejected 109、sizing_zero_volume 41、concurrent_limit 4；K为96、52、4。原空头只允许case1a的正式限制仍保留，K的96条short_case2候选全部被拒绝，并未借关闭MACD旁路该限制。

## 模型成交、换月与执行因果

| 项目 | H | K |
|---|---:|---:|
| 声明模型总成交笔数（开+平） | 408（203+205） | 453（224+229） |
| 模型成交数量合计 | 3,876 | 6,519 |
| 模型实际成交品种数 | 19 | 19 |
| 换月形态诊断 targeted / skipped | 10 / 2 | 14 / 3 |
| 换月hist非空条数 | 12 | 0 |

两臂均有原19全部品种模型成交。交易笔数和数量不等于已验证可执行容量、独立闭合轮次或真实实盘成交。K换月17条诊断中14条targeted、3条skipped（不足历史、无正允许数量、形态不符各1）；未删除非MACD换月风控。

对execution_proxy_usage逐行核对signal_date到交易日历下一交易日：H408笔与K453笔全部0处不符。配合候选均在自身已完成week_end，普通周信号的因果顺序仍是本周最后交易日收盘形成信号 → 下一交易日/下一交易周首日的日K open；休市日不会撮合。每日风控退出和换月等非普通交叉订单仍可在周中形成，再按下一交易日日K open执行，不能把所有成交都称作周线新入场。

两臂bar_open_acceptance均PASS_DECLARED_BAR_OPEN_MODEL，daily_price_mismatch、daily_data_invalid、modeled_clock_mismatch均0；minute_reads/proxy_reads/AI模型读取均0。夜盘品种交易日周一可配周五21点模型时钟，这仅是交易日归属约定；minute_quote_confirmed=false，不声称分钟行情、盘口或容量已确认。

## 审查边界与后续

- P0/P1：本专项范围内未发现MACD漏关、周覆盖漂移、提前信号或撮合时点错误。完整财务/原始行情独审仍独立进行，本文件不预称K accepted。
- P2：候选与模型笔数不能直接量化收益归因；即使候选 presence可精确配对，组合并发、仓位、风险记忆、换月和开平拆分仍使财务路径非线性。旧周聚合器的重复update非幂等边界仍存在，但本次H/K重复周bar均0，未因此改冻结代码。
- 过拟合反思：此次只有预声明固定模块消融，没有按K结果调参或筛品种；但同一历史窗口已反复使用，仍不形成新增PIT/OOS证据。
- 是否有继续价值：有，本次已清楚识别MACD两个作用及真实发生的候选变化；不由交易增多推断更优，不为收益继续救援扫参。
- 后续：由另一独立审查完成财务、开放仓位、风险暴露和数据/执行总审后形成研究结论；保持NO_PROMOTION，不将模型计数称作qualified executable counts。

## 只读证据SHA256

写入本文件前复核所有下列源SHA未变。未更改任何被冻结源。

```json
{
  "/Users/mac/.codex/worktrees/weekly-no-half-r-20261022/fian/research/lines/futures_weekly_formal_no_half_r/outputs/H_attempt001/terminal.json": "5735f6e169092907592d941ac44c91dbba821f03c25cbd2ac051c066b4da384e",
  "/Users/mac/.codex/worktrees/weekly-no-half-r-20261022/fian/research/lines/futures_weekly_formal_no_half_r/outputs/H_attempt001/preflight.json": "3b350e62b46678cb7df9a57f38c81af664b3d3f2e26f85e6672d4fb81bda572f",
  "/Users/mac/.codex/worktrees/weekly-no-half-r-20261022/fian/research/lines/futures_weekly_formal_no_half_r/outputs/H_attempt001/actual_strategy_settings.json": "425d7010b151ffe676b8469e4cdea4c1d8655137f40229e464723de9d726fc91",
  "/Users/mac/.codex/worktrees/weekly-no-half-r-20261022/fian/research/lines/futures_weekly_formal_no_half_r/outputs/H_attempt001/effective_parameters.json": "aecbeae238fad8e86083db33d39bf5619c7c2d1831b250242fcd96c7d7e4e48d",
  "/Users/mac/.codex/worktrees/weekly-no-half-r-20261022/fian/research/lines/futures_weekly_formal_no_half_r/outputs/H_attempt001/postflight.json": "2d86d527910b748046132992651a414784708e04c45d564e843e66734bc24ca9",
  "/Users/mac/.codex/worktrees/weekly-no-half-r-20261022/fian/research/lines/futures_weekly_formal_no_half_r/outputs/H_attempt001/bar_open_acceptance.json": "752bb426847ee5ec245c0111cae0571ef04ba6ba0f59a3209dc0b9137dc2bf98",
  "/Users/mac/.codex/worktrees/weekly-no-half-r-20261022/fian/research/lines/futures_weekly_formal_no_half_r/outputs/H_attempt001/ai_selection_acceptance.json": "cc7da481cc0b3afb3b09bafed3c3f5a1e4aaa58e8d2e37b240e966102ce7cc5a",
  "/Users/mac/.codex/worktrees/weekly-no-half-r-20261022/fian/research/lines/futures_weekly_formal_no_half_r/outputs/H_attempt001/data_read_counts.json": "93d3de2922f2827829f6ecf964a43097e5ef67962cc83491d97fed1657306277",
  "/Users/mac/.codex/worktrees/weekly-no-half-r-20261022/fian/research/lines/futures_weekly_formal_no_half_r/outputs/H_attempt001/weekly_coverage.json": "52d707882969cc6cd97a4be2c727032d423857ae164799164af94026b9193910",
  "/Users/mac/.codex/worktrees/weekly-no-half-r-20261022/fian/research/lines/futures_weekly_formal_no_half_r/outputs/H_attempt001/weekly_bars.csv": "9b698f74051c149dd46a60452d55ba1325c83f937c093421cc08d2e9a7c38650",
  "/Users/mac/.codex/worktrees/weekly-no-half-r-20261022/fian/research/lines/futures_weekly_formal_no_half_r/outputs/H_attempt001/weekly_readiness.csv": "f4b727209728191acfaf97bb71f54d6c386cb260f3f46dd92c24c64724d86e3a",
  "/Users/mac/.codex/worktrees/weekly-no-half-r-20261022/fian/research/lines/futures_weekly_formal_no_half_r/outputs/H_attempt001/entry_candidates.csv": "9cbf14d91627c5aab85fbd769fb516e682d9b0dccfb596504fed1f8d7c9af9bf",
  "/Users/mac/.codex/worktrees/weekly-no-half-r-20261022/fian/research/lines/futures_weekly_formal_no_half_r/outputs/H_attempt001/trades.csv": "d0b1b33eed0052aca52d55973650988b82394f799404de5231202f97a8daecc4",
  "/Users/mac/.codex/worktrees/weekly-no-half-r-20261022/fian/research/lines/futures_weekly_formal_no_half_r/outputs/H_attempt001/execution_clock.csv": "6cabb3e10f5e9ccea23419459a26cac29bb3541ca57aca84370857c69e83b192",
  "/Users/mac/.codex/worktrees/weekly-no-half-r-20261022/fian/research/lines/futures_weekly_formal_no_half_r/outputs/H_attempt001/execution_proxy_usage.csv": "84798bbff2f52466a88ab393dd73d5911f87e550164349d2d7131abf4a990952",
  "/Users/mac/.codex/worktrees/weekly-no-half-r-20261022/fian/research/lines/futures_weekly_formal_no_half_r/outputs/H_attempt001/rollover_shape_same_volume.csv": "7df2573dc501676d43ac29f4e2fe92437a589faccf3676677126a49257caf77c",
  "/Users/mac/.codex/worktrees/weekly-no-half-r-20261022/fian/research/lines/futures_weekly_formal_no_half_r/outputs/K_attempt001/terminal.json": "d749c8b7202f32033ae46dcd583d436ab9e81429d64adf97628ccd5288e8c682",
  "/Users/mac/.codex/worktrees/weekly-no-half-r-20261022/fian/research/lines/futures_weekly_formal_no_half_r/outputs/K_attempt001/preflight.json": "5149ae60fbe7c6f1ac2fb58fdfe8f441bcce8bc276ae426f42f83328d21f0d17",
  "/Users/mac/.codex/worktrees/weekly-no-half-r-20261022/fian/research/lines/futures_weekly_formal_no_half_r/outputs/K_attempt001/actual_strategy_settings.json": "72539839e9243d49ca82beee24bb2f81e74ec88677c0f828888e0e851e90e784",
  "/Users/mac/.codex/worktrees/weekly-no-half-r-20261022/fian/research/lines/futures_weekly_formal_no_half_r/outputs/K_attempt001/effective_parameters.json": "aecbeae238fad8e86083db33d39bf5619c7c2d1831b250242fcd96c7d7e4e48d",
  "/Users/mac/.codex/worktrees/weekly-no-half-r-20261022/fian/research/lines/futures_weekly_formal_no_half_r/outputs/K_attempt001/postflight.json": "2d86d527910b748046132992651a414784708e04c45d564e843e66734bc24ca9",
  "/Users/mac/.codex/worktrees/weekly-no-half-r-20261022/fian/research/lines/futures_weekly_formal_no_half_r/outputs/K_attempt001/bar_open_acceptance.json": "f9cd4f98ef0ca289cd176bc28a85f1a1e32aaf25077ca98eeff817551a0e16a1",
  "/Users/mac/.codex/worktrees/weekly-no-half-r-20261022/fian/research/lines/futures_weekly_formal_no_half_r/outputs/K_attempt001/ai_selection_acceptance.json": "cc7da481cc0b3afb3b09bafed3c3f5a1e4aaa58e8d2e37b240e966102ce7cc5a",
  "/Users/mac/.codex/worktrees/weekly-no-half-r-20261022/fian/research/lines/futures_weekly_formal_no_half_r/outputs/K_attempt001/data_read_counts.json": "93d3de2922f2827829f6ecf964a43097e5ef67962cc83491d97fed1657306277",
  "/Users/mac/.codex/worktrees/weekly-no-half-r-20261022/fian/research/lines/futures_weekly_formal_no_half_r/outputs/K_attempt001/weekly_coverage.json": "52d707882969cc6cd97a4be2c727032d423857ae164799164af94026b9193910",
  "/Users/mac/.codex/worktrees/weekly-no-half-r-20261022/fian/research/lines/futures_weekly_formal_no_half_r/outputs/K_attempt001/weekly_bars.csv": "9b698f74051c149dd46a60452d55ba1325c83f937c093421cc08d2e9a7c38650",
  "/Users/mac/.codex/worktrees/weekly-no-half-r-20261022/fian/research/lines/futures_weekly_formal_no_half_r/outputs/K_attempt001/weekly_readiness.csv": "f4b727209728191acfaf97bb71f54d6c386cb260f3f46dd92c24c64724d86e3a",
  "/Users/mac/.codex/worktrees/weekly-no-half-r-20261022/fian/research/lines/futures_weekly_formal_no_half_r/outputs/K_attempt001/entry_candidates.csv": "0c796fb4f2e99411c6dbd2c77514e7258363c31297e9be885d84ac036ea3a382",
  "/Users/mac/.codex/worktrees/weekly-no-half-r-20261022/fian/research/lines/futures_weekly_formal_no_half_r/outputs/K_attempt001/trades.csv": "84620e2bce029238c0b3d55a04c5bd70ce56e8bdf466aa4aa504625f552f61e3",
  "/Users/mac/.codex/worktrees/weekly-no-half-r-20261022/fian/research/lines/futures_weekly_formal_no_half_r/outputs/K_attempt001/execution_clock.csv": "862a76dc0a74d34d3a68c986c2c19125f77a5c7e2ac9f1d8af5f5acb65773c9d",
  "/Users/mac/.codex/worktrees/weekly-no-half-r-20261022/fian/research/lines/futures_weekly_formal_no_half_r/outputs/K_attempt001/execution_proxy_usage.csv": "d02df85f1da02056644b6bf13e7ec0f4729e656adda234fc9d445cbdb8de5041",
  "/Users/mac/.codex/worktrees/weekly-no-half-r-20261022/fian/research/lines/futures_weekly_formal_no_half_r/outputs/K_attempt001/rollover_shape_same_volume.csv": "05bde9b8528c701e93f70da1d0701d736f5df29f1b2231e7aebfd16aef205ec8",
  "/Users/mac/.codex/worktrees/weekly-no-half-r-20261022/fian/research/lines/futures_weekly_formal_no_half_r/outputs/K_attempt001/macd_acceptance.json": "153d50ccc168f326c8976b778e1dd835a603cd643b0a840b74c6301ea12990ba",
  "/Users/mac/.codex/worktrees/weekly-no-half-r-20261022/fian/research/lines/futures_weekly_formal_no_half_r/tools/stage014_no_macd.py": "693b21c396d97a03913ea77de7d250f10f16be30628ea0f922d2fe4483291dc6",
  "/Users/mac/.codex/worktrees/weekly-no-half-r-20261022/fian/research/lines/futures_weekly_formal_no_half_r/tools/stage008_three_ma.py": "5f5554eb35033912658a2db6182b97418eafa5253ede88cf27caf09c47dc3061",
  "/Users/mac/.codex/worktrees/weekly-no-half-r-20261022/fian/research/lines/futures_weekly_formal_no_half_r/tools/weekly_adapter.py": "ff1aab44517515015efe0dc743a54b555eecddcaf3024db7057693dbc7a97afd",
  "/Users/mac/.codex/worktrees/weekly-no-half-r-20261022/fian/research/lines/futures_weekly_formal_no_half_r/tools/stage011_bar_open_execution.py": "ceba51f9dd8edbb1e2cd42ce74212208e9866e5f0d84d12183a356d37162a3c0",
  "/Users/mac/.codex/worktrees/weekly-no-half-r-20261022/fian/research/lines/futures_weekly_formal_no_half_r/outputs/stage005_data/mapping.csv": "873d2bfa6900557616993896c9a0b13faabfb09e0899bd5beaafe000d78532cb"
}
```
