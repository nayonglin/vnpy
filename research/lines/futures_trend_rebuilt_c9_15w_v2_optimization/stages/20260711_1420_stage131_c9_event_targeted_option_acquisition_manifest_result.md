# Stage131 当前 C9 真实事件定向期权采集清单终版

- line_id：`futures_trend_rebuilt_c9_15w_v2_optimization`
- 当前模式：`day`
- 记录时间：`2026-07-11 14:20 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `codex/stage130-option-probe`
- 阶段性质：Stage130 后的数据 acquisition manifest；不是策略候选
- 是否重要突破：是，但只突破“当前 C9 全量真实事件可形成闭合采集清单”，不代表期权策略有效
- 是否触发A/B：否；`ready_for_option_strategy_ab=false`

## 外部调研与判断

- 参考资料：TqSdk 官方 GitHub/API 文档、CME 保护性期货期权示例、Israelov 的 protective-put premium/timing drag 研究。
- 我的判断：先覆盖冻结 C9 的全部真实交易事件，比按 2022 亏损品种或结果标签下载更可审计、过拟合更低；历史 premium、流动性和可成交性没有拿到前，不能设计 strike/DTE/保护比例，更不能声称回撤会改善。

## 本次变更

- 新增脚本：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/tools/stage131_c9_event_targeted_option_acquisition_manifest.py`
- 新增测试：`tests/test_rebuilt_c9_v2_stage131_c9_event_targeted_option_acquisition_manifest.py`
- 新增预声明：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/stages/20260711_1308_stage131_c9_event_targeted_option_acquisition_manifest_predecl.md`
- 新增参数：冻结四源 SHA、`405/793/388/367/8148/2037` 基准计数、entry-risk 三层关联法、`long -> PUT / short -> CALL`、逐事件 `TqBacktest(entry_date) + query_options(expired=False)` 数据合同。
- 修改参数：无正式策略参数；review 后把 coverage 风险从成交价到止损的现金距离修正为 `entry_risk.risk_per_contract × lot volume`。
- 删除参数：删除旧的 `5/10` 自然日关联窗口；改为冻结曲线的下一交易日语义。
- 删除结果：旧的 fill-to-stop coverage 口径和无 detached manifest hash 的输出均废弃；无策略回测结果被删除。

## 数据与归因参数

- 数据区间：最早 entry `2018-01-15`，最晚 exit `2026-05-07`；覆盖全部冻结 Stage847 C9 closed lots，不只截取 2020+ 或 2022。
- 账户规模：不适用；本阶段不运行策略和账户回测。
- 成本口径：不适用；没有订单、成交、premium 或滑点计算。
- 样本过滤：无结果过滤；不读取 realized PnL、R、winner、MFE/MAE、2022 标签或资金曲线收益字段。
- 关联口径：`388/388` Open trade 全覆盖，`360` 条下一交易日同手数直接关联、`23` 条有中间 Close 的同日 retry 继承、`5` 条下一交易日唯一 volume mismatch。
- 风险口径：已有 `373` 条 `risk_amount` 与 `risk_per_contract × lot volume` 最大绝对误差 `1.1641532182693481e-10`；缺失 `32/32` 全部恢复，最小原风险金额 `200`。成交价到原止损的现金距离只作诊断。

## 结果

- 期末权益：不适用
- 总收益：不适用
- 最大回撤：不适用
- Sharpe：不适用
- 总滑点：不适用
- 总交易次数：`0`
- 胜率：不适用
- 其他关键指标：`405` lots、`238` 合约、`365` 唯一合约+入场日 query events、`332` 入场日、`19` 产品、`405` acquisition requirements；`13` 条入场成交价已跨原止损价，仍保留同源 `entry_risk.stop_price`，未反推。
- 完整性：四源 SHA 全匹配；event/lot/volume/original-risk reconciliation 错误均 `0`；结果标签持久化 `0`；网络、TqSdk import、订单 API、CTP、live 配置变更均 `0/false`。
- manifest：14 个 scope 文件 bytes/SHA 全闭合；manifest SHA256 `63184047a307e0e5e9ce1406fa8ddb614fff4635ad22885fd936d63dcfea9f1c`，detached checksum 精确匹配。
- 回归：Stage130+131 `.py311/bin/python -m unittest ...` 共 `21/21` 通过；`git diff --check` 通过。

## TDD 与废弃产物

- 按 RED/GREEN 修复：同日 retry 必须有中间 Close、结果标签白名单隔离、`query_options` 方法名、下一交易日而非自然日、source `usecols`、原风险金额口径、detached manifest checksum。
- 旧输出分别隔离在 `/var/tmp/vnpy_stage131_pre_retry_close_gate_20260711_1322`、`/var/tmp/vnpy_stage131_pre_outcome_sanitization_20260711_1327`、`/var/tmp/vnpy_stage131_pre_query_method_fix_20260711_1331`、`/var/tmp/vnpy_stage131_pre_trading_calendar_link_20260711_1340`、`/var/tmp/vnpy_stage131_pre_source_usecols_20260711_1346`、`/var/tmp/vnpy_stage131_pre_final_20260711_140610`、`/var/tmp/vnpy_stage131_pre_doc_p2_fix_20260711_141352`；终版不引用这些产物。

## 独立审查

- 独立 agent `Dirac` 首轮终审：`P0=0/P1=0/P2=1`，唯一 P2 为预声明 `load_frozen_sources` 返回类型少写 source_inventory。
- 修正文档并因 lineage 变化整体重跑后，增量终审为 `P0=0/P1=0/P2=0`，批准置信度 `99.9%`。
- 批准边界：只批准 `ready_for_metadata_batches=true`；明确不批准 `ready_for_option_strategy_ab`。

## 输出文件

- report：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage131_c9_event_targeted_option_acquisition_manifest/rebuilt_c9_v2_stage131_c9_event_targeted_option_acquisition_manifest_report_stage131_c9_event_targeted_option_acquisition_manifest_v1.md`
- query events：同目录 `*_query_events_*.csv`
- requirements：同目录 `*_acquisition_requirements_*.csv`
- decision/lineage：同目录 `*_decision_*.json`、`*_lineage_*.json`
- manifest/checksum：同目录 `*_manifest_*.csv`、`*_manifest_sha256_*.txt`

## 结论

- 本阶段结论：`stage131_event_targeted_option_acquisition_manifest_ready_for_metadata_batches`。
- 是否进入下一步：是，但只进入 Stage132 冻结 metadata 分批获取与覆盖审计。
- 下一步：逐事件独立历史上下文、原子写入、断点续跑、每请求唯一终态；保存 untouched 与 normalized metadata。覆盖门通过前禁止 premium 保护层 A/B、IV/skew 规则或参数扫描。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：覆盖冻结基准全部事件，不读取结果标签，不按年份、盈利、品种或 option 返回结果删样本；修复均来自数据恒等式、接口语义和独立 review，而不是救收益。

## 继续价值反思

- 运行前判断：有。
- 运行后判断：有，但边界严格。
- 原因：365 个请求已从模糊数据需求变为可复核清单；继续价值仅在数据覆盖与质量审计，尚没有任何策略晋级价值。

## 合入建议

- 是否更新本线 `LINE.md`：是。
- 是否更新 `research/registry.md`：是，这是数据获取路线的重要里程碑。
- 是否追加根目录 `memory.md/back_log.md`：只追加 `back_log.md`；不追加 `memory.md`。
