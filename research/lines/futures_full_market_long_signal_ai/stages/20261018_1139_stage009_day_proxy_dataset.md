# Stage009：冻结DAY代理特征与区间数据的唯一实际构建

- line_id=`futures_full_market_long_signal_ai`；2026-10-18 11:30—11:39 CST。先读registry、LINE、Stage007及其JSON，协议SHA=`2e5da3da4440223e3ac978256d563b80d5bd4264cec56d4085ed6062d7bad0a4`，未修改公式/协议或另问形式审批。
- 独占新增 `tools/stage009_day_proxy_dataset.py`、`tools/test_stage009_day_proxy_dataset.py`、本文和 `outputs/stage009_day_proxy_dataset/`；未改其他源、LINE、registry或原始数据，不派agent。
- 重要突破：数据构建进展，是；信息优势/真实收益突破，否。全部399252原观察行保留；本次0fit、0模型加载、0金融/native/prepare/provider/下载，不把数据标签分布当策略绩效。
- 开始/结束新增选参过拟合：**否**，公式、输入、区间和预算已事前固定，未因结果改参数或删品种；历史反复观察的研究选择风险仍在。继续价值：**是**，交011独立接受后才有资格做007唯一固定统计实验；真实执行、窄损与投注生存尚未验证。

## 真实终态与覆盖

唯一实际build于11:38:18—11:38:54完成，**exit0，35.834889875秒**，原session45546，启动chunk2cc675、终态poll1b88f8。一次只读SQL流式取得1552456个合约日/9520epoch；未做399252次查询、重hash大库或重建004。

| 项目 | 行数/范围 | 解释 |
| --- | ---: | --- |
| 全观察行 | 399252 | 与004/005同event/product/u身份，98产品×4074日；不是可交易或独立训练经验数 |
| 有原reference | 212852 | 不因D或label状态删去 |
| feature_ready | 194709 | 同epoch连续21个source-calendar合法正量bar，15维均有限 |
| 连续历史缺口重暖 | 11942 | 不拿前21个观测行凑21个交易日 |
| 同epoch历史不足 | 6201 | 十年同名或其他epoch不借历史 |
| 无原观察 | 186400 | 原行保留、未知数值空 |
| label_identified | 194168 | 只在理想连续价格DAY屏障模型内可识别，不是实际经济标签 |
| feature_ready但label未知 | 541 | 全部保留供之后预测，未用于提前筛feature cohort |
| 双触达区间 | 6000 | [-1,4]，不确定负类；基础预算后[-1.2,3.8] |
| ready上下文缺失 | 22 | 其他家族无可用u−1特征时前三维0、missing=1，不删本行 |
| ready唯一日期 / family | 4054 / 94 | 日期数也不是独立有效样本量；F合并只控制已知重复 |

history_state完整分布：ready194709、no_reference_observation186400、source_calendar_gap_rewarm11942、insufficient_same_epoch_history6201。label_state完整分布：no_reference_observation186400、stop_only121154、day_close51292、history_unready18139、profit_only15722、double_touch_interval6000、missing_D460、right_censored85。两套状态分别说明历史与目标，不能相加或以一个取代另一个；尾部85中含4个历史尚未ready者，因此ready未知为460＋81＝541。

## 实现合同

每个原reference只使用截至u的同epoch最后21bar，必须恰覆盖source-calendar的u−20..u。20个TR按007原公式、ATR20算术均值；ATR须有限正值。M0依次保存r1/r5/r20归一收益、body、range、close_location（平价0.5）、gap、TR5/ATR20、volume相对过去20bar均值的log、过去20bar高点breakout、ATR/C。OI不是输入，没有旧train_flag、openingOI或AM120门。

M1严格只追加协议四维。先按u日期汇总所有feature_ready观察的r1_atr，F与普通同family取均值；当前u仅取前一个source-calendar日，排除自身family后，按其他family等权算median、正值比例、线性q75−q25。未按D、label、未来涨跌或是否入模筛其他品种，不拼每日代表合约价。当前其他市场状态或未来状态不会进入u上下文；缺上下文也不改变M0/M1共同feature_ready cohort。

DAY目标只查004原planned D的同epoch行，不取下一有价行、未来主力或其他合约。F=D.open；R=.25ATR20，SL=F−R、PT=F+4R。等号计触达；仅SL=[−1,−1]、仅PT=[4,4]、均无触达=(D.close−F)/R、双触达=[−1,4]。proxy上下端仅扣固定0.2R预算，不是实际费用/PnL。无D、D超上界、非法D价格、非正SL或历史不ready均保留明确状态和空区间，不补0；identified才填label_known_date=D，仍只是D收盘后模拟日期合同，不造午夜或精确发布PIT。

`feature_labels.csv.gz`只含身份、family、ready/状态、own11+market4、atr20诊断和代理区间/known-date；**没有原OHLC、volume、理想F或屏障价格进入训练文件**。价格哨兵另放audit_paths.csv.gz，明确不供010训练。year_counts.csv是状态计数，不是收益表。

## 固定TDD、数值环境与单次命令

四方法先RED（chunka47214，exit1，四项均为selector尚未实现的真实AssertionError），后GREEN（0719df，4/4，0.055秒）；字段细分为统计资格/真实经济资格后同四方法最终GREEN（8cc728，**4/4，0.049秒**）。覆盖：

