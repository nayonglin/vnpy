# Stage515：固定续持模型 CODE READY，尚未实际训练

时间：2026-10-21 03:12 CST；研究线 `futures_full_market_long_signal_ai`。先读取registry、LINE最新513、508科学建议与511小manifest/代码schema；不读四张511历史payload或旧source，不改LINE/registry/root总账。

开始反思：长期重复使用同一历史择题，过拟合风险**是且高**；本次收益后调参**否**。继续固定单一步续持实验**有条件价值是**：对象是已持仓继续原policy相对下一合法open退出，不是原入场模型的重新命名；每步负预测同时可能截断右尾，必须真实资金验证。

## 冻结实现

严格遵循514 SHA `d90a160e62ae460a16dabb867e2a7495aceda59ebbd6b5e7487d5ee1084bb32a`：2cutoff×main/held0/held1六头；sumw1/ridge1/intercept不罚；6当时X+6missingflag、train-only weighted observed mean/std(ddof0)、缺失填mean即z0。R0固定旧u的0.25N；SL0/ownlow20/uanchor/source生命周期∩K/原候选入场不变。剩余时间使用两个真实target日期早者减当前日历日，不把cachelen或sample尾当到期。

Y仅两未来SELL净值差/R0，BUY沉没抵消，fill已含滑点不二扣。两actual availability严格早于cutoff，K事前cohort严格已过；训练要求stress入场BUY+SELLestimate在D已支持，不要求base支持。所有未知/未入场/force/stale由完整1552456动作cohort单列，不把未知补0。known训练集按日期/日期内族/族日所有候选state均分质量，held本族排除且scaler/weights各自重算；不另X去重。

四表一次joint stream，保存新compact raw_state/X/quotedcomponents/两available clocks/phase/codes及identity，以供独审不二扫旧表。六头fit前逐个写training indices/X/Y/w与scaler，后写portable、正规方程、df。预测按当前t_date选择2020/2023头，pre2020无头hold，=0/nonfinite hold。原A157 OWN `VOLUNTARY_RESELECT` entrychoices全保留，按每path首次负预测提出退出；这只是单位诊断，不是资金收益。517另推进实际账户重投资/占族/预算。

## 新toy与代码事实

8项独立新synthetics PASS（0.202秒）：因果特征真实日期/缺失、两SELL成本与unknown、日期族重叠权重、strict cutoff+held、scaler缺失不泄漏、ridge正规方程/intercept、按当前日期换头与首次negative、四表tiny联接/未知cohort/源各一次。初始模块不存在的RED已保留；无全仓库旧测试/历史回测重跑。TDD/verification技能只用于本隔离工具的真实新fixture，不制造旧策略验收。

最终代码SHA `5fe49e2d592bbb2fbbb19c8ac9d8ad4b036794ff230db2053c89a3a5592733a2`，tests SHA `a481fa24ec7de31898363dd735405b97bfa7e30fa575e4e66c433f0986970f5f`；code_ready在 `outputs/stage515_continuation_fit/code_ready.json`。只允许root读取516最终静审后，以exact514SHA+ordered source bindings+fresh output授权唯一actual；本stage不自行启动。handoff为portable_models_binding、held_diagnostic_binding(summary)及protocol_sha256，无manifest循环绑定。

新增研究参数：6持仓X/6missingflag、固定续持ridge1（不是旧正式参数修改）；修改/删除旧策略参数0。新期末权益、总收益、最大回撤、Sharpe、滑点、交易次数、胜率均N/A。历史fit/cash/SQL/native/旧sourcepayload均0；累计505fit/274完成cash+1旧partial不变。正式/生产/CTP/邮件/任务/Git未动。

结束反思：收益后救参过拟合**否**，同史长期择题风险**是且高**；继续root授权一次固定模型actual **有条件价值是**，放大投注**否**。全市场高质量long/更高收益低回撤/窄损加注完整目标active未完成；历史研究不等今天日线。

## 实际前重要诊断修订

root指出截至END未提出退出但A尚未终止或terminal quote未知，不能用未来终端增量0冒充已知。已在任何actual之前修正：仅A原policy已知闭合且该成本SELL已知、或者已知未参与取消才赋确切0；open/intent/entryunknown/quoteunknown继续unknown。单列截至END请求未变化，不以它代替终端metric；新selected_action_anchors小JSON保留来源状态。3张Achoice各一次移到联流前，不增加大源读取。8toy补充此边界并PASS（0.203秒）。最终代码SHA `13a67a2798bddd75e86c03461b122b1d241fc959a60b7a56ae41892d0d49293a`，tests SHA `8444c3ad9dceb77120615fc4b1971936543f3e312ba0ffd5abaea4f69dbfd98f`；覆盖上文旧SHA，模型/X/Y/权重/风险科学口径没有改变。
