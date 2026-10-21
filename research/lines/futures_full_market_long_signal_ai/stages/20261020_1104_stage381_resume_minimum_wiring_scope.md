# Stage381 恢复推进：修正过宽的收盘前接线禁令

- line_id：`futures_full_market_long_signal_ai`；2026-10-20 11:04 CST；非重要收益突破、非正式策略晋级。用户恢复持续目标，goal工具真实返回active；此前blocked历史保留，新的阻塞审计重新开始。
- 前一turn为no progress并满足旧3轮阻塞阈值；本次实查UTC03:02:15/北京时间11:02:15，仍未到15:15。没有启动采集或轮询形成中日线。
- 本次识别到**真实可做的剩余依赖**：370/378空态和357固定持久化定义已经存在。此前把所有接线都推迟到361产物之后，范围收得过紧；这不应继续充当整个目标无事可做的理由。现在只补这两个必要薄桥，不将工程正确当盈利进展。

## 调研与独立读前判断

实读370 manifest/378结果、339全构造过程、360固定计划及357写盘定义。383独立读前确认：旧baseline只缺envelope schema适配；完整357 input_snapshot provenance可从原321对象恢复，warmup/inventory、日期/98域/完整economics、D_context与clock都有明确来源。原357未保存完整内存composed，但并非恢复界面无从定义。

[Freqtrade维护者前视偏差说明](https://github.com/freqtrade/freqtrade/blob/develop/docs/lookahead-analysis.md)区分完整历史计算与当时可得输入，也提示检查只对覆盖路径有效。本次判断：保持同一因果输入与模型独立状态需要先完成真实读取/恢复入口；不运行其重复历史回测命令、不新增alpha假说或模型。

## 新范围与不变内容

[固定scope](../outputs/stage381_resume_shared_input_wiring_scope/scope.json)：4174B/SHA `793e44a108da1ba442aa4fa14892604aec8b03ed65fe3f0366fb3dfe10d1b587`，是对378/380“收盘前不做任何接线”的明确有限修正，不覆盖旧证据。

1. 382读取原370 model/scaler/T0/T_init/state/journal，转为376 baseline context；原accountID、policyhash、事件与账本保留。latest直接读取原378。不得new_state、初始化、写原状态或append journal。
2. 382按已存在357/339定义从final warmup/inventory恢复同core状态和SnapshotMarket，完整原calendar/products/331+344 economics/provenance/clock保持。不得再次append u20、读raw874或原生缓存。重建observations/raw26与保存357观察核对，不评分；保持development_only=True。actual361值尚不存在，实际恢复和接受仍待新日线实物。
3. 一个必要新组合fixture覆盖公开读取入口与不doubleappend，383独立源审/同一fixture。384只做一次真实双context小读取证据，0新账户/append/推断；不扩通用系统或另建审批层。

训练、标签、风险成本、窄损、K/退出、新旧模型版本与原359/370/375/376/378全部不变。原360仍仅20日15:15—21:00一个874×3日线批次、最多1API/不重试，随后362独审/363接受。没有调度、订单或生产权限。

本阶段新fit/cash/账户/行情API/SQL/旧价格或训练实体读均0，科学参数和回测结果新增/修改/删除0；所有新资金指标N/A。开始过拟合：新增按收益调参否、历史择题风险仍在；继续价值：是，这两项是实际前瞻资金对照的未完依赖，有实物/定义可用。接口完成也不满足高收益/低回撤/高质量泛化/极窄损加注目标，goal不能complete。

[恢复状态](../outputs/stage381_resume_shared_input_wiring_scope/resume_status.json)保留active和新审计计数0；不更改旧380 blocked返回，不把过去的3轮沿用为恢复后的3轮。只更新本线记录，不追加根总账或修改正式版。
