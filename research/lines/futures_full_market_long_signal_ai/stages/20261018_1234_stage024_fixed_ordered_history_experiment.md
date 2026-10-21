# Stage024 固定S摘要／真实20bar时序／同四元组BAG信息实验

- line_id：`futures_full_market_long_signal_ai`。
- 当前模式：六所全市场long-only独立研究，固定代理信息筛选，**不是金融账户回测**。
- 记录时间：2026-10-18 12:34 CST；实际完整运行12:32:11—12:33:55 CST。
- 工作区/分支：`/Users/mac/Desktop/fian`，`codex/ai-training-data-expansion`；不新建分支或工作树。
- 阶段性质：执行Stage022收益前冻结的单一表示与学习器实验；唯一启动、唯一完整，108个真实年度fit。
- 是否重要突破：否。结果是清楚的未通过证据，未发现可进入窄止损加注研究的稳定质量增量。
- 是否触发A/B：沿Stage022预声明三臂研究合同，不改正式策略或生产资格；金融与生产资格均为false。

## 外部调研与判断

本阶段沿用Stage021/022已完成的原始资料调研，没有再次搜索或复制外部实现：[Lo、Mamaysky与Wang原论文](https://www.mit.edu/~alo/Papers/1705-1765.pdf)、[MiniRocket原论文](https://arxiv.org/abs/2012.08791)、[作者GitHub](https://github.com/angus924/minirocket)。判断保持不变：序列表示可能提供现有摘要之外的可预测信息，但存在统计条件分布差异不等于存在交易利润；MiniRocket默认大量特征也不等于本研究所需的小容量受控比较。这里只检验一个固定学习器能否利用同20bar四元组的时间位置，不能把结果外推为所有序列AI、所有技术形态或默会知识均无效。

## 本次变更

- 新增脚本：`tools/stage024_ordered_history_experiment.py`、`tools/test_stage024_ordered_history_experiment.py`。
- 修改/删除旧脚本、正式策略、旧回测结果或参数：0。
- 新增固定研究参数：S11、20bar×4通道ORDER和完整四元组字典排序BAG；128维RFF、139项头加截距；`default_rng(20261018)`依次生成91×128正态W与128相位b；S主动维11、ORDER/BAG主动维91，`gamma=1/(2*d_active)`；Ridge `alpha=1,solver=cholesky,fit_intercept=True`，BLAS线程1。
- S只以同训练日期等权、population均值方差标准化；序列跨20位置池化四通道，ORDER/BAG共用同四尺度，不做lag独立标准化或额外头scaler。
- 每个scope-year保存训练event_id、sequence_index和原日期权重到一个共享NPZ，三臂均绑定同一文件；每个fit立即保存scaler、系数、截距、版本和训练身份hash。保存实际W/b。共108个fit JSON与36个训练成员NPZ，可通过完整fit闭包export-only而不重新训练。
- 不下载、不读SQL、不输入D坐标、market-lag或绝对ATR；不引入AI池、C9信号、品种筛选、setup或新的score阈值。

## 参数、输入和真实运行证据

冻结协议为`outputs/stage022_ordered_history_protocol/protocol.json`，SHA `ae0708cb9eb232d5c5d7936fc705f77b2f361e4b039442e707b82c828b27f99a`。

原009完整母表399252行，ready194709、identified194168、ready未知541；原52MB输入的manifest SHA `ea26675e8322bee8a3c71d4ba0c731055a52a161359c1ac456de628029a5071e`，沿011接受。023序列manifest SHA `3b8da3d7e94a9e3e3fc755b233d2bb93ef6ebf6813a66a0a0a913052eb8bf64a`；`ordered[194709,20,4]`以float64公式后量化为`<f4`，在消费时转float64，event_id严格按009原ready顺序一一绑定，BAG从已量化的完整四元组排序。没有按未来D是否可评价删输入。

12个年度测试2015—2026，训练从2010年起扩窗；每年首个source trading date为exclusive cutoff，u和label_known_date均严格小于cutoff且label_identified才可训练。主main及两个SHA256(family)%2家族留出，各三臂，共12×3×3=108fit。家族留出排除该组全部历史训练行。2010—2014是预声明训练暖机区，不发出年度测试预测；因此测试期共有161609条ready预测（identified161105、未知504），不能误称194709行都已OOS预测。原541未知在输入中完整保留，其中37条属于测试起点以前。

标签与成本完全沿007/009：下一source日同reference epoch OPEN，止损0.25ATR、目标4R、DAY退出，基础研究成本0.2R、压力成本1R；双触达保留区间，未知不当负类。mask唯一`score>0`。ORDER-S、ORDER-BAG以同一事件的mask系数差乘共同区间，完全相同mask精确抵消；不使用018不同入场的外界。每source日共同identified cohort品种等权，再日期等权。原source空日NaN；moving-block bootstrap为60个source日、2000次、固定seed，所有列共享索引，CI不含重训与研究选择不确定性。

必要行为fixture：RED实际tool chunk `8160fd`，5失败，0fixture fit；GREEN `218072`，5通过、1fixture fit。覆盖成熟与族排除、pooled尺度/四元组几何、共享映射与S带宽、same-mask抵消/未知空日、保存系数重放和日期权重。只编译这两个新脚本；旧套件、真实pilot、其他宽度/alpha/seed试跑均0。

唯一全表CLI：`.py311/bin/python .../tools/stage024_ordered_history_experiment.py fit --bindings .../outputs/stage024_ordered_history_experiment/input_bindings.json --output .../outputs/stage024_ordered_history_experiment/experiment`。

真实初始chunk `39bf1f`返回session `91664`，后续保持同一handle，终态chunk `0709c8` exit0；运行104.698917秒、108真实Ridge fit、0金融/SQL/网络/下载，失败尝试0。实际stdout保存`fit_stdout.log`，逐fit系数与身份保留；没有重复启动，没有导出后再重训。

## 结果

以下全为date_equal、按全体共同机会分母的normalized代理效用，不是每笔平均现金R，更不是组合收益率。

| 2020至今主main | 区间下端均值 | 区间上端均值 |
| --- | ---: | ---: |
| S自身 | -0.0037273672 | 0.0009228137 |
| ORDER自身 | -0.0021926731 | 0.0015155197 |
| BAG自身 | -0.0007172334 | 0.0017550974 |
| ORDER−S（same-mask精确区间） | -0.0020275875 | 0.0041549875 |
| ORDER−BAG（主表示对照） | -0.0025562979 | 0.0008412805 |
| ORDER−同日参与率诊断 | -0.0018021288 | 0.0050227493 |
| 同mask 1R压力ORDER自身 | -0.0239477200 | -0.0202395272 |

- 2020至今ready预测107844条：identified107437、未知407（missing_D326、right_censored81）。ORDER选中已知2781条、1038日期、87家族；选中未知22条也保留，不能偷当无交易或亏损。
- ORDER自身lower的95%CI `[-0.0058934425,-0.0006231141]`；ORDER−BAG lower的CI `[-0.0044295059,-0.0007078031]`；ORDER−S lower的CI `[-0.0056891753,0.0010349905]`。这是**下端估计量的CI**，不能与整条部分识别区间混同。
- ORDER自身和两项配对的识别区间均跨0，因此不能凭下端为负断言真实路径一定更差，也不能用上端为正声明真实增量。固定质量门均要求保守证据，本次没有得到。
- 2015至今ORDER自身lower `-0.0044856489`、ORDER−S lower `-0.0058727852`、ORDER−BAG lower `-0.0041830485`、参与率lower `-0.0029671148`，四门全失败。
- 2020—2025六个完整年，ORDER−S lower正3/6，ORDER−BAG lower正0/6；2026部分年ORDER lower `-0.0002086767`。
- 家族留出0：ORDER自身/ORDER−S/ORDER−BAG lower分别 `-0.0037526959/-0.0022941439/-0.0046739584`；留出1分别 `-0.0090106040/-0.0099601498/-0.0082156363`。六个家族稳健门全失败。
- 固定20门：**2真18假**，仅日期及家族支持两门通过，`quality_information_screen_pass=false`。不把BAG表面损失较少升级为另选winner。
- ORDER选中已知中确定profit_only245条、double_touch74条，目标先到比例识别范围约8.81%—11.47%，误删确定profit_only8627条；这是稀有质量诊断，**不是胜率**，不据此另挑阈值。
- 期末权益、总收益、最大回撤、Sharpe、总滑点、真实总交易次数、真实胜率：全部N/A，本阶段金融回测0。

## 输出与身份

主要目录为`outputs/stage024_ordered_history_experiment/experiment/`；完整annual/scopes统计、8张scope-period日表、3份scope预测、108个模型与36份训练身份都在该目录，详细数值见`metrics.json`，不在根目录重复大表。

- 新源SHA：`f2bfc43d2b685df6f77a535bd6fb696f18bf54dac93b6ff39f5b60cb6e03fa46`。
- tests SHA：`2b69c1cc3d1801d0392efa3ef890df61832bf6cdb4937639ac64d2eefb9f0669`。
- 最终manifest SHA：`51c28a267edce63fd19d1049d4a9458b6e21cf1a5c81a02be40ee45333948097`。
- metrics SHA：`59446b20312120eaf097ed1de930349790ccd49546c7c1a0c97af1f346b38ef3`。
- actual_terminal SHA：`963e5050155d03e42736456f42ad1c6181c0fef214cf67e50791712407f59250`。
- 两期间共同bootstrap索引hash分别为`91e84837482c10cbad55454535baed44b9af310d5332415abb4306f88d200113`、`5c0b1b714adfa5aac8e05636efabd8d8b26606cf46693031b1dcf3a9c24321de`。
- 本记录冻结时025独立验算仍由root调度，不预写通过；独审结果以其独立receipt为准。

## 结论、过拟合和继续价值

运行前过拟合判断：本次是收益前冻结的新信息问题，不是旧失败包救参；风险仍存在于表示和学习器选择、共同历史数据反复研究，以及固定随机方向本身。运行后判断：未证明可利用优势，继续扫描20bar窗、四元组定义、宽度、深度、种子、bag或score阈值来救本次结果会构成明显过拟合，**停止这个特定表示＋学习器＋OPEN包**。

运行前价值判断：有价值。它比继续盘点现有文件更接近“AI识别全市场优质做多”，并用ORDER−BAG隔离时间位置。运行后价值判断：继续重复本包无价值；保留失败证据和转向结构不同的信息问题有价值。这里没有证明所有AI或跨周期趋势结构均无用，亦没有达到用户更高真实净收益、更低回撤、窄损加注生存目标，不允许直接加杠杆。

后续TODO：完成025全表输入/成熟家族/保存系数/精确配对/CI/20门独审；root归档和决定下一独立信息问题。不得修改正式版或用小止损/加注弥补识别失败。

合入建议：本agent不改LINE、registry、root memory或back_log；由root按独审结论统一更新。只登记必要模型、决策、特征合同、资格证据，不复制原始日线DB、OHLC或私有配置；本阶段无commit/push/deploy/CTP/邮件/委托。
