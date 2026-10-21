# Stage067 结算字段真实投影一次完成：保留全母体，交独立来源审查

- line_id：`futures_full_market_long_signal_ai`。
- 记录时间：2026-10-18 16:30 CST；actual开始16:25:41.678，约16:26:39完成；工作区 `/Users/mac/Desktop/fian` / 当前 `codex/ai-training-data-expansion`。
- 阶段性质：root精确SHA授权后的唯一真实source投影；不是模型训练、收益回测或研究输入接受合同。
- 是否重要突破：否。新增观测已真实投影，但净收益/回撤、AI质量、极窄止损与加注都没有新证据。
- 正式A/B：不触发；没有修改正式池、策略、生产或其他研究线。本阶段不改066、预检stage、LINE、registry或064。

## 授权、冻结身份与真实终态

root fresh核三SHA且确认`experiment/`不存在后，明确授权本owner按已保存命令仅执行一次。先落盘`outputs/stage067_settlement_source_projection/root_actual_authorization.json`，SHA `a58356fb56429699fdc930afa9e1c7893f58ed50fb41c053028f03edb7d95d4d`，再启动进程。

- 不变代码SHA：`dacbb8d58e42f98c003d83c5a673a9bc651d645f092e17bd02e1dcdecb49f048`。
- 不变测试SHA：`75da6692514ca859ebca2a29885a4d58c42e762ee9e84d96ec0b0a6fe44b6545`。
- 不变协议SHA：`aa5dd80908bc21a06731761ac4539f2acfb86091061d2fa761592652dde9553a`。
- 实际session `34352`，首chunk `250bf8`，terminal chunk `d25891`，**exit0，一启动一完成，无actual重试**。
- actual自身terminal计时`57.677114`秒；写完manifest后的stdout计时`57.697150`秒。两者边界不同，不另算一次运行。
- actual terminal SHA `fb572fc86a54b1bf3e36d20ca3efff8fea705cd8761395717def6f34ffd42c32`。
- 最小执行收据`outputs/stage067_settlement_source_projection/actual_execution_receipt.json`，SHA `60b3428811e36b04439be1725d3480e0410a9ef5d67b425f3842f83422e9358e`。

## 调研判断与本次输入口径

