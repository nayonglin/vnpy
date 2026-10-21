# Stage011：固定DAY代理数据的唯一联合独立审查

line_id=`futures_full_market_long_signal_ai`；2026-10-18 11:42 CST；独立审查人`ai_label_validation`；非策略收益突破。先读registry/LINE、007冻结协议和005观察资格，再等待009唯一实际build真实终态后审两个源与实际数据。只新增本文和 `outputs/stage011_day_proxy_dataset_review/`，不改007/009/LINE/registry或其他线，不派agent，不新增模型路线或标签条件。

## 结论

**009代码与实际数据通过007固定代理实验合同，Critical/Important/Minor=0/0/0。** 本receipt只签 `qualified_for_fixed_proxy_experiment=true`，接受的 `data_manifest` 为009实际manifest `ea26675e8322bee8a3c71d4ba0c731055a52a161359c1ac456de628029a5071e`。`real_economic_labels_ready/financial_ready/production_ready`仍false；不以泛称model_ready=false阻止已冻结007的纯统计实验，也不把这次接受冒充真实交易标签或alpha资格。

没有重审007设计或增加训练准入条件。训练/评价实现和实际fit由010/root按原计划推进，后续012审模型与实际结果；本阶段不审未完成010、不fit、不预测、不从数据质量通过推断实验将成功。

## 实际运行与对象

唯一独立实际命令：

```sh
.py311/bin/python research/lines/futures_full_market_long_signal_ai/outputs/stage011_day_proxy_dataset_review/review_actual.py
```

实际11:42:04.913506—11:42:27.220277 CST，脚本计时22.306773秒；初始tool session21421/chunk`c5272b`，本人只poll该自有handle取得`14bc9b`，**exit0**。独立脚本stdlib-only，不导入009、不重建dataset、不运行作者/旧suite或native/金融/provider/模型，不全hash大库。输入JSON/CSV/NPY均核SHA后消费同份bytes；原DB以mode=ro/query_only读取，前后stat一致、无WAL/SHM。

009作者真实原session45546由作者poll获得`1b88f8 exit0`，11:38:18—11:38:54，35.834890秒、唯一build1次；本人消费其已终态manifest/terminal，并未伪称自己poll作者session。

| 接受对象 | SHA256 |
|---|---|
| 冻结007 protocol | `2e5da3da4440223e3ac978256d563b80d5bd4264cec56d4085ed6062d7bad0a4` |
| 009 builder | `f7e9eaa56bee511e670a0f09175e58321ab358a501b3e0d63a5d6e2b3ddb89c4` |
| 009四方法测试 | `1ee59dd763fb1d54b2bb65b35f36b5690b5d6e8511c0393610f4092f7d79ac51` |
| 009 manifest | `ea26675e8322bee8a3c71d4ba0c731055a52a161359c1ac456de628029a5071e` |
| feature_labels.csv.gz | `9b2452fa5fc8bb0c97d702d0caffa2a2b22e46e38ea52ab4842c13d25f120a48` |
| audit_paths.csv.gz | `a0ed32d19c102767bb789cdb1bab2ab28da1b714fa426ca1a368947b87ee6fef` |
| 009 actual_terminal | `8c253db4603cb4027e58344feba601994b7289eacae018718065e51e1ba0ac69` |

代码/测试及所有009小source binding实际SHA全符，005观察接受与004原母体、source calendar均绑定一致。原clean DB SHA `a63f92ce7e1d51080ba92f7214fc493f1e6a69aa0079d6ecef7190eea9b58711`仅继承266既有价格/单位资格；本次378552320 bytes、mtime_ns1792236170627661666、inode28078628读前后一致，不冒称重新逐价认证或历史发布PIT。

## 全表独立核验

将009逐行与004已接受母体zip核对原身份、u、真实epoch、D、状态与long方向；完整399252行及98×4074格不丢失。按年计数独立重算，与009各年输出一致。

| 口径 | 独立实际计数 |
|---|---:|
| 全表 / 有参考观察 | 399252 / 212852 |
| feature_ready | 194709 |
| label_identified | 194168 |
| feature_ready但标签未知 | 541 |
| 双触达interval | 6000 |
| ready但跨市场上下文缺失 | 22 |
| ready唯一日期 / family | 4054 / 94 |
| no_reference | 186400 |
| 同epoch不足21bar / calendar缺口重暖 | 6201 / 11942 |

标签状态为day_close51292、stop_only121154、profit_only15722、double_touch_interval6000、missing_D460、right_censored85、history_unready18139、no_reference186400。`missing_D+right_censored`不机械等于ready未知541，因为4条末端right_censored自身也未就绪；两个状态维度分开保留，不补结果0。

