# Stage505 已持仓继续/主动退出时钟支持实现

- line_id：`futures_full_market_long_signal_ai`；记录时间：2026-10-21 02:28 CST。
- 当前状态：仅 code_ready。Stage504 正式数学/绑定与 root actual 许可尚未收到，没有启动实际测量。本阶段不是回测，不是重要突破版本。
- 工作范围：仅 `tools/stage505_continuation_support.py`、对应新测试与本阶段输出，不改 LINE/registry、旧源码、正式策略、生产或 Git。

## 开始判断

新增按收益调参过拟合：否。本阶段只判断原成熟完整路径中是否存在必要的收盘决策时钟，不读收益、价格或退出原因，不搜索持有期、止损和风险。历史反复选题的过拟合风险仍高。继续价值：是；只有先确认可区分于原终结日的决策支持，才值得后续独立的早退出政策研究。

调研与判断：执行 root 本轮已经完成的外部机制调研结论，只复用已独立接受的 Stage466/467 metadata 与原156日历边界纯函数，不重读129大源。metadata 能证明的只是 `t+1` 严格早于原终结日和共同K的候选必要条件；不能证明没有已知强退、原生价格可成交、提前退出有利或样本统计足够。

## 实现与预定合同

- 白名单24列，身份、u/D/entry/exit/label-known时钟、状态、原family hash和两cutoff状态；没有价格、numeric Y或exit_reason。
- 严格候选时点：`t >= entry` 且 `t+1 < original_exit`、`t+1 < K`，即 `[entry, min(exit-2,K-2)]`。原156 `before_calendar_blocked` 与 `after_calendar_pending` 保留，不伪造未来Kindex。
- `t=exit-1` 的次日恰为原终结日，只列 ambiguous upper，不认证或并入严格机会。
- 两cutoff、main/holdout_0/holdout_1 采用原family hash补集，u与label_known都严格早于cutoff。预定一次保留所有445475条原eligible closed mature-pre2023动作（含无严格机会与K阻挡状态），并以247795/445475作K前成熟交叉锚。
- 通过interval差分计算每fold机会展开上界、精确年龄计数、source-day union、family-day union与family/year覆盖，重叠月份/entry cohort不充独立样本。
- 完整动作1552456与全部原状态守恒；全母域399252/nochild186400及98产品/95家族/六所继承466/467接受证据。有动作域自然为97/94，不强迫虚造第98产品子动作。
- 运行入口要求 exact504 SHA、root JSON授权、一个fresh目录、一次metadata流与calendar1读、0fit/0cash预算。每读阶段写checkpoint；没有自动恢复/重启。

## 验证与当前结果

5个有价值新toy先RED（源码缺失）后GREEN：同日/次日terminal不制造严格支持；K/cutoff equality与held补集；重叠union；unknown隔离不补0；K尚未落入日历与日历前阻挡。CLI `--help`正常。未跑旧suite。

本阶段 actual metadata/calendar/old mothers/SQL/cache/price/Y/fit/cash均0，未产生金融成绩。新增/修改/删除策略参数、目标、标签、模型和资金账均0。期末权益、总收益、最大回撤、Sharpe、总滑点、交易次数、胜率均N/A。

## 结束判断与下一步

实现本身新增收益拟合：否；不宣称alpha。继续本次支持测量有价值：是，待root504实际授权后一次测量并独立复核；支持好只允许讨论后续状态构造，不授权训练或金融。完整目标尚未达到。
