# Stage013：全市场固定代理实验的接受、否决与复现保存

line_id=`futures_full_market_long_signal_ai`；2026-10-18 11:53 CST。沿用`codex/ai-training-data-expansion`，HEAD `4f42805c2c71f8492a44a6876a82672f410f44df`；新代码以实际SHA绑定，未提交、推送或部署。本阶段不改变策略或模型参数。

## 进展审计与决定

最近的三重滤网问答只核对概念，没有新增策略实证，按目标进展审计记为`no_progress`；本轮没有把问答当目标完成，恢复既有009→011→010→012实际链。本轮为`progress`：新增完整代理表、唯一固定72模型实验与独立数值接受，结果使下一步从继续该特征包转为停止它。

**接受结果的算术与逻辑；否决本次四项滞后市场特征＋固定DAY代理政策作为高质量信息候选。** `quality_information_screen_pass=false`，15门7真8假。独立审查通过不等于策略门通过，更不授予真实收益、窄损加注或生产资格。

## 真实执行与证据

- 009四方法RED→GREEN、两新增源编译；唯一build原session45546→1b88f8 exit0，11:38:18—54，35.834890秒。全399252行保留，194709 ready、194168可识别代理区间、541 ready未知、6000双触达。SQL一次读1552456源行，不重新hash大库。
- 011代码/实际表联合独审原21421→14bc9b exit0，22.306773秒；全表身份/状态/lag与固定屏障公式及20个SQL样本接受，C/I/M=0/0/0。只签`qualified_for_fixed_proxy_experiment=true`；真实经济、金融、生产仍false。root以2d4339实读最终收据/终态并核009同manifest，之后才授权010。
- 010原session38894→326eab exit0，11:44:14—59，45.664339秒，恰72次实际Ridge fit；同一冻结信息实验的12年度/主样本及两组留出模型，并非72次金融策略搜索。无重新拟合、无export-only、无调参。fixture另计6次tiny fit。
- 012独立于010作者，原15277→8be961 exit0，11:49:26—45，18.545825秒。重放72训练身份/权重/scaler/正规方程、646436个标量预测、年度/期间/共享bootstrap和15门，C/I/M=0/0/0。仅纯系数重算，0fit/0SQL。首次wrapper错误解析venv symlink在import前失败，已保留失败终态；修正解释器后唯一完整数值审查，不是重跑模型。root以2ecaf0实际读取最终收据与终态。

| 关键资产 | SHA256 |
| --- | --- |
| 007固定协议 | `2e5da3da4440223e3ac978256d563b80d5bd4264cec56d4085ed6062d7bad0a4` |
| 009实际manifest | `ea26675e8322bee8a3c71d4ba0c731055a52a161359c1ac456de628029a5071e` |
| 011独立收据 | `cf71e0c9a9cc570aa803ad437a117861961c64b13ec920a8b5ab573577301b4a` |
| 010实际manifest | `fc1abeaffb5a15e9b782109fbbadedeab3fb56d4d40eb663d3ba3fb42f0a9b27` |
| 010模型记录 | `28e5c62700127fbf9d04245b6288b70c1b589d3ac3453ba917f0f365d1167b71` |
| 010指标 | `fd1d389573399709619ab9ac3172af422afc7c6195af4a0661e8efdf4559ddfc` |
| 012独立收据 | `e6656decde31912f93fce6b5aaf910760a11971d4558f5e4bb0c39e5b169775f` |

## 结果与解释

下表单位是共同可识别cohort内先品种等权、再日期等权的归一化proxy-R；不是单笔平均现金回报或账户收益。

| 2020—2026-10-16固定统计 | 结果 |
| --- | ---: |
| M0自品种价量lower均值 | 0.0014201341 |
| M1另加四项市场信息lower均值 | 0.0010478387 |
| M1−M0配对区间均值 | [-0.0004276603, -0.0001564018] |
| 配对lower的95%区间 | [-0.0012862966, 0.0005119296] |
| 相对同参与率参考lower的95%区间 | [-0.0007966173, 0.0007917488] |
| 同mask成本预算1R后的M1 lower | -0.0027241532 |
| 两组family留出paired lower | -0.0000548398 / -0.0002727749 |
| 2020—25完整年度paired lower为正 | 3/6 |

主区间107844条ready预测，107437可评价，407未知仍有预测；M1可评价入选473行、223日期、80family。支持数量足够并不补救增量、成本和跨年份失败。2015+配对lower均值亦为负。自身点均值小幅为正、2026部分年为正，均不能作为加注依据。固定样本配对均值区间两端为负，但抽样CI跨0，因此不夸大为已统计证明所有M1都更差；同样不能推出全部AI选品无效。

本轮金融/账户回测为0；期末权益、总收益、最大回撤、Sharpe、总滑点、总交易次数、胜率均N/A，不把473代理入选行称真实成交。参数新增、修改、删除均0；未修改旧回测结果或失败记录。原更高收益、更低回撤、全市场AI识别、极小止损及增加投注目标均未完成，goal保持active。

## 本地保存与边界

按freeze skill精确登记必要协议、源/测试、系数/scaler、全部预测、指标、终态及独审证据；本地登记位置为`research/ai_assets/futures_full_market_long_signal_ai/stage013/20261018_fixed_day_quality_v1/manifest.json`，是否完成以该真实manifest和登记回执为准。不commit/push，不更动正式物料。

010作者角色别名显式映射：`model_reproduction_asset→model_artifact`、`reproduction_asset/source_protocol_binding→feature_contract`。这只解决登记枚举，不改变冻结源码或重跑实验。009原始特征表保留本机；为保存实际X/y，013一次投影只删非模型输入`atr20`绝对价格诊断，其他CSV字符串和行序原样保存。399252行、50981934B、SHA `c344963bc77eee77a34951aaa6654bd4885acd71a0edf20330f16cb477f8b58b`；原root进程5406→a2886a exit0，0fit/0金融。该投影不替换实际输入，不含原始OHLC；原始库、观察价格表、audit价格表、env与运行环境不进入Git。

## 后续取舍与调研判断

停止为本四列/固定政策增加interaction、阈值、topN、成本或坏年补丁。014独立取舍区分旧C0/C_TS真正负结果与B未完成/EMA尚无金融结果，不虚构已败或已胜。唯一保留的下一问题是：同一事前全市场long setup上，仅改变开盘入场为随后可观察的顺势价格确认，能否有每setup净增量，而非单纯少参与。须固定共同风险/退出/成本并保留未触发、未知及路径歧义；不能用入场前的日低作入场后止损，不能同时加入加注、止损宽度或持有期搜索。本阶段没有启动该新实验。

调研沿用007已读的[Kaminski/Lo作者摘要](https://dspace.mit.edu/entities/publication/bb69ca4b-0cdc-487f-831d-63b2e84fafee)、[DeePM作者论文](https://arxiv.org/abs/2601.05975)及[作者GitHub](https://github.com/kieranjwood/deepm)；014另实际读取Elder原著和[Backtrader原作者执行源码](https://github.com/mementum/backtrader/blob/master/backtrader/brokers/bbroker.py)。判断：滞后跨市场建模和结构化入场有理论动机；本次本地结果没有确认四列增量，作者/开源来源不提供本市场盈利保证。未下载运行外部代码。

开始/结束新增选参过拟合：**否**，固定实验失败后未改参数；历史反复研究选择偏差仍在，不能称全新未见样本。继续救本方案：**否**；继续原完整目标：**是**，下轮须有机制区别及可识别执行证据，不能用杠杆弥补尚未成立的识别优势。
