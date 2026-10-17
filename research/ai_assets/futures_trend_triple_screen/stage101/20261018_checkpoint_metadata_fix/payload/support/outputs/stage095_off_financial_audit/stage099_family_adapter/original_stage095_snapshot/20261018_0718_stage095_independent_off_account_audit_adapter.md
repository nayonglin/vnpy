# Stage095：A_OFF / B_OFF 独立经济审计薄适配

- 记录时间：2026-10-18 07:18:04 +0800。
- line_id：`futures_trend_triple_screen`。这是审计准备，不是重要 alpha 突破，也没有新金融结果。
- 本次仅新增独立审计入口及本目录文件；未改065/084、035/028、071/087或其他冻结来源，未改LINE/registry。

## 判断与范围

本次不构成调参过拟合：没有策略参数、样本窗口、模型、仓位或成本变化。继续有价值：原始checkpoint/seal证明身份与文件闭合，仍不能代替逐实际fill现金、库存、成本和完整日历的独立复算。本次调研仅核本线088库存、原001 A0、030/033/038审计和冻结065/084真实schema；按root边界不联网、不重扫旧suite，不把外部时间切分资料当alpha证据。

本审者没有实现065账户checkpoint/084runner或035/028策略，能够独立审会计。本审者实现过071/087，因此这两条来源资格只继承独立078/081/094，绝不在095自签数据资格通过。

## 可执行入口与输入边界

入口：`/Users/mac/Desktop/fian/research/lines/futures_trend_triple_screen/tools/stage095_independent_off_account_review.py`。

```sh
.py311/bin/python research/lines/futures_trend_triple_screen/tools/stage095_independent_off_account_review.py --schema-check
.py311/bin/python research/lines/futures_trend_triple_screen/tools/stage095_independent_off_account_review.py --audit --arm A_OFF --completion-evidence /ABS/root_actual_terminal.json --completion-evidence-sha256 ROOT_SHA
```

B_OFF仅替换arm。同臂真实terminal后即可独立审计，不必等另一臂。CLI导入和schema-check只有标准库；必须先通过root实际工具终态记录及其外部SHA才打开指定账户目录，再加入冻结数值栈。无engine/strategy构造，无模型加载、预测、训练，无行情/DB重载，无网络或金融重放。

root输入schema为`stage095_off_actual_completion_v1`。精确字段见本输出目录两份`*_completion_input_TEMPLATE_NOT_TERMINAL.json`；它们的`actual_terminal_observed=false`，不是终态、不是执行授权，不能通过真实审计。root需填真实session/chunk、exit0、run_id、确切owner/export路径、runner与独立checkpoint writer身份、summary/raw/manifest/seal/sealreceipt/context六个SHA。owner仅接受固定`outputs/stage065_pairwise_off_account/{A_OFF,B_OFF}`的attempt1；合法纯导出位置可以是本臂`exports/export_NNN`。

解包前复用冻结065实际ownership/context/preflight/source快照/manifest/seal门，再使用033仅账户数据类型白名单unpickler。非fixture、1641日、2020-01-02至2026-10-14、15万、真实preflight/readiness的document/path/SHA/source/data绑定、writer≠runner均核对。只核已消费来源身份，不重新资格全市场分钟或本审者自己的数据源码。

## 经济复算与最少适配

1. 原030的逐fill成本与现金、稀疏库存至逐日mark/equity、日净值/费用/交易数、完整1641日、Sharpe/DD/保证金统计照原算法。成本只按唯一真实trade_id扣一次；若原commission为0如实保留，不构造成本稳健性通过。033复用原始positions一次扫描，不再解读第二套行情。
2. 所有原始frame、capture派生clock/usage及实际导出CSV按同冻结pandas序列化SHA对应；原始TradeData独立身份审计仍用033。另比真实frame fill与clock的价格、数量、方向、offset、交易日/合约，不只信seal/summary。实际母单retry要求同合约同日严格早于retry的真实parent；换月要求真实旧合约close先于新合约open；末日尚未平的母单全部排除胜率分母，仍保留未平MTM于权益恒等式。
3. A_OFF必须是exact native类、`ordered=None`；不得出现B的TS导出。母单算法提取原001已接受A0标量块，不套B候选字段；在该块之外核真实parent时间与换月close lineage。
4. B_OFF owner仍为B_OFF，producer明确B_TS。038原generic/OI/candidate映射、T/S/q/风险/保证金与保守gross原a前缀算术保留；只把预算校验的一处正rank门改为`rank==0`，仍按`(0,原serial)`检查gross顺序。035的`b_ts_final_budget_original_rank=0`是真实pairwise rank；pending `rank=1,2,3...`只是原product插入顺序ordinal，绝不写回AIrank。另将030 ordered证据中一处`setup_day<signal_day`按已冻结035合法同收盘准备改为`<=`，weekly_asof仍严格早于signal。
5. 共同八OFF键、实际runtime None、rank/score为0、tilt与AI rank保护关闭、完整参考settings/parameters除八键及空信号路径归一化外完全一致；月AI池仍保留。参考仅读取SHA绑定的小settings/parameters文件，绝不读取旧账户曲线。
6. 日级原报告保证金乘数1.10保持；额外1.65仅诊断，不替换七门，不声称分钟组合峰值或fill时重预算硬上限。

每臂接受收据为`outputs/stage095_off_financial_audit/ARM/RUN_ID/account_checks.json`。任何复算失败保留`audit_failure.json`，不写accepted。参数、回测结果新增/修改/删除均为无；期末权益、总收益、DD、Sharpe、滑点、成交数及胜率当前均N/A，未读取账户。

## 验证与当前状态

最终source的py_compile无诊断，`--schema-check`真实exit0，检查fixture/live/wrong_arm/tiny四个拒绝边界，并静态compile三段将实际执行的源投影。均仅stdlib，无账户/PnL打开、无engine/模型/网络。详见`static_verification.json`；开发中两次schema执行均非金融，第一次之后仅对齐真实084 readiness字段、raw frame↔clock数值和适配段静态编译。没有镜像算法unit suite，没有旧suite或全市场重复测试。

095目前**没有独立金融通过结论**；对数学的最终证据必须是root各臂真实终态后，各完整账本独立一次复算。若出现065/084实质金融问题，只报告完整阻塞清单，不由审者修改源或回放。

两臂均accepted后，以下入口才可生成四行对照与原001七门：

```sh
.py311/bin/python research/lines/futures_trend_triple_screen/tools/stage095_independent_off_account_review.py --compare --account-review /ABS/A/account_checks.json /ABS/B/account_checks.json --account-review-sha256 A_SHA B_SHA
```

四行固定为：A0受限fixed-model反事实、原B失败N/A、A_OFF、B_OFF；同时列B_OFF对受限A0的收益/DD语境。单赢较弱A_OFF不等于达成原目标；固定2020—2026、收益更高且DD更低的目标没有降低。`original_goal_achieved=false`、不得promotion；后续OOS/成本压力/多周期/未见样本资格仍未建立。

## 源与交付

- 审计源SHA256：`796aaef7994018196deb4799132a0cd288c027516f21ce672646c880d05990dd`；bytes：`37776`。
- 模板、helper/source pin、三处适配源SHA与实际有限验证：本Stage095输出目录。
- TODO仅为等待root真实A_OFF/B_OFF终态及确切输入SHA，再执行各臂一次审计；本阶段不替root签终态或写engine response。
