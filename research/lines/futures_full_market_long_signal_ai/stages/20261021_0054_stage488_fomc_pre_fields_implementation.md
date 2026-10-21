# Stage488：公告前精确字段来源实现，尚未actual

- line_id：`futures_full_market_long_signal_ai`；记录时间2026-10-21 00:54 CST；非重要突破。只修改本线488工具/输出及本唯一stage，不修改LINE/registry或旧阶段。
- 先读registry及482/483/484/486、067来源代码/041乘数合同、266 clean schema与单边量合同。研究判断继承482已经查验的BoE原研究及固定作者源：名义成交暴露须用公告前同一完整合约、成交手数×结算价×现金乘数；这只是条件研究代理，不能把外部论文的市场/时段迁成中国延迟交易alpha。本子任务未另网络下载/运行外部代码。

## 已实现接口与边界

新增`tools/stage488_fomc_pre_fields.py`，API为`project_fields(protocol, output, *, authorization)`。root exact487协议SHA及488源码SHA不符即禁止真实字段访问；fresh输出禁止覆盖/重启。主函数仅用`protocol.source_fields`，SQL把54,089精确(epoch,pre_date)请求JSON经`json_each`做LEFT JOIN，按clean WITHOUT ROWID复合主键定位，同时join sources；只有一次SELECT，不扫描/拉回1552456全量native，不探schema/count、不重新算ATR。

直接使用clean `d.volume`的单边手数，原`native_volume`和`volume_factor`只作一致性检查，不二次折半。按041 exact epoch快照取`contract_multiplier`，不以产品默认替代未知乘数；041已有order_book_id/maturity/de_listed，故不必再读原7.1MB RQ metadata。乘数为每报价点每手现金价值的研究快照，统一CNY为既有假设，非逐日PIT/历史券商实规或法律债券面额证明。

固定复用067的`SourceReader/needs_fallback/resolve_observation`及rule annotation，禁止其全native/ATR/run_actual入口。只有原行已核身份/OHLC且结算列确实不存在时，才走固定RQ fallback；坏值、缺行、错身份、OHLC冲突不得换源。必要CSV每物理文件最多一次；H5最多两次只读打开、每必要key日期索引缓存一次，不全blob重hash。旧067实际receipt为2619 CSV/56,926,025物理字节；新子集体量未测量，不用额外读源测量。root收益前同意4096 CSV/1GiB硬上限，协议尚待最终绑定。

数值确认与规则/PIT资格分开：native质量/OHLC、精确源locator/epoch/date/OHLC、有限非负V、精确有限正M、范围内有限正S可给条件数值`source_numerically_verified`；规则未知/最终边界/PIT状态完整保留，绝不声称解开067严格mask等于accepted067。0V保留numeric_notional=0且log缺失；其余未知不填0、不用close/上一日/别名补S，不删请求或母体。

输出`exact_pre_fields.csv.gz`完整保留原484八列身份，canonical数值为`pre_volume/pre_settlement_source_verified/cash_multiplier/log_turnover_source_verified/source_numerically_verified`；另有native和候选OHL/原字段存在性、原与选中来源locator/route、原打印文本/parsed数值、source_numeric_state、inherited067/rule/lifecycle状态。`manifest.artifacts.exact_pre_fields`绑定产物，供489 exact三键join并共同缺失回退A，不以有值子集冒充98全市场。所有strict_pit/training/alpha/production资格保持false。

## 四项新fixture及读取披露

按root限定用test-driven-development写四个pure dict边界：已单边量不再次折半、0量保留但无log、仅缺列fallback、坏值/缺行/OHLC冲突不fallback。占位行为先运行exit1，4 tests/8断言失败（含subtests）/0error、0.001s；随后实现首次绿exit0、4/4、0.000s。均不读真实输入、无SQL/行情CSV/H5/模型/资金回放；不跑旧suite/全仓测试，遵从用户避免重复检测。首次写入时尚待最终487对齐，没有真实actual授权或执行。

