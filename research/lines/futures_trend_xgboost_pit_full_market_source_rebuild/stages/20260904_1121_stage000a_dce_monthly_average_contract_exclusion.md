# Stage000A 大商所月均合约目录分类澄清

- line_id：`futures_trend_xgboost_pit_full_market_source_rebuild`
- 当前模式：day
- 记录时间：2026-09-04 11:21 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `codex/stage130-option-probe`
- 阶段性质：Stage001首次prepare失败后的供应商合约身份分类修复；不是覆盖结果、模型、标签或回测。
- 是否重要突破：否。
- 是否触发A/B：否。

## 首次prepare失败证据

- 获授权命令：`.py311/bin/python .../stage001_full_market_source_rebuild.py --phase prepare --authorized-data-rebuild`。
- 截止日目录原始返回：`4,855`个 `CZCE/DCE/GFEX/INE/SHFE` `FUTURE` 标识。
- 失败位置：目录规范化在任何映射、增量日线或覆盖审计之前停止。
- 原错误：`catalog_contract_symbol_invalid:DCE.l2602F`。
- prepare receipt：未生成。
- 增量日线：未下载。
- 标签、模型、策略回测、CTP、订单API、生产写入：全部0。

## 根因调查

- 对同一截止日目录重新做只读诊断，非普通 `[品种][3/4位年月]` 格式共`33`个，后缀全部为`F`。
- 33个标识只涉及大商所 `l/pp/v`，`instrument_name`全部明确为“月均塑料/月均PP/月均PVC”，例如 `DCE.l2602F`、`DCE.pp2602F`、`DCE.v2602F`。
- 它们与普通交割月合约共享 `product_id` 和 `delivery_year/month`，若直接纳入同日期限曲线，会把非标准月均变体与普通合约混在同一到期月，破坏“具体标准合约曲线”的身份合同。
- 其余未知后缀模式数量为0；不是目录普遍格式变化。

## 单一修复

- 仅在普通合约正则校验前排除精确模式 `exchange=DCE` 且 `symbol=[A-Za-z]+[0-9]{3,4}F`。
- 排除列表写入 prepare receipt 的 `catalog_exclusions.dce_monthly_average_contracts`，不得静默丢弃。
- 任何其他未知合约格式仍抛出 `catalog_contract_symbol_invalid`。
- 不修改数据区间、交易所范围、主力映射、252/241/90%/2合约、30品种、36月或10挑战者硬门。

## TDD与实现身份

- 红灯：把 `DCE.l2602F` 加入目录fixture后，6项依赖目录规范化的测试按原错误失败。
- 绿灯：加入精确排除规则并新增未知格式拒绝测试后，限定测试 `18 passed`。
- 修复后纯数据合同 SHA256=`5ec652e7ca6d562f44a5112b602e6f849369bde2fbd1ac0f603e4a71dfdb99a7`。
- 修复后runner SHA256=`405a92fc52bc7fd6de9f4561e2a3d00aea6711893879b1ab3982b62f72427c27`。
- 修复后核心测试 SHA256=`16ed4301912230e3e794743f8f4f930aa02dbdbc4b61d8b4a65a7b43177a3e19`。

## 结论

- 本阶段结论：失败由供应商目录包含明确命名的非标准月均期货变体导致，不是源不可用或覆盖门失败。精确排除不会利用任何收益、标签或覆盖结果。
- 是否进入下一步：是；按原授权、原截止日和原硬门重跑 `prepare`。
- 下一步：prepare receipt 必须显示恰好33个被排除月均标识；若出现其他未知格式，继续失败停止。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：分类只依据截止日API的合约代码和中文名称，发生在映射、行情和覆盖计算之前；没有查看任何收益或调整效果门。

## 继续价值反思

- 运行前判断：有。
- 运行后判断：有。
- 原因：根因边界精确、修复自由度为一个供应商合约变体类别，且原研究门完全未变；重跑prepare可以直接验证分类是否完整。
