# Stage212 Stage935 AI 池生产源路径一致性修复

- line_id：`futures_trend_stage819_intraday_rules`
- 当前模式：生产自动化候选修复、隔离只读资格验证；尚未安装实盘
- 记录时间：2026-08-03 22:01 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy_stage174_postclose_orchestration` / `codex/stage174-postclose-orchestration`
- 阶段性质：执行接线与发布安全修复，不修改 alpha
- 是否重要突破：否；这是阻断旧 AI 池继续被误用的必要修复
- 是否触发A/B：否；模型、排序、TopN、资金和订单规则均未改变

## 外部调研与判断

- 参考资料：Pandas 官方时间序列指南 `https://pandas.pydata.org/docs/user_guide/timeseries.html`；Pandas 官方 `reindex` 文档 `https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.reindex.html`。
- 我的判断：月度池应使用“最新完整月份”的稀疏候选截面，不能强制候选事件文件与日频文件同日；真正故障是 Stage183 写入 runtime control root，而 Stage182/Stage935 从静态 `backtest_outputs` 读取旧文件。修复必须同时绑定路径、日期和文件字节身份，不能只修一个环境变量。

## 根因

1. Stage183 运行时产物遵循 `OFFICIAL_LIVE_OUTPUT_DIR`，日频和持仓源已更新到 `2026-08-03`。
2. Stage183 摘要和 Stage182 源路径此前仍指向静态项目 `backtest_outputs`，Stage182 实际选到旧的 `2026-06-30` 截面。
3. Stage935 因此报告缺少 `2026-07-31` 月度截面，邮件失败；旧实现还缺少候选隔离、完整 Top9、可靠回滚和同路径内容替换防护。

## 本次变更

- 新增脚本：无。
- 修改脚本：
  - `build_qmt_roll_stage183_ai_product_pool_source_refresh.py`：从真实 runtime artifact root 建路径，分别报告日频/持仓/稀疏候选日期，并记录 size、mtime_ns、SHA-256。
  - `build_qmt_roll_stage182_ai_product_pool_live_inference_runner.py`：新增显式 `--source-dir` / `--output-dir`，只写候选目录；推理前后核对源文件字节身份。
  - `run_qmt_roll_stage935_official_live_monthly_ai_pool_update.py`：校验 Stage183 路径、日期、字节身份；要求 Stage182 声明并复核同一份源；候选验证后以 combined last 原子发布；任何替换后异常或后验失败恢复旧 combined；最近四个月及当前月必须各 9 行且当前 combined 与 live Top9 产品/排名完全一致；control 与正式数据根相同则在执行子命令前阻断。
  - 相关单元测试与 Stage947 集成 fixture。
- 删除脚本：无。
- 新增参数：Stage182 `--source-dir`、`--output-dir`。
- 修改参数：无策略参数修改。
- 删除参数：无。
- 关键提交：`97c22c51e`、`5d3fc3ce6`、`94bbc0753`、`bf0b8154e`、`199a76ef8`、`18fafb409`、`9270bf113`。

## 回测/归因参数

- 数据区间：只读生产源最大日期 `2026-08-03`；月度评估截面 `2026-07-31`。
- 账户规模：不适用；未运行策略回测、账户仿真或 CTP。
- 成本口径：不适用。
- 样本过滤：沿用冻结的 Stage182 模型和最新完整月份规则。
- 策略/归因口径：只验证 AI 池生成与发布接线；不修改 C9/15w 策略、0.5R 止损、一次重试、手数或信号。

## 验证结果

- TDD：先复现跨根旧源、候选直接发布、combined 截断、替换后异常、源内容替换和目录不隔离，再修复。
- 回归：`61` tests passed；三份修改脚本 `py_compile` 通过；`git diff --check` 通过。
- 真实源隔离资格目录：`/private/tmp/stage935-ai-qualification.1i01EK`，所有候选输出均在 `/tmp`，未覆盖正式文件。
- validation：`valid`，blockers `[]`。
- eval_date：`2026-07-31`；source_max_date：`2026-08-03`。
- Top9：`jm.DCE, si.GFEX, SA.CZCE, au.SHFE, lc.GFEX, cu.SHFE, SM.CZCE, lh.DCE, fu.SHFE`。
- 最近四个必需截面：`2026-04-30, 2026-05-29, 2026-06-30, 2026-07-31`；每月均为 `9` 行，缺失 `0`。
- 源 SHA-256：position changes `b3bacdf711c3282f703ea022332d89fc1fe007cc1fb25eb1a25abac7a1eff847`；entry snapshots `96a36c13cdccd5ce73e718d780b4122e2554959d60b697bfbc9f8f99176a33a2`。
- 候选 SHA-256：live pool `3bc1e2941380feb8ebc539f2fd04f7d992d06804c4ceaace0b8b5fbfdd561d05`；live eligibility `ac786798ab35312c0fa8535f238d065020cfbafda123a30c6675d4af3267b21c`；combined `56b6a35419831809a27cf222a019e0a62c9dc34390fd996243ee26353a7004cf`；summary `c846c0cc6a039faa79e8b6f766c01a67b5a2f2f4e776f6c444ccb8a789112ffb`；report `99a38a81d45912af981faac97820f35c88ea857600314bf849901189ef57a979`。
- send/cancel/order API：`0/0/0`。

