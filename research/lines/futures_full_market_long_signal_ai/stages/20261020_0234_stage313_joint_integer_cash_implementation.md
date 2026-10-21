# Stage313：同批整数分配的四本现金adapter实施

- 时间：2026-10-20 02:34 CST；line_id=`futures_full_market_long_signal_ai`；非重要突破，仅新源码实施，**0actual、0fit/cash、0SQL/network、0实际大表读取**。
- 冻结311：`outputs/stage311_joint_integer_budget_protocol/protocol.json`，SHA `f97b23b7732a9ff97272cd793e4ed6c42dc60df6377543d0ab8bcfee527e1259`；candidate=`JOINT_INTEGER_SCORE_BUDGET`。
- 科学判断及外部依据沿303/310/311，不重复调研或改结论：原核联合比例，非先到先得bug；新政策仅检验score代理目标、同时整数资源和整数冻结预算的完整包。score不是概率或已校准现金期望，保留历史适应性与数值求解限制。

## 新接线与数据边界

新增 `tools/stage313_joint_integer_cash.py`，复用已接受307的四book调度与财务/费用/滑点/闭合净胜率、开放/unknown/stale/集中度、全family-year含0、年度及070固定2000/block252配对daily-log统计。旧157四控制只读取摘要/daily/已接受报告，0重放。

直接一次读取原157 `signals_VOLUNTARY_RESELECT.csv.gz`（4365行、583263B，SHA `c7546f99a0ce40adbc2a1772cb1ea66eb280e1ab98303c3d7b4ddbd7f35f9732`），先`dtype=str`，数值逐字段直接float/int恢复；保留其它原literal，K pending空值为NaN，不捏造日历末日。base和stress共用该原冻结stress score，不重评分。不读129actions334MB、306choices、新模型、训练、标签或完整score，不调用旧selector/make_signals。

实际时仅原mother7身份列一次、132 accepted native cache恢复一次、economic projection一次；所有book复用同一market/economics/prepared。`prepared=v.author.organize(signals,mothers,dates)`；312 API显式传`base_kernel=v.kernel`，不以另一个独立131实例代替。原内部`VOLUNTARY_RESELECT`信号schema不改，外部账户、摘要和manifest统一新candidate。

原131 `make_signals:97–123`已规定score正、ready/potential=1、有限low20和正N，以及family/u信号唯一；157 `make_voluntary_signals:96–98`继承后只添加K。313相应断言是持久化合同验证，不是新候选筛选。source_read_receipt记录4365/399252、单次源读和0重算。132恢复只做accepted cache/数据库stat与原恢复方法的单流缓存完整性读取，不做SQL或单独大表prehash。

## audit、失败与名义门

312每个prepare/reserve批次的`allocation_audit`完整导出为各book `allocation_audit.jsonl.gz`（level1），含空批次、未触发同状态old/actual rows、触发problem/solution/全部solver阶段。`allocation_diagnostics.json`和顶层`allocation_summary.json`保存batch/trigger/quantity/freezing变化/solver/解析解计数。old reservations仅作同状态诊断，不当历史控制重放。真实D减量/取消仍在原budget账。

若312异常附带allocation_audit，313落`failed_allocation_audit.jsonl.gz`及失败receipt后原样raise，终态failed，不把失败账计为completed，不fallback/retry，不再启动后续book。已完成账与失败现场均保留。

根授权要求exact311/new312+313 source/test/freshoutput/max0fit/max4cash。100万初资，2020连续与2023空仓各base/stress至2026-10-16。双stress期末权益严格更高且DD严格更浅共四谓词才名义通过；base与CI描述，unknown/stale另报，不能当金融资格、alpha或生产证明。本阶段未启动这些账本。

## 新fixture及源码冻结

仅两个必要合成方法，先RED（2 failures），再GREEN（2 tests/0.011s）；312精确module名接定后最终同两方法GREEN0.011s。没有旧suite、作者312求解器调用或真实cash内核调用。第二方法的2次stub callback/1次模拟完成只验证失败调度，不是研究现金次数。

1. 原数字token末位/内部身份不漂移，pending K空值保留，母anchor不被改写。
2. 第二次stub allocator失败时保存完整audit、started2/completed1、failed终态、不第三次启动或重试。

| 自有冻结文件 | bytes | SHA256 |
| --- | ---: | --- |
| stage313_joint_integer_cash.py | 22666 | `95a79f610f967209f88dc580c94a5091d15d943bf88ab2e99f4d406fe9f9aa96` |
| test_stage313_joint_integer_cash.py | 4584 | `edc48873120f0fb0f5d81f505769c447191d8f449c71631b9d1fe7d2ef5e5769` |
| implementation/fixture_terminal.json | 3657 | `8f0ea11e85bd6151de9bce674837f09b73818c91ba2442e168fd3b51e6607756` |
| implementation/input_bindings.json | 9916 | `07ceea8af02c70f61d1297a153573a7001408f381b05e88c6895c9c55d7bd085` |

implementation文件在 `outputs/stage313_joint_integer_cash/implementation/`。312最终两份binding已闭合，四文件source_bundle与root授权模板已冻结；314已一次静读313 final source/test，未见适配器核心阻断，不重跑作者tiny，统一独审receipt待其312检查完成。工具不另建静审资格schema，root仍须在真实314接受后签发actual授权。

| 最终implementation文件 | bytes | SHA256 |
| --- | ---: | --- |
| source_bundle.json | 5293 | `fa94323d083c56efecad0cd55867b3bbf6033157c93e5c5d016db33b37dff6e8` |
| authorization_template.json | 1856 | `703fc40f285d24c472202652c9bf7648089cd93ffcf5fdc33b51256401f45602` |
| implementation_receipt.json | 2419 | `0a694cd91ecc3ea4851003b5ff36b29c3b38f10daf7bd2e3598d729b210e08de` |

312 source/test分别绑定`f8113be2f68a45875dcf35d6624fe56d3f0008c32dbd0b50af8507e27a14898a` / `ec794ca2072a56bad6929313890a1c42a772923a5a3339e0f92143f44784efbf`，没有由313重跑其tests。实际唯一CLI由root另授，作者不执行：

```sh
.py311/bin/python research/lines/futures_full_market_long_signal_ai/tools/stage313_joint_integer_cash.py \
  --protocol research/lines/futures_full_market_long_signal_ai/outputs/stage311_joint_integer_budget_protocol/protocol.json \
  --protocol-sha256 f97b23b7732a9ff97272cd793e4ed6c42dc60df6377543d0ab8bcfee527e1259 \
  --authorization <root_final_authorization.json> \
  --authorization-sha256 <root_final_authorization_sha256> \
  --output research/lines/futures_full_market_long_signal_ai/outputs/stage313_joint_integer_cash/actual_run1
```

新增/修改/删除金融参数和结果均0；权益/收益/DD/Sharpe/滑点/交易次数/胜率N/A。过拟合：本实施未用新结果调参数，历史自适应研究风险是；继续价值仅为311固定包一次有限反证，用户完整收益/DD目标未完成。不改LINE/registry/旧source或生产；等待312/314及root唯一actual，失败不救参。
