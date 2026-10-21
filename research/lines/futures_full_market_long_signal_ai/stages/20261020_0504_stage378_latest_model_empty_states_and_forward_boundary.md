# Stage378 新模型独立空态完成，等待真实新输入

- line_id：`futures_full_market_long_signal_ai`；记录：2026-10-20 05:04 CST。独立全市场做多研究，非重要收益突破、非正式C9晋级或生产动作。
- 本轮主进展：373已单次训练latest模型，374独审、375独立T1已签；376接最薄新版本接口，377独审后本阶段创建独立空模拟态。完整高收益/低回撤/高质量做多/极窄止损与加注目标仍active、未达成。

## 调研判断与本次改动

[时间顺序评价文档](https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.TimeSeriesSplit.html)、[维护者交叉验证说明](https://github.com/scikit-learn/scikit-learn/blob/main/doc/modules/cross_validation.rst)和[Freqtrade维护者前视偏差说明](https://github.com/freqtrade/freqtrade/blob/develop/docs/lookahead-analysis.md)支持分开训练资料和真正未见评价。我的判断：一次固定规则的成熟训练更新值得前瞻验证；接口接通、样本更多及算术正确，都不是盈利或稳定泛化的证据。此处没有照搬其反复历史回测命令。

[375训练完整报告](20261020_0453_stage375_latest_mature_training_and_freeze_decision.md)：成熟动作445,475→788,336，新增342,861，日期3,139→4,054、品种族77→94；1fit/40.580642秒、0旧预测/现金。动作重叠不等于独立交易。原52列、目标、成熟/权重/scaler规则、Ridge alpha1不改；最大u15日/known16日，未补造19/20标签。当前累计454完整fit/246cash，另1旧金融不完整尝试。

新增376工具/唯一组合fixture及本地两个新空态；没有删除代码或旧结果。新增的是profile/来源/兼容元数据，科学参数不变：base/stress各100万，start/next_u=5290/u20，NARROW初损0.25N、单family风险0.25%、总风险2%、margin cap25%、buffer1.10，原费用/滑点/退出/F0继续保持。未提高投注。

## 真实身份与兼容边界

原320推断及156 fold校验固定2023截止槽，不能原样接375 cutoff2026-10-20。376只派生明确的metadata engine_view：数值、列序及参数逐项不变，旧API cutoff槽标为engine_fold_tag；另存真实cutoff、新模型/scaler文件SHA、T1和兼容解释。325 identity绑定完整派生对象，四源/hash guard不放松，原320/325/156不改；真实375文件字节不动。输出旧fold标签不等于2023训练事实。

新模型T1仍为北京时间04:48:38.399842；使用单独执行journal，未借375冻结journal或370旧账户。新base/stress ID均为latest前缀，状态caller_policy绑定新view hash；旧359 T0与370原2023各100万空态均不变。

## 一次前置失败、一次成功初始化

第一次root调用05:01:03在账户创建前失败，0.047504秒：376把datetime传给只收字符串的368._time，datetime.replace因此TypeError。原actual_run1不存在，0new_state/0calendar/0评分/0资金；原终态和源/fixture均完整保留在失败快照。该失败不计金融partial或模型fit。

只在376调用处补`.isoformat()`一处，未改旧helper或任何数值规则。同一fixture补公开入口，RED复现原错、GREEN1方法0.369秒；377独跑同一小组0.365秒并核有限差异。原独审GO漏过公开入口的覆盖缺口已承认、原passed收据未覆盖。没有旧suite、训练重读或金融重跑。

root随后明确另调用一次，exit0/0.233115秒；总root调用2次、前置失败1次、**实际初始化1次/新空态2个**，无自动重试。真实321 `paper_state_initialized`：

`T_init=2026-10-19T21:03:07.185431+00:00`，即北京时间20日05:03:07.185431。

当前`initialized_inactive`，两态awaiting_u，pending/positions/fills/closed均空、无资金proposal。它们的初资不是回测期末权益。本阶段fit/cash/真实推断/seal/D/API/SQL均0；本轮新增权益、收益、最大回撤、Sharpe、总滑点、交易次数和胜率全部N/A。

377最后只读小metadata/state/journal，独核真实T1<T_init<15:15前置期限、完整view/profile/原材料绑定、独立空态及genesis canonical关系，P0/P1/P2均0。仍需稍后实际source_completed_at才能判定初始化的前瞻资格，不能用初始化成功代替。

## 输出与实际未完成项

- [实际初始化结果](../outputs/stage378_latest_model_initialization_decision/actual_run1/result.json)；[完整初态envelope](../outputs/stage378_latest_model_initialization_decision/actual_run1/initialization_envelope.json)，25,851B/SHA `62e4c0878c04ee2677dfd63f9489b74785a995aabaa25785bc13c432706d48e9`。
- [实际独审](../outputs/stage377_latest_model_forward_review/actual_initialization_review_receipt.json)，5,096B/SHA `47e96e50a89372446debbfb5f41c44b1dde1a578dfa4c28d75d5e191b0639a0c`；[入口修复独审](../outputs/stage377_latest_model_forward_review/public_entry_repair_review_receipt.json)。
- [小源码保存清单](../outputs/stage378_latest_model_initialization_decision/preservation_manifest.json)，保存新工具/fixture副本及旧359/370/375、实际状态和准备材料的精确引用；不复制大行情/训练数据，不声称独立运行时或生产发布。
- [裁决](../outputs/stage378_latest_model_initialization_decision/decision.json)，SHA `b30887d3b44faec37e17581447602b448abbb1f4eef5eb81641ca22c2ba401ba`；[唯一下一范围](../outputs/stage378_latest_model_initialization_decision/next_scope.json)，SHA `3ba0ae14bc15df7dfcac8f43a2c4d87d113bd6773045bfbdb4b8899ef81204db`。

当前future预测0，`actual_compact_restore_ready=False`。376只有接收同一已验收内存composed的接口；357未直接保存完整composed，因此今天实际361产物出来后还需最小纯恢复适配，以及旧370到376的自身context绑定。不能据合成fixture称真实端到端已跑通。

下一步维持原360：20日15:15后且21:00前仅一次874×3日线批次→362独审→363接受；此前不轮询形成中数据、不再做旧史回测或重训。实物到齐后从final warmup/inventory/canonical lineage和原完整calendar/products/economics/clock恢复一次共同视图，不再次append u20或另抓候选行情。

两个版本必须分别核模型freeze及自身T_init早于实际source完成，并取得早于完整prescore eligible-or-unresolved执行域Dopen的新完整资金proposal真实seal。旧未出资seal不可用；unknown/late留gap，不跳u重置。当前仅u20/D21，没有永久日更或调度就绪声明。

## 开始与结束反思

- 新增按收益选参过拟合：开始/结束均否；本轮仅同规则训练更新与必要接口修复。历史多轮择题及增加一个估计版本的自由度仍在，未消除。
- 继续价值：开始/结束均是；现有新模型和独立空态可支持真实新数据对照。继续旧金融重跑或无实物的接线工程没有价值；待新日线实物后再推进。
- 算术/身份与空态置信度高；盈利、跨周期、真实成交、极窄损与加注资格没有新证据。完整目标active，不改正式C9、生产、CTP、订单、邮件、launchd、分支/commit/push；只更新本线LINE/registry，不追加根总账。
