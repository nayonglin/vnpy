# Stage024 启动前盈余资金组件：作者交接

- 时间：2026-11-02 14:13（北京时间）。研究线：`futures_weekly_short_ma_slope_gate`。
- 用户已允许以当前真实权益作为新启动账户，并将相对15万元本金的差额作启动前盈余口径；不能把该授权写成已验证的历史策略收益。
- 重要突破版本：否。仅增加显式会计基线政策；无信号、alpha、原风险手数、MRO或金融回测变化。后续由root冻结新m4，既有m3与历史release不覆盖。
- 作者写边界：funding.py、新test_weekly19_opening_surplus.py；root额外明确授权funding_store.py的最小前向guard调用。未修改backend、runtime、pipeline、SOP、manifest、注册表、生产或Git/index。
- 本文与Git测试只使用合成fixture。没有读取或保存真实账户金额、成交、账号、凭证或私有资金状态。

## API与精确状态合同

```python
begin_cash_observation(state, broker, now, *,
    opening_equity_mode='exact_150k', operator_decision_id=None) -> next_state
assert_opening_equity_forward(current, following) -> None
```

失败均为FundingError（ValueError）。函数不修改输入，不发送委托、不转资、不修改broker Balance/Available。

默认exact_150k保留原严格金额与状态字节，不新增opening_equity字段。显式operator_existing_account_v1要求SHA256格式operator_decision_id及同账户/release、完整、fresh、aware-time、CNY原始CTP账户envelope；真实E必须正，单位为整数分，上限2**63-1。允许E低于本金，signed差额可负，不能因这个记录虚增E。Available仍要求原始合法非负十进制；完整查询/rawSHA/账户/时序门不变。

只有新mode在state新增以下严格exact-keys对象：

| opening_equity字段 | 语义 |
| --- | --- |
| schema | weekly19.opening-equity.v1 |
| mode | operator_existing_account_v1 |
| source_kind | operator_manual，不冒认自动broker/HMAC确认 |
| classification | operator_designated_pre_start_surplus |
| operator_decision_id | 显式不可变人工政策决定引用SHA；本纯组件校格式，决定本体与生产政策绑定由caller负责 |
| baseline_trading_fen | 原15万元本金锚，不改后续funding floor |
| observed_equity_fen | 原始账户Balance严格转整数分，真实正E |
| opening_surplus_fen | observed_equity_fen - baseline_trading_fen，允许负数，不是T或已验证PnL |
| verified_strategy_pnl | 恒False |
| baseline_checkpoint | 原5字段trading_day/observed_at/raw_sha256/deposit_fen/withdraw_fen |
| broker_account | 原raw_payload/raw_sha256，仅私有持久状态保存原始绑定；不新增source_qualified |
| accepted_at | 原始基线受理时钟，aware ISO；不会在后续读取时续期 |

state schema仍为external-funding.v2。R保持初始场外备用金、T=0、requests/receipts/admissions为空；initial_trading_fen与reserve_initial_fen保持原值。初始化已有gross Deposit/Withdraw作为checkpoint基线，不扣R、不转为补资、不当利润。后续recommend_topup原15万floor及confirm/manual现金守恒流程均未改。

validate_state完整重核新对象字段、strict整数/正E范围/signed差额桥、原始raw与账号/release、原初受理时效、checkpoint/日切链不倒退及request baseline不早于opening。该历史基线不代替任何后续fresh实际账户门；既有来源资格仍由生产caller独立验证，state恒production_qualified=False。

## 同actor/CAS边界

- 同一初始source与同mode/decision再次调用begin，返回相同状态/revision/字节；不刷新accepted_at。
- 首次新mode只能从revision0、未观察现金、无资金活动的初态产生一笔fund revision。不能把旧exact已观察状态临时改为该mode，不能夹带recommend/receipt等其他fund活动。
- 已存在opening对象后，forward helper要求逐字语义相同，拒删除、改mode/decision或替换另一套自洽基线。仅靠单个可选字段validator不能识别“从旧状态删除该字段”，实际不可回滚由前向CAS硬门保证。
- FundingStore只增加导入及_forward_ledger调用，正常commit与journal recovery共享；旧无opening->无opening直接兼容。
- root/runtime owner将把同一helper接入实际PipelineStateStore和Runtime的前向入口，并把这唯一fund转移与verified bootstrap runtime同actor原子存。该外层接线不由本20单测冒称已审；本组件也不建立外部仓的entry/stop/ownership。

