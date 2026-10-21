# Stage067 结算字段全母体投影：实现与有限验证，等待精确SHA授权

- line_id：`futures_full_market_long_signal_ai`。
- 记录时间：2026-10-18 16:22 CST；工作区 `/Users/mac/Desktop/fian`，沿当前 `codex/ai-training-data-expansion`。
- 阶段性质：root明确授权的单一新增字段输入步骤；本记录冻结时尚未执行全域投影。只新增067脚本、测试、本stage及本输出目录，不改066、LINE、registry、其他研究线或正式版本。
- 是否重要突破：否。数据输入代码与有限测试不是净收益、回撤或AI进步。
- 是否触发正式A/B：否；不认可066建议的54槽或任何新模型实验，模型与交易协议仍需root之后另冻。

## 调研结论与最小设计

继承066已实际核查的一手材料：[SHFE 2020结算细则](https://www.shfe.com.cn/upload/20200930/1601455533699.pdf)、[INE结算细则](https://www.shfe.com.cn/regulation/ineregulation/businessmethods/settlement/202606/t20260622_832188.html)、[IF交易细则](https://www.cffex.com.cn/u/cms/www/202003/27165505w3j5.pdf)、[T交易细则](https://www.e-cffex.com.cn/u/cms/www/202007/08152235b2ys.pdf)、[国债交割细则](https://www.e-cffex.com.cn/u/cms/www/202007/08151817ah9p.pdf)，以及[RQAlpha维护者字段读取源码](https://github.com/ricequant/rqalpha/blob/master/rqalpha/data/base_data_source/data_source.py)。

判断不变：真实结算字段有OHLCV不能唯一重建的新观测，但不是买压或统一全天VWAP。所核CFFEX股指/国债普通日结算都用末小时而精度不同；最终交割分别涉及标的指数末2小时和国债期货最后日全日成交基准，不能混成日结算。SHFE/INE所核商品普通日规则为全日加权；无成交、停板回退、调整与规则变更另存状态。DCE/GFEX默认族未在067绑定独立primary规则，明确标`family_default_assumption_no_primary_rule_bound`，不签全历史规则资格。

采用已有读取流程的有界扩展：

1. 仅从049 `features_all.csv.gz`读取`sequence_index,event_id,product_id,family_id,u_date,reference_epoch`；不读取label状态、netR或用未来结果筛行。保留399252身份、98目录产品、六所、普通/F和所有unknown。
2. `v`严格为完整source日历中u的前一日，仍用u指定的同一真实epoch；不是该合约上一条可用记录，不拿上一日另一主力补空。一次只读native SELECT同时取得OHLC/量/source_id/source_locator及source目录绑定。源日历史只用于原042 `EpochSeries`纯Wilder20 ATR，输出`N(v)`，不调用55信号、价格链、经济账本或cash。
3. 首选accepted locator原源。官方规范CSV按精确物理row/source_member/raw_row绑定；原RQ按metadata完整交割年月、key/row/date绑定。原TQ文件也先验证原row及OHLC。**只有原schema没有settlement列时**，才允许固定RQ H5替代；坏值、零值、非finite、缺行、身份错绑、重复日期、无成交或OHLC冲突都吸收为unknown，不再试其他来源。
4. 可比关系固定同epoch/date、OHLC绝对容差`1e-8`，不按行情或成绩放宽。保留候选C/S/前结算/N、源打印文本或float64非原始打印精度标签、candidate quote epoch/date、accepted与选取locator。即使冲突，候选值也保留供root判断；不复制完整原始OHLC、DB或H5。
5. `C=S>0`且有成交是合法零差值；无成交填充、最终交割边界/未证定义、范围冲突和缺值均有显式状态。规则族/primary绑定、vendor生命周期、N暖机状态单列。`value_observed`只表示该C/S观察的源比较状态，**不是训练mask**；`feature_available=0`、`training_accepted=0`、`strict_pit_accepted=0`始终保持。没有输出标准化x或模型score。
6. `available_at`不伪填时钟；`availability_basis`固定为历史重建+一完整source日滞后，不声称当年首次发布快照。一日滞后不能消除vendor回溯修订。保存的候选数值/locator足够供root在之后明确的研究接受合同中消费，**不要求为同一字段再重读DB/重建一次**。

## 文件、冻结身份与准确命令

- 新增脚本：`research/lines/futures_full_market_long_signal_ai/tools/stage067_settlement_source_projection.py`；39083 bytes；SHA `dacbb8d58e42f98c003d83c5a673a9bc651d645f092e17bd02e1dcdecb49f048`。
- 新增测试：`research/lines/futures_full_market_long_signal_ai/tools/test_stage067_settlement_source_projection.py`；19026 bytes；SHA `75da6692514ca859ebca2a29885a4d58c42e762ee9e84d96ec0b0a6fe44b6545`。
- 候选输入协议：`outputs/stage067_settlement_source_projection/protocol.json`；3748 bytes；SHA `aa5dd80908bc21a06731761ac4539f2acfb86091061d2fa761592652dde9553a`。
- 接受的纯042 kernel继承SHA `ca40a4cf7b761b34f70d973a943723601d0ecf5fc355da3559d5bcbeff36661d`；不修改该文件。
- machine handoff：`outputs/stage067_settlement_source_projection/preflight_handoff.json`；完整拟执行命令：同目录`proposed_actual_command.txt`。`experiment/`目前不存在。

拟执行命令已经保存为具体可审核结果，**本stage冻结时尚未运行**：

```sh
.py311/bin/python research/lines/futures_full_market_long_signal_ai/tools/stage067_settlement_source_projection.py --protocol research/lines/futures_full_market_long_signal_ai/outputs/stage067_settlement_source_projection/protocol.json --protocol-sha256 aa5dd80908bc21a06731761ac4539f2acfb86091061d2fa761592652dde9553a --authorize-source-sha256 dacbb8d58e42f98c003d83c5a673a9bc651d645f092e17bd02e1dcdecb49f048 --output research/lines/futures_full_market_long_signal_ai/outputs/stage067_settlement_source_projection/experiment
```

CLI和可import的`run_actual`入口都必须校验代码SHA与协议字节SHA；错误授权在输出目录或真实输入/SQL读取之前失败。实际输出目录必须fresh，不静默覆盖或重试。

## 一次实际预算与来源身份边界

- 一次actual启动、一次native SELECT，计划读取原accepted `1552456`合约日/`9520`epochs；不额外SQL查schema/count/source，不改DB。schema取自既有266/042代码，062六个案例不冒充全native缓存。
- 原accepted必要CSV按resolved物理路径至多读一次；在该必要小文件读取中核已有SHA/bytes与locator，不扫描无关规范目录。保存读取收据，不复制原文件。
- RQ H5最多两次只读打开：原源及获准的缺列替代。仅访问实际所需epoch对应的确定key；同key日期索引最多读取一次，随后只取所需行。记录实际行局部fingerprint，不能称全blob重验。
- H5/DB全文件hash扫描均0：H5的`d288f6e...8bfee`和DB的`a63f92ce...11`是继承事实；核path/bytes/已有stat并保存`h5_rehashed=False/database_rehashed=False`。原RQ locator目录身份与冻结H5继承SHA/bytes矛盾时该行unknown，不能因同路径或同OHLC就假称原内容。
- 0 fit、0 cash、0 labels build、0下载、0资产登记；不加载053/061模型或EIA新成绩，不修改生产、凭证、CTP、邮件、定时任务、commit/push。
- 一次输出只需全399252最小字段与状态、family×年覆盖、summary、来源/运行/manifest收据。family×年分母包含无观察、未知、冲突与普通/F，不先dropna。所有来源重建假设与规则不足照报。

## TDD与独立复核

先写合成测试，初RED因067实现文件尚不存在而失败；`tests_red.txt`原样保留。初实现16项GREEN。随后新增两个真正边界反例：浮点locator会截断为实际行、H5继承身份未一致；两项真实RED后修正，19项GREEN。独立静态复核提出三项Important（H5内容身份、N/规则与训练mask分离、可导入入口授权），再补反例RED并修正；另对冲突候选值保留做一次RED→GREEN。

最终仅跑新067测试：`tests_green_final.txt`，**22 tests，0.021秒，OK，命令exit0**。测试只用临时小CSV/H5/数据记录；单SELECT测试使用FakeDatabase，未调用真实SQLite引擎或本机DB。未跑旧suite、actual、拟合或账户。

行为覆盖：精确source前一日及换约、全母体/label无关、F与完整年份身份、合法C=S、缺列才fallback、坏原值与冲突吸收、重复源日、原物理locator与打印文本、no trade/zero/nonfinite/范围/最终边界、纯N(v)因果与gap重置、CLI/直接入口错误授权，以及未知分母。

独立agent `/root/next_full_market_information/participant_primary_sources`仅静态检查指定新代码/测试；最终回复：**剩余Critical/Important=0/0**。它未跑tests、actual、SQL或下载；本结论只接受关键实现边界，不是实际数据质量/全域投影验收。初审发现与后续修正均保留在本阶段收据，不隐去。

## 本阶段结果与反思

- 新增参数：输入投影容差`1e-8`、固定一source日lag、固定原locator→仅缺列RQ替代；它们是数据协议参数，不是交易参数。新增/修改/删除策略参数、回测结果均无。
- 期末权益、总收益、最大回撤、Sharpe、总滑点、总交易次数、胜率：全部N/A。
- 实际全域投影/真实SQL/fit/cash/download：本stage冻结时全部0。fixture与代码/协议准备不计实际source projection。
- 开始是否新增过拟合：**否**。结束是否新增过拟合：**否**；没有读取EIA新成绩、没有基于收益择源或改旧失败模型。主要风险是来源选择/回溯修订，被固定顺序、吸收unknown与非PIT标签显式约束，但尚未由真实投影消除。
- 开始继续价值：**是**。结束继续价值：**是，仅限按当前精确SHA完成一次实际字段投影并判断能否接受新增观测**；source工程成功不能替代更高净收益、更低回撤或窄损/加注验证。
- 下一步：root核本候选SHA/协议后授权唯一actual；本owner再执行一次并交真实终态、全mother覆盖/冲突和来源假设给独立复核。后续是否接受研究输入、怎样做全日级三臂实验仍由root另冻，不偷渡066模型设计。
- 暂不更新LINE/registry、根memory/back_log，不触碰正在登记EIA的064。
