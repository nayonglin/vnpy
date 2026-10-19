# Stage071：多手0.5%风险预算复盘兼容性研究（接口待冻结）

- 时间：2026-10-20 00:24 CST；研究线 futures_trend_full_market_noai_one_lot。
- 重要突破：否；新显示合同准备，不产生回测结果。
- 明确基线：用户选定交易合约自身周线N，交付e553d1703，金融run_20261019_contract_weekly_long_v1，manifest859982f079da55aa1292154d5fc9b1004d1f0d5f23f75c4ec58ca892a102cb25；不是旧主力周M或无周门A。
- 用户已更正风险为**0.5%=0.005，100万5000元**；废弃本轮最初0.0005/500元及risk005命名。新源拟run_20261020_contract_weekly_risk05_v1，尚无新金融绩效。

## 必须适配

canonical FIFO支持volume>1和分批平仓，gross已乘matched_volume与size；按open_trade_id聚合完整episode，weighted_exit按平仓数量。001只把累计平仓volume等于原OPEN数量的entry算完整，其他部分留残仓披露，这些核心可复用。025并行context与手数无关。063精确合约周图和067复位脚本与手数无关，保留所有原周期合同与周数据验证。

045不可沿用：硬拒非1手、重复open_id闭合段。新071须用实际接受的**整笔initial risk=实际开仓volume×per-lot initial risk**，每个matched close按matched_volume/open_volume分摊risk，再由canonical episode求和；禁止每个分平片段重复整笔risk或使用每手risk充当整笔分母。完整episode R仍为毛盈亏/整笔实际初始风险，不以目标预算或净盈亏作分母。胜率样本按完整entry，不按每手或每个部分平仓片段。

分摊entry fill的commission/slippage各按matched_volume/open_fill_volume，close fill成本按matched_volume/close_fill_volume；所有字段为该fill全部数量的总现金成本。残仓未分配到已平片段的开仓成本已经在账户发生，绝不称未支付费用或再次从日账扣除。完整episode+部分已实现片段+剩余entry成本需与全部成交成本闭合。

canonical lot_count是FIFO匹配段数，不是合约手数；新UI需要显示meta.volume，独立说明lot_count。原canonical“净利润”卡片实际gross，新071需窄文字适配，明确毛/净盈亏和费用，图表实现不复制。

新071链拟025 raw→071多手风险/费用及身份修正→063精确周→020独审→067 current-trade Reset。旧001/025原始中间页的一手标题不能进入最终页；旧工具/产物不改。

## TDD准备与边界

已新增test_stage071_fractional_recap.py，3项纯归因合约测试先RED（071模块尚未实现，等待068/070收据字段）：3手分1+2平，毛500/初始风险300/R1.666667/成本18/净482，只1个完整样本；另4手仅平1手保留残余，片段净-56/成本6、剩余entry费用分摊9，全部现金成本33闭合；拒绝把3手收据总risk写100或filled_volume写1。当前全线因此有3个明确待实现RED，不声称整线通过。

外部调研：[CME仓位规模](https://www.cmegroup.com/education/courses/trade-and-risk-management/proper-position-size)、[CME期货盈亏](https://www.cmegroup.com/education/courses/introduction-to-futures/calculating-futures-contract-profit-or-loss)、[vn.py官方回测文档](https://github.com/vnpy/vnpy/blob/master/docs/community/app/cta_backtester.md)。判断：单位止损现金风险与整笔风险必须乘实际手数；账户净盈亏要扣总费用；FIFO按数量配对不等于逐手独立统计。实际策略定义以本次冻结本地068/070收据为准，不从外部资料引入新阈值。

新增/修改/删除金融结果：无；本阶段无金融回跑、下载、生产/CTP/订单访问，不改Git/LINE/其他线。过拟合：显示工作否，没有收益选参；继续价值：是，防止多手R和费用数量级错误。金融候选是用户新规格，同样本后验研究限制保留。下一步等真实receipt命名、每手/整笔语义与entry/fill identity后实现并GREEN，独立校验完整与残余账本。

## 实现冻结与专项验证（2026-10-20 00:34 CST）

前文“接口待冻结/未实现/RED”为设计阶段状态；现068/070/075字段已落盘并核对，Stage071/072均已完成，实现后无金融回放，尚未生成真实新版本产物。

- RED→GREEN：先新增缺模块/缺接口断言，再实现窄适配。联合9项专项测试全部PASS，运行1.732秒。命令：`MPLCONFIGDIR=/private/tmp/fian-stage055-mpl /Users/mac/Desktop/fian/.py311/bin/python -m unittest discover -s research/lines/futures_trend_full_market_noai_one_lot/tools -p 'test_stage07[12]*.py' -v`。
- 071共5项：3手分1+2平只1个完整样本；risk300/毛500/R1.666667/成本18/净482；4手只平1手保留残仓片段及费用；拒绝每手当整笔risk/错数量/错误0.0005；全冻结fixture输出不改任何非金融图形payload、原顺序和尾部选择标签，原source/parent hash不变，禁止覆盖。
- 072共4项：仅接受N859982…基线与0.005固定政策、仅2项参数变化；错误比例/旧1手flag/额外参数变化或N hash错误均拒绝；Plotly figure JSON与042原函数逐值一致；PNG仅2个白名单文字常量改变，反向恢复AST与原函数逐字结构一致；fixture全HTML/PNG/hash与禁止覆盖PASS。
- CSV统一round_trip还原冻结float；预算与收据授权严格Decimal边界，无epsilon放宽。实际CSV字段为stage068_open_budget，风险分母为stage068_entry_risk（整笔），按实际volume×stage068_risk_per_contract复核，不导入金融模块。
- 071最终页明确毛/净盈亏与交易手数，原canonical lot_count仍表示匹配平仓段数，不当作合约手数。费用按成交总现金及匹配数量归因；完整entry、残仓部分已实现、剩余开仓费用闭合。保留原周期数组及坐标，补R不重选。
- 072只比较用户选定N→新0.5%多手版；复用原Plotly AST与PNG绘图，不复制图表，不使用A/M为新基线。源、父复盘、N基线、各依赖及原始绘图hash闭合。

冻结文件SHA256：

```json
{
  "stage071_fractional_recap.py": "007a29ea34511d2b164955ded29394f4ef4d331c0e797547b03b57cb34b90ef8",
  "test_stage071_fractional_recap.py": "5a7a18b7571f34da44d3ce0258668f008242349fe9c6f1fdb926224a26d2dbe3",
  "stage072_fractional_overview.py": "18413d4f4a75ec0ef9fa7d750ed20549999ee232714f335ea87949addefe8aa7",
  "test_stage072_fractional_overview.py": "2d61408141d05afdf128eb31109c6f693c1e32af8269ce0985b746a3207b5efa"
}
```

下一步：root冻结代码并唯一金融运行；完整源和025父复盘生成后，071→063→020→067，再072。实际全量逐笔/周值/2862点/JS/browser验证后再补新阶段证据。当前不声称新收益、业绩改善或金融独审通过。独立金融审查由root委托073负责，本任务仅展示/原始数值。

新增/修改/删除金融结果：无；旧源码/产物/LINE/Git均未修改。过拟合判断：显示工作否，不按结果重选、不改风控；继续价值：是，多手R、费用与完整样本身份必须准确，研究候选仍保留同样本与日线近似限制。
