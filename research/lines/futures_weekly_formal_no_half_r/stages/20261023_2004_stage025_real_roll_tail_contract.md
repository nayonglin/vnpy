# Stage025 固定全期换月尾部真实行情补充合同

- 记录时间：2026-10-23 20:04:40 CST；line_id：futures_weekly_formal_no_half_r。N_attempt001在2019-08-15严格失败，terminal=failed/postflight输入不变；未产生完整绩效，不发布截断权益。该日旧ru1909真实bar缺失，synthetic carry interval=None被原日K开盘门拒绝。旧/new副本都止于8/9，不是准许改interval或延期成交的理由。
- 不修改任何冻结策略/执行/旧工具。原mapping实际ru1909最后main日2019-08-06、8/7新ru2001；8/15是换月尾部执行第7日。原_rollover_delay_due首新target日elapsed=0，随后第6日达到5才发单，第7日开盘成交；若等待中target变更则reset，回旧target也须保守继续扫描，不能只补6天。
- 金融前固定完整日期窗原19 mapping的715个main regimes与5011 unique最久合法换月尾部要求：7日基础+纯mapping reset延伸（3regimes，最长27日），不模拟利润/持仓/信号来挑keys。已发布stage025_roll_tail_requirements；missing140键/24 native，清单SHA97d1297bda73d6862506fe3ab93ddb972b55577ab31925f676ba9a3913a40ca8。v1部分7旧FU过期身份分类纠正可加v2，native/date需求集不变，不恢复过期bar。
- 固定补源规则预先授权：优先只读复用Stage022已冻结完整Tq86400秒原serial，其本已含ru1909尾部；缺精确日才对本140清单所涉合同定向下载。必须真实物理YYYYMM/inclusive生命周期、有限合法OHLC、正volume、同日closeOI与raw精确吻合/SHA；CZCE跨十年必须验证真实年份，不借新十年串历史。旧源zero而新Tq正量的只能按原固定Tq authority条件准入，冲突保留，不宣称供应商共识。
- 定义确定性准入谓词并在看N002/P收益前批准：只新增上述140键中满足全部条件的正量真实bar。零量/原源无行/已过期13键不进入DB/周/撮合；保留各自证据/结构标签，不能填价填0或替代合约。将合格新tail正量与旧455 approved_supplement精确合并，旧573zero/18structural两政策不改，新combined policy绑定清单、原raw、receipt、本合同与旧政策全部SHA；用未修改Stage023 assembler产全新data副本v2，原副本/失败N001全部保留。
- 新N以原runner --attempt002运行2015—2026-10-23；P以同一最终data_v2 --attempt001跑2020—2026-10-23。旧stage024报告工具和N001输入不变，新增stage026派生报告真实绑定N002/P001，不伪装失败账本。核心alpha/风险/成本/MA/21-ready/19池/无4仓限制均不变。
- 接受标准仍为完整账户日历+真实持仓/成交日正量0缺口、严格次交易日同合约开盘无延期、无分钟/proxy/AI读取、周源单物理epoch及完整周、设置/成本与M逐值核对、会计/FIFO末仓守恒、独立review。尾部真实zero可能无法成交，若实际持仓触及即失败，不能转成后续有效日成交。旧FU pre2018-07-16是否零候选/成交/仓位必须在新完整路径重核；若消费旧180的50吨规格而用M10吨静态参数，不可声称真实历史规格已通过。
- 此次新增是真实行情覆盖修复，不是策略优化、调参或按收益择源；运行前是否过拟合：否（固定全期数据规则、保留失败），仍非PIT/OOS/完整历史main重建。继续价值：是，修复数据覆盖后才有资格评价跨周期收益；如真实无流动性导致失败，保留负结论不救参。无正式晋级/生产/订单/邮件/定时任务/推送。