全部ready的11维自身特征、ATR20及4维上下文有限；不ready的11维为空；全部unknown的四个收益端点和label_known_date为空。已识别标签均有u<D、known_date=D、D在源上界内，双触达明确为gross[−1,4]、base[−1.2,3.8]而非确定坏类。所有字段仅归一化代理，不含模型输入OHLC或假现金/权益。

对全部399252行独立重算4维上下文：以原source-calendar的u−1，取该日所有feature_ready的同epoch r1，先按exchange及去_F family均值、排除own family，再按等权family算median/breadth/线性IQR；无其他family为0/0/0/missing1，不前填、不用OI、未来D或标签状态筛选。541条ready未知标签保留在这个输入集合中（末端行是否真正被后继使用取决于日期，不声称所有末端行均参与区间内预测）。全部结果与009相符。

还对全部212852条观察诊断路径核ATR/状态及固定F、0.25ATR距离/保护价/目标价，按D高低/close独立重算已识别区间及0.2R扣减，全部一致。**这一步的价格来自009诊断表，只是独立公式与关联核验，不能称全体原DB逐价重建。** 原价格独立重算范围另如下。

## 分层原SQL与源码边界

只读原DB执行20个固定形状probe，读取413条同epoch历史/D记录：六所早期ready及末端、三类F、calendar缺口、不足历史、缺D、双触达、profit-only。逐probe从原DB读取截至u最后21条真实bar和原固定D，核连续source-calendar、TR20/ATR及全部11维；缺口不能拿下一观测补，跨epoch不能拼。原D仅同epoch原预期下一日；缺D、末端删失与双触达状态均匹配。具体event/epoch/u/D/原行数在`actual_review_checks.json`，不按新模型或盈亏抽样。它是有限结构覆盖，不代表对全部194709条历史窗口重新资格。

完整读审009两源/四方法，未复跑已真GREEN的作者测试：

- builder`:50–64,149–168`自身特征只取同epoch截至u的21bar、20个TR；cal索引跨度与唯一日期一起保证连续，缺口重暖、零ATR不就绪；固定11维与007逐项相符，不用openOI/旧train门。
- `:67–87`DAY标签只用固定D，未知保持空，理想屏障的双触达保留区间，成本是固定研究预算；没有真实tick/手续费/成交资格的声明。
- `:95–115`上下文的selected只看feature_ready，u−1取源calendar前驱，F族先均值后排own；没有label_identified或D存在筛选。`:121–135,180–192`完整母体和ready/identified分别保存。
- `:202–216,235–287`单条SQL只读清洗源、小绑定核同bytes；原始OHLC只在独立audit诊断而非trainer输入。源上界与protocol SHA强绑定，dataset/feature_label_csv同一绑定。资格原manifest保留pending，不自改为accepted；独立receipt另授固定代理实验资格。
- 四方法覆盖11维/零ATR、屏障等号/未知/费用、F族lag/无label筛选、真实SQLite未来前缀/缺D/重暖/epoch隔离；是作者组件验证，不冒充本次独立工具运行。

未来隔离的结论限定于固定代码的数据流、全表lag重算及原SQL截至u/固定D证据，不声称历史vendor当时已发布同字节。label_known_date=D是模拟收盘后日期合同，不是午夜PIT；训练截止、缩放与holdout是否正确由010/012另审，不能由本数据receipt代签。

## 资格与反思

本阶段只接受009在007固定continuous-price/ideal-immediate/DAY/0.25ATR/1ATR/0.2R预算代理假说下用于一次统计识别实验。真实经济标签、成交执行、窄损加注、组合现金/收益/DD及生产仍未合格；这些缺项不再转成阻塞纯统计fit的新条件。当前无模型分数或实验成绩，不能以194709行称独立样本量或高质量信号已存在。

调研沿007已查作者原文、Backtrader官方执行假设和既有266字段/单位资料，不新增外部代码或网络；判断是合同内代理可识别不等于真实交易收益可识别。新增/修改/删除策略参数、模型、财务回测结果均0；期末权益、收益、回撤、Sharpe、滑点、交易次数、胜率均N/A。本次新fit/prepare/native/金融/provider/network全部0。

开始/结束新增选参过拟合：**否**，只核已冻结规则，没有看新模型/按收益选参数；旧历史被反复研究的选择风险保留。开始/结束继续价值：**是，下一步直接完成冻结的72-fit单次筛查及012结果独审**，不再扩数据资格循环，不以失败后改屏障/交互/成本/阈值救参。目标active，尚无新alpha。
