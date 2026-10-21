# Stage317：既有纯COMMON52前瞻最小依赖盘点

记录时间：2026-10-20 02:46（Asia/Shanghai）。所属线：`futures_full_market_long_signal_ai`。非重要突破；只读盘点，0fit、0cash、0SQL、0价格/大表读取、0大文件hash、0旧程序import。只新增本stage及[小refs](20261020_0246_stage317_forward_minimum_dependency_refs.json)，不改LINE/registry、模型或策略。本次不读取296/297、306/307、311/313新成绩。

结论：**可冻结既有最少纯52模型及原政策身份；尚不能声称已有可执行的新日期前瞻生成器。没有发现需要重训才能补回的模型/特征scaler缺失。** 后续只需一个最小、无未来标签的因果生成与观察接线任务；不应把这些工程缺项扩成正式生产资格循环。

## 已有的精确小状态

原130记录有main/holdout0/holdout1×2020/2023共六fold；前瞻沿用最新`main/2023-01-01`，不重新选择cutoff，不借held模型部署。实际读取并对原130 manifest核SHA：

| 状态 | 实际路径（本线下） | 字节 / SHA256 |
|---|---|---|
| portable52 | `outputs/stage130_contract_choice_fit/actual_run1/folds/main/2023-01-01/portable_model.json` | 2787 / `a9d3e60d70d3b0d30be3bcee49074131ef1be0ae1660dff3bbaa1bb1217330a4` |
| 原scaler | 同目录`scaler.json` | 4680 / `130ddae5588b257097a0e91fa7bceba1c86ae049cbab5849140369443fd47932` |

portable含52有限coef与intercept `-1.1014442064238599`；scaler含26列顺序、mean/scale及52设计列顺序，顺序一致、scale均有限正。固定计算为有限raw列按原mean/scale标准化、非有限值标准化位置0，再追加26个原missing flag；`score=z52·coef+intercept`。不fit、不用近期样本重居中。原joblib739字节仅stat，非恢复算术所必需；未unpickle。原130源码曾检查portable与原predict近似一致，本317没有新运行预测或宣称bit级复验。

原129/130及263接受的070/131/157代码binding、156/157协议与manifest身份均可继承，详见refs；无需为前瞻恢复重读训练CSV/Y、COMMON大NPZ、旧scores、旧actions/mothers或normal equations。小状态恢复不等于未来因果接线已验收。

## 可推导但尚未执行的最小因果链

1. 原129 `own11`、`maturity_pool/maturity13`和u时点资格可抽成纯u入口，输出原26列。自身11列需要含u的21条同真实月份、源calendar连续有效bar；peer13由同product-u可见真实YYYYMM月份构成，价格仅用u及过去，保留原query排除/缺失规则。最后成本/low20距离仍用原2N单位。原`action_stream`调用未来first-exit标签，不是可直接运行的新日生成器，不能伪造未发生label。
2. 不混淆两种归一化：own11用SMA20 TR；原042 `EpochSeries.N`先20TR种子再Wilder递推。未来续接需原N/run/last close与low20/窗口状态，或之后获授权的因果历史重算；仅取21bar重新种N会改变政策。原132 cache已有OHLCV/N/low20/run，但本次未加载/提取。
3. mother沿004原代表规则：u正成交量最大，close OI参与并列，再按epoch。纯52不直接消费OI值，也仍需这个anchor输入。全原98产品/95family（普通与_F产品池不混）及不可用父行保留；全真实月份先评分、原u资格与score>0、D<K在argmax前，原156 tie与family优先级不变，不能只用157历史4365条入选缓存。
4. K目标为交割前月1日；真正K是首个源交易日>=目标。156原函数在精确K pending但真实D已确认且`D_date<K_target`时已有充分证明，不伪造K日期；其余依原unknown/blocked状态。旧calendar未接上未来D，这是实际缺项；不以未来first_seen回补过去known。
5. 157 `make_voluntary_signals`是历史身份/choice join再加K边界，历史signal缓存不是未来生成器。070/131原NARROW资金核可复用（参考初始100万、单family0.0025、总risk0.02、margin0.25、buffer1.1、0.25N及原base/stress成本）。成本/实际D执行、持仓与pending各用自己的账本状态。历史`run_cash_account`自建空账本且按end限制准备D，不是现成滚动前瞻服务；下一观察合同应固定初始化及连续own-state，不由317另选新政策。

## 真缺项与现有历史数据边界

| 类别 | 最小缺项或边界 |
|---|---|
| 接收 | 尚未绑定授权的新日完整真实月份输入交付、源交易日完成时刻、received_at及版本/修订receipt；266是历史清理入口，不证明已安装持续接收器。无需为此启动下载、CTP、邮件或定时任务。 |
| 日历/时点 | 下一真实源session D、实际首开deadline与可见版本需接线；自然日、夜盘日期、交易日不可互换。 |
| 元数据 | 新epoch经济映射、tick/lot/multiplier/fee/margin、lifecycle、单位/质量须有当时可得版本；旧041静态映射不保证未来覆盖，不用邻月代理。 |
| 新日生成 | 原52纯u特征/资格、mother和action身份、固定模型推断、156选择到157/131输入的薄适配尚未实现或新日验证。 |
| 连续观察 | 初始账户状态、pending持久化、base/stress独立own-state和每次decision/账本receipt尚需最小合同。正式C9的production manifest/activation并非本研究观察的前置依赖。 |
| 域 | 原固定98是已接受历史母域，不能冒称未来永远全市场。未来新上市catalog first_seen须记录；unsupported、经济缺项与unknown保留，不默默drop，也不擅自扩模型输入。 |

当前历史DB/cache/economic projection/calendar路径均存在且字节匹配继承binding（refs仅stat，不重hash/加载）。132 cache历史上止于2026-10-16，这能做warmup来源，不能证明之后数据已接收或具备PIT版本。完整历史价格和正式生产环境未在本317恢复。当前`.py311`元数据：Python3.11.5、numpy2.2.3、pandas2.2.3、scipy1.17.1、scikit-learn1.6.1、joblib1.6.0；未安装/升级、未import旧程序。

官方[模型持久化文档](https://scikit-learn.org/stable/model_persistence.html)要求保留预处理/输入语义与环境，不能把跨版本pickle加载当等价保证；[维护者GitHub源文档](https://github.com/scikit-learn/scikit-learn/blob/main/doc/model_persistence.rst)身份已核，本轮浏览未获得其全文，未据此增加推断。这里优先用已有portable算术和原scaler，版本信息仍需保留，网站当前版本不触发本地升级。外部共两页，未新增检索/下载。

## 最早真正forward与研究反思

317本身不是最终冻结。root后续须固定不可变T0；只有**T0之后才完成的源交易日u**，且当时实际接收的版本能在真实D首开前封存decision，才属于forward。晚取已完成的2026-10-19永远是历史回填；2026-10-20也仅在其真实交易日完成晚于T0且满足D期限时才可能成为首个u，本317不声称其日历/数据已确认。迟到则记`no_forward_decision`，不补发历史D、不把修订版回溯成当时所知。

新增/修改/删除模型参数与回测结果均无，权益/收益/DD/Sharpe/胜率等不适用。当前不是一次新拟合过拟合操作；纯52本身经历过历史研究，其既有选择风险仍在，前瞻不会自动抹去。继续的价值在于固定一个现有政策并收真实新证据；没有价值的是借准备依赖继续同史换函数或新增资格循环。下一步由318给最小观察合同，再另行授权因果生成器；本317到此停止，0actual。
