# Stage157：固定自愿日历政策现金封装实现，未启动实际账户

- 时间：2026-10-19 01:35 CST；line_id=`futures_full_market_long_signal_ai`；非重要突破。
- 本阶段属于Stage155已冻结的同一研究，不新建策略路线，不回到旧议题。root维护LINE与registry。

## 改动与参数

新增`tools/stage157_voluntary_cash.py`及6个关键合成fixture。复用已接受Stage131纯现金内核、Stage132缓存读取，以及Stage148现有配对CI/导出/报告帮助函数；旧源码不修改，不复跑旧账本。

唯一策略增量仍是155固定的VOLUNTARY_RESELECT：完整候选由156先执行D<K筛选再按旧分数重选。现金侧保持所有原经济参数和原始生命周期字段，仅在信号私有副本设置`effective=min(source_lifecycle,K)`，另输出来源/自愿/有效边界及生效来源。K以后不新入场；原边界更早保留。K晚于完整来源日历时pending，不夹到末日，不造平仓。所有canonical锚引用来自原完整399252母表，不能由新选择反推。

原100万元、0.25N止损、family风险0.0025、总风险0.02、保证金cap0.25/buffer1.1、1%往返容量、同源D开盘、anchor/20low、tick、费用和滑点均不变。无新增特征/标签/模型/训练参数，无删除参数。固定只允许2020连续/2023冷启动×base/stress最多4新现金账户；旧131 B四本只读复用。052完整日历/132精确缓存，SQL/下载0。

缺K开盘行情沿原内核保持手数和旧mark，并保留deferred请求，下一真实报价才尝试成交；没有自动交割/合成现金清零/未来末价过滤。内核泛称`lifecycle_exit`必须结合边界sidecar解释，不能称法定截止证明。

预期输出含4完整新ledger/daily/positions/open/closed/reservation/capacity/entry未知，4新+4旧只读指标，8组95 family×year含零分解，4新financial/commodity及ordinary/F按年含零分解，全部gap/stale/open诊断及4组固定070 bootstrap CI。nominal gate不使用旧held结果，不主张新模型泛化；生产/加注/goal complete恒false。

## 有限验证

测试先执行缺实现RED：6个fixture均明确失败于缺Stage157实现；实现后GREEN。最后一次6 fixture全通过，0.048秒。覆盖source更早不延长、有效边界取K、D==K拒绝、日历外pending不夹末日、K连续两日缺价保留数量/旧mark再真实成交、完整canonical晚日变更、四账户预算与主stress严格DD及未知不能通过。按年sector/variant零行及资金归因恒等也在合成账本上核对。

CLI help正常；import native SQL=0；已存在输出目录被fresh-output guard拒绝；旧全局ARMS仍为(A,B)。未运行旧全套测试或真实行情账户。

- implementation：28964字节；SHA256 `367d8202040fd30eb05b0070895c9a03706645446bd102c6d5de04f22824ba9b`。
- tests：6306字节；SHA256 `4151dedc684405b0d527383a10780c45ca0d9ac55854dcfe6ebdadc4f78b23ca`。
- 精确source bundle由`source_bundle()`生成，共16项。实际运行必须root另签source/input/output授权，不能由此记录自动启动；158独立审已收到接口，尚未对真实结果出结论。

## 调研判断、结果与反思

本阶段不新增网络检索，遵循155预算`new_primary_source_search=0`；参考前置152—155分级官方资料及既有被接受现金内核。判断维持：目录/生命周期字段不能代替历史自然人/券商清仓规则，统一自愿政策有资格作有限机制检验，不能伪称法律认证。

本阶段实际新增fit/cash/SQL/标签/下载均0，累计397fit/206cash不变。新增/修改/删除回测结果0；期末权益、收益、最大回撤、Sharpe、总滑点、交易次数、胜率均N/A，不能用合成fixture当研究金融收益。

开始/结束过拟合判断：按新收益调参**否**，参数和比较门已在新结果前冻结；同史案例启发风险**是**，不能抹去。继续价值：一次完整候选重选和4现金账户证伪**有价值**，无限补历史规则或扫描日期救参**没有价值**。下一步root静态审及精确授权后唯一actual，随后158独立核新选择/现金/CI；任何失败保留，不自动重跑。

