# Stage045：以实际初始风险补充毛R展示与冻结浮点精度修正

- 时间：2026-10-19 18:43 CST；研究线 `futures_trend_full_market_noai_one_lot`。
- 本阶段仅补充既有金融回放的风险展示证据；不是重要突破，不修改策略参数、预算政策、039/040/041、001/025、canonical、冻结金融源、父复盘或任何旧输出。
- 金融回放次数 **0**、行情下载 **0**、生产访问 **0**。新的金融结果仍由根任务与独立审查负责；本阶段不产生新的权益/收益/回撤/Sharpe/滑点/成交/胜率。

## 展示合同与实现

新增 `tools/stage045_budget_r_recap.py`，接口为 `--source --parent --output`。

- Source 为 `run_20261019_native_budget_one_lot_v1`；根任务已完成新金融回放及独立审查，并报告原规范父复盘有 3,059 个完整 episodes。parent 为 `recap_20261019_native_budget_one_lot_v1`；新目录规划为 `recap_20261019_native_budget_one_lot_v1_r`，其后由 Stage020 绑定独立审查形成 reviewed 终稿。
- canonical FIFO 在旧格式中将 risk_amount/R 留空，但新 source 每笔实际 open 已有 `stage041_entry_risk` 及 accepted audit。现在对唯一 open_trade_id 绑定实际接受的初始止损风险；验证金额有限、正数、没有超过开盘/原信号预算，并与真实 fill 到冻结 stop 的距离、乘数/tick 下限及 audit 对齐。
- **毛 R = canonical episode realized_pnl / 实际接受的初始止损风险**。分母是 `stage041_entry_risk`，含引擎原 tick 最小风险下限；不是 target budget。分子是合约价差毛盈亏，不是扣费后的 net_pnl，也不是账户收益率。
- 仅将 source 风险送入原 canonical `_all_trade_episodes` 提取聚合风险与 R；只回填 closed_lots/all_trade_episodes/chart_manifest 的 `risk_amount/r_multiple`，以及 records.meta 的同两字段。
- CSV 使用标准 csv 模块保留其余单元格原字符串，不通过 pandas 重格式化其他列。所有 plot arrays、坐标、其余 metadata、记录顺序、原始盈利/亏损尾部标签不变；不做 R 尾部重选。页面警示明确说明旧标签来自父页 R 缺失时的筛选口径，新增 R 不追溯改变筛选。
- `_html` 仍为原 canonical 函数；替换不准确的全局“R不可获得时显示N/A”披露，加入上述 R 定义与保留原顺序/标签说明，未复制 HTML 布局或图表实现。

## 哈希闭合与输出隔离

- 逐个验证 source manifest 全部文件及 code_snapshot 哈希、parent 所有 artifact、嵌入 records/cache 一致性、源/父 summary 绑定及 canonical SHA。
- `risk_enrichment_manifest.json` 绑定 generator SHA、source manifest SHA、父 summary SHA 与全部父 artifact SHA。排除且仅排除两项获授权 R 字段后，对全部 records（包含全部图形数组、坐标及剩余 metadata）计算前后哈希，必须完全相同。
- 新输出另写 records/index/CSV/summary 并重算全部 artifact 哈希。源与父页只读；任何已有、嵌套、覆盖原输入的输出路径均拒绝。运行期间 generator/源 manifest/父 summary 变化则拒绝写入。

## 首次真实展示失败与定位

首次由根任务调用初版045，在 `BACKTESTING.120` 触发 `actual_open_risk_exceeds_signal_authorization` 并于创建 output 前退出。已核对 `_r` 目录当时不存在，源与父页未变化。

独立复现证明这是 **CSV解析边界错误，不是金融回放P1**：

| 项目 | 值 |
| --- | --- |
| 冻结CSV budget字符串 | `32146.359636085206` |
| JSON原信号target | `32146.359636085206` |
| pandas默认读取 | `32146.35963608521` |
| 默认读取人为引入差值 | `+3.637978807091713e-12` |
| `float_precision='round_trip'` | 恢复 `32146.359636085206`，与JSON差值0 |

修正045的源 trades/audit/metadata 与父 closed CSV 为 round_trip；**没有增加 epsilon，没有放宽 `risk <= open_budget <= original_target`。** 根任务授权同步修正尚未交付成功的 NEW044：所有CSV精准读取，直接核对记录中的实际预算不能高于原JSON授权。另加“真实 budget 比 target 高1 ULP仍必须拒绝”的回归，避免用宽容差掩盖真实越界。039/040/041与金融源始终未动。

## TDD与最终冻结验证

- 045：初始5项RED→GREEN，17位预算回归再次先RED（重现假越界）→GREEN，最终 **6/6通过**。
- 用例明确：gross100、net80、target budget100、实际初始风险20，输出 R 必须为 **5**，不能是1或4；所有非R数据完全相同。另覆盖缺失风险、源/父篡改、输出覆盖、17位等值授权。
- 044：新增精确读取及真实高1ULP拒绝两项均先RED→GREEN，最终 **10/10通过**。
- 两文件再次冻结后的全线测试：**137 tests，24.584秒，全部通过**；`git diff --check` 通过。
- 045最终 SHA256：`318b01cf92c6eb7c8c8f36f0d4f30a7a9950a94a9fc688e784a135a8ccedc500`。
- 044最终 SHA256：`27cb66d7209c93a0d878326fb3582436251496d6e31c6e9fdefc331cc0e9b0ec`。

## 后续与反思

- 根任务按原 `--source --parent --output` 命令重新执行045，再运行020和044并独立检查全体 R 分母、JavaScript及浏览器交互；这里的 fixture 成功不冒充全量真实页成功。
- 开始/结束过拟合判断：**否**。只是把已存在的实际风险证据展示出来，并修复数据读取忠实度；不改变交易和尾部筛选，不用收益反推规则。
- 开始/结束继续价值判断：**是**。实际风险已存在时应按复盘合同展示 R；同时不能混用预算、净收益或解析误差，所有原图形和成交事实必须可证明不变。
