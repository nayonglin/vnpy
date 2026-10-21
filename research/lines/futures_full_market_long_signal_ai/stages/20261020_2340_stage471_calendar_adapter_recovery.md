# Stage471：整数日历输入适配失败与唯一准备恢复

- line_id：`futures_full_market_long_signal_ai`；时间：2026-10-20 23:34 首次准备失败，23:37—23:40 保存证据及最小修复；非重要突破版本。
- Stage469 协议、470 的 15 fit 和所有产物完全保留。本 agent 未自行启动/轮询任何真实现金进程。

## 已确认的失败事实

root 独占 session42675 的真实现金启动 exit1。`outputs/stage471_annual_mature_cash/actual_run1/actual_terminal.json` 显示：`ValueError: handoff/source native calendar differs`，cash_started=0、cash_completed=0、new_fit=0、SQL=0。失败在准备阶段，尚无完成的现金账/现金检查点。

唯一根因是输入表示错误。470 的原字节 calendar.npy 为 int64 `YYYYMMDD`，5587 行，首 `20050104`、末 `20271231`；471 用 `.astype(str)` 得到 `20050104`，而原 native `store.calendar` 的同一天是 `2005-01-04`。直接将此整数当 `datetime64[D]` 同样错误，因为它会被解释成距 epoch 的天数。本次没有更改源日历字节、日期取值、模型更新时间或现金时间范围。

失败源和 fixture 已在修改前保存：

| 证据 | 字节 | SHA256 |
| --- | ---: | --- |
| `failed_attempt1_source.py` | 36370 | `75ee7e771eb0d5d24b227388cce729e833add017e237b133250c2efa970299bb` |
| `failed_attempt1_fixture.py` | 6664 | `6bebd32d17f066c064c2fe771458da2221789567f5942dfb7f56937f784cddc0` |
| actual_run1 终态 | 549 | `fb0fc7b00ee686f7c6765c8ed8fe0ec2908ac3335b0ed62fe13ac08257c18e90` |
| actual_run1 manifest | 3758 | `0ff6336c67bd16db2fb69f711175263c1fa313bc5c1ab376afdcd5e0a30119e7` |

文件位于本线 `outputs/stage471_annual_mature_cash/`；`failure_receipt.json` 绑定全部证据、原 handoff、真实 dtype/首末值、补充授权与读取预算偏差。修复验证再次确认 actual_run1 的 manifest/终态 SHA 均未变化，未覆盖失败现场。

## 最小修复与验证

遵循 systematic-debugging，先读完整失败终态，再对照 470 已运行成功的解码分支。唯一假设是整数日历转字符串缺少年月日分隔。

新增 1 项最小回归 `test_integer_YYYYMMDD_calendar_decodes_as_iso_dates`：先保留原解码行为，实测 RED，明确断言 `['20050104', ...]` 与预期 `['2005-01-04', ...]` 不同；然后将 `decode_calendar()` 改为与 470 完全相同的整数 `YYYYMMDD` 拆分规则，非整数沿原 datetime 日类型分支，重验 GREEN/exit0。

只小读已绑定的 470 派生日历，完整 5587 个日期与 470 已验证的解码规则一致，首 `2005-01-04`、末 `2027-12-31`。本修复没有 restore native、重算模型、读原 actions/COMMON、跑真实 cash、SQL 或下载。未扩旧 suite。

AST 比对原失败源码与新源码：唯一新增函数 `decode_calendar`；原函数仅 `execute` 改动，且将其中 `calendar` 赋值归一化后 AST 完全相同。所有金融、模型、年度时钟、风险、预算、止损、费用、滑点和 gate 代码未改。

| 新 source bundle | 字节 | SHA256 |
| --- | ---: | --- |
| `tools/stage471_annual_mature_cash.py` | 36662 | `d640f3efd92f6561d1a3baa25d65b0e52701a70444da2bf55a38149c5ac9bc85` |
| `outputs/stage471_annual_mature_cash/synthetic_fixture.py` | 6918 | `acb30c3ce1efa73e27f9aaf28dd83f022cd936e5fb43bb44a24dc45f639d0581` |

完整最小回归输出、source bundle、AST 和原现场未变核验见 `calendar_adapter_recovery_verification.json`。旧 implementation_verification 保留其当时旧 source binding，不伪装覆盖成首次成功验证。

## 预算偏差、授权与结果

首次准备已 restore 同 accepted native cache 1 次，随后才发生格式比较失败。虽然它未启动现金账，不能把该 load 从累计统计删除。root 明确补充授权：允许一次准备恢复到 `actual_run2`，下一完整四账再次加载同 cache 1 次。因此授权累计 load=2，分解为失败准备 1+完整四账共用 1；本修复过程另加载 0。原 actions/COMMON/模型重算/SQL/下载仍为 0。

该补充授权仅恢复准备输入适配，不增加金融账户预算：真实新现金仍最多四本，原控制重放 0。由 root 在 actual_run2 使用新 bundle 独占启动；本 agent 不自动重试。一次真实结果后仍由原同一个独立 agent 合并审查模型、selection 和四 cash，不重放已完成 phase。

新增策略参数 0；修改策略参数 0；删除策略参数 0。新增/修改/删除真实回测结果均 0。当前期末权益 N/A、总收益 N/A、最大回撤 N/A、Sharpe N/A、总滑点 N/A、手续费 N/A、总交易次数 N/A、胜率 N/A。Stage471 真实现金启动 1/准备失败 1/完整 0；cash kernel started/completed=0/0。本修复 fit 0/cash 0。470 已完成的 15 fit 不因本修复重算；全线累计由 root 最终合并。

## 调研判断与反思

本次调研是仓库内精确对照 470 的工作实现和已绑定 calendar 内容；不提出新研究频率或新 alpha。沿用 469 已核的官方时间顺序/扩窗资料结论：方法原则不能替代本机输入类型验证，也不能推断未来收益。

开始/结束新增过拟合：否。修复由真实输入格式断言触发，候选财务尚未产生，没有按盈亏、年份或 family 调整任何规则；历史同史择题风险仍在。

开始/结束继续价值：是，有条件。首次失败只暴露本现金适配的日期表示错误，未提供年度政策的财务反证；完成原授权一次四账仍能检验假说。必须公开累计两次 native load 的准备偏差，不能将工程修复写成策略进步。goal active，未获晋级、加注或生产资格。
