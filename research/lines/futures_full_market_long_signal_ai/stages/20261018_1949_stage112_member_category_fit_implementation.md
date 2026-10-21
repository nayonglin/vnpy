# Stage112 CONTROL/NFC固定54项信息对照：实现冻结，0fit

- line_id：futures_full_market_long_signal_ai；2026-10-18 19:49 CST；重要突破：否。唯一目标仍是全市场long-only质量、窄损和成本后收益更高/回撤更低；正式策略、CTP不在范围。
- 本阶段0actual fit/SQL/cash/label/download，累计沿110为361fit/94现金。只实现冻结110+implementation_clarifications，不读109新数值、旧模型或旧分数，不重跑旧金融/旧suite。

## 判断和模型合同

类别数量与总OI、OHLC不同，存在新增可观测信息的可检验问题；这不是方向保证、因果溢价或收益承诺。仅采用110已收敛的gross分母，107 own-ratio未实测且不再待测。不在本实现扩充网上获取、来源资格或正式ABC晋级。

新脚本`tools/stage112_member_category_fit.py`直接引用071接受的成熟切片、并发唯一性/u等质量/mean1权重、有限值均值总体std、缺失投影、Ridge和原ready20动作；结构沿086接受的54项信息对照。源码与validator均为新NFC语义，未修改旧源或冒称same_epoch OI。

两臂CONTROL/NFC、两cutoff 2020/2023、main/holdout_0/holdout_1，共最多12fit。54项为26 COMMON+26共同missing+shared external_missing+scalar。CONTROL末槽0；NFC为本fold成熟训练有限scalar加权标准化，missing标准化0；两臂共同背景、外部missing、训练ID、weights和scaler完全一致。COMMON保留原2N量纲及071定义。

仅自身NARROW closed、u<cutoff且非空known<cutoff训练；held按sha256(family)%2整family排除标签、只预测对应held分区，统计完全训练内。外部可得性不筛训练、不筛预测、不筛动作。main与两held合计各arm均保完整161014事件，共644056分数，notready/noref/unknown都保留；held只作诊断，不能进入现金。

在任何fit之前，六个cell全部检查本fold成熟训练有效scalar的正加权变异；常量用精确相等判定var0，不加epsilon或近零阈值。任一不支持，整包status=`unsupported_scalar_support`、0fit、cash_eligible=false；报告有限/非零/年月/family及加权统计。有限值存在不等于样本充分，不能只训SHFE或移动held/cutoff凑门。

正常输出12个joblib/portable模型、各54coef+intercept/55维正规方程、六套scaler、训练ID/weights/原目标、normalized输入与预测身份，完整main/held/合并分数、逐u和年度held诊断、全状态机会统计、终态与manifest。held诊断为NFC−CONTROL的共同ready/closed/known<=end机会，每u已知机会先均值再u等权；取消不填0，未知动作差异和所有状态计数独立保留。没有held现金或未知收益0假设。

## 接口与停止

正常manifest schema=`stage112_member_category_fit_v1`，status completed、cash_eligible=true、actual_fit_calls_attempted/completed=12、prediction_rows=644056、native_source_queries/cash_replays=0。绑定110/clarification、原COMMON与NARROW refs、111 projection/manifest/terminal、root源接受与源码。main分数为原ID7+policy NARROW/arm CONTROL或NFC/cutoff/history_ready20/selected/score/scope main/external_missing；无源方向/规模/可得性动作门。

113只消费正常完整main与held报告绑定，按原070八现金执行，不能让held进入现金，也不能因held负而选择性删账户。任一执行异常保留现场、failed终态、无自动修复重启；支持门失败是明确科学停止，不伪造正常fit。最终CLI为最小四参数，root另签exactauth后唯一执行。

## 最小新增验证

新增两项fixture针对真正的新接线：held标签和未来source不能进入fold统计/训练，缺失预测保留且两臂同53背景；以及任一六cell常量导致整包停止。未重复旧成熟、报价、现金或Ridge suite。111/112最终合计8 tests、0.788s、OK，命令与精确SHA见`outputs/stage112_member_category_fit/implementation_receipt.json`；本fixture没有模型fit，更无真实输入读取。

新增/修改/删除交易参数均0；模型/scalar/分母/lag/54维/alpha1/窗口/held/目标/stop/风险/费用均沿110。新增/修改/删除回测结果均无；权益、收益、DD、Sharpe、滑点、交易数、胜率均N/A。实现冻结只证明可检查代码就绪，不能计为收益进步或研究目标完成。

## 反思

按本包结果选参：否，0actual且科学先冻结。历史多轮研究的过拟合与来源覆盖偏差风险：是，已见registry及以前阶段上下文，不称未见OOS。继续价值：有，但只限这个新增类别信息、固定lag/Ridge/NARROW的有限反证；六cell信息支持失败或后续经济门失败就停止，不换分母、方向、模型、规模门、stop或风险救参。正结果也只能进后续严格研究，不能正式晋级或加注。
