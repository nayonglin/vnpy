# Stage085 全母体真实epoch滞后OI源投影实现

- line_id：`futures_full_market_long_signal_ai`；2026-10-18 17:48 CST；沿现checkout/分支，无新worktree。
- 重要突破：否；实际SQL/fit/cash/新label/下载/整DB-H5 hash均0；累计333fit/70cash不变，目标active未达成。
- 仅新增本085源码/新测试/outputs与本唯一stage，不改旧源/旧结果/LINE/registry/其他线/正式版。

已先读根AGENTS/registry、本线078与084冻结记录/协议、084收益前clarifications、Stage266固定unit_contract与cleaner的精确schema/数量转换段；没有SQL/schema probe、H5或原raw读取。本次只窄核[CME OI定义](https://www.cmegroup.com/education/lessons/open-interest)和[TqSdk维护方字段入口](https://github.com/shinnytech/tqsdk-python/blob/master/tqsdk/api.py)，没有重复批量研究或下载。判断：OI是日终未平仓匹配存量，不能当净多资金；来源/单位存在不证明预测性，只实施一次固定连续标量的来源准备，不复活旧价格×OI确认规则。

唯一source公式是e=原reference_epoch(u)，v/w为冻结完整source calendar的u-1/u-2，x=(close_oi(e,v)-close_oi(e,w))/volume(e,v)。始终查当前真实e的两日，即使e当时尚非代表；缺严格lag日不跳到别的有价日，不用前日代表替代，不跨source_id差分。OI有限非负、V_v有限正，真零/同为零合法；不读openOI，不硬加abs(deltaOI)<=V、不裁剪/填补/插值/carry、不调整模型/标签/风险/现金。

消费Stage266已经canonical单边的V/closeOI，factor仅作证据与一致性检查，绝不重复除2。RQ沿固定exchange/date单位规则，已证明.5→1的canonical制度转换可以比较。TQ固定单边；official继承stat-bound Stage266的已接受canonical资格，只核合同允许的.5/1且V/OI因子一致，不按年份猜制度，不因DB不存在raw unit_regime而拒绝已接受行，不重建原raw资格。真正未知factor/source family/quality/数值保留missing原因。输出使用unit_rule_id和unit_state，不伪造raw unit_regime字段。

实现stage085_oi_projection.py提供纯build_projection与隔离actual CLI。future actual只一次readonly immutable SELECT，LEFT JOIN sources.family，同时取必要closeOI/V/factor/原数量/locator，不读取OHLC/openOI或整库hash；仅读已绑定070NARROW身份、052 calendar/database与unit_contract。SQL可扫描既定完整范围，只保留母体所需e-v/w键于内存，不导出全native。DB用bytes/mtime/inode/WAL/SHM stat与继承SHA绑定，绝不写旧DB。

已与086并行作者冻结接口：`outputs/stage085_oi_projection/experiment/oi_projection.csv.gz`完整399252行同原顺序，identity为sequence_index/event_id/product_id/family_id/exchange/u_date/u_index/reference_epoch；v/w date/index/source_id/source_family/factor/unit_state/unit_rule_id/quality/locator/原与canonical数量全部保留。consumer列为oi_scalar_raw、oi_missing、oi_observed、projection_state、missing_reason；成功state observed_same_epoch_same_source_canonical，合法0保留为观测，缺失scalar null且共享mask1，source层不以ready/经济/标签状态筛行。086预测161014完整母体、ready仅动作门，由另一owner实现。

future manifest schema stage085_oi_projection_v1，status completed/mode actual、protocol与implementation_clarifications精确绑定、projection/terminal/source_read_receipt file binding；mother_rows399252/native_source_queries1/actual_model_fit_calls0/new_cash_accounts0/new_labels0。terminal使用status/exit_code/completed_projection_rows与计数，不加冗余completed bool。有限first source cases、分交易所年/原因coverage与summary均来自同次数组，供0额外SQL初核；全面独审另由root084给一次OI列SQL预算，不在本实现擅自使用。

TDD先观察7测试方法缺实现失败，再实现后7项全部绿（0.020秒）：同e换代表/缺w不借旧epoch、严格lag缺日、同source、真零/openOI缺失不相关、无效V、未知因子和canonical跨制度不二次转换。只运行test_stage085_oi_projection.py，0旧suite/大probe。精确源码/测试/CLI/接口/终态约定在outputs/stage085_oi_projection/implementation_receipt.json与proposed_commands.txt。root精确source/protocol/clarifications/freshdir授权之前不运行实际；失败保留且无自动修复重试。root另交088一次聚焦code preflight。

新增研究观测1、正式交易参数新增/修改/删除0；新增金融结果/旧结果改删0。期末权益/收益/DD/Sharpe/滑点/交易次数/胜率均N/A。

开始/结束新增按新收益调参过拟合：否，公式/lag/同源/单位与母体已先固定，当前无新金融成绩、不会按覆盖率强迫完美补源；既有择题风险仍在。继续有价值：是，限固定信息对照所需的一次来源投影，OI先验偏弱，来源合格不等于收益进展。整体目标仍active，不据本实现声称改善或完成。

17:51 一次实际源投影完成：root在088 source preflight C/I0及fresh源码/测试/084协议/clarifications后签精确授权；owner唯一执行，24.653308秒exit0。完整399252行保持原身份/顺序；actual source SELECT1、fit0/cash0/新label0/download0/整DB-H5 hash0，无修复或重试。累计333fit/70cash不变，数据源准备不计金融成绩。

| 源投影状态 | 行数 |
|---|---:|
| 完整母体 | 399,252 |
| 可观测 | 206,012 |
| 缺失 | 193,240 |
| 可观测且真实零 | 1,826 |

缺失原因全保留：different_source_id803；missing_v_bar1537；missing_w_bar2035；v/w都缺2465；无reference_epoch并缺v/w186400。没有因观测或标签/ready20筛母体、没有缺失置观测零、没有因覆盖率补源。必要SELECT扫描既定1,552,456条，留同epoch lag键217,836，缺请求键6,811；仅读source quantity/因子/来源，不读openOI/OHLC/H5。DB stat前后完全相同，canonical因子未再次应用。

- manifest.json：6542 bytes，SHA `a2b7c284ef2755ce0103c24cf16874fd66ae734ca9ba1cdc08e53cf76876c159`。
- actual_terminal.json：479 bytes，SHA `4355d946e1b516e05d14ed5d06e62cf2fe4460397804679a26cf5e6f5be62f05`。
- oi_projection.csv.gz：32723925 bytes，SHA `b5cd60bdc0e9206289b0747f2fcbc14eac9285e342ef6e568cfd4862e896eba4`。
- projection_summary.json：535 bytes，SHA `825e73c0309ad4f5de15661dca5aa096ce30ed7acea3bdda84f32c46376bd620`。
- source_read_receipt.json：1478 bytes，SHA `4fb78e1b198c1224987887819a04660ef9e9742f84e667fa4d9861df1359955f`。

已将manifest/projection/terminal精确bindings交root与086/087作者；其训练/现金必须root再独立授权，085未自启。按root安排不为085单独新做实际全面独审，088在source/fit/cash三个最终manifest绑定后做一次联合全面核对；085没有消耗独审另给的OI SQL预算。原始实际outputs与源码保持冻结。

结束是否新增按成绩/覆盖调参过拟合：否，先冻公式/lag/同源/单位，只执行一次，所有missing原样保留；既有研究选择风险仍在。继续有价值：是，限让固定OI−CONTROL信息对照消费该来源，观测率本身不证明预测/收益优势。期末权益/收益/DD/Sharpe/滑点/交易次数/胜率仍N/A，整体goal active未达成。
