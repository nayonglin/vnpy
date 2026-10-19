# Stage072：0.5%多手资金总览方案（接口待冻结）

- 时间：2026-10-20 00:24 CST；研究线 futures_trend_full_market_noai_one_lot。
- 基线固定用户选N/e553d1703/manifest859982f079da55aa1292154d5fc9b1004d1f0d5f23f75c4ec58ca892a102cb25；只比较N→新risk05，不继续默认A/M表。
- 新政策固定0.5%=0.005，100万5000，整手floor、无1手上限；exact weekly long-only不变；最终政策字段等待068/070。
- 042/055/062的source loader硬max_position_size=1、one_lot flags和一手标题不兼容，不能伪装旧预算输入。新072将独立核新源合同、显式N目录/hash、声明的risk-sizing参数变化白名单，其他参数/数据/周门核对；复用042完整hash工具和原032 AST Plotly图形函数，逐点验证资金/高点/回撤。
- 042静态PNG有一手标题，必须仅更换标题/资金口径文字；拟独立AST白名单文字适配或局部public suptitle参数适配，不复制/改变绘图计算与坐标。HTML同样显著0.5%/多手/按止损整数定仓、分平与残仓费用边界。
- 新072暂未实现，没有新产物/金融结果。待receipt合同后先有意义测试RED→GREEN，覆盖拒绝旧M/旧A基线、0.0005误口径、旧一手flags、图形不变及新标题/比较表。最终全2862点/版本值/JS/hash/浏览器单独验证。
- 重要突破：否。金融参数/结果在本展示任务中新增、修改、删除均无；无金融回跑、下载或生产访问；不改旧工具/LINE/Git/其他线。
- 过拟合：显示工作否，不用收益调整规格；继续价值：是，保证新多手结果与用户选定N正确对比；同样本研究不当作样本外晋级证据。

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