## 01:38 CST 唯一实际运行与报告定位错误

root唯一actual已完成4现金账户，终端elapsed=22.503708333秒；全部四本40个文件，以及资金/比较/固定CI/分解等金融输出均已写出。随后在写`budget_and_tick_disclosure.json`前取错Stage128字段层级：作者使用`execution['cash']['anchor_and_execution']`，但真实128约定为top-level `execution['anchor_and_execution']`。因此原`actual_terminal.json`保留status failed、exit1、精确KeyError及new_cash_accounts=4。错误发生于报告元数据，不回滚、篡改或重跑已完成的现金模拟。

以下仅转录现存4本summary，待158独立核验，不作为晋级结论：

|窗口/成本|期末权益|总收益|最大回撤|Sharpe|总滑点|fills|闭合交易数|闭合胜率|
|---|---:|---:|---:|---:|---:|---:|---:|---:|
|2020连续/base|2,229,270.22|122.9270%|-15.6274%|0.97845|140,259.04|2,592|1,295|12.2008%|
|2020连续/stress|1,528,419.71|52.8420%|-11.3593%|0.78745|167,960.05|1,912|952|12.0798%|
|2023冷启/base|1,825,436.55|82.5437%|-9.9021%|1.32096|53,623.57|990|494|12.9555%|
|2023冷启/stress|1,526,645.82|52.6646%|-6.4228%|1.22302|83,952.08|849|422|13.0332%|

累计变为397 fit/210 cash；新增fit/SQL/标签/下载0，现金只新增这一批4本。原基准和旧结果未修改或删除，源`stage157_voluntary_cash.py`仍28964字节、SHA `367d8202040fd30eb05b0070895c9a03706645446bd102c6d5de04f22824ba9b`。

root授权一个独立、仅元数据的`stage157_voluntary_finalize.py`补齐缺的disclosure、manifest和单独continuation起止记录；不import任何cash/cache，不恢复缓存、不读SQL、不重算选择/资金/CI，不调用原execute。原全部文件按事前/后hash保全，新manifest明确status `completed_with_metadata_continuation`、原failed金融终端newcash4与新metadata终端newcash0/reused4并存。158明确可识别此透明状态，仍将独立核全部新账本。

修复回归只增加一个top-level anchor定位fixture：缺实现RED→GREEN，0.008秒；CLI help通过，未扩大旧测试。finalizer 10778字节、SHA `e2ca0e9a2c98a4bb69b740e31dfb1b749a2365ccc1395701992a0f05bfbf4975`；test 1038字节、SHA `1f9e44c3e39b2c04fd4d88a84c90ec19a02edf76a2c00a468cdc63edf9ae1236`。本记录时仅向root提交精确CLI待其唯一运行，作者未启动finalizer。

修复不改变策略、参数或金融结论，收益后救参**否**；修复明确字段定位且保留失败证据**有价值**，重新计算四本**无价值且禁止**。后续仅元数据完成和158一次独审；仍不推广、不加注，不声称完整目标达成。

## 01:41 CST 元数据唯一续接实际完成

root完整静态审finalizer后唯一执行exit0；metadata terminal elapsed=0.007833708秒，new_cash_accounts=0、reused_completed_cash_accounts=4、financial/bootstrap recalculations=0、fit/SQL=0。63个原有文件事前/后binding均不变，原578字节failed terminal及SHA `70dda58b3fec76865db85b8efe96b99fb4c15f76b0e9c1efab75e73c71ac81b1`保留。四本仍只来自22.503708333秒那一次金融actual，不新增为八本，不重算旧比较或CI。

新manifest为72159字节、SHA `0c27edef98e636032404272dda9e067e2794d7b7cf49e4ca5401b8b3ea34c7a4`，明确`completed_with_metadata_continuation`并同时引用原失败终端与新元数据完成终端。新增disclosure正确引用128 top-level anchor，仅补报告；原作者源码及策略/资金/参数均不变。

158独立审正在进行，本记录不声称review accepted、金融结论有效或达成目标。未再次跑测试、actual或现金。累计保持397fit/210cash。
