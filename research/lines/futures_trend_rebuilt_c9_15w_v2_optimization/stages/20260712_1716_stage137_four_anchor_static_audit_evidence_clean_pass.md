# Stage137 四锚点 static audit 证据修复后通过

- line_id：`futures_trend_rebuilt_c9_15w_v2_optimization`
- 当前模式：`audit`
- 记录时间：`2026-07-12 17:16 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `codex/stage130-option-probe`
- 阶段性质：真实四锚点静态审计与机器证据复验
- 是否重要突破：否；仍未运行绩效
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：Pandas nullable integer、in-toto materials digest、Python `os.replace`。
- 我的判断：attempt 5 同时闭合内容身份和机器证据；能否进入 canary 仍取决于新的独立 raw-data review。

## 本次变更

- 新增脚本：无
- 修改脚本：无；运行 correction 8 review-2 批准版本
- 删除脚本：无
- 新增参数：无
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：`2020-01 / 2022-01 / 2022-07 / 2026-01`，统一终点 `2026-06-30`
- 账户规模：冻结 C9 `150,000`；卫星账本未运行
- 成本口径：未运行绩效与成本计算
- 样本过滤：current-AI 固定 SHA、`504` 行、`55` eval_date
- 策略/归因口径：双 worker、`4 × 14` canonical identity、PIT/FIFO/margin static、satellite replay 前停止

## 结果

- 期末权益：未计算
- 总收益：未计算
- 最大回撤：未计算
- Sharpe：未计算
- 总滑点：未计算
- 总交易次数：未计算
- 胜率：未计算
- 其他关键指标：`audit_pass=true`、`canary_not_run`、`full_allowed=false`；eligible/mapped/selected 仍为 `193/96/91/16` 且全部一一相等；所有 coverage/future/order/default/fallback/overclose 失败计数为 `0`；terminal-open 仍仅 `2026-01` 两组。

## 证据复验

- 所有 `19` 个 CSV 可由标准 `pd.read_csv` 读取。
- `satellite_daily`：`0` 行、`48` 列；`replayed_orders`：`0` 行、`24` 列；summary/reconciliation 也均为零行固定 schema。
- `price_audit`：`1,881` 行，按锚点 `1129 / 320 / 384 / 48`，`requested_start_month + date + vt_symbol` 重复 `0`。
- repeat identity：`56` 行、`4 × 14`，mismatch `0`；price canonical key 含 requested start。
- repeat source：`997` 行、每锚点 `394 / 244 / 230 / 129`，并集等于 final `394`。
- source lineage：same-content rewrite `8`；post-read false-positive `0`；post-final rewrite `0`；first/last/final mtime 均为精确 `int64` 且无缺失。
- output 由 render 前后两轮 memory+disk bytes binding 后原子替换；目录共 `24` 个文件，其中非 chart 证据 payload `21` 个。

## 输出文件

- report：`outputs/stage137_current_c9_quality_one_way_satellite/report.md`
- summary：零行固定 schema
- orders：candidate static ledger；replayed orders 零行固定 schema
- daily：base identity daily；satellite daily 零行固定 schema
- quality：decision、input/AI/repeat/source/PIT/FIFO/margin/price evidence

## 结论

- 本阶段结论：本地主线程复算显示 correction 8 三个证据问题已在真实 static output 中消失，原内容门禁无回退。
- 是否进入下一步：等待独立 reviewer，不先运行 canary。
- 下一步：独立 reviewer 重新哈希全部来源并复算 raw evidence；仅在 P0/P1=0 时运行一次四锚点 1x canary。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：没有运行卫星绩效、没有修改策略参数或根据收益选规则。

## 继续价值反思

- 运行前判断：有。
- 运行后判断：有。
- 原因：静态证据已达到直接按锚点机器复算的条件，下一步终于可以在固定合同下检验真实收益/回撤假设。

## 合入建议

- 是否更新本线 `LINE.md`：暂不，尚无绩效结论
- 是否更新 `research/registry.md`：否
- 是否追加根目录 `memory.md/back_log.md`：否
