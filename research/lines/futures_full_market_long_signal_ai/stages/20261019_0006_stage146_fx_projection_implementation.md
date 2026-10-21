# Stage146：ECB相邻发布行保守滞后投影实现

- line_id：`futures_full_market_long_signal_ai`；改动时间2026-10-19 00:06 CST；非重要突破，只实现冻结协议。仅维护本唯一stage及146工具/fixture，不改LINE、registry、旧工具或正式策略。
- 先读registry、本线LINE、145计划、145独审及最终18343字节协议；最终协议SHA为`be0431bff87dc90d91a9f1b16940c9a6d8112a66d4309879abef46466ce4f270`。本次研究判断承接144/145的ECB官方归档、BIS文献与时钟独审结论：汇率可以是外部信息，经济方向先验弱；归档和额外lag只支持有边界的历史重建，不证明首发vintage或alpha。本实现不再扩展下载或资格工程。

## 变更

新增`tools/stage146_fx_projection.py`。`project_dates(values,u_dates)`先用完整ECB原表日期找`n<u`的最后真实行，再按原表位置取d=n前一行、w=d前一行；之后才检查n/d/w双腿。q为`log((CNY[d]/USD[d])/(CNY[w]/USD[w]))`；任一相邻身份不足、腿非有限或非正保留missing，不跳到更老的有效行、不插值、不填零。

assigned固定为n+1自然日08:00 Asia/Shanghai；decision固定为u日15:00，并断言assigned不晚于decision。保存n/d/w日期、原表位置、USD/CNY双腿、自然日age、change/finalization日期、assigned/decision及missing状态。母体投影仅按u映射，与reference_epoch或observed状态无关，不将假期重复状态称为每日新公告。

actual只允许root精确源授权，schema为`stage145_exact_root_authorization_v1`、stage=`projection`，需最终protocol SHA、当前`source_bundle()`及输入角色`values/content_receipt/mothers`。fresh输出固定在`outputs/stage146_fx_projection/actual_run1`；实际入口还核144内容收据和全399252母身份。输出`projection.csv.gz`、`source_dates.csv.gz`、summary、started/terminal和manifest；异常保留失败终态，不自动重试。

## 验证和计数

应用TDD技能；4个新合成fixture先RED（缺实现），后GREEN：同日/未来值不能改变过去；紧邻缺腿不能跳行；finalization行缺腿不能冒充有效桥；空reference/no-observed母行仍全部保留。最后146/147合并9项fixture通过，py_compile和CLI --help通过。不运行旧suite，不做fixture模型拟合。

验证记录位于`outputs/stage146_fx_projection/red.log`、`green.log`及implementation_receipt；最后合并fixture记录位于147的`final_fixture.log`。146源码SHA为`87c7c726c244d3cb4a546d0dfc463e959db4c534d0f3a4b71d505c7426216f8a`；精确完整source bundle以implementation_receipt和函数读回为准。

本阶段新增/修改/删除策略参数0；仅新增固定投影字段，无lag/window/符号扫描。新增/修改/删除回测结果0。实际投影尚未运行，新增fit/fixturefit/cash/SQL/下载均0；累计391fit/202cash未变。期末权益、总收益、最大回撤、Sharpe、总滑点、交易次数、胜率均N/A，不能把fixture结果写成财务证据。

开始与结束新增按收益选参过拟合：否，时间、公式和缺失均事先冻结；历史研究择题及归档修订假设风险仍存在。继续这个有限实现有价值：是，用于证伪新增信息能否改善既有全域决策；若控制零列桥失败则整包停止，不延长source工程救参。后续TODO：root精确源授权后单次actual；完成147/148后由独立149检查原ZIP相邻日期、矩阵/预测和现金，不提前签strictPIT、正式、加注或完整目标资格。

## 00:08 CST：root单次actual读回

root签发精确`outputs/stage145_fx_information_protocol/authorize146_projection.json`（1979字节，SHA `02d16b9c7dbc97530174339e71250e067b672323b1a646de955c34f5a2ad6014`），仅允许一次146。root实际启动时间为2026-10-19 00:08:23 CST；`outputs/stage146_fx_projection/actual_run1/actual_terminal.json`确认completed/exit0、14.870506秒、fit_attempt/completed=0/0、cash/SQL/download=0，automatic_retry=false。没有由实施agent运行第二次actual或改冻结源。

完整母体399252行、4074个国内u日期；399252母行全部q observed，missing0。可用n发布cohort为4021，国内重复as-of状态53；后两者揭示重复全球状态，不能视为4074次独立宏观创新。该结果接受的是本投影覆盖，不证明独立经验、经济收益、首发vintage或严格PIT。

实际证据如下（均位于本线目录）：

- manifest：`outputs/stage146_fx_projection/actual_run1/manifest.json`，SHA `c8e9c1a86a125b136bd2f3bbcf4dc711173ee06f3bbb8bcba0fc9f0baac95334`。
- summary：同目录`summary.json`，SHA `fed76d285a602e4442587e276f766052fa52ce42adf610ef6fb967f9fb405862`。
- terminal：同目录`actual_terminal.json`，SHA `17c8f50b2558a8779691ac0ead8d3717bf611c44e2e50398df9e5a616a22d53c`。
- projection：同目录`projection.csv.gz`，38276964字节，SHA `82258773ac6729c57cb218b27b8ae5571f55cfac16a39d1d27da92ddc2e789e9`。
- 每u源状态：同目录`source_dates.csv.gz`，186600字节，SHA `4be7416d02f81a401089fbc493e104d5c19007868be971745ca945e5b9cf9e83`。
- CLI终态日志：`outputs/stage145_fx_information_protocol/actual146_cli.log`，显示completed与相同actual_run1目录；root授权及started记录绑定了实际源和输入。

本次新增/修改/删除策略参数或金融回测结果仍0，新增模型/现金账户均0；累计391fit/202cash未变。权益/收益/DD/Sharpe/费滑/交易次数/胜率N/A。结束新增按收益选参过拟合：否，本次只执行固定投影；继续价值：是，全部覆盖允许147按冻结全局零列桥继续，但仍须147实际全六折桥、拟合与后续独审，不把missing0提前等同为alpha。147尚由root独占执行，本文不预报其终态。
