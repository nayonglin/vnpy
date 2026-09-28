# Stage001换月标签可成交性资格计划

## Task 1：审计核心TDD

- [x] RED：endpoint正成交/正持仓通过，0或非有限值失败。
- [x] RED：单一合约路径只生成entry和exit事件，不为中间持有日重复造订单。
- [x] RED：换月边界生成roll_close与roll_open两个1手事件，合约身份分别正确。
- [x] RED：volume/OI恰好100通过，任一99失败；百分比计算可手算。

## Task 2：Stage001 runner

- [x] 验证上游filename manifest与source path manifest，冻结输入SHA。
- [x] 发布endpoint审计、执行事件、路径汇总、失败明细与summary；不打开close。
- [x] 合成发布/verify-only测试、跨线回归`89 passed`且py_compile通过。

## Task 3：唯一执行与记录

- [ ] 生成一次性authorization receipt，唯一`--run`和`--verify-only`。
- [ ] 中文记录全量失败结构并更新LINE/registry；无回测则不拉独立回测reviewer。
- [ ] 通过才允许标签值预注册；失败则关闭本标签路径，不按结果调门。
