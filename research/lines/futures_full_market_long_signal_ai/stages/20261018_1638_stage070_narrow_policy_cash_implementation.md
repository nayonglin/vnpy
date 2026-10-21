# Stage070 窄初损全母体标签与24账户隔离实现

- line_id：`futures_full_market_long_signal_ai`；时间：2026-10-18 16:38 CST。
- 是否重要突破：否；当前为实现与合成边界验收，目标 active 且未达成。没有实际金融成绩。
- 只新增本线 Stage070 三源码、一个新测试及本唯一stage；不改042/049/053/054/061/062、LINE、registry、其他线或正式版。

调研：本轮实际浏览 [Backtrader维护方订单文档](https://www.backtrader.com/docu/order-creation-execution/order-creation-execution/)与[维护方broker源码](https://github.com/mementum/backtrader/blob/master/backtrader/brokers/bbroker.py)，沿069/068冻结的open gap优先、否则low触及预定boundary的研究约定。结论：日OHLC可以在本单一事前保护边界模型内确定分支，不能证明真实排队、盘中跳价或停板成交；不据外部收益挑选k或其他参数。

实现新增 `stage070_policy_kernel.py`，将WIDE=2N/NARROW=0.25N明确作为函数参数；u共同预算、D配额只减量、持仓初始risk冻结与共同风险缩减统一使用kN*M+既定往返费滑。SL0基于原D.open，退出边界max(SL0,已完成20low)，未另加单调stop/PT/DAY/持有上限/盘内retry。只引用旧042纯数组、成本与记账定义；新账户入口为本地新实现，不运行旧金融入口或全局monkeypatch。

新增标签实际入口只生成一次NARROW完整399252母体，WIDE真实标签只精确引用已接受049。合成helper可对两个k独立重算first-exit/成熟供边界验证。完整状态、unknown/censor/取消保留；目标为各policy net_R_stress，另存net_pnl每手CNY及共同2N*M诊断。必要一次native载入同时生成raw OHLC代理，每行严格v=u-1同一真实epoch，不用标签或067可用性筛母体；071以后独立接受mask。

接口：`outputs/stage070_narrow_policy_cash/labels/labels_narrow.csv.gz`、`ohlc_proxy.csv.gz`、`manifest.json`。标签保留049字段并增policy/policy_k/net_R_common2N_base/stress。代理含sequence/event/product/family/u/reference_epoch、u_index/v_index/v_date、H_v/L_v/C_v/N_v、ohlc_proxy_raw/proxy_state/N_state；成功状态valid_same_epoch_previous_source_day与N_v_ready20，真零合法。manifest schema为stage070_narrow_labels_v1，完整实际后status completed/mode actual；actual终态另绑定。

现金入口只读071 `predictions.csv.gz`，schema列policy/arm/cutoff/sequence_index/event_id/product_id/family_id/u_date/u_index/reference_epoch/history_ready20/selected/score。六组合各161014全母体前向拼接分数；按20/23模型时钟更新，2020连续账户旧仓保持政策、2023同分数冷启无旧仓。真实资金矩阵仅3信息×2政策×2窗口×2成本=24，共享1次native载入。逐账户fills/reservations/rejections/daily/positions/open/closed、年度/family含零贡献、实际退出CNY右尾、费滑/名义额/保证金/冻结风险、gap与小于tick披露；252日/2000次/seed20261018同源日配对logbootstrap及069门均在收益前实现。空参考DD标N/A不强判负，全空信息/政策包标不识别；历史stale影响资格标unknown，不由末日平仓掩盖。

新增测试遵循TDD，先观察缺实现/缺manifest绑定/全空误判/缺参考NaN语义失败再补实现。仅运行新行为11项，最终全部通过，未跑旧suite。覆盖两k完整first-exit/独立成熟、窄先闭合宽后unknown、gap超R、u联预算/D减量/持仓冻结风险、全mother/无55与未来label过滤、raw代理严格前日、精确授权/freshdir、071绑定链及空参考门。测试收据、精确源码与测试SHA见 `outputs/stage070_narrow_policy_cash/implementation_receipt.json`；root后续独立review，不由作者核心导入自证真实结果。

实际CLI统一要求 `stage069_exact_root_authorization_v1`，authorized_by root、stage labels/cash、exact_source_authorized true、固定069协议SHA、current source_bundle、必要input_bindings和绝对fresh output完全匹配。必要inputs与拟命令已写proposed_authorization_inputs.json/proposed_commands.txt；它们均不是实际授权。只有root最后签精确SHA收据后，唯一owner才按labels→071 fit→cash执行，禁止自动重试。

新增研究参数为069已冻结的0.25N；正式参数、旧参数和旧结果修改/删除0。新增实际标签、SQL、fit、cash、下载、整DB/H5 hash均0。期末权益、总收益、最大回撤、Sharpe、总滑点、交易次数、胜率全部N/A；累计实际仍沿既有321fit/42现金，不将合成小数组记为新金融实验。

开始/结束新增过拟合：否，当前只实现先冻结规则，未看新经济结果或按成绩调参；既有研究选择风险仍存在。继续有价值：是，补齐可独审的政策依赖监督、完整母体和现金预算边界，足以在一次限定预算实际实验中反证；不代表窄损或结算信息已改善策略。实际完成以后仍必须独立agent全面复核数据、逻辑、bug、预算和置信度。

16:42 交接补充：独审建议且root明确接受唯一实际前证据小增量。labels/cash从各自已载入arrays确定性选首次类别，保存finite_native_cases.json.gz，包含旧epoch完整Wilder暖机至决定分支、显式缺日、reference schedule/economics和event/fill或position；不按PnL挑案例，不新增SQL/整native复制/金融或镜像测试。三源码语法检查通过，既有11新行为合成语义未改。旧implementation_receipt.json保留为prefreeze；最终SHA与delta见implementation_receipt_final.json，root精确授权必须采用最终bundle。

16:43 实际标签交接：root按最终源码/测试/069协议精确SHA授权后，由owner唯一执行一次，51.205秒成功exit0；完整399252新NARROW标签、同次raw OHLC代理和6类有限路径证据已落盘。实际新增label build1/native SQL1/fit0/cash0/download0/整DBhash0，未重建真实WIDE。NARROW完整闭合184031、entry unknown358、path unknown919、open127、intent81、known cancel9812、notready203924；全部保留，raw proxy ready194709尚不等同071研究mask。exact bindings与终态见actual_label_handoff.json及labels/manifest.json；root后续自己唯一执行071，现金须另精确授权。此次只是监督支持域生成，不是账户回测；权益/收益/DD/Sharpe/交易数/胜率仍N/A。结束是否新增过拟合：否，固定政策一次构建，没有看结果救参；继续价值：是，完整政策依赖监督已可供固定12fit验证，但目标仍active未达成。

16:48 实际现金交接：root在071 12/12fit和966084预测完成后，再签最终070源码/协议/全部输入exact binding授权；owner唯一现金实际33.286秒exit0。24started/24completed共享1SQL，fit0/download0/整DBhash0，无自动重试、无旧金融重跑。此前labels新增1SQL；连同067来源既定1SQL，本联合包总SQL=3，12fit/24cash，累计研究333fit/66cash。所有真实现金结果、年度/family含零贡献、成本/名义额/风险、未决与有限native路径已写cash manifest；作者交接汇总见actual_cash_handoff.json，独立全面实际复审由root另交072，尚不以作者汇总自证。

| 账户 | 期末权益 | 总收益 | 最大回撤 | Sharpe | 总滑点CNY | 费用CNY | 闭合交易数 | 净胜率 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| NARROW_COMMON_cold_2023_base | 1,648,765.8025 | 64.876580% | -19.090369% | 1.087775 | 43,506.0481 | 22,789.1975 | 376 | 19.946809% |
| NARROW_COMMON_cold_2023_stress | 1,193,716.3390 | 19.371634% | -12.023859% | 0.759172 | 53,168.1186 | 30,923.6610 | 322 | 20.807453% |
| NARROW_COMMON_primary_2020_base | 1,483,678.5860 | 48.367859% | -18.724479% | 0.589385 | 54,041.2597 | 26,191.4140 | 542 | 17.712177% |
| NARROW_COMMON_primary_2020_stress | 1,224,435.2890 | 22.443529% | -11.913826% | 0.501397 | 81,200.1849 | 43,314.7110 | 488 | 17.827869% |
| NARROW_OHLC_PROXY_cold_2023_base | 1,649,085.5850 | 64.908558% | -19.053089% | 1.088494 | 43,551.9800 | 22,794.4150 | 375 | 20.000000% |
| NARROW_OHLC_PROXY_cold_2023_stress | 1,212,089.4335 | 21.208943% | -12.230603% | 0.812669 | 52,636.7510 | 30,695.5665 | 320 | 20.937500% |
| NARROW_OHLC_PROXY_primary_2020_base | 1,479,287.5060 | 47.928751% | -18.697466% | 0.587414 | 53,330.3771 | 25,782.4940 | 534 | 17.790262% |
| NARROW_OHLC_PROXY_primary_2020_stress | 1,211,667.0315 | 21.166703% | -12.213632% | 0.477029 | 80,431.1672 | 43,067.9685 | 482 | 17.634855% |
| NARROW_SETTLEMENT_cold_2023_base | 1,648,765.8025 | 64.876580% | -19.090369% | 1.087775 | 43,506.0481 | 22,789.1975 | 376 | 19.946809% |
| NARROW_SETTLEMENT_cold_2023_stress | 1,193,716.3390 | 19.371634% | -12.023859% | 0.759172 | 53,168.1186 | 30,923.6610 | 322 | 20.807453% |
| NARROW_SETTLEMENT_primary_2020_base | 1,483,678.5860 | 48.367859% | -18.724479% | 0.589385 | 54,041.2597 | 26,191.4140 | 542 | 17.712177% |
| NARROW_SETTLEMENT_primary_2020_stress | 1,224,924.2205 | 22.492422% | -11.909054% | 0.502501 | 81,106.7194 | 43,250.7795 | 487 | 17.864476% |
| WIDE_COMMON_cold_2023_base | 1,131,176.0885 | 13.117609% | -3.908033% | 1.108976 | 4,734.1574 | 2,243.9115 | 202 | 40.099010% |
| WIDE_COMMON_cold_2023_stress | 1,109,405.9275 | 10.940593% | -3.752644% | 1.043102 | 13,373.6496 | 6,454.0725 | 198 | 39.898990% |
| WIDE_COMMON_primary_2020_base | 1,169,433.1320 | 16.943313% | -3.745721% | 0.907522 | 7,567.4275 | 3,251.8680 | 314 | 38.216561% |
| WIDE_COMMON_primary_2020_stress | 1,128,735.0885 | 12.873509% | -4.035552% | 0.762323 | 21,030.0053 | 9,194.9115 | 306 | 38.562092% |
| WIDE_OHLC_PROXY_cold_2023_base | 1,132,626.4740 | 13.262647% | -4.852440% | 0.989292 | 4,985.8951 | 2,348.5260 | 213 | 39.436620% |
| WIDE_OHLC_PROXY_cold_2023_stress | 1,113,454.8560 | 11.345486% | -4.736985% | 0.947914 | 13,996.1871 | 6,780.1440 | 210 | 40.000000% |
| WIDE_OHLC_PROXY_primary_2020_base | 1,154,669.9175 | 15.466992% | -4.763670% | 0.756598 | 7,686.3547 | 3,280.0825 | 324 | 37.345679% |
| WIDE_OHLC_PROXY_primary_2020_stress | 1,127,672.4405 | 12.767244% | -4.679296% | 0.682661 | 21,487.3986 | 9,327.5595 | 314 | 39.171975% |
| WIDE_SETTLEMENT_cold_2023_base | 1,137,197.9550 | 13.719795% | -4.854981% | 1.017182 | 4,848.2876 | 2,277.0450 | 205 | 39.512195% |
| WIDE_SETTLEMENT_cold_2023_stress | 1,117,802.4675 | 11.780247% | -4.726376% | 0.974616 | 13,712.5989 | 6,597.5325 | 202 | 40.099010% |
| WIDE_SETTLEMENT_primary_2020_base | 1,160,347.5450 | 16.034755% | -4.731790% | 0.787363 | 7,640.8457 | 3,242.4550 | 318 | 37.106918% |
| WIDE_SETTLEMENT_primary_2020_stress | 1,137,706.0060 | 13.770601% | -4.616132% | 0.741186 | 21,334.9879 | 9,218.9940 | 307 | 38.436482% |

主2020 stress：NARROW SETTLEMENT相对WIDE SETTLEMENT收益更高，但回撤更深，未达到政策继续门。NARROW/WIDE信息门亦均nominal unsupported；历史stale存在，不能由期末多数仓位非stale掩盖，未知资格仍待独审。窄损ready195328行中380行损距小于tick，未临时删品种或改k。按冻结门停止相应固定信息/政策包，不扫相邻stop/滞后/阈值/family/年份或模型救参；主目标仍active未达成。

实际结束新增按成绩调参过拟合：否，本固定包一次完成、源码/科学合同未变，没有追加参数或挑选样本；历史研究选择和闭合条件风险仍需承认。继续救本固定包有价值：否，名义门失败；继续完成独立数据/逻辑/预算/置信度复审与保存有价值：是，防止把收益上升错判为收益回撤同时改善。正式发布/加注/生产/CTP/邮件/订单均0。