## TDD与证据

1. 修改生产源码前，冻结默认exact合成样本canonical SHA为`778f9e43850d0633173780bd70303cf8391ed83c95745cb4a5ad8984c5d48193`，新测试再次核对一致。
2. RED：`/private/tmp/weekly19_Stage024_funds_red.log`，19项中18失败/1通过，明确为缺显式API；保留旧默认兼容正例。
3. 首轮新19项GREEN：`/private/tmp/weekly19_Stage024_funds_green_attempt001.log`，0.017s。
4. 原fund/manual相关回归：`/private/tmp/weekly19_Stage024_funds_related_attempt001.log`，107项通过，1.100s。
5. 补充实际FundingStore journal恢复替换基线拒绝与合法int64上界，最终`/private/tmp/weekly19_Stage024_funds_related_attempt002.log`：108项通过（20新用例+88原fund/manual），1.079s。
6. 3文件compile与尾空格检查通过。无金融回测/真实CTP连接/SMTP/订单/撤单/转资/安装；临时目录仅保存合成测试state。

最终命令：

```sh
PYTHONPATH=tests:examples/portfolio_backtesting .py311/bin/python -m unittest tests.test_weekly19_opening_surplus tests.test_weekly19_external_funding tests.test_weekly19_manual_cash -q
```

覆盖：正/零/负/上界E、负差额、错误mode/decision、账号/release/rawSHA/query/freshness、输入不变、幂等/模式与基线重置、初始化Deposit不得二次T、后续原floor建议、真实新增receipt与重复receipt、持久对象损坏、现金链回退、原自动fixture/人工跨日、实际private store commit/recovery自洽替换、删opening/换decision/旧exact加policy拒绝。

## LOCK与独立交接

| 文件 | 当前SHA256 |
| --- | --- |
| examples/portfolio_backtesting/qmt_roll_weekly19_funding.py | 5fdaa73e81d2503ba35dc78575167c8e21af6f1cbd614b8015af908bd6bb9609 |
| examples/portfolio_backtesting/qmt_roll_weekly19_funding_store.py | 2f36685376bf96c4b3a3349c71fa254cbdd338296c858753bdf73ba7fd39f78a |
| tests/test_weekly19_opening_surplus.py | 2422937b51f186108d86fed76ab956995ef0ace394f59d012925aa0beb790c7a |

已把精确合同、SHA与日志交root、runtime owner和独审。作者不再改这3文件，独审发现先通知root受控解锁，保留旧证据。root负责新m4身份、完整CI、生产来源与安装；离线通过不是production qualification。

## 调研、判断与后续

对照[Python 3.11 Decimal官方说明](https://docs.python.org/3.11/library/decimal.html)，采用已有严格十进制解析后整数分计算，避免binary float损害等式守恒；没有引入新的余额推导、自动银行或结算producer。新增政策属于会计启动边界，不属于alpha优化。

新增参数仅opening_equity_mode/operator_decision_id；默认不变。没有删除参数；补资阈值、R/T金额守恒、真实权益/Available来源均不改。无新增/修改/删除回测结果，期末权益/收益/回撤/Sharpe/交易次数等均不适用。

过拟合：否，不重算或筛选策略表现。继续价值：是，以不可变来源基线诚实区分启动前差额、新策略后续盈亏与真实补资；后续只需完成外层同actor接线、独审及新物料流程，不继续开发用户已取消的自动银行/最终结算producer。

## 独立组件复验回执

独审已在`Stage024_review_root_components_attempt002.json`独立执行本新opening20测试通过，并与startup14、原入口5及额外坏形状/CLI3合计42调用全绿；11文件前后SHA无漂移。回执SHA为`c301fa9a4e049dc885a9340bdbcd632f3333135cd31f212f1cd8651aa120f1b3`。所审fund/store未发现新增P0/P1，仅为partial组件scope；runtime/adoption与整链恢复/实际生产资格仍由后续新source验收，未因此宣称已安装或通过真实资格。
