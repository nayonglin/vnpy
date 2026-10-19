# 双版展示命令（尚未执行真实生成）

按root明确传入的完整两源、025raw与各臂独立金融PASS报告运行；所有目录新建，不覆盖。025/001不按long_weekly_filter或riskflags做策略过滤，原样支持quarter两版trade/daily/market schema，仍是中间页；094/095修正0.25%/周门口径，最终020后083恢复多手卡片、067恢复当前交易Reset。

```sh
display_py=/Users/mac/Desktop/fian/.py311/bin/python
display_line=/Users/mac/.codex/worktrees/full-market-noai-one-lot/fian/research/lines/futures_trend_full_market_noai_one_lot
# 此块分别以contract_weekly / no_weekly运行；025由root执行，不重复启动。
display_tag=contract_weekly
display_source="$display_line/outputs/run_20261020_risk025_${display_tag}_v1"
display_prefix="$display_line/outputs/recap_20261020_risk025_${display_tag}_v1"
"$display_py" "$display_line/tools/stage025_parallel_context_recap.py" --source "$display_source" --output "${display_prefix}_raw" --workers 4
"$display_py" "$display_line/tools/stage094_quarter_risk_recap.py" --source "$display_source" --parent "${display_prefix}_raw" --output "${display_prefix}_fractional"
"$display_py" "$display_line/tools/stage095_quarter_weekly_display.py" --source "$display_source" --parent "${display_prefix}_fractional" --output "${display_prefix}_exact_weekly"
# 仅在各臂独立金融审查PASS已绑定该源时，root执行：
"$display_py" "$display_line/tools/stage020_review_finalizer.py" "${display_prefix}_exact_weekly" "<该臂独立金融PASS报告.md>" "${display_prefix}_reviewed"
"$display_py" "$display_line/tools/stage083_final_multilot_labels.py" --parent "${display_prefix}_reviewed" --output "${display_prefix}_reviewed_labels"
"$display_py" "$display_line/tools/stage067_current_trade_reset.py" --parent "${display_prefix}_reviewed_labels" --output "${display_prefix}_final"
```

两臂final均完成后：

```sh
"$display_py" "$display_line/tools/stage096_quarter_pair_overview.py" --enabled-source "$display_line/outputs/run_20261020_risk025_contract_weekly_v1" --disabled-source "$display_line/outputs/run_20261020_risk025_no_weekly_v1" --enabled-recap "$display_line/outputs/recap_20261020_risk025_contract_weekly_v1_final" --disabled-recap "$display_line/outputs/recap_20261020_risk025_no_weekly_v1_final" --output "$display_line/outputs/overview_20261020_risk025_pair_v1"

"$display_py" "$display_line/tools/stage097_validate_quarter_display.py" --enabled-source "$display_line/outputs/run_20261020_risk025_contract_weekly_v1" --disabled-source "$display_line/outputs/run_20261020_risk025_no_weekly_v1" --data-source "$display_line/outputs/run_20261019_contract_weekly_long_v1" --enabled-raw "$display_line/outputs/recap_20261020_risk025_contract_weekly_v1_raw" --disabled-raw "$display_line/outputs/recap_20261020_risk025_no_weekly_v1_raw" --enabled-fractional "$display_line/outputs/recap_20261020_risk025_contract_weekly_v1_fractional" --disabled-fractional "$display_line/outputs/recap_20261020_risk025_no_weekly_v1_fractional" --enabled-weekly "$display_line/outputs/recap_20261020_risk025_contract_weekly_v1_exact_weekly" --disabled-weekly "$display_line/outputs/recap_20261020_risk025_no_weekly_v1_exact_weekly" --enabled-final "$display_line/outputs/recap_20261020_risk025_contract_weekly_v1_final" --disabled-final "$display_line/outputs/recap_20261020_risk025_no_weekly_v1_final" --overview "$display_line/outputs/overview_20261020_risk025_pair_v1" --output "<全新Stage097_actual_pair_validation.json>"
```

097可分阶段只验源/已完成中间图；最终必须传完整两臂链路及overview。脚本通过不替代root浏览器default periods/filter/prev-next/linked zoom/current Reset与PNG可读性验收。关闭版金融features/audits空、JSON null和N/A维持；复盘可有纯市场周图，不能冒称策略查询过周provider。
