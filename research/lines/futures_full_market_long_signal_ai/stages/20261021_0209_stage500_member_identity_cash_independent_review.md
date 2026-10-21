# Stage500：具名会员B/C八账独立现金审查（core＋tail完成）
**最终状态（2026-10-21 02:13 CST）：现金范围已由原8账core＋唯一tail闭合，material P0/P1/P2=0/0/0。下面“两过程失败边界”及尾项未核文字是中途审查历史，最终以文末tail收据为准；两个旧审查器错误均保留，没有金融回测重跑。source/model/argmax/held独审仍单独引用498，500不替代它。**

- line_id：futures_full_market_long_signal_ai；day；记录时间：2026-10-21 02:09 CST。独立审查员，与496/497作者隔离；非重要突破、不更改原策略/参数/模型、正式C9或部署。
- 调研与判断继承Stage495的交易所披露说明与维护者字段实现：具名披露只能代表经纪会员汇总，不是最终投资者身份或聪明钱证明。本阶段是独立现金会计与置信度审查，source/model/argmax/held另属498，未重复其范围。

## 两个实际过程与失败边界

1. root授权首actual：session2905，exit1，18.4570075秒。缓存字符串reader不符合原102 diagnostic CSV自动推断数值的类型合同，daily.stale_positions比较str>0触发TypeError。cache一次；0 SQL/fit/策略现金回放。首本会计/原生检查已走到诊断，但未完整checkpoint，不把它继承为完成。原source与测试原字节保留actual_run1/source_snapshot。
2. root逐字授权dtype-recovery1：session15374，exit1，69.54775075秒。最小修复在内存已绑定gzip bytes上按原reader语义解析（date/year/family保留str，其他列推断数值，round_trip），新dtype反例RED→GREEN及恢复入口反例通过。额外cache一次，累计2；首26文件中必要25派生输入明确重读，旧auth不再读。没有任何金融账或模型重跑。
3. 第二过程**8本核心账均完成且每子phase持久化**，随后合并annual导出检查直接取原157 summary中不存在的display字段account_id而KeyError。此错误属于审查报告适配，无策略/原始数据错误证据。没有自动重启、没有扩大修复。

## 已完成核查

- 8本原始raw checkpoint与全部9类导出逐格一致；12136笔fills、10232行daily、16332行positions、23994条budget、6054个closed root、16个terminal open。8份raw_export、8份saved_account、8份native_capacity、8份完整audit和all_books_phase均保存。
- 独立成交会计、所有fee/不利fill/slippage、滑点已经含在fill价不再双扣、持仓数量/未实现盈亏/每日权益、实际开平价格锚、.25N与20low边界、anchor/lifecycle、联合风险/保证金及整数参与量预算、D开盘拒绝/减量、unknown entry/capacity、stale未置零。
- 原157 own四账日线与摘要、全部12条summary及95族归因合计核对通过。A不是原157 baseline_refs里的131B。全六所98品种/95族保留，来源仅SHFE/INE不能推断全市场身份机制成立。
- 已完成核心scope material P0/P1/P2=0/0/0；**不得据此声称整个500最终审查通过**。尚未执行：合并annual/paired annual尾部、12组2000次原252日block indices配对CI、C−B经济等价及唯一换月资金链、截至2025同账截面最终导出核、manifest剩余hash收尾。

## 已核八账指标（账户100万元，2026-10-16止）

| 账户 | 期末权益 | 总收益% | 最大回撤% | Sharpe | 总滑点元 | fills | closed | 胜率 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| NARROW_B_MEMBER_AVAILABILITY_cold_2023_base | 1619649.9269999994 | 61.964992699999954 | -7.95540610854184 | 1.1350638470421557 | 47873.4683092286 | 946 | 472 | 0.1228813559322034 |
| NARROW_B_MEMBER_AVAILABILITY_cold_2023_stress | 1510636.6065 | 51.06366065000001 | -6.383449268618168 | 1.1900391579797471 | 78380.60865013492 | 774 | 386 | 0.12953367875647667 |
| NARROW_B_MEMBER_AVAILABILITY_primary_2020_base | 2163642.1424999996 | 116.36421424999996 | -15.317366667974008 | 0.9513954406609194 | 137079.0073513686 | 2532 | 1265 | 0.12094861660079051 |
| NARROW_B_MEMBER_AVAILABILITY_primary_2020_stress | 1533845.1225 | 53.38451225000001 | -9.776428124852954 | 0.8279209067802734 | 166134.86292936423 | 1816 | 904 | 0.12389380530973451 |
| NARROW_C_MEMBER_IDENTITY_cold_2023_base | 1619649.9269999994 | 61.964992699999954 | -7.95540610854184 | 1.1350638470421557 | 47873.4683092286 | 946 | 472 | 0.1228813559322034 |
| NARROW_C_MEMBER_IDENTITY_cold_2023_stress | 1510636.6065 | 51.06366065000001 | -6.383449268618168 | 1.1900391579797471 | 78380.60865013492 | 774 | 386 | 0.12953367875647667 |
| NARROW_C_MEMBER_IDENTITY_primary_2020_base | 2163642.1424999996 | 116.36421424999996 | -15.317366667974008 | 0.9513954406609194 | 137079.0073513686 | 2532 | 1265 | 0.12094861660079051 |
| NARROW_C_MEMBER_IDENTITY_primary_2020_stress | 1533845.1225 | 53.38451225000001 | -9.776428124852954 | 0.8279209067802734 | 166134.86292936423 | 1816 | 904 | 0.12389380530973451 |

