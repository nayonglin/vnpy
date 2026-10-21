# Stage214：既有训练域与同K行动域盘点工具完成（尚未actual）

- line_id：`futures_full_market_long_signal_ai`；记录时间 2026-10-19 20:07 CST；非重要突破。
- 接续被中断的完整300行工具，不重写旧源或210–213报告。只新增3个定向合成fixture与本实现就绪记录，root唯一actual仍未启动。
- 已读取registry/LINE、冻结213协议和156门实现；沿用213已经完成的原出版页/GitHub调研，不新增研究题目。判断仍是训练行动域差异可以盘点，但差异不等于模型或财务优势；本阶段不读Y/X，不产生训练许可。

## 代码、边界及验证

- 工具：`tools/stage214_training_domain_probe.py`；原实现保持不变。冻结213 SHA `17805a9fa6dd2df655ea9f4bebb84993f9c6beb6733d0772ea2c5812abee1033`。
- 3个新合成测试一次完成、3 passed/0 failed：精确156 D<K与D=K、before/after-calendar、sentinel和样本末之外K；缓存17g权重直接astype(float)恢复与身份/成熟拒绝；三域原权重质量、year/family/product及reason聚合守恒、有限机械anchors。
- 测试只读小代码并生成内存数据，旧六train cache、原actions/COMMON/q/native/价格/SQL全0。未按目标Y、分数或成交状态筛行，未归一/截断/重算旧权重。
- `source_bundle`、精确CLI和root授权schema保存在`outputs/stage214_training_domain_probe/implementation_receipt.json`。actual目录必须不存在；协议硬绑定、三源码和六fold完整身份必须通过root授权才读取。
- actual预算仅6个accepted130训练缓存各1读；只指定10列，旧SHA继承、bytes与前后stat，禁止大输入hash。全6fold/year/family/product输出；总anchors≤16，按冻结六fold原sequence机械均匀抽取。215独审只核新小产物及合成边界，不再读取旧训练cache。

## 参数及金融结果

新增/修改/删除策略参数均0；新增/修改/删除回测结果均0。本阶段fit/cash/prediction/selection/label/SQL/旧cache读均0，累计仍427fit/230cash。期末权益、收益、最大回撤、Sharpe、滑点、交易、胜率全部N/A，不把几何统计当收益。

## 反思与TODO

- 开始/结束过拟合风险：是，历史择题风险仍有；本盘点不读取Y、不按新结果选年份/家族/质量阈值，不新增救参。
- 继续本盘点价值：是，一次最小域盘点能否决不存在结构差异的假说；自动训练或加注价值尚未证明。
- TODO：root精确授权唯一actual，215独审三域/守恒/gate anchors，root216作结构研究价值决策。完整目标保持active，不晋级、加注或触碰正式生产。

## root唯一actual终态（2026-10-19 20:09 CST）

- root session `75259` 唯一实际执行，exit0，耗时 `10.307905792` 秒；6折启动/完成均6，没有重跑。manifest `12249B / SHA 4bd6448ed19577a08ccf3db6dcc487332ea1b6a80571022e64a805fbcec6ad7e`（root提供身份）。
- 只读small summary/terminal追加本记录；本agent未重读旧训练缓存、未改冻结代码或LINE/registry。215独立审查当前pending，以下只是作者产物，不预告审查通过。

| 训练scope | cutoff | 原行数 | 当前admissible行数 / 原权重质量 | 当前inadmissible行数 / 原权重质量 | inadmissible权重占比 | unknown行数/质量 |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| main | 2020-01-01 | 247795 | 216443 / 215906.400102633750 | 31352 / 31888.599897366264 | 12.868944% | 0 / 0.0 |
| main | 2023-01-01 | 445475 | 390340 / 387066.072069422691 | 55135 / 58408.927930577091 | 13.111606% | 0 / 0.0 |
| holdout_0 | 2020-01-01 | 171712 | 150511 / 150301.098958206043 | 21201 / 21410.901041793884 | 12.469077% | 0 / 0.0 |
| holdout_0 | 2023-01-01 | 297404 | 261338 / 260263.851144880988 | 36066 / 37140.148855118947 | 12.488113% | 0 / 0.0 |
| holdout_1 | 2020-01-01 | 76083 | 65932 / 65804.595839045709 | 10151 / 10278.404160954295 | 13.509462% | 0 / 0.0 |
| holdout_1 | 2023-01-01 | 148071 | 129002 / 127274.582133656673 | 19069 / 20796.417866343330 | 14.044896% | 0 / 0.0 |

- 6个accepted130训练缓存各1次读取（attempted=completed=6），calendar读1。fit、cash、old_cash、prediction、selection、new_labels、original_actions、COMMON、native、price、SQL、大输入hash均0；累计427fit/230cash不变。
- 六折均存在当前admissible和inadmissible，unknown全0；旧权重未归一、重算或截断。总体三域质量守恒最大浮点残差`5.820766091346741e-11`，均在各折披露的8 ULP界内。重叠fold不可当成六组独立市场样本累加。
- 本次事实：原训练loss约12.47%—14.04%的原权重来自当前同K政策不可选的D>=K动作。不是“坏样本”证明、旧训练bug或alpha；它们仍可能提供有效共享斜率，限制训练也可能损失效率。只支持训练/使用行动域有差异，下一步须由root216独立判断是否值得另行冻结实验；本actual不授权任何模型/现金或重标。
- 本阶段新增金融回测为0，权益/收益/回撤/Sharpe/滑点/交易/胜率仍全部N/A。开始/结束过拟合风险仍是历史择题风险，未读Y或按成绩调参；继续完整目标有价值，继续以本差异自动救参或加注没有依据。完整goal active。