一手来源与GitHub判断继承本线066/067预检：[SHFE 2020结算细则](https://www.shfe.com.cn/upload/20200930/1601455533699.pdf)、[CFFEX IF规则](https://www.cffex.com.cn/u/cms/www/202003/27165505w3j5.pdf)、[国债交易规则](https://www.e-cffex.com.cn/u/cms/www/202007/08152235b2ys.pdf)、[RQAlpha维护者字段读取源码](https://github.com/ricequant/rqalpha/blob/master/rqalpha/data/base_data_source/data_source.py)。真实结算基准相对收盘具有OHLCV不能唯一重建的新观测；跨所/最终交割/无成交与回退语义不同，不能称统一全天VWAP或买压，日级获利仍未证明。

原049完整身份严格保留。仅按`u`的前一完整source日`v`、同一真实epoch投影；不取上一条可用bar、不拼主力。N取accepted历史的纯042 Wilder20 `N(v)`。不读label/netR筛测试行，不加载053/061模型或EIA新成绩。

原accepted source locator优先；只有原schema缺结算列才允许固定RQ替代，坏值/缺行/冲突不换源。固定OHLC绝对容差`1e-8`。候选C/S/前结算/N、原/替代locator、候选quote epoch/date、打印/单位/规则/N/可得假设状态保留，即使unknown也不从母体删除。

## 全母体覆盖与unknown

完整输出**399252行、399252唯一event、98产品、95family**；family×年覆盖1615行，分母合计399252，无dropna缩池。

| 投影状态 | 行数 | 解释 |
|---|---:|---|
| observed_historical_reconstruction | 207849 | C/S通过固定同epoch/date与OHLC比较；仍是历史重建观测 |
| no_reference_epoch | 186400 | 原母体本来无参考epoch，保留而非归为结算下载失败 |
| missing_native_v | 4002 | 精确v日同epoch无accepted native，不取更旧记录替代 |
| source_date_missing | 311 | 固定RQ替代源无精确日期，均在2026；不转别源、不补值 |
| settlement_outside_native_range | 9 | 候选S越出同日范围，保留C/S/N与locator为unknown，不裁剪/修价 |
| rule_family_unknown | 681 | DCE.L_F、PP_F、V_F各227行；不借普通合约定义套用 |

207849条观测占全部母体`52.059601%`，占原有参考epoch的212852行`97.649541%`；两分母都披露。观察覆盖94产品/94family，不由此声称所有产品均已具结算资格；其余产品/家族原行仍完整输出。

与accepted native的来源路由计数：原locator `115002`、只有原缺列才RQ替代 `93848`、无native/epoch路由 `190402`。同OHLC固定容差比较成立`208850`，其余`190402`未比较；**源OHLC冲突与源身份/日期冲突各0**，这不等于S值或历史PIT均已认证。

全部N(v) ready20为`194709`行，观测且N ready20为`193817`行；N不暖机的原C/S值仍保留。观测且已有primary规则族材料的`141491`行；另有DCE/GFEX等默认族重建假设，完整状态照报，不能把没有逐期规则vintage写成已核历史规则。

9条range unknown来自LR两条、B两条、M/P/Y/EB/LC各一条。具体event/日期/epoch/C/S/N在小表`actual_nine_range_unknown.csv`；本阶段不诊断为某一种修订或数据bug，不追加SQL/源读取或更换值来救它们。root已明确保留这些unknown，不重跑。

年度完整分母/参考分母/观测数保存在`actual_annual_coverage.csv`；例如2020为`23814/15271/14802`，2023为`23716/16455/16353`，2026截至源尾为`18424/15964/15039`，不把2026当全年。

## 实际读取预算与来源身份

- **1次native SELECT**：1552456合约日、9520epochs；精确请求212852个epoch×v日，其中208850可取得native。没有额外schema/count/source SQL。
- 必要CSV：**2619个唯一物理路径，各1次**；读入56926025 bytes，扫描863096原文件行。只读accepted相关源，不扫描无关规范目录，不复制原CSV。
- RQ H5：**2次只读打开**；3709个唯一key、3767次key访问（两个用途可重访key，但日期索引缓存），日期索引实际读取864639行、实际值169629行。没有遍历全10547键或重建全源。
- H5/DB全文件hash扫描均**0**。H5继承内容身份`d288f6e4...8bfee`，核path/bytes/已有stat；明确`h5_rehashed=False/database_rehashed=False`。必要原RQ目录身份与该继承事实比较，不冒称本轮全blob重验。
- 仅实际读取行的局部fingerprint为`2a312e0063dc34079c3f579342e25e7e03e97162484d807607cb0a90bf98908f`，范围明确`only_actually_read_rows_not_full_blob_reverification`。
- 0 labels build、0 fit、0 cash、0下载、0 archive/资产登记；不改DB/H5/原始OHLC、source代码或协议。

## 交付与接受边界

实际输出目录：`outputs/stage067_settlement_source_projection/experiment/`。

| 文件 | bytes | SHA256 |
|---|---:|---|
| settlement_projection.csv.gz | 31253909 | b9407b90c727f976201d70bf4cceb91994f78712d17441bc9887d00d609159f4 |
| family_year_coverage.csv | 362208 | 4207a9dcd747e08a6db03882c07778b1acf23f4051a96ea7d493f5c7a2b98cd2 |
| summary.json | 1745213 | c2437f4bbcc744d4b31a58f9cb8c1a36ebf56deb2649521312fe1659322ad4f7 |
| manifest.json | 2421 | 75e63071fa5d90c27d6fd54acd278b80c523bba1ef6236c2848b889d05496303 |

小交接摘要为同067输出根目录下`actual_root_handoff.json`、`actual_bounded_output_checks.json`、`actual_annual_coverage.csv`、`actual_nine_range_unknown.csv`与上述执行收据；只读规范输出做覆盖核对，没有再读原源或DB。

额外输出摘要helper第一遍因numpy int64不能直接JSON序列化失败，年度/9条小CSV此前已写；第二遍只转换输出计数类型完成。**这是两次输出后处理，不是两次source actual**；失败原因和0原源重读/0新SQL/0actual重跑已记入收据，未改冻结代码或协议。

实际全行`feature_available=0`、`training_accepted=0`、`strict_pit_accepted=0`已核。`available_at`不伪填实际时钟；历史重建+固定一source日滞后仅为研究假设，不能消除回溯修订。保存的候选值/locator/状态已足够供root另立069接受合同消费，不需为同一投影再建一次数据库输入。本阶段不认可任何54槽、fit/现金设计或信号。

实现前22项新合成行为测试和聚焦静态复核C/I=0/0的边界仍保留；**真实数据独立来源review尚由root安排，不能把静态复核冒充actual接受**。

## 结果与反思

- 本阶段新增/修改/删除策略参数与回测结果：无。期末权益、总收益、最大回撤、Sharpe、总滑点、交易次数、胜率全部N/A。
- 运行前新增过拟合：**否**；运行后按结果择源/救参：**否**。一次精确冻结投影，9条range与其他unknown保留，未用收益或已完成label改变来源/产品/时钟。历史重建与研究选择风险仍存在。
- 运行前继续价值：**是**；运行后继续价值：**是，限独立核来源后由root决定研究接受并另冻实验**。现成新增观测有实际覆盖，但不是净收益进步；不提前缩止损或加注。
- 不更新LINE/registry、根memory/back_log；不修改其他线。该owner在交付真实终态后结束，释放并行slot。
