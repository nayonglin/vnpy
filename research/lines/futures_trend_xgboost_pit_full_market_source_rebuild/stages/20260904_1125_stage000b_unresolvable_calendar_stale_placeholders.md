# Stage000B 主力日历不可解析陈旧占位处理

- line_id：`futures_trend_xgboost_pit_full_market_source_rebuild`
- 当前模式：day
- 记录时间：2026-09-04 11:25 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `codex/stage130-option-probe`
- 阶段性质：Stage001第二次prepare失败后的供应商日历身份澄清；不是覆盖结果、模型、标签或回测。
- 是否重要突破：否。
- 是否触发A/B：否。

## 第二次prepare失败证据

- Stage000A修复后重跑prepare，截止日目录查询完成，随后在主力日历身份检查失败。
- 原错误：`mapping_contract_not_in_catalog:CZCE.LR605`。
- prepare receipt：仍未生成。
- 增量日线：仍未下载。
- 标签、模型、策略回测、CTP、订单API、生产写入：全部0。

## 根因调查

- 截止日目录 `query_quotes(product_id=LR)` 不含 `CZCE.LR605`，旧TqSdk归档也无该文件；直接 `query_symbol_info(CZCE.LR605)` 返回不存在。
- 但精确区间 `TqContCalendar` 在 `2021-01-18..2021-04-08` 共53个交易日持续返回 `CZCE.LR605`，属于品种停滞期间保留的旧主力值，不是该日期可解析的具体合约。
- 对80个商品连续品种、1,318个日历日期做全量对比，只有两类不可解析占位：
  - `KQ.m@CZCE.LR -> CZCE.LR605`：53行，`2021-01-18..2021-04-08`。
  - `KQ.m@DCE.bb -> DCE.bb2101`：53行，`2021-01-18..2021-04-08`。
- 不可解析品种数2、总行数106；其他日历非空值全部存在于截止日目录。

## 单一修复

- 映射产物新增 `calendar_main_contract_tq` 和 `mapping_resolution`。
- 对目录可解析值：`mapping_resolution=resolved`，正常写入 `main_contract_tq/vt`。
- 对日历空值：`mapping_resolution=vendor_blank`，主力映射保持空。
- 对不可解析陈旧值：保留原值到 `calendar_main_contract_tq`，但把可执行 `main_contract_tq/vt` 置空，`mapping_resolution=unresolved_not_in_asof_catalog`；不得邻日回填或猜测合约。
- runner固定期望不可解析集合恰为 `{CZCE.LR605, DCE.bb2101}`；出现任何第三种身份或集合变化即失败停止。
- 不修改数据区间、交易所、映射历史门、日线门、曲线门、30品种、36月或10挑战者门。

## TDD与实现身份

- 红灯：把未知日历合约测试从“抛错”改为“保留原值、可执行映射置空”后，原实现1项失败。
- 绿灯：加入保守空值转换和runner固定身份门后，限定测试 `18 passed`。
- 修复后纯数据合同 SHA256=`fe6f576bf5ab39b3df312214778bf78b1b727d74ddd9d45259b2051c248bfa73`。
- 修复后runner SHA256=`dedcd2f166263a5b72240dc67094967d3e06f9bee45d3df6ad2f6ed1de7fff91`。
- 修复后核心测试 SHA256=`acf26abf0290acacf62ca370c0becdd0904badb44c8246b87864a7f673a862e9`。

## 结论

- 本阶段结论：两个冲突都是供应商日历对停滞品种保留旧主力值，不能构成可执行PIT映射。置空是保守缺失处理，只会降低资格，不会增加覆盖或收益。
- 是否进入下一步：是；按原授权和原硬门第三次运行prepare。
- 架构停止线：若再次出现新的目录/日历身份冲突，不继续追加例外，停止并重新评估TqContCalendar是否适合作为统一映射生产者。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：处理依据目录可解析性和固定日期范围，发生在日线与覆盖计算之前；不可解析值被置空而非补成有利数据。

## 继续价值反思

- 运行前判断：有。
- 运行后判断：有条件。
- 原因：异常全集已全量枚举且只有两个固定身份，保守处理不放宽门；若第三次prepare仍出现新的身份问题，继续打补丁的价值将转负。
