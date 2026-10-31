# Stage016 runtime restart P1修复

- line_id：futures_weekly_short_ma_slope_gate；day；时间：2026-10-31T17:18:30.284310+08:00。
- 不覆盖1712原封批次，原金融、565AST、31冻结源与b473e88f21d2d139615e638c9df0e0fac5358596d919624f55411438926a303c manifest不改。
- root集成发现：fresh broker已经包含restart期间尚未本地入账真实fills，旧constructor在应用事件前对账会因仓位不匹配失败。禁止构造savedpos+freshaccount假envelope绕过。
- 修复：build/Runtime新增recovery_events=()纯参数；仅已有durable state可以使用；所有fill必须匹配durable原planned signal identity，按execution time和稳定tradeID排序先apply真实fills，再apply累计orders，最后与未经篡改fresh broker positions对账。调用既有严格raw/source/semantic/volume/cost校验，重复无经济副作用。任何中途失败不返回成功runtime，根transaction不落地。
- meaningful反例：旧saved pending plan为0实际仓，而fresh query为1真实手；无recovery仍拒绝；填入真实partial fill+order（故意order放前）后正确恢复1手、真实成交成本及fresh broker E149999；重复restart无重复记仓。无saved state导入外来事件直接拒绝。
- 新增/修改/删除交易参数：无；只新增恢复事件入口。无金融回测或生产/CTP/API操作，production_qualified=false。
- 验证：owned28tests绿（含565 AST条目）；日志：20261031_1718_stage016_runtime_recovery_tests.log。仍须独立review与真实capture资格；不能把fixture当真实provider。
- 过拟合：否，修恢复次序而非调alpha；继续价值：是，普通restart闭环必要。

```json
{
  "examples/portfolio_backtesting/qmt_roll_weekly19_runtime.py": "784dfef6cb75ed0a3352c03ee44cb6554334781f06decf72fe2e389b8a0bf62a",
  "tests/test_weekly19_runtime.py": "709b9ee071fd1484c9b442d2ab1927e4f96c28ef2312b67c9d367baf83d208cf",
  "tests/test_weekly19_strategy_equivalence.py": "ef03927995ea9c7cec41f43952f08c58d99700b64f786017bfaf89c46ba025cd"
}
```
