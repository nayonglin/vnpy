# Stage001 canary 前独立审查 NO-GO 与闸门修复

- line_id：`futures_trend_candidate_marginal_risk_contribution`
- 当前模式：研究候选 / canary 前代码审计
- 记录时间：`2026-07-12 19:46 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `codex/stage130-option-probe`
- 阶段性质：独立审查、负例复现、闸门修复；未运行收益回测
- 是否重要突破：否
- 是否触发A/B：是；仍停留在 canary 前，不接入正式版

## 独立审查

- 审查员：独立 agent `Tesla`
- 结论：`NO-GO`，`P0=0`、`P1=2`、`P2=3`，置信度 `97%`
- P1-1：canary 判定忽略 pending order、terminal/持仓/保证金 reconciliation，且 broker10 为 `NaN` 时比较会绕过门槛。
- P1-2：运行时先抓取当前工具哈希、再把它自设为 expected，不能证明运行的是独立审查过的代码字节。
- P2：缺少负方向、pending/terminal/NaN/source-review 负例；未来行审计计数被写死为0；协方差/零方差异常未按整批 no-op 降级。
- 审查员确认：T-1、精确63共同日、actual-contract 不拼接、MRC/RC/IC/CC、LedoitWolf、`current_pos` 符号和 planner 后 hook 未见 P0。

## 负例复现

- 修复前单测：`23` 项中 `3 failure + 3 error`，准确复现六类缺口。
- 对抗输入：`pending_order_count=2`、terminal error=`999` 或 broker10=`NaN`，旧判定仍可能返回 `canary_pass=True`。
- 判断：这是统计准入 fail-open，不是 alpha 表现问题；禁止在修复前运行 canary。

## 修复

- `evaluate_canary` 增加强制 schema、四锚点 A/C 唯一覆盖、runtime 四锚点覆盖和所有关键数值有限性检查；缺列、重复、缺锚点、`NaN/inf` 一律 fail-close。
- pending order 必须为0；终局持仓允许非零，但必须与累计成交严格一致。
- 新增逐日 position change 对成交、position continuity、terminal position、`c3/total margin`、broker10 ratio 的独立恒等式审计。
- pending、position、trade 重复键或非法字段均阻断。
- 协方差、零方差和数值线性代数异常按事前口径整批 no-op，保持原候选手数并写明 `risk_compute_error`。
- `current_or_future_row_count` 改为真实被排除行数；选样仍严格 `< cutoff`。
- 新增外部 review manifest：清单固定代码、测试、预声明、数据合同、静态审计、Stage137 manifest、return panel 和输入源；canary 命令必须显式传入独立审查确认的 manifest SHA，且运行前后均重验。

## 验证

- `.py311/bin/python tests/test_candidate_marginal_risk_contribution_stage001.py`：`23/23` 通过。
- `py_compile`：通过。
- 静态面板重建：SHA256 仍为 `f7309d2ea3709731c2cbcebd8bf6b57e92309ec20367a885426421da86b04da9`。
- 静态覆盖：`567/567` 合约、`116,445` 行、零重复键、零未来日期；`264/265` 批次精确63日，唯一 `lh2109.DCE` 58日整批 no-op。

## 回测结果

- 期末权益：N/A（未运行）
- 总收益：N/A（未运行）
- 最大回撤：N/A（未运行）
- Sharpe：N/A（未运行）
- 总滑点：N/A（未运行）
- 总交易次数：N/A（未运行）
- 胜率：N/A（未运行）

## 结论

- 本阶段结论：首轮独立审查正确阻断了存在 fail-open 的实现；缺陷已由先失败后通过的负例覆盖。
- 是否进入下一步：否；必须先由另一名独立 agent 对修复后固定字节复审并签认 review manifest SHA。
- 下一步：复审若 `P0=P1=0` 才运行四锚点 1x canary；否则继续禁止回测。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：没有观察任何候选收益，修复仅收紧数据和执行准入，不改风险公式、窗口、参数、锚点或绩效门槛。

## 继续价值反思

- 运行前判断：有。
- 运行后判断：有，但仍只允许一次冻结 canary。
- 原因：独立审查发现并修复了可复现的统计闸门问题；若下一轮审查或 canary 失败，应停止该具体实现。

## 合入建议

- 是否更新本线 `LINE.md`：canary 及结果独立审查后统一更新
- 是否更新 `research/registry.md`：否
- 是否追加根目录 `memory.md/back_log.md`：否；尚无回测突破或正式候选
