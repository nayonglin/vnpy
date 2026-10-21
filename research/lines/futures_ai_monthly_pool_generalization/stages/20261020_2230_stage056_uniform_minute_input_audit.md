# Stage056 132精确需求的统一实际分钟输入audit

- line_id：futures_ai_monthly_pool_generalization；2026-10-20 22:30 CST；输入机制进展，非收益突破。不改055/源/LINE/registry。
- 实际pilot前协议已冻：outputs/stage056_uniform_minute_input_audit/protocol.md。只审052 exactheld需求，055当前范围132/320窗、778范围外保留，不硬套旧2020+ schedule到全部历史/新产品。

## 实现与实际结果

新增tools/stage056_uniform_minute_input_audit.py及7项测试。exactepoch以Stage006月份/orderbookid、vendor native及source日期寿命绑定payload实键，CZCE年代不靠短码；broker资格不提升。每小file单次raw读取/SHA/内存列投影、单provider独立session envelope，原完整expected不缩、不拼source、不补timestamp、不改价格。开跑逐key核052 state OHLC与当前clean一致；055前后SHA 9736b1b0a362e4a12b2c7839db067c59e0a3b430be0c65c384f2a4433ba9d8c2相同。

首个pilot selector误把旧incomplete证据中的排除大CSV排序在前，scope guard拒绝，未打开大CSV。失败run/源码/计划/receipt保留，先增回归见红再修selector限定冻结428路径。正式成功pilot5case/4唯一小file：2完整、1部分缺格、2空session；缓存小pilot file给full复用。失败尝试已经读过部分小pilot文件，因此只声称正式full内部每CSV一次，不伪称多次尝试合计一次。

22:28:26–29统一全batch：428小CSV/331962462 bytes/3267045行投影+10 SQLite native索引投影，最大单CSV6.8MB。531 source-component审计=128条件通过、66日OHLC冲突、15缺格、322 session envelope无行。117/132需求有条件数据输入，关联287首阻塞月窗；15/33窗无合格输入。128 source members按完整minute输入hash去重为117路径，无不同passed输入分歧；同数据所有provenance保留。221MB聚合CSV未读取。

当前完整run为outputs/stage056_uniform_minute_input_audit/run_20261020_222826_843552。manifest列requirement/state、数据CSV及SHA、canonical input SHA、全部source_ids/bindings、expected grid/055 SHA、源daily OHLC/entry open/exact metadata身份。所有通过/拒绝/unsupported保留。physical/session/broker/usable_for_trading均False。该117不是新增完整60日标签、287不是独立训练经验。

## 验证、反思与下一步

7项TDD/回归通过，全线173 tests通过；057实际独审已请求，自测不冒充独审。058 adapter可读manifest，但057 go前暂不注入source，且不得改变minute_paths/receipt之外原字段。后续仍须统一C2/reference replay和未知传播，不能把数据输入通过直接变类别标签。

权益、总收益、DD、Sharpe、总滑点、交易次数、胜率N/A；正式/模型alpha参数新增修改删除0。策略运行、C2 outcome、模型fit、labels changed、下载、订单、生产修改均0。

开始/结束新增按收益调参过拟合否：只按既定metadata/helper规则审全部132，不按收益、old accepted或OOS第三块选case；继续价值是，首阻塞资料覆盖可审，但还无模型/收益改善证据。正式A/C仍因身份缺项不跑。
