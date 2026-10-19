# Stage083：最终多手标签与退出语义窄适配

- 时间：2026-10-20 00:55 CST；本研究线独有新增工具/测试，非金融突破。071/072/063/020/067、金融源、旧输出均未修改。
- 已确认063/020调用canonical _html会恢复原“净利润”（实际毛额）与“平仓lot”（实际匹配段数）卡片，故071中的窄label修复不能直接作为最终页保证。新083放在020之后、067之前，严格只替换两处JS卡片表达式，并追加一段html.escape纯文本说明；整页逆向替换后必须与parent原HTML逐字一致。不得复制renderer、改变数组、标记、坐标、排序或筛选。
- 新卡片为“毛/净盈亏”（显示毛额、净额与分摊成本）和“交易手数”（meta.volume原开仓数量）。全部非HTML产物原字节复制、records.json字节hash及HTML内嵌JSON完全一致，source metrics保持原值；新manifest绑定parent全hash、source全hash/代码snapshot、canonical和083生成器hash。输出必须新隔离目录，输入篡改/标签合同改变/重复补丁/覆盖均拒绝。
- 只读canonical核查：_trade_episodes的exit_date/exit_price取最终平仓片段，weighted_exit_price另按全部平仓数量加权；_records.exit_marker_price取row.exit_price（行情同源才显示），JS y使用该marker。未把加权均价画在最终退出日，但也未逐fill画中间退出箭头。新显著说明：紫色点为最后一笔实际成交价、紫线为最终实际退出日期；价格涨跌按全部退出的加权平均退出价，不是最终日成交均价。
- 额外潜在边界：canonical同日exit_date再按无补零lot_id词法排序；若同entry同日多段跨数字位数，可能终段错序。旧canonical不改，081逐笔按原始fill顺序独立核final exit_price/date/marker，实际发生就fail closed。v2源当前1313完整entry中8项含2次退出，8项退出均跨不同日期，故此次不触发同日排序边界；待records全量再核。
- TDD三项先RED后GREEN（0.942s）；再补Node JS验证，联081共7项PASS（2.595s）。覆盖两处限定替换的可逆证明、披露、重复/合同变化拒绝、实际final marker与加权价区分、完整冻结fixture全非HTML字节相同、输入tamper/覆盖拒绝、Node --check。
- 081相应只在071/final检查修复后label，中间063 canonical未修复页仍检查所有金融meta/图数据，不把中间标签误判为最终结果；新增源fill顺序的actual entry/final-exit日期/价/marker全量校验。071/072冻结SHA不变。

```json
{
  "stage083_final_multilot_labels.py": "d4ab4471ec71297ddc3938bf5e687ff42227845f2ffd07cc07d81eb2745d8571",
  "test_stage083_final_multilot_labels.py": "ced9fff14ee96c45a8acb5fbbf397ca576bf30e26c01ae069f8790f6bc99fd0b",
  "stage081_validate_fractional_display.py": "843e7bdcc8ffe3014d34e8195003a0dcbcf5cdf395ce7e06a9255318b4d38f52"
}
```

实际命令：`/Users/mac/Desktop/fian/.py311/bin/python research/lines/futures_trend_full_market_noai_one_lot/tools/stage083_final_multilot_labels.py --parent <020 reviewed> --output <全新labels目录>`；随后root调用067，再072总览。

当前新v2金融已完整退出，源manifest b5357eef7ec6f3ce9a844bfbf680b7eb5fe24e4fb6e91dec6e87f6ea56933635。081独立source-only展示预核PASS：1321实际开仓收据、1313完整entry/10644合约手数、8残仓/58手、无残仓已实现片段；完整entry中另有8项分2次退出。此为显示计量/数据闭包，不替代独立金融080审查或最终HTML验收。源/基线完整hash、全部fill费用397578.07237591373及剩余entry费用分配1066.4024799999393闭合，未金融回跑；真实HTML尚待025。独立预核JSON为20261020_0055_stage081_v2_source_display_preflight.json。

新增/修改/删除金融参数和结果：无；无下载/生产/订单/Git/LINE操作。过拟合：否，纯展示语义修正且不按收益选参；继续价值：是，避免多手量与费用误读，不把渲染成功当作晋级。
