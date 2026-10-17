# Stage007 官方历史 K 线流单窗口探针：数据取齐，原资格检查因 OI 字段语义拒绝

- line_id：`futures_trend_triple_screen`
- 当前模式：离线研究中的一次正规提供商数据探针；未执行 C9 金融策略，`production_qualified=false`。
- 记录时间：2026-10-17 23:49 CST，读取时钟后记录。
- 工作区/分支：`/Users/mac/Desktop/fian` / `codex/ai-training-data-expansion`。
- 阶段性质：单窗口数据能力与质量验证，不是 C0 第三次尝试。
- 是否重要突破：否；澄清普通历史回放通路可用，并发现原日线对照中的持仓量字段语义错误。
- 是否触发A/B：本阶段不新增金融 A/B，Stage001 累计金融 attempt 仍为 4，完整 A0 仍为 1。

## 外部调研与判断

- 参考资料：[官方快速入门](https://doc.shinnytech.com/tqsdk/latest/quickstart.html)、[官方版本说明](https://doc.shinnytech.com/tqsdk/latest/version.html)、[官方鉴权源码](https://github.com/shinnytech/tqsdk-python/blob/master/tqsdk/auth.py)，与本机已安装 TqSdk 3.10.2 的正常 API 路径。
- 我的判断：普通 `TqBacktest + get_kline_serial` 与要求 `tq_dl` 的区间下载 API 不同。本次实际取得数据，证实此前 `DataDownloader` 权限不足不能推广为普通历史 K 线流不可用；本次成功也不能推广为所有年份、品种、账号权限或批量下载权限。
- 质量判断：必须同时保留原拒绝和新发现的字段语义证据；不能为得到通过结果修改已运行工具或覆盖 receipt，也不需重新连接取得同一批分钟。

## 本次变更

- 新增脚本：`tools/stage007_tqsdk_stream_probe.py`、`tools/test_stage007_tqsdk_stream_probe.py`。
- 修改脚本：无正式源码修改；已网络运行的工具、测试、quality 和 receipt 在结果整理时保持原字节。
- 删除脚本：无。
- 新增参数：固定 `--preflight` / `--run`；单一合约 `SHFE.rb2010`、60 秒序列、固定提供商回放窗口 2020-08-11—2020-08-13、目标交易日 2020-08-12、父进程墙钟硬限 180 秒。
- 修改参数：无策略参数修改。离线 preflight 初次仅因 SDK 静态源码路径布局不符失败，已保留 `preflight_failure1.json`；修正指纹路径后离线通过，未在该步骤连接提供商。
- 删除参数：无。
- 执行前门：5 个 focused 契约测试通过，离线 preflight 通过；root 核对后启动唯一网络 `--run`，自动审批通过。无自动重试。

## 回测/归因参数

- 数据区间：提供商窗口 2020-08-11—2020-08-13；验收目标仅交易日 2020-08-12，物理 2020-08-11 21:00—2020-08-12 14:59，原 helper 预期 345 分钟。
- 账户规模：N/A；仅显式创建 1 个 SDK 本地 `TqSim` 供官方回放框架运行，未运行 C9 或任何金融策略。
- 成本口径：N/A；不计算收益、成交、费用或滑点。
- 样本过滤：只收录已在 serial 中观察到后继 K 线的目标分钟；末尾形成中 K 线不能因回放结束被强行判完成。同键完成值冲突拒绝。
- 策略/归因口径：Tq 纳秒按 UTC 绝对时间转 Asia/Shanghai；夜盘归属沿原 session helper。独立 raw 沿原 9 列格式，另存逐键后继证据。仅核对目标合约日线 CSV 和原 SQLite，不改缓存或执行合同。
- 隐私边界：凭证只在本机读取，不进 argv、manifest 或日志；SDK 原 stdout/stderr 不保存，日志仅固定安全类别。鉴权与授权检查未修改。

## 结果

- 期末权益：N/A。
- 总收益：N/A。
- 最大回撤：N/A。
- Sharpe：N/A。
- 总滑点：N/A。
- 总交易次数：N/A。
- 胜率：N/A。
- 其他关键指标：提供商回放尝试 1 次，耗时 38.22 秒，未触发 180 秒 hard kill；创建本地 TqSim 1 个，C9/金融策略回放 0，CTP/券商连接 0，下单 0，撤单 0。
- 正常认证及历史流实际可用；无认证、权限、配额或网络拒绝。本次可能消耗提供商当天 1 次回测配额，不尝试绕过或扩大次数。
- 目标取得 345/345 个唯一完成分钟，缺失 0，全部具有观察到后继 K 线的完成证据。
- 日线 CSV 七字段聚合全部一致。原 SQLite 对照仅在被工具解释为 `close_oi` 的 `open_interest` 字段拒绝，其余 OHLCV 一致。

| 字段 | 完成分钟聚合 | 原日线 CSV | 原 SQLite 对应字段 |
| --- | ---: | ---: | --- |
| open | 3,795 | 3,795 | open_price，匹配 |
| high | 3,809 | 3,809 | high_price，匹配 |
| low | 3,780 | 3,780 | low_price，匹配 |
| close | 3,805 | 3,805 | close_price，匹配 |
| volume | 740,132 | 740,132 | volume，匹配 |
| open_oi | 1,064,817 | 1,064,817 | open_interest 实际为此口径 |
| close_oi | 1,053,986 | 1,053,986 | 无可据此声明的独立 closeOI 字段 |

原终态严格保留：worker `completed_quality_rejected`，`quality.accepted=false`，父进程 exit 1。该状态来自 OI 对照语义，不代表权限失败或分钟数据坏；本记录没有将其改写为原资格门已通过。

### 已定位的字段语义根因

root 对照目标相邻三天的精确 SQL 与原 CSV，发现 DB `open_interest` 逐日等于 CSV `open_oi`。本任务只读核到导入生产代码 `examples/portfolio_backtesting/import_tqsdk_all_futures_daily_to_db.py:115` 明确赋值：`open_interest=float(getattr(row, "open_oi", 0.0) or 0.0)`。

因此 Stage007 复用的数据库对照把 `open_interest` 映射为 `close_oi` 的假设错误。原 DB 有自己的确定导入语义，不能把它任意改标为 closeOI，也不能编造缺失的 closeOI 值。本阶段不改 DB、原 CSV、分钟、工具或原拒绝产物；后续应在独立 Stage008 协议下，零网络按正确字段对应重新资格审查。

## 输出文件

目录：`outputs/stage007_tqsdk_stream_probe/`。

- report：本阶段记录。
- summary：`network_attempt1/parent_receipt.json`、`network_attempt1/worker_receipt.json`。
- orders：N/A；未创建委托。
- daily：N/A；未产生账户日权益。
- quality：`network_attempt1/quality.json`、`network_attempt1/completion_evidence.csv`、`preflight.json`、`preflight_failure1.json`、`network_attempt1/attempt_started.json`。
- 独立原始分钟：`network_attempt1/raw_completed_minutes.csv`，只保留本机，不进 Git。
- raw SHA256：`0805e7083b24e988469bee78fabc53419d2855e85f92928256a184d9db9480ac`。
- completion evidence SHA256：`3eecacbf83069daac6e0508b5ebdb79e6db50ba60b89b1486d76ce2979f8aff2`。
- 原拒绝 quality SHA256：`9bf02a770b12c7fe65d2efb105e3bfc4f29227d2961352eb0a614a6d5eb6625e`。
- parent receipt 记录输入指纹全部不变、无自动重试、无缓存写入；其余输出指纹见该 receipt。
- 本阶段不冒称独立全量数据审查已完成；root 将安排 Stage008 对现有同 SHA 产物重新资格审查。

## 结论

- 本阶段结论：正规普通 TqBacktest 历史 K 线流在当前账号、当前时间、该窗口实测可用；345 根完成分钟与原 CSV 七字段一致。原严格 gate 仍为拒绝，已定位拒绝源于 DB OI 字段的错误解释。
- 是否进入下一步：是，进入 Stage008 零网络重新资格审查；不再次连接，不重新下载。
- 下一步：冻结新数据合同，以 CSV 七字段与 DB OHLCV、DB `open_interest → 首分钟 open_oi` 的真实语义核对；DB closeOI 标为不存在/未知。该检查通过并获独立审查后，仍需另行决定精确批量需求，不能直接并入 base/overlay 或重跑 C0。

## 过拟合反思

- 运行前判断：否，固定窗口来自已确认分钟缺口，不读收益、不调 alpha。
- 运行后判断：否，保留原拒绝、原数据和确定的导入语义；纠正字段理解不以提升策略表现为条件。
- 原因：下一步验证应依赖导入源码与独立价格字段，而非通过放宽容差、改值或择优挑数据消除不一致。原历史样本选择风险仍存在。

## 继续价值反思

- 运行前判断：是，一个完整小窗口能检验合法数据通路和质量约束。
- 运行后判断：是，实际数据已齐且根因明确，继续价值在零网络重新审查现有证据，而非再跑提供商或金融账户。
- 原因：未验证的字段假设应先修订合同，重复获取同一数据不能解决语义问题。

## 合入建议

- 是否更新本线 `LINE.md`：由 root 统一更新，本任务未改。
- 是否更新 `research/registry.md`：由 root 决定，本任务未改。
- 是否追加根目录 `memory.md/back_log.md`：否，尚无正式候选晋级。
- 可归档工具、测试、小型 receipt 和记录；raw 分钟与私有配置不进 Git。任何正式数据源接入、执行 fallback 或生产发布均未获本阶段批准。

## 后续独立审查补记

- `outputs/stage007_independent_review/` 已完成独立审查：原始完成分钟通过；P1 共 1 项，限定为旧资格检查将 DB `open_interest` 误映射为 closeOI。Stage007 原拒绝与已运行字节继续保留，不能回写成原合同通过。
- 独立 review receipt SHA256：`3e2e7c1e89cd53b48c8d547119984db7cd482895a093b729eac1fbde61aa12c3`。
- 正确 OI 合同在 Stage008 独立处理，不以此次审查自动授权数据合并或金融重跑。
