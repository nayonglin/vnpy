# Stage035 同行对应信息COMMON／ALIGNED／SHUFFLED固定实验

- line_id：`futures_full_market_long_signal_ai`。
- 当前模式：国内六所全市场long-only独立信息研究，固定理想代理，非金融账户回测。
- 记录时间：2026-10-18 13:08 CST；实际全表13:06:38—13:07:34 CST。
- 工作区/分支：`/Users/mac/Desktop/fian`，`codex/ai-training-data-expansion`；无新分支或工作树。
- 阶段性质：033收益前冻结后的唯一完整108fit，无失败、无重启、无真实pilot或参数搜索。
- 是否重要突破：否，未通过质量筛选；用户完整净收益/回撤/窄损加注目标仍未达到。
- 是否触发A/B：沿预声明三臂研究合同；不改正式策略、生产资格或此前024/029结果。

## 外部调研与判断

沿032/033已实际核读的[原作者论文](https://arxiv.org/abs/2201.08283)与[作者GitHub](https://github.com/stefanosbennett/mlj-lead-lag)，本agent未重复搜索、安装或执行外部代码。判断：同行值与历史关联的对应关系无法由全市场median/breadth等摘要恢复，值得一次有机制对照的检验；论文的美股网络结果、相关关系和因果影响必须区分。本次20日同步Pearson＋滞后shock单q投影并非直接复现论文，也不穷尽完整跨市场面板。

## 变更、输入与固定参数

- 新增`tools/stage035_peer_alignment_experiment.py`、`tools/test_stage035_peer_alignment_experiment.py`及本阶段输出；旧024/029及其他代码、参数、结果修改/删除0。
- 三臂同19槽：OWN11＋034的scope专属market4＋peer_count/rho_abs_sum/relation_missing共18公共列，再加COMMON常数0、ALIGNED原对应q或SHUFFLED同值确定null q。
- 公共18只按同训练日期等权population均值方差标准化；q按同训练ALIGNED/SHUFFLED各w/2合并估计一个均值方差，三个臂共享同一scaler。COMMON标准化后仍为常数，截距吸收，有效方向18，不能把次对照冒充同容量主对照。
- 固定Ridge `alpha=1,solver=cholesky,fit_intercept=True`，BLAS线程1。无RFF、PCA、非线性、交互、seed/window/lag/hash/阈值搜索，不复用024任何模型或mask。
- 12年2015—2026×main/holdout_0/holdout_1×三臂＝108fit；每年首个source日为cutoff，train要求u及非空label_known_date严格早于cutoff、ready/identified为1，2010起扩窗；held组全历史训练排除，test仅该组全部ready。三个scope必须使用各自034上下文，训练和测试的peer池/market4均按033排除held family。
- 原完整009母体399252、ready194709、identified194168、ready未知541不变。034 event_ids严格按009 ready原顺序一一绑定；三scope各[194709,9] `<f8`；不按D筛特征、不追加暖机删除ready。新源码彻底丢弃009旧全市场market4，X只使用034对应scope的七公共ctx及指定q。
- 标签沿原007 OPEN/.25ATR SL/4R PT/DAY、proxy_lower训练，基础研究成本0.2R与同mask1R压力；不换029去顶标签。
- 所有ready测试先预测，唯一mask score>0；共同identified机会等权后source日期等权。相同mask在共同区间中精确抵消，ALIGNED−COMMON/SHUFFLED不是独立边界粗相减。参与率是事后同日随机参与诊断，非u可执行策略。源网格空日NaN。
- main两个期间60源日moving-block、2000次、seed20261018、所有列共同索引；CI仅固定预测，不覆盖重训/择题/真实金融。20门全部收益前固定。

033协议SHA `6328b2429106028531916050982bcf57f033285366a745f2f08a29a308a2556b`。009父manifest `ea26675e8322bee8a3c71d4ba0c731055a52a161359c1ac456de628029a5071e`及011固定代理接受绑定不变。034最终manifest `2a3abe55eabf0fba5bb5d749fb4343d1bf341e3d217b93619554ab11bf98d990`，context NPZ `ba38c6386d56c290f5dbaf3770b9db21c754e8e4f9185e32a9328c0ce45ab272`。评价只沿parent scope4074日期，未把完整5587日历的scope外空日混入。目录family数不能误当ready family数。

## 测试、复现与真实进程

4个必要行为：成熟/族排除与scope绑定；公共18和pooledq共用尺度/COMMON常数；same-mask共同payoff与未知空日；保存19项系数重放和日期等权。RED实际chunk `0a80dd`，四失败、fixture fit0；GREEN `af4e31`，4/4、fixture fit1；只编译这两个新脚本，旧套件和真实pilot0。

root fresh确认034最终输入、037设计无阻塞后明确授权。唯一实际CLI为`.py311/bin/python .../tools/stage035_peer_alignment_experiment.py fit --bindings .../outputs/stage035_peer_alignment_experiment/input_bindings.json --output .../outputs/stage035_peer_alignment_experiment/experiment`。初始chunk `eb3402`返回session44639；中间`de7313/eb6001`保持同一活句柄；最终`bbde30` exit0。实际55.520969秒、108真实fit、0金融/SQL/网络；无失败/重启/换参。

每fit立即fsync保存19个coef、截距、shared18/pooledq scaler、训练ID与权重SHA、cutoff/held/context_scope/版本。36个训练成员NPZ只存sequence_index及原权重；可由已绑定034 ID表无损恢复event_id，不重复压缩Unicode ID。完整108模型可export-only重放，不需重训；本轮未为验证再调用export-only或旧实验。

输入194709 ready/541未知中，2010—14预声明暖机不发年度OOS预测；2015+共161609 ready预测，identified161105、未知504；37条未知属于暖机，并非按D缺失删除。2020+ ready107844、identified107437、未知407全部保留。

## 结果

以下是全共同机会分母下date_equal normalized代理效用，不是每笔平均R、净现金收益或账户复利。

| 2020至今main | 识别下端均值 | 识别上端均值 |
| --- | ---: | ---: |
| COMMON自身 | -0.0001476939 | 0.0016202897 |
| ALIGNED自身 | -0.0003786893 | 0.0012529859 |
| SHUFFLED自身 | -0.0001334687 | 0.0013565298 |
| ALIGNED−COMMON | -0.0003673038 | -0.0002309954 |
| ALIGNED−SHUFFLED（主对照） | -0.0002881089 | -0.0000606557 |
| ALIGNED−参与率诊断 | -0.0007000395 | 0.0016555825 |
| 同mask1R压力ALIGNED自身 | -0.0059562295 | -0.0043245543 |

- ALIGNED自身lower的95%CI `[-0.0028305234,0.0007694866]`；主ALIGNED−SHUFFLED lower的CI `[-0.0005926294,-0.0000262100]`，upper的CI `[-0.0003292157,0.0002416563]`。次ALIGNED−COMMON lower的CI `[-0.0006914976,-0.0000843258]`。
- 两个配对在**当前历史样本**的部分识别均值界都小于0，未表现出正的对应信息增量；但配对upper估计量的区块CI仍跨0，不能外推为未来所有同行信息必然负贡献，更不能混淆识别区间与估计量CI。
- 2015+ ALIGNED自身lower `-0.0003735256`，ALIGNED−COMMON `[-0.0002636832,-0.0001854524]`，ALIGNED−SHUFFLED `[-0.0002433378,-0.0000711861]`，参与率lower `-0.0006210802`，四个次周期门均失败。
- 2020—2025完整6年两配对lower均仅正1/6；2026部分年ALIGNED自身lower `-0.0006155012`。
- held0 primary自身/对COMMON/对SHUFFLED lower分别 `-0.0008261703/-0.0004179870/-0.0003430347`；held1分别 `-0.0032469757/-0.0000237826/+0.0001011978`。held1单项正值不能挽救自身为负或挑该组晋级。
- 固定20门 **3真17假**：只有日期/家族支持两门和held1相对SHUFFLED一门为真，`quality_information_screen_pass=false`。不事后选择COMMON或SHUFFLED作为赢家。
- primary ALIGNED选中已知701条、360日期、83家族，选中未知22条保留；其确定profit_only88条、double_touch31条，目标先达比例识别范围12.55%—16.98%，误删确定profit_only8784条。这是诊断，不是真实胜率，不据此修改阈值。
- primary context：main关系缺失9.1020%、平均peer54.9044、Z15.8985；held0缺失12.0740%、peer33.3472、Z9.8026；held1缺失7.1718%、peer21.7193、Z6.4059。覆盖与输入池差异完整保留，不以较好组替主结论。
- 期末权益、总收益、最大回撤、Sharpe、真实总滑点、成交次数和真实胜率：全部N/A，金融回测次数0。

## 输出与身份

最终目录`outputs/stage035_peer_alignment_experiment/experiment/`，包含108个模型、36份成员、三scope预测（含对应九ctx值）、8个daily、所有年度/期间/cohort/稀有诊断和共同CI。159份内部资产约61MB，不包含原始OHLC/日线DB/audit/私有配置。

- 源SHA `7141bb6e026fece3baa88d1a98db1d5cbe2a6ed8268d5e5ed9d116b7d4204292`。
- tests SHA `dd884292b6d5053337c17fccf9442c475fea7d5736bd80427d71beb0bb54b9a4`。
- 最终manifest SHA `073526fb3439f42b744519b6a7cb7c4a2931d8169e36c040513d27bc44962c51`。
- metrics SHA `7ed12a42651b08c6ab916b08b5a523512fd02ce51e1ee977ed697f561123ec68`。
- actual_terminal SHA `30d7d00de27e1f5b9d1aa07a793802f20e9e4e4f62e1411b608ab1c3990edb36`。
- all2015/primary共同bootstrap索引hash分别`91e84837482c10cbad55454535baed44b9af310d5332415abb4306f88d200113`、`5c0b1b714adfa5aac8e05636efabd8d8b26606cf46693031b1dcf3a9c24321de`。
- 037设计审查无实质阻塞；本记录冻结时数字独立复算待root确认完整终态后执行，不预写通过。现冻结源与结果，不为独审外的细枝末节重训。

## 反思、后续和记录权限

运行前新增按结果救参：否，032/033先于本ctx/fit，仍有多年历史择题风险；运行前继续价值：是，限检验新增同行对应信息。运行后新增选参：否，完整108fit未中途停选臂；继续扫描20rho/window/lag/hash/peer/seed/阈值或GNN来救这个结果将增加过拟合，**停止本固定单q＋Ridge＋OPEN包**。

运行后继续本配置：否；保留明确失败证据并继续用户完整全市场AI目标：是。本研究未穷尽跨市场信息或复杂因果关系，也未证明真实净收益/DD、执行、极窄止损与加注生存资格，不能以代理小实验替代原目标。

TODO：037独立核034时钟/own及held边界、108训练缩放/全预测、预选6正规方程、全部统计/CI/20门；root归档并决定下一个独立问题。本agent不改LINE、registry或root memory/back_log，不commit/push/deploy/CTP/邮件/委托。
