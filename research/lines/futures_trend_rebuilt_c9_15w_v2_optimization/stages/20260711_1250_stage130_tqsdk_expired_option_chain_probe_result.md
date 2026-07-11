# Stage130 TqSdk 2022 历史期权链数据探针结果

- line_id：`futures_trend_rebuilt_c9_15w_v2_optimization`
- 当前模式：`day`
- 记录时间：`2026-07-11 12:50 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `codex/stage130-option-probe`
- 阶段性质：固定单标的、固定三日窗口的历史期权链数据可得性探针；不是收益回测，不产生策略候选
- 是否重要突破：是，但只突破“历史链无法读取”的数据阻塞
- 是否触发 A/B：否；只批准进入 acquisition manifest

## 外部调研与判断

- TqSdk 官方仓库和 `TqApi` 文档支持期权合约查询、历史回测和 K 线读取；`DataDownloader` 适合长期批量下载，但属于专业版能力，必须由实际权限和数据质量门裁决。
- TqSdk 回测模式会把 `query_options` 的过滤时点固定到当前回测时间。`DCE.m2209` 期权在 `2022-03-09` 尚未到期，因此正确查询语义是 `expired=False`，不能按今天已经到期而使用 `expired=True`。
- 本阶段判断：固定窗口已经证明历史 metadata 和日线序列可读取；但三日探针不能证明完整历史覆盖、可成交 premium、流动性、IV/Greeks 或保护层收益。

## 本次变更

- 新增脚本：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/tools/stage130_tqsdk_expired_option_chain_probe.py`
- 新增测试：`tests/test_rebuilt_c9_v2_stage130_tqsdk_expired_option_chain_probe.py`
- 新增预声明：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/stages/20260711_1152_stage130_tqsdk_expired_option_chain_probe_predecl.md`
- 新增参数：固定 underlying `DCE.m2209`、窗口 `2022-03-09 -> 2022-03-11`、`query_options(expired=False)`、日线 `duration_seconds=86400`、缓存长度 `20`
- 修改参数：首轮错误的历史状态谓词 `expired=True` 修正为 `False`
- 删除参数：无策略参数；未加入 IV、Greeks、收益阈值或保护比例

## 无效运行与根因

- `2026-07-11 12:06 CST` 首轮使用 `expired=True`，返回 query `0`。独立 review 为 `P0=0/P1=1/P2=3`，确认是回测时点状态谓词误用；无效产物隔离保存，不作为权限结论。
- `2026-07-11 12:29 CST` 同标的、同窗口、同端点修正谓词后返回 query `70`，但选择器错误报告无 CALL/PUT 对。根因是 metadata 先归一化成 `datetime64[ns]`，选择器二次归一化时把纳秒误当 Unix 秒，全部溢出为 `NaT`。错误产物隔离在 `/var/tmp/vnpy_stage130_invalid_double_normalization_20260711_1229`。
- 按 TDD 新增“已归一化 metadata 仍可配对”回归测试，先验证 RED，再让 datetime 列直接保留，只有原始数值列才按 Unix 秒转换。修复后 focused tests `8/8`、相关 TqSdk 回归 `19/19`。
- 上述两次均为 API/数据归一化 P1 修复，没有换标的、窗口、端点或按收益救参。

## 固定探针结果

- 生成时间：`2026-07-11 12:34:18 CST`
- decision：`stage130_tqsdk_expired_option_chain_ready_for_acquisition_manifest`
- query option count：`70`
- metadata：`70` 行，`35 CALL + 35 PUT`，symbol 唯一
- 选择结果：`DCE.m2209-C-3500` 与 `DCE.m2209-P-3500`，同标的、同行权价 `3500`、同到期 `2022-08-05 15:00:00`
- raw bars：`60` 行，三品种各 `20` 行；窗口前 `48` 行、窗口后 `3` 行，重复 `0`
- 最终 bars：`9` 行，标的/CALL/PUT 各覆盖 `2022-03-09/10/11` 三天；窗口外 `0`、重复 `0`、OHLC 缺失 `0`、OHLC 关系错误 `0`、负成交量 `0`
- 原始文件 hash：metadata/raw/filtered `3/3` 真实 SHA256 验证通过
- manifest：排除 manifest 自身后 `13/13` 文件集合、bytes、SHA256 全部匹配
- lineage：tool/test/predecl/raw 文件 SHA256 全部匹配；明确 `history_database_snapshot_complete=false`
- 凭证逐字泄露扫描：当前产物与无效归档命中 `0`
- 订单/CTP/live：订单 API `0`，CTP `false`，只使用 `TqSim`；正式策略、实盘入口、邮件和 launchd 均未修改

## 独立终审

- agent：`Helmholtz`，只读、无网络、未修改文件、未复跑网络探针。
- 结论：`P0=0/P1=0/P2=4`，批准 `ready_for_acquisition_manifest`，总体置信度 `0.96`。
- P2-1：当前 readiness 只要求 `raw_hash_count>=2`，未把 `probe_status=extracted` 和三个 raw 文件逐项验证写成通用硬门；本次实际为 `extracted + 3/3`，不阻断当前结果，下一采集器必须收紧。
- P2-2：报告只汇总窗口外 `51`，未拆成前 `48` 和后 `3`；最终 9 行无未来日期，不构成当前 PIT 泄漏，下一阶段必须分拆披露。
- P2-3：保存的 metadata 已归一化/裁列，不是 untouched API 原始字段；下一阶段必须同时保存原始 epoch 和完整源字段。
- P2-4：本次配对参考值是全链中位行权价，不是真实标的价格，且选中 CALL 三天成交量为 `0`；只能证明序列可取，不能证明 ATM、premium 或流动性。

## 回测指标

- 期末权益：不适用
- 总收益：不适用
- 最大回撤：不适用
- Sharpe：不适用
- 总滑点：不适用
- 总交易次数：`0`
- 胜率：不适用
- 原因：本阶段没有策略、头寸或收益回测，禁止伪造绩效口径。

## 输出文件

- report：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage130_tqsdk_expired_option_chain_probe/rebuilt_c9_v2_stage130_tqsdk_expired_option_chain_probe_report_stage130_tqsdk_expired_option_chain_probe_v1.md`
- decision：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage130_tqsdk_expired_option_chain_probe/rebuilt_c9_v2_stage130_tqsdk_expired_option_chain_probe_decision_stage130_tqsdk_expired_option_chain_probe_v1.json`
- metadata：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage130_tqsdk_expired_option_chain_probe/rebuilt_c9_v2_stage130_tqsdk_expired_option_chain_probe_option_metadata_stage130_tqsdk_expired_option_chain_probe_v1.csv`
- raw bars：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage130_tqsdk_expired_option_chain_probe/rebuilt_c9_v2_stage130_tqsdk_expired_option_chain_probe_raw_probe_bars_stage130_tqsdk_expired_option_chain_probe_v1.csv`
- filtered bars：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage130_tqsdk_expired_option_chain_probe/rebuilt_c9_v2_stage130_tqsdk_expired_option_chain_probe_probe_bars_stage130_tqsdk_expired_option_chain_probe_v1.csv`
- lineage：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage130_tqsdk_expired_option_chain_probe/rebuilt_c9_v2_stage130_tqsdk_expired_option_chain_probe_lineage_stage130_tqsdk_expired_option_chain_probe_v1.json`
- manifest：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage130_tqsdk_expired_option_chain_probe/rebuilt_c9_v2_stage130_tqsdk_expired_option_chain_probe_manifest_stage130_tqsdk_expired_option_chain_probe_v1.csv`

