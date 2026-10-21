# Stage339：compact状态到新u的薄增量适配器

- line_id：`futures_full_market_long_signal_ai`；2026-10-20 03:33 CST。
- 性质：待用实现，非重要收益突破、非正式A/B/C。先读registry/333scope/334与既有320/325/330必要小源码；官方/维护者调研沿已接受335，不再扩搜。
- 本轮0actual：未读331真实744状态或9520inventory内容、未读新行情/旧价格cache/原econ，0接收API/SQL/fit/cash/资金state初始化；无CLI或调度入口。

## 实现与接口

新增[339适配器](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/tools/stage339_incremental_snapshot.py)及[唯一新tiny组](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/tools/test_stage339_incremental_snapshot.py)。未改320/321/322/325、作者接收器、模型、旧数据、LINE/registry或其他研究线。

纯API为`build_incremental_snapshot(warmup_states, epoch_inventory, normalized_rows, *, dates, previous_u_date, u_date, products, economics, calendar_confirmation, normalization_receipt, source_receipt, D_context=None, clock=None, core)`。root wrapper可从331已接受warmup_evidence的`epoch→final_state`与全inventory一流构造输入；`core`必须注入同一`caller._components().core`，避免WilderState跨模块类身份不同。函数不自行开文件、查库或加载econ；必要原8MB经济参数缺lookup仍由root按授权最多一次提供RAM对象。

返回与330/325相容的snapshot：完整products、series_by_epoch、warmup_state、market、dates/u/D_context/economics、source_receipt以及clock。固定`development_only=True/frozen_at=None`，只能交原325的observe_only；不调用322。root另行加载原纯52 main2023 model/scaler，并调用原`process_snapshot`，本适配器没有另一套特征、标准化、打分或选择公式。

## 数据接受边界：不把下载成功当canonical

336已明确本轮raw只保留provider单位，`canonical_model_rows=[]`，不能直接喂模型。因此339要求root/337提供**显式已接受canonical overlay**及`normalization_receipt={status:completed, canonical_rows_accepted:true,...}`。它不是重新资格化旧大源的框架，而是防止把接收成功偷换为模型输入合格的最小接口。

每行必须有`contract_epoch_id/trade_date/canonical_values`，其中canonical_values含OHLCV及close_oi；另须明确：identity_state=`known_explicit`、date_mapping_state为`operational_midnight_label`或`session_mapped`、units_status=`canonical_normalized`、canonical_quality_status=`accepted`、model_input_eligible为真以及source_receipt。没有默认accepted或默认0。单位、日期、身份、质量或来源未知均逐行保留reasons，不append；closeOI明确为None仍保持原OI unknown语义，不填0。已声明accepted但OHLCV不通过原004 candidate检查的行也不消费。

已接受同epoch/date重复直接报错，不按商品名dict覆盖。<=原checkpoint日的35bar重叠、>目标u的未来行不消费；不会借receiver原始窗口偷偷重播历史或播种N。新catalog产品超出原98只报unsupported，不加入母域或推断历史别名；已明确真实YYYYMM身份的新月份，才允许从新首次合格u开始，经济元数据未知照旧不合格。

## 因果续接与缺失

- 有精确前u状态：`WilderState.from_dict`续原递推，不从21条重种N，不回放已接受旧历史。
- 已知epoch在inventory证明前u无bar：从空WilderState append新合格u，run从1开始；不制造前u报价。新的epoch同样从新首次合格u开始，暖机不足仍不足。
- 前u状态存在但当前无合格新行：保存旧state供未来gap识别，传320时转为`to_series()`数组。不能把旧WilderState当作当前u快照，也不能carry旧值当current。其后恢复时，由已更新inventory的gap事实从空state起，不跨未知日连续递推。
- `calendar_confirmation`须显式确认目标date/index/proof，并与稳定dates坐标一致；D_context独立接受原320的严格next-source-index校验，默认未确认，不因旧calendar恰含未来日期或有未来bar而升级D。
- clock只透传root已核335语义，默认source_completed_at/D_open_at均None；不推断完成或把实收时刻写成源完成。T0仍None，10月19日晚取仍development/history。

额外返回`_row_dispositions`、`_continuation_evidence`、`_inventory`与incremental_audit供一次实际独审。continuation记录before/新bar来源/final_state；inventory完整保留旧epoch及原rows计数，仅另计canonical_rows_appended，last_index/date与has_current_bar变为最新已消费canonical checkpoint坐标，不冒称收到的所有raw行数。原98产品95family必须完整，包括DCE.S无观测母行。

## 唯一新组验证与故障披露

采用test-driven-development：先RED1（适配器缺失）。首轮实现触发原004 candidate的`KeyError quality_status`，按systematic-debugging核明339虽验证accepted却遗漏传字段，只在原边界补显式quality_status，未改原核；同组GREEN1/.247秒。随后在**同组**加入已持久化第二新日子例，最终GREEN1/.355秒；自有两文件py_compile exit0。未跑旧三个组件组、旧suite或真实金融。

新组使用真320/325及其原纯helper、真实321 journal，只有市场/经济输入与模型系数是synthetic；不mock特征或Wilder数学。手算检查N从2按新TR6续为2.2，再按TR3续为2.24；gap/新epoch均run1且N为None，未知单位和缺当前行保持无current，未知后恢复不假连续，旧状态/输入不可变，98母域及DCE.S保留，全部observe资金调用为0、NaN由原caller转null。最终结果没有新金融指标，权益/收益/DD/Sharpe/滑点/交易/胜率N/A。

## 冻结与下一步

| 文件 | bytes | SHA256 |
|---|---:|---|
| stage339_incremental_snapshot.py | 11940 | `25ac52ec822abb70249830bf0cbf2e040803f2d3972c9beabfdc3c4a13cfb89b` |
| test_stage339_incremental_snapshot.py | 7930 | `8efd557fe3856ea730db5701bf71fdd4d0c310594951969573c3af8c93260590` |
| [source_bundle.json](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage339_incremental_snapshot/implementation/source_bundle.json) | 2190 | `23149bbd1c18e242f7bfa0cff1cfc3840e6b346c2974141207eeaae1189ef6af` |
| [fixture_terminal.json](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage339_incremental_snapshot/implementation/fixture_terminal.json) | 1295 | `415a71070adeb54200fe8e02c971b04f636535ea16080443f2b8bd5b170f4a9b` |

已直接交source_design供340仅新delta独审，不要求复跑tiny；实际新u必须先337/root接受receiver数据与canonical overlay，再由root另授权wrapper唯一运行。本阶段到待用source为止，不强行用units_unverified数据跑观察，更不初始化账户。

过拟合反思：开始/结束均为本次不新增收益导向调参；原纯52与政策冻结，不证明AI优越或未来alpha。继续价值：有，避免新接收每次重载110MB、错误重种N或carry；数据未获接受时只交待用实现即足够，不为推进而降格输入。累计fit/cash不变，用户完整目标仍未达到。