1. 同epoch21bar的全部11个公式及平价/零ATR边界，含独立手算收益、成交量均值和ATR。
2. SL/PT边界等号、双触达区间、DAY未触达、0.2R预算、缺D、右删失、非法价和非正SL，未知不赋0。
3. F族内均值、排除own family、u−1而非当前日信息、未识别label也可贡献ready上下文、无其他family时missing。
4. 真临时SQLite只读与小库SHA不变、一次SELECT、全行/no-observation保留、追加未来高量/价格不改早期特征/目标、缺D不跳下一有价日、calendar缺口和跨十年epoch不借历史。

只编译新增两源，chunkc9d3b9 **exit0**；未跑旧suite、无fixture fit。实际数值环境为`.py311/bin/python`、Python3.11.5、NumPy2.2.3、pandas2.2.3、SQLite3.43.1；不导入旧金融FROZEN/qmt/native栈，不安装依赖。component_verification.json保留RED/GREEN、两源SHA和当时尚未actual build的事实。

唯一实际命令：

```sh
.py311/bin/python research/lines/futures_full_market_long_signal_ai/tools/stage009_day_proxy_dataset.py \
  --protocol /Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage007_quality_protocol/protocol.json \
  --protocol-sha256 2e5da3da4440223e3ac978256d563b80d5bd4264cec56d4085ed6062d7bad0a4 \
  --output /Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage009_day_proxy_dataset/export
```

没有因观察超时重启。终态后仅新产物SHA链校验（c249bf，exit0），未重读源SQL或重建数据；actual_build_invocations=1。writer自身不签独立数据资格，011尚待完成。

## 冻结交接

所有实际数据在 `outputs/stage009_day_proxy_dataset/export/`：

| 文件 | SHA256 |
| --- | --- |
| ../tools/stage009_day_proxy_dataset.py（从本线tools读取） | `f7e9eaa56bee511e670a0f09175e58321ab358a501b3e0d63a5d6e2b3ddb89c4` |
| ../tools/test_stage009_day_proxy_dataset.py（从本线tools读取） | `1ee59dd763fb1d54b2bb65b35f36b5690b5d6e8511c0393610f4092f7d79ac51` |
| manifest.json | `ea26675e8322bee8a3c71d4ba0c731055a52a161359c1ac456de628029a5071e` |
| feature_labels.csv.gz（51830368 bytes、399252行） | `9b2452fa5fc8bb0c97d702d0caffa2a2b22e46e38ea52ab4842c13d25f120a48` |
| actual_terminal.json | `8c253db4603cb4027e58344feba601994b7289eacae018718065e51e1ba0ac69` |
| audit_paths.csv.gz（14637634 bytes） | `a0ed32d19c102767bb789cdb1bab2ab28da1b714fa426ca1a368947b87ee6fef` |

manifest schema=`stage009_day_proxy_dataset_v1`；dataset与feature_label_csv为同一path/SHA/bytes/rows/columns binding，source_calendar及完整4074日期网格一起给010；004 manifest、005独立receipt、007/spec及22项小源字节绑定均明示。原DB继承SHA `a63f92ce7e1d51080ba92f7214fc493f1e6a69aa0079d6ecef7190eea9b58711`，378552320 bytes、mtime_ns1792236170627661666、inode28078628；前后state一致，无WAL/SHM，不重hash大库，不把stat/hash当逐价全验证。

`statistical_proxy_available=true`；`qualified_for_fixed_proxy_experiment=false`及pending_independent_stage011_review表示作者不自签；011通过后可以单独签该固定统计实验研究资格。`real_economic_labels_ready=false`、model_ready/financial_ready/label_ready/production_qualified=false表示真实经济/模型部署未就绪，**不能反过来阻断011通过后的007固定代理筛查**。已与010作者明确共同接口；010应保存全部ready预测及541个未知目标状态，不得仅预测identified集。

实际最终路径/SHA已交root、011作者和010作者；011只独审，不重建009；010仍等其receipt绑定相同manifest后才允许唯一实际72fit。本文写完后代码/产物不再修改，当前不自行开始结果审查或新实验。

## 判断与边界

沿007已读MIT Kaminski/Lo、Backtrader官方执行假设/bracket和DeePM作者资料/GitHub的判断，不新增网络：止损/跨市场信息增量需要条件与执行验证，不能从外部论文推得本仓库alpha。0.25/4/DAY/0.2R是事前固定的研究假设，不是已证明最优或“极小”止损。

这些是理想即时触达模型内的区间，不是包含gap/tick/限价/费用/成交量/保证金的真实现金上下界；无重试、roll或隔夜手数，不等于旧native退出或原组合反事实。identified子集也不等于全市场可交易。下一步只按007固定信息增量问题检验，不换阈值/屏障/成本救结果；失败允许停止该特征包＋代理政策，而非否定所有AI。

新增/修改/删除策略参数与财务回测结果0；权益、收益率、DD、Sharpe、滑点、实际交易次数与胜率均N/A。开始/结束新增过拟合否、继续价值是，目标仍active，无alpha及正式资格主张。
