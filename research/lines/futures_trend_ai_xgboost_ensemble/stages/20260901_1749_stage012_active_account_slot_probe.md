# Stage012：首个活跃边际月份账户标签探针

## 阶段信息

- 预注册时间：2026-09-01 17:49 CST
- 是否重要突破版本：否；Stage011非收益活动资格后的第二次标签可识别性探针
- 当前线上：m0005 `ai_top10_plus_fu_official_live_v1`，生产HEAD `d492ee072...`
- 回测区间：`2018-01-01 -> 2022-06-30`；决策日`2022-05-31`
- 资金/规则：15万元、当前Stage847-C9/Stage037、正式成本/保证金/整数手/相关性/最多4持仓
- 不训练模型、不改生产、不连接CTP、不调用订单API

## 机械来源与四臂

- Stage011只用T18成交的`experiment_arm/offset/date/vt_symbol`四列，机械选中首个“rank10有开仓且至少两个低排名候选有开仓”的月份；绩效列消费为空。
- A1/A2：rank10 `ru.SHFE`。
- C12：rank12 `OI.CZCE`替换`ru.SHFE`。
- C13：rank13 `au.SHFE`替换`ru.SHFE`。
- rank1..9固定为`FG,jm,hc,CF,lh,sp,MA,SM,AP`，固定`fu.SHFE`；除`2022-05-31`第10席位外全部历史月池相同。

## 身份与确定性门

- 继承Stage010完整输入闭包：m0005 release、数据库、全量分钟K、主力映射、合约元数据、产品全集、生产代码、vnpy、vnpy_portfoliostrategy、解释器/包元数据、Stage009排序、Stage011选择、本runner/预注册和全部eligibility。
- 四个独立冷进程、独立`TMPDIR/MPLCONFIGDIR`、不复用checkpoint；生产模块导入后冻结完整`sys.path`，运行后逐项一致。
- A1/A2汇总、曲线和交易逐值一致；所有臂在`2022-05-31`及以前曲线逐值一致。
- 额外保存目标期`entry_candidates/trade_events`，只用于解释零标签，不作为收益筛选。

## 预声明门

1. 全部身份、A/A和决策日前路径门通过。
2. C12/C13至少一臂在目标期收益或最大回撤相对A差异超过`1e-12`。
3. 每臂墙钟不超过10分钟。
4. 通过只表示账户标签生产协议具备可识别性，允许做覆盖/稀疏性研究；单月赢家不得晋级模型或正式版。
5. 若标签仍为常数，停止“逐月全历史反事实批量生产”形状，先根据entry candidate和账户门归因，不再换月份救援。

## 过拟合与继续价值（运行前）

- 是否过拟合：否。月份和challenger由不含绩效的最早活动规则唯一决定；但结果绝不能当收益证据。
- 是否值得继续：是。Stage010证明任意首月会产生零标签，Stage012是活动资格后的唯一一次确认，可决定是否值得投入数百次真引擎生成训练标签。

## 2026-09-01 18:10 身份加固重跑修订

- Stage010独立复核发现首次Stage012继承的身份合同漏纳入解释器启动时实际加载的根目录`sitecustomize.py`、有效`.pth`及`.pth`执行导入模块；首次结果只能视为行为证据，不能作为clean identity结果。
- 本次只加固审计，不改变月份、候选、资金、规则、回测区间或任何模型参数；四臂全部新建冷进程，不复用首次attempt。
- 新合同纳入`sitecustomize.py`、site-packages根目录全部`.pth`、已加载`_distutils_hack/sitecustomize/usercustomize`启动模块文件。
- 决策日前路径门扩展为曲线、交易、`entry_candidates/entry_risk/trade_events`全部逐值一致；A1/A2也扩展三类诊断逐值一致。
- C eligibility必须只改变目标月rank10这一行；Top9、固定`fu`和其他月份所有字段逐值不变。
- 修订不允许改标签可识别阈值或根据首次收益选择新候选；原预声明通过/停止逻辑保持不变。
