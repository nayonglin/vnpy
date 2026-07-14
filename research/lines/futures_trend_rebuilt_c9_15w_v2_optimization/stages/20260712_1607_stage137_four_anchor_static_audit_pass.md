# Stage137 四锚点 static audit 首次通过

- line_id：`futures_trend_rebuilt_c9_15w_v2_optimization`
- 当前模式：`audit`
- 记录时间：`2026-07-12 16:07 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `codex/stage130-option-probe`
- 阶段性质：真实四锚点静态身份与输入审计
- 是否重要突破：否；只通过运行前静态门禁
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：in-toto Link materials、Python `hashlib` / `os.replace`。
- 我的判断：本次 path+size+SHA、锚点内双 worker、跨锚点并集与最终重哈希形成了可信内容闭环；mtime 血缘列仍有纳秒整数 CSV 精度假阳性，必须修正后再决定 canary。

## 本次变更

- 新增脚本：无
- 修改脚本：无；运行 correction 7 已审查版本
- 删除脚本：无
- 新增参数：无
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：`2020-01`、`2022-01`、`2022-07`、`2026-01` 四起点，统一终点 `2026-06-30`
- 账户规模：冻结 C9 `150,000`；本次未运行卫星账本
- 成本口径：`1x` 字段存在，但未运行绩效、滑点或手续费计算
- 样本过滤：current-AI 固定 SHA `fc50e035cd66b65e94261ef70476747daa94ae73071d0f4d7206ff7b644271fc`，`504` 行、`55` 个 eval_date
- 策略/归因口径：每锚点两个独立 current-C9 subprocess；14 组 raw/derived frame canonical identity；在 satellite replay 前停止

## 结果

- 期末权益：未计算
- 总收益：未计算
- 最大回撤：未计算
- Sharpe：未计算
- 总滑点：未计算
- 总交易次数：未计算
- 胜率：未计算
- 其他关键指标：`audit_pass=true`、`canary_pass=false`、`failed_checks=[canary_not_run]`、`full_allowed=false`；四锚点 eligible/mapped/selected 分别 `193/193/193`、`96/96/96`、`91/91/91`、`16/16/16`；全部 coverage/future/order/default/fallback/overclose 失败计数为 `0`；`2026-01` 有 `2` 个 terminal-open lifecycle，其余为 `0`。

## 身份与来源证据

- current AI/golden：四锚点全部 PASS；2020 golden daily 最大 account/net/margin 误差分别 `2.328306e-10 / 2.910383e-11 / 2.328306e-10`。
- repeat frames：`4 × 14 = 56` 行，schema/content mismatch 均为 `0`。
- repeat source：每锚点路径数 `394 / 244 / 230 / 129`；合计 ledger `997` 行；并集 `394` 路径，恰等于 final manifest；重叠 size/SHA drift `0`。
- current environment SHA：四锚点完全一致。
- candidate orders：`651` 行，base trade key 重复 `0`、零 delta `0`；静态未 replay。
- source rewrite：真实 worker same-content rewrite 合计 `8`；final `post_finalization_mtime_only_rewrite=0`。
- 待修：final `post_read_same_content_rewrite=294` 为可疑假阳性，初步归因 nullable 纳秒整数经 CSV 读为 float 后精度损失；等待独立 reviewer。

## 输出文件

- report：`outputs/stage137_current_c9_quality_one_way_satellite/report.md`
- summary：`summary.csv`，`0` 行、`33` 列
- orders：`candidate_orders.csv`；`replayed_orders.csv` 为零字节静态空表
- daily：`base_daily.csv`；`satellite_daily.csv` 为零字节静态空表
- quality：`decision.json`、`input_audit.csv`、`current_ai_audit.csv`、`repeat_identity_audit.csv`、`repeat_source_manifest.csv`、`source_manifest.csv` 及 PIT/FIFO/margin 静态证据

## 结论

- 本阶段结论：四锚点静态内容身份与输入 coverage 门禁通过；没有产生或宣称任何卫星收益。
- 是否进入下一步：否，暂不运行 canary。
- 下一步：独立 agent 从 raw CSV/JSON 重算；判断 mtime 纳秒精度和零字节空表严重度。必要时 TDD 修复、重跑 static audit 并再次独立审查。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：没有查看卫星收益、没有调整 selector、`25%`、锚点或绩效门槛。

## 继续价值反思

- 运行前判断：有。
- 运行后判断：有。
- 原因：内容门禁首次闭环，同时暴露了 mtime 血缘统计的机器精度问题；修好后才适合进入真实 canary。

## 合入建议

- 是否更新本线 `LINE.md`：暂不，尚无绩效结论
- 是否更新 `research/registry.md`：否
- 是否追加根目录 `memory.md/back_log.md`：否