## 结论

- 本阶段结论：历史商品期权链的 metadata 和固定窗口日线可以通过当前 TqSdk 凭证读取，Stage045 的“没有 accepted 数据集”阻塞已经从完全未知推进到可建立真实 acquisition manifest。
- 是否进入下一步：是，但只进入采集清单和覆盖率验收，不直接做保护层 A/B。
- 下一步硬门：保存 untouched metadata；使用真实标的入场/止损价格定义候选行权价；逐项终态/hash；拆分 before/after-window；检查期权成交量、持仓量、premium、买卖价或分钟成交可得性；统计当前 C9 真实交易事件的同标的期权覆盖率。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：没有收益标签和参数搜索，标的/窗口在运行前固定；两次修复针对 API 历史状态和时间单位，不按下载结果或策略收益换样本。把后续 strike/DTE/保护比例按 2022 扫描才会转为高风险过拟合。

## 继续价值反思

- 运行前判断：有。
- 运行后判断：有，但只限数据采集与可实施性验收。
- 原因：期权保护层在机制上与既有降风险、AI/OI、账户阈值和现金桶路线正交；同时外部研究提醒静态保护性期权常被 premium drag 吞噬，三日数据成功绝不能直接解释为目标可达。

## 合入建议

- 更新本线 `LINE.md`：是。
- 更新 `research/registry.md`：是；属于历史期权数据阻塞的重要突破。
- 追加根目录 `back_log.md`：是；记录数据能力边界和不得夸大的限制。
- 更新根目录 `memory.md`：否；尚无策略候选或正式变更。
