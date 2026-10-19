# Stage081：0.5%多手展示独立验收准备

- 时间：2026-10-20 00:46 CST；研究线futures_trend_full_market_noai_one_lot；重要突破：否，验证工具。
- 首轮v1于2017-03-13失败，独立Stage076已确认强制减仓两P1。失败prefix不能生成复盘/全期业绩；不修改v1、070/074或已冻结071/072。新成功源预计run_20261020_contract_weekly_risk05_v2，本记录尚无该源真实验收。
- 新081是独立只读验证器，不导入071/072/063/金融策略；从成交自建数量匹配，完整原始entry才计样本，分平残余单独核对，全部fill费用=完整entry成本+残仓已实现片段成本+剩余entry费用分配。用实际volume×开盘每手风险与严格Decimal预算重算整笔R分母；不以目标预算或每手风险充当整笔风险。
- exact周图独立从合约日线、上市日和完整calendar聚合：仅accepted-clean与显式execution_only=False，allow_new_open仅显式False拒绝；缺完成周EOW置空，坏周不压缩，MA在完整合约周格先算再裁；不调用063/058作为答案。全周OHLCV/MA、共享label/x/width，全部非周payload、raw→071非金融payload均有hash/逐值校验。020/067最终records要求原字节不变。
- 072验收核用户N的固定manifest859982…，12行N→新比较、全部2862点的资金/高点/回撤、CSV与Plotly三个trace逐点、PNG签名/大小、标题5000元/0.5%/无旧1手口径、所有HTML内嵌JS经bundled Node --check。PNG视觉及浏览器交互由root另行实测，不把此准备记录说成真实v2通过。
- TDD三项核心测试先RED后GREEN，再补完整冻结链路回归，最终四项GREEN：3手分1+2平/费用18/毛500/净482/风险300/R1.666667/单一完整样本；另一4手部分平1手保留净-56、剩余3手及费用9；拒绝超量平仓；同品种两合约反向趋势不混价、坏周不压缩MA；改风险允许、改坐标必拒；完整冻结fixture验证收据、页面record/hash/嵌入JS并拒绝tampered record。独立081四项PASS；连071/072合计13项PASS（3.283秒）。071/072文件hash与上轮冻结值一致。

```json
{
  "stage071_fractional_recap.py": "007a29ea34511d2b164955ded29394f4ef4d331c0e797547b03b57cb34b90ef8",
  "stage072_fractional_overview.py": "18413d4f4a75ec0ef9fa7d750ed20549999ee232714f335ea87949addefe8aa7",
  "stage081_validate_fractional_display.py": "fb6565cb95642901227819c76c12f8d2cb61ab7aae1926910e61fdc65444b1da",
  "test_stage081_validate_fractional_display.py": "0373aab1283f252fc094ebb9b6bc73e9a921f84a1cad03275232d7bd3ecb0557"
}
```

实际命令模板：

```sh
/Users/mac/Desktop/fian/.py311/bin/python research/lines/futures_trend_full_market_noai_one_lot/tools/stage081_validate_fractional_display.py --source <成功v2源> --baseline research/lines/futures_trend_full_market_noai_one_lot/outputs/run_20261019_contract_weekly_long_v1 --raw <025目录> --fractional <071目录> --weekly <063目录> --final <067目录> --overview <072目录> --output <全新stage081实际验收.json>
```

支持按已完成产物分阶段传参数，最终必须覆盖全部链路。报告只写新指定JSON，不能位于冻结输入内；失败退出不签PASS。后续真实金融源、父复盘路径和080独审由root通知，071→063仅渲染，020等待独审成功；不重跑金融。

外部调研沿用Stage071/072已核的CME期货数量风险/盈亏与vn.py官方回测资料，不引入新阈值。判断：多手的计量单位和总现金必须贯穿完整entry归因，当前独立验证有价值。过拟合：本显示验收否，不做收益选择、不更改策略；金融候选仍是同样本后验研究，不能从渲染PASS推导晋级。新增/修改/删除金融结果：无；未下载、未访问生产、未修改旧代码/产物/LINE/Git/其他研究线。
