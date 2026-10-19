# Stage081补充：v2仅诊断，待成功v3的展示流水线

- 时间：2026-10-20 00:56 CST。独立金融审查发现v2 pending OPEN延期后native actual0 reconcile清层/receipt的新P1，不能保留延期意向；等待root最小复现及085/086修复、新完整v3。v1失败prefix、v2完成账本/已生成raw均只诊断，不交付，不据此报绩效。20261020_0055_stage081_v2_source_display_preflight.json仅验证展示数量/费用/R闭包，不能替代策略意向协议的金融正确性或独立金融审查；该报告历史内容保留，不提升为最终验收。
- 071/072/081/083现有工具继续冻结，本次只读审查及命令准备，不生成v2的071/063，不重跑金融，不改任何旧源/输出/LINE/Git。
- 083范围复核通过：generate只读parent及source，限定两处JS指标表达式及一段html.escape纯文本note。unpatch_html必须完整逆向还原原HTML，嵌入records前后相同；records.json、全部其他artifact逐字节hash相同；summary仅新增展示manifest/source_warning/产物hash，不修改backtest_metrics、源参数、周值、任何坐标或图形计算。补丁放020后、067前。没有调用canonical重渲染，没有strategy/金融engine入口。
- 081/071/072的run_id都从显式source读取，不硬编码v1/v2；仍固定用户N859982…，严格0.005政策、receipt接口和参数变化白名单。v3仅修复执行协议且保留既定policy/参数/数据接口时无需改工具。若接口或参数另有改变，应先停下核对，不能放松白名单冒充同源。

## 命令（仅准备，尚未执行）

运行前条件：root确认v3完整manifest/summary闭合，独立金融审查无阻塞P1，明确批准该源用于交付；root先生成同v3的025 raw。以下以拟定v3名称为例，实际源/run名由root通知，所有目标目录必须不存在。基线N不变，不能替换旧M/A。

```sh
display_py=/Users/mac/Desktop/fian/.py311/bin/python
display_line=/Users/mac/.codex/worktrees/full-market-noai-one-lot/fian/research/lines/futures_trend_full_market_noai_one_lot
display_source="$display_line/outputs/run_20261020_contract_weekly_risk05_v3"
display_base="$display_line/outputs/run_20261019_contract_weekly_long_v1"
display_raw="$display_line/outputs/recap_20261020_contract_weekly_risk05_v3_raw"
display_r="$display_line/outputs/recap_20261020_contract_weekly_risk05_v3_fractional"
display_weekly="$display_line/outputs/recap_20261020_contract_weekly_risk05_v3_exact_weekly"
display_reviewed="$display_line/outputs/recap_20261020_contract_weekly_risk05_v3_reviewed"
display_labels="$display_line/outputs/recap_20261020_contract_weekly_risk05_v3_labels"
display_final="$display_line/outputs/recap_20261020_contract_weekly_risk05_v3_final"
display_overview="$display_line/outputs/overview_20261020_contract_weekly_risk05_v3"

"$display_py" "$display_line/tools/stage071_fractional_recap.py" --source "$display_source" --parent "$display_raw" --output "$display_r"
"$display_py" "$display_line/tools/stage063_contract_weekly_recap.py" --source "$display_source" --parent "$display_r" --output "$display_weekly"

# root填入绑定v3源的独立金融审查报告，且明确通过后才运行此步骤。
"$display_py" "$display_line/tools/stage020_review_finalizer.py" "$display_weekly" "<v3独立金融审查通过报告.md>" "$display_reviewed"
"$display_py" "$display_line/tools/stage083_final_multilot_labels.py" --parent "$display_reviewed" --output "$display_labels"
"$display_py" "$display_line/tools/stage067_current_trade_reset.py" --parent "$display_labels" --output "$display_final"
"$display_py" "$display_line/tools/stage072_fractional_overview.py" --source "$display_source" --parent "$display_final" --baseline "$display_base" --output "$display_overview"
"$display_py" "$display_line/tools/stage081_validate_fractional_display.py" --source "$display_source" --baseline "$display_base" --raw "$display_raw" --fractional "$display_r" --weekly "$display_weekly" --final "$display_final" --overview "$display_overview" --output "<全新Stage081_v3_actual_validation.json>"
```

081最终报告之后仍须root浏览器复核默认周期、筛选、下一笔/上一笔、联动缩放、当前交易Reset axes、净/毛额与手数、分批退出标记（实际数量按v3报告，不沿用v2）、总览N比较/全部曲线与PNG可读性。不得把脚本语法通过等同浏览器通过。

- 新增/修改/删除金融结果：无。过拟合：否，纯交付门禁与展示命令准备；继续价值：是，应先修复延期意向协议再产生可信结果，不应为已有渲染成本继续交付v2。
