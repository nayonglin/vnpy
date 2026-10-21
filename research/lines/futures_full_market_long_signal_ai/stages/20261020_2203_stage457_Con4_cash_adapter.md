# Stage457：固定Con4增量四现金适配器（仅实现和合成验证）

- line_id：`futures_full_market_long_signal_ai`；时间：2026-10-20 22:03 CST。不是重要突破；未运行真实回测。
- 当前边界：仅新工具`stage457_con4_cash.py`、本输出目录及本唯一stage；不改旧代码、其他agent文件、LINE/registry、Git、生产、C9或原四账户。
- 当前研究仍为全市场98产品/95家族/六所独立long-only；A是accepted130/156/157自身四本，C是`COMMON52_PLUS_LAGGED_CON4_Z_RIDGE53`；protocol453 SHA `c82dfb499558b0ecc32e8f9654b3361f68741a74400c67507b1d01a69ca9e053`。

## 变更和冻结参数

新增457薄包装器及极小synthetic fixture；沿434的执行/导出结构，使用原157私有信号适配/自愿K边界和原131 unchanged kernel，完整原mothers构canonical。新增候选身份、456接口和精确root授权绑定；原157 CLI/authorize/baseline_references均不调用。accepted157自身四控制与453、263元数据逐项相等；不绑定旧155/131B。

新增策略参数=0；修改参数=0；删除参数=0。固定100万、0.25N止损、family风险0.0025、总风险0.02、margin0.25、buffer1.1、participation0.01、原base/stress、2020连续/2023冷启和原成本/退出。新fit=0，上限四个新候选账；不重跑原A。真实授权后原actions只遍历一遍、原native缓存只restore一次，SQL/API/新下载为0；bootstrap仅用原保存252日/2000次indices，不重生、不用epsilon修补。

经济门严格沿453嵌套452的exact157：四本收益>0且财富始终正；相对accepted157自身各账收益不低/DD不更深，primary2020stress收益严格更高/DD严格更浅及配对日log增长差CI95下端>0。Sharpe、逐年/年度结果仅披露，不引入旧HGB的Sharpe或至少4年硬门。两held的已知u-equal增量各>=0；无有效bounds的异动作unknown不能宣称held过门。现金nominal、金融未知、held未知及实际资格分层；production/increased betting/goal complete均False。候选summary使用原157字段`unknown_capacity_fills`，避免历史review别名问题。

## 验证与接口

先红：fixture在无457工具时明确`AssertionError: missing Stage457 Con4 cash adapter`；后绿：`.py311/bin/python research/lines/futures_full_market_long_signal_ai/outputs/stage457_Con4_cash/synthetic_fixture.py` exit0。覆盖合成parent/admission、正确四控制/错误旧控制拒绝、三个非primary允许相等、primary严格方向、1e-14负增量不容差、正财富、stale/执行未知分层、held零增量接受/未知阻断、4次合成callback及失败1次不重试。它未调用金融kernel，临时合成文件随fixture清理。两新文件AST parse及CLI `--help`均exit0；遵守root范围未跑旧suite。

456接口已与作者确认：`stage456_con4_fit_select_manifest_v1`/completed/candidate/protocol_sha256；inputs完整继承453.identity_reuse.inputs；artifacts消费choices_main/boundaries/held_diagnostic（choices_held由456披露）；changed_main_parent_choices>0且cash_eligible=True，否则零新账。root授权需`stage457_exact_root_authorization_v1`，精确source_bundle、263 refs、456 manifest、`model_selection_review_accepted=true`及独审receipt binding。

工具SHA `a9e262902ec5b997824f1c7485707b42f6645fb4635bb6e2ec042a51d8d5bc7b`（27145字节）；fixture SHA `434e855fb890fd1f1a450114538d94066a6ee4ba801afe5711fceabf1b150871`（5410字节）。详见本目录`implementation_receipt.json`。

未来CLI（本轮没有执行）：

```sh
.py311/bin/python research/lines/futures_full_market_long_signal_ai/tools/stage457_con4_cash.py --protocol research/lines/futures_full_market_long_signal_ai/outputs/stage453_Con4_fixed_protocol/protocol.json --protocol-sha256 c82dfb499558b0ecc32e8f9654b3361f68741a74400c67507b1d01a69ca9e053 --authorization /exact/root/auth.json --authorization-sha256 ROOT_AUTH_SHA --output /Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage457_Con4_cash/actual_run1
```

## 调研判断、结果和反思

调研沿447/448/449/453已核CFTC发布日历、原研究及GitHub downloader血缘；本轮仅代码落地，新网络=0。判断仍是：美国周频关系不能证明国内0.25N/自愿K/成本后的alpha；只能固定一次独立信息增量证伪，不应另扫lag/来源/窗口/方向救参。

新增/修改/删除回测结果均0；期末权益、总收益、最大回撤、Sharpe、总滑点、胜率=N/A，总交易次数=0。真实fit/cash/SQL/API/下载=0；旧母表/actions/native/金融结果未读。累计沿453仍460fit/250完成cash及1旧partial。工具可执行不代表获准执行；真实结果完成后仍必须由独立agent全面复核数据、逻辑、置信度和bug。

开始/结束反思：本轮按新收益调参过拟合=否，未读Y/价格/score/现金结果、未调参；同史反复择题的长期过拟合风险=是。继续价值=是，仅固定候选的一次必要执行验证；本轮实现和fixture完成后，等待source支持、456独审和root精确授权，不继续扩大工程或变体。