## 回测结果

- 期末权益：未新增、未修改、未删除；本阶段未运行回测。
- 总收益：未新增、未修改、未删除；本阶段未运行回测。
- 最大回撤：未新增、未修改、未删除；本阶段未运行回测。
- Sharpe：未新增、未修改、未删除；本阶段未运行回测。
- 总滑点：未新增、未修改、未删除；本阶段未运行回测。
- 总交易次数：未新增、未修改、未删除；本阶段未运行回测。
- 胜率：未新增、未修改、未删除；本阶段未运行回测。

## 审查

- 第一轮独立审查发现：P0 `1`（原子替换后目录 fsync 异常未必回滚），P1 `2`（combined 可被截断；源文件缺字节身份绑定），P2 `1`（测试修改全局路径未恢复）。
- 已修复：combined 替换尝试前建立恢复依据；严格每月/当前 Top9；Stage183→Stage182→发布全过程 SHA-256 绑定；测试清理全局状态。
- 第二轮独立审查发现：P0 `1`（发布成功后备份清理 fsync 异常会误报 blocked 且无法回滚），P1 `1`（历史月只校验 9 行，未校验唯一产品、rank 1..9、top_n=9），P2 `0`。
- 已修复：激活完成且 hash/后验验证通过后，备份清理失败只记录 warning，不再把已成功激活误报为 blocked；最近四个月每月均要求 9 个唯一产品、rank `1..9`、`top_n=9` 且包含固定 `fu.SHFE`。
- 修复后回归 `61` 项通过，真实生产源隔离候选重新验证 `valid` 且新增历史月结构 blocker 全空。
- 最终独立复审：`P0/P1/P2=0/0/0`，结论 `READY`（仅代码候选 ready，不代表已取得生产安装资格）。

## 生产门禁

- 固定 Stage174 候选 HEAD 已核对为 `cc5ddf64f80711c0e3324b84bbbd3758c6581c26`。
- Stage174 Task3 正式 CTP 只读 captures 仍为 `0/2`，未建立 qualification bundle，未执行 Stage948 prepare/activate。
- 2026-08-03 22:01 CST 七个 launchd label 均无 PID，但 night-session 为 `spawn scheduled`；没有 stop/kill/bootout/kickstart。
- 磁盘仅剩约 `2.3 GiB`、使用率 `100%`，不满足完整双 capture 和 release 构建的安全空间门禁。
- 当前结论：代码候选修复完成，正式安装仍 `fail-closed`，生产 stable 未切换。

## 结论

- 本阶段结论：旧 AI 池的底层路径分裂已在候选代码中修复，真实生产源隔离验证通过，但尚未获得正式发布资格，不能宣称已经安装实盘。
- 是否进入下一步：是；先完成第二轮独立审查，再等待磁盘和 Stage174 两次正式只读 qualification 全部通过。
- 下一步：不得人工干预夜盘进程；自然静默且磁盘门禁通过后，完成 Task3 两次 capture；随后只通过 Stage948 prepare/activate 发布并核验 stable、manifest、receipt、7 labels 和 API counter 全零。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：没有按收益、月份、品种或交易结果调参；只修路径、日期语义、文件身份、原子性和 fail-closed 完整性。

## 继续价值反思

- 运行前判断：是。
- 运行后判断：是，但仅限完成资格与安全发布。
- 原因：候选已证明能生成正确的新 AI 池；继续扫模型或参数没有价值，完成证据链和受控发布有直接生产价值。

## 合入建议

- 是否更新本线 `LINE.md`：待正式安装完成后统一更新。
- 是否更新 `research/registry.md`：否；本阶段不是 alpha 或正式版本切换完成。
- 是否追加根目录 `memory.md/back_log.md`：待 Stage948 正式激活后再追加重要合入摘要。