B/C六位相近/相同不能推出所有选择相同；498另核main恰一次换月，held动作不变。当前500没有独立关闭经济等价或配对CI，不把浮点末位收益/回撤差当alpha，不修饰未知为零。

## 输出、结论与下一步

- partial_core_review_receipt.json绑定全部8核心audit、失败终端和未完成边界。
- all_books_phase.json为8核心账完成证据；两失败process终端均保留，无automatic retry。
- 如root选择关闭尾部，只应有限新daily/fills/小摘要/原indices审查，继承已完成8账checkpoint，cache/SQL/fit/策略回放/旧大流及source/model重核均0；当前尚无该tail实际授权，不自行启动。

运行前后反思：长期同历史择题过拟合风险高，是；500不择参、不改变科学规格，历史CI仍条件证据非blind，不能加注或生产。继续价值是完成8账独立核查；反复审同一大源/现金内核无价值。更高收益更低回撤、全市场高质量long与极窄损加注的完整目标未达成。新增/修改/删除模型和策略参数0；新增金融回测0，仅审查8个已有新账。当前不更新LINE/registry及根memory/back_log，不操作Git/CTP/邮件/任务。

## 唯一tail闭合（最终）

root精确授权tail-only：session44224，真实exit0，1.4646531659527682秒；49个输入各唯一一次读取。当前cache0/core账户复核0/SQL0/fit0/策略现金回放0；累计cache保持2。tail继承partial_core_review_receipt（b450b36…）及all_books_phase（2e4f360…），没有重新做八账会计、原生价锚或source/model/argmax。A的canonical account_id来自495 control_accounts_reused；不要求旧157 summary补display字段。

已闭合：12账户年度与paired annual导出、12条截至2025同账截面、95族×12账户总表、原252日block/2000次indices的12组paired CI、双gate、B/C经济等价和唯一换月资金桥。每个CI cell单独checkpoint。只校验实际请求的导出与已核core，不宣称重新hash所有无关raw附件或重新认证全部原始市场数据。

### 身份增量实际未改变资金路径

四个2020/2023×base/stress场景，B与C的成交经济身份、数量、reference/fill价、fee、slippage、realized gross均完全相同。每个场景最大逐日权益差=0元，最大每日权益增长额差=0元；四组C−B配对CI均为[0,0]，收益和DD差均为0。账户/root/budget名称前缀不同不属于经济差异。作者表中个别浮点predicate末位差不构成alpha，unsupported结论不受影响。

main 161014母中确有1次不同选择，并非所有score或action相同：2026-07-29 SHFE.FU，B选202610、C选202609。四口径×两臂全部对应budget_state/D_state=family_occupied，D_qty=0，实际fill=0；已有同族仓位占用使唯一换月没有进入现金账户。因此身份分数微变与资金无增量能够同时成立。held标签/动作变化由498单独验证，不在tail重新求argmax。

### 对A比较与置信度

C与B对A点差相同：2020base收益−6.56280760pp、DD浅0.31005322pp；2020stress收益+0.54254125pp、DD浅1.58287243pp；2023cold base收益−20.57866275pp、DD浅1.94674261pp；2023cold stress收益−1.60092170pp、DD浅0.03931211pp。primary stress日log差CI95=[−0.0000618416176155,+0.0000718433572042]跨零；cold2023base CI95=[−0.0002989924278862,−0.00000846327445157]全部为负。

C−A和C−B双门均不通过：三项相对A收益下降、primary CI未正，身份增量本身0现金效应。A对比held差异未知2/1仍保留，C−B held差异未知0/0；所有账本的历史stale与执行未知继续fail资格，不置零、不修补log。本结果仅否定这次冻结低容量身份模块能提升策略，不证明所有可能的会员信息都毫无价值；不以同史扩词/调ridge/放容量救成绩。

最终结论：本包不支持加注或正式接入。继续整个目标仍有价值，但固定身份包应关闭，避免反复消耗同一历史；未来需要真正不同的信息或机制及新证据。长期择题过拟合风险高，是；一次冻结反证有价值，是；本轮失败后再调同包无足够价值。完整目标active未达成。

最终证据：

- core：outputs/stage500_member_identity_cash_review/partial_core_review_receipt.json，SHA b450b36cf42ac60293009fbaeb5582907cc55579263ec6d79b4d876b42d4fd42。
- core八账：actual_dtype_recovery1/all_books_phase.json，SHA 2e4f360d173dcb82d4360c88e93adfcf8475617e5d25daad9d5f9714c56b439d。
- tail：actual_tail1/review_receipt.json，SHA 6fe843ff3408e8badb95017114922b436560092912d8ace2e654a8f8b45c10f1。
- tail真实终端：actual_tail1/terminal.json，SHA 1b7febf0cc2efcc49d00f795fddc916c276c73fce136e70da9a0749882636155。
- 12CI/双门：actual_tail1/paired_gate_phase.json，SHA 510f75cbf1a07e32b2e786ca637d86fd149b2d927dc6621dba17f7864470aac2。
- C−B经济等价：actual_tail1/C_minus_B_economic_equivalence.json，SHA 3c855606f6fda27009a7321e9ff0f0eefc6ee63ee02861695625fc36cc1f9c3e。
- 唯一换月资金桥：actual_tail1/C_minus_B_choice_cash_link.json，SHA 3c37b72a899ad6c4e6cc5511ae5d079a3d9a67fcfb76b9b184741e9fd39e01f3。