prep读取披露：041 `economic_projection.json`为单行8MB元数据，我用sed误读了整个既有投影（非行情），已立即告诉root；不把它藏进真实actual的单次预算，也不重复读它。其他prep读取为源码/小protocol、manifest、receipt、单位合同及067既有1.7MB summary（仅输出既有汇总）。六个真实输入binding提案已交root；本子任务没有重新读母/227流、真实行情CSV/H5/SQL或网络。

## 参数、结果、反思

新增/修改/删除策略、训练、止损、资金参数与回测结果均0；新增仅来源实现与fixture。期末权益、总收益、最大回撤、Sharpe、总滑点、总交易次数、胜率均N/A；0新fit/0cash，沿486累计481实际fit/258完成cash及1旧partial。此实现不提供收益/胜率/窄损/加注结论。

开始/结束按新收益调参过拟合：否，未读新成绩；长期同史反复选题风险：是且高。继续价值：是，仅为冻结后的精确来源与一次可否决金融增量实验解除真实字段缺项，不能把来源工程当收益突破。本实现没有自行actual授权，不等待今日线，也不改正式/生产/原四前瞻/CTP/邮件/调度/Git。

## 最终冻结对齐与交接

root487正式协议53191B/SHA `e8bd8f4029170a56aaf5513ce43e2bfaa931def02369f252edae5a6228066582` 已读取核对；源码对齐source_fields.inputs六role、budget的`native_selects_max/CSV_unique_physical_file_reads_max/CSV_total_physical_bytes_max/H5_readonly_opens_max`及contract.requests_rows/canonical_output_columns，不引入别名兼容。最终仅重跑同四项fixture，exec chunk `b9e8b7`，exit0、4 tests/0 failures/0 errors、0.000s；这不是新实际行情运行。

交接`outputs/stage488_fomc_pre_fields/source_bundle.json`绑定最终源码、test、本stage、root487、TDD红/绿receipt及输入binding提案。CLI确切参数为`--protocol/--protocol-sha256/--authorize-source-sha256/--output`，API授权对象确切字段为`actual_authorized/protocol_path/protocol_sha256/source_sha256`。root尚未发actual授权，需独立490预审后由root启动唯一actual；本agent到此停止，不读取真实SQL/CSV/H5或代为启动。

## 2026-10-21 01:05：一次来源预算恢复，尚未第二次actual

root唯一actual24896已exit1；本agent实读其原terminal/receipt确认9.727780625秒，唯一阻断为CSV数量到4096，已读87,318,923物理字节，未触1GiB字节边界。SQL1精确返回54089请求、50060有native/4029缺失，H5/Y/COMMON/fit/cash为0。此4096预算来自代表母来源的经验，不能覆盖全candidate，属于来源预算工程失败，不是经济效果失败。原读取未checkpoint，不假称可复用。

root冻结child协议54773B/SHA `cf55afebcbf3a51139fc18a2b86522cb8c96f477c56f1798b505801375998aac`，唯一科学变更是CSV数上限4096到54089精确请求的数学界；其余时钟/数值/特征/标签/模型/资金合同不变。后续允许一次明确重复源读取，累计source SQL将为2；不是金融重跑或按成绩救参。若第二次来源仍失败，本轮停止，不继续微修。

旧源码/test已另存recovery_pre_source.py/recovery_pre_test.py，旧receipt/源bundle不覆盖。生产源码严格只改一行数量上界检查：由4096改成contract.requests_rows，同时运行时仍使用child冻结的CSV cap；无数值/字段/来源fallback/SQL变更。新增一项pure预算fixture，授权被mock且已有临时输出让函数在任何真实输入/SQL前退出：允许cap=exact请求数，拒绝cap>请求数。先红exec e19d21、1 test/1断言失败/0error、0.001s；修改后只将原四项和新增项一起跑一次，exec036a15、exit0、5/5、0.002s。未执行第二次actual或任何新真实源读取。

新实现/test、旧备份、child协议、局部diff、红绿证据及本stage绑定见recovery_source_bundle.json。累计金融仍481fit/258完成cash+1旧partial；金融八指标N/A。开始/结束新收益调参过拟合否，长期择题风险高；继续一次明确预算恢复有价值，仅为落实全candidate来源并保持原科学合同，不提供收益/窄损/加注资格。
