# Stage250 原始现货历史归档工具（仅源码与模拟验证）

- 时间：2026-10-19 22:14（Asia/Shanghai）。研究线：`futures_full_market_long_signal_ai`。
- 性质：原始来源归档实现，不是模型或收益突破；本阶段尚未联网运行。
- 来源与判断：沿 Stage242–249 已接受的生意社原网页来源证据与 Stage246 的 stdlib urllib 保存方式，参数全部读取冻结249协议；不再扩展来源研究。原始归档有继续价值，但 HTTP 成功不代表有效报价、连续历史或历史时点可用性。
- 新增：`tools/stage250_raw_spot_archive.py` 与四项模拟传输检查。一次调用最多250个新日期、最多2并发，全局启动间隔至少0.75秒；无重试、无最新页回退、无自动下一批。9个已接受原文仅继承绑定，不重读重哈希。
- 持久化：HTTP前先原子保存开始记录；完成终态、原始body/错误/截断/重定向信息分别保留；中断的既有尝试转为 `attempted_unknown`，以后不自动重新获取。独占锁与新批次目录防止重复执行。
- 修正：独立预审指出慢 fsync 可能消耗启动间隔；限速基准改为持久化写入返回后的 dispatch 时刻，原 spacing 检查加入0.9秒慢写反例。
- 验证：初始4项 RED→GREEN（0.090秒）；限速修正后只单独复验原 spacing 方法，GREEN（0.056秒），其余3项不重跑。中间单方法断言因浮点相减得到0.7499999999999999而失败，改为等价的 `t2 >= t1 + 0.75` 后通过，完整终端保存在 `implementation/fixture_terminal.json`。
- 冻结：工具 SHA `b9236cb60933deee5fdad45c387c999154340c3e5345e1c8bd9bfd06ea624bea`；测试 SHA `505d3565539c8bc7f35956fc1b9223227d0454541a03c36251c138996f153ea7`；`outputs/stage250_full_raw_spot_archive/implementation/source_bundle.json` SHA `f5139b786227f8a36bf3366d814ebc49a8b05418a6d16a913a2ea57a9abbac07`。
- 计数：本阶段0 HTTP、0 fit、0 cash、0 SQL、0旧suite；累计439 fit / 234 cash。未新增/修改/删除回测结果，权益、收益、回撤、Sharpe、交易次数和胜率均不适用。
- 过拟合反思：否，操作仅保存预先冻结日期的原文，不读取标签、不选择策略参数；来源口径与历史时点资格仍需后续证据。
- 下一步：独立源码预审解除后，由root唯一执行 `--batch-id batch001 --limit 250`；本作者不启动实际网络。
