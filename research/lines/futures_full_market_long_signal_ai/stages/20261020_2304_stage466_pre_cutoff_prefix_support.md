# Stage466：原cutoff前开放前缀支持的一次metadata测量

- line_id：`futures_full_market_long_signal_ai`；记录：2026-10-20 23:04 CST；工作区：`/Users/mac/Desktop/fian`。
- 性质：必要条件测量，非重要突破、非新模型/回测；原六所98产品95家族long-only目标、原0.25N first-exit目标保持不变。
- 依据：root 465 `next_scope.json` SHA `6b70dfb796bb69809377eca3f963885d0ef56fea3702e907438c8a34b957417d`，绑定464精确合同与32字段白名单。464 locator确认227/233不能无损替代，因此授权原129一次白名单流投影。
- 开始反思：新增按收益救参的过拟合**否**，本次不读取数值Y、价格或分数；同史适应性择题风险**是**。继续价值**是，但仅核可观察前缀是否存在与可重建**，不借此重开K_TARGET/DOMAIN/log效用或模型。

## 裁决与限制

**原两个cutoff均存在可验证的合格开放前缀；不存在额外前缀的停止条件未触发。模型/IPCW/辅助损失/资金仍NO_GO。** 作者测量程序报核心时钟矛盾与未分类为0，结果等待root另派467独审；本阶段不自行签发独审通过。

这只确认原成熟闭合回归以外确有“已进入、此前尚未退出”的观察信息，**没有读取或证明其终值R方向、大小、独立删失、尾部正支持、alpha或加注资格**。原130成熟纪律没有被证明有bug。观测age最大值也不能覆盖未见尾部。

## 外部调研与本地源判断

沿464已经核过的[官方IPCW条件](https://scikit-survival.readthedocs.io/en/stable/api/generated/sksurv.metrics.concordance_index_ipcw.html)、[维护者源码](https://github.com/sebp/scikit-survival/blob/main/sksurv/metrics.py)、[AFT文档](https://scikit-survival.readthedocs.io/en/stable/api/generated/sksurv.linear_model.IPCRidge.html)与[原作者删失识别研究](https://arxiv.org/html/1905.02508v1)，本次没有重新下载/执行外部算法。判断保持：时间信息可存在而金额目标仍未识别；不能把支持测量清洁当作IPCW默认可识别。

原129会在capacity不合格时保留 `u_action_eligible=0`，随后仍可能继续模拟filled路径；因此全表保留这些行，而**额外可用prefix只取u合格**，不能用filled替代eligible。227缺少三个不可派生reason字段，233带K金额且缺last_path，均不用于重建新样本。

## 一次执行、源读取与身份守恒

- 隔离脚本：`outputs/stage466_pre_cutoff_prefix_support/prefix_support.py`；8个手算小fixture覆盖cutoff当日退出、event日、held missing k−1、exit-cost事件mark未知、entry/cancel无暴露、ineligible filled无合格支持等。先以未实现stub观察8项断言失败，完成后8项通过；最初NotImplemented占位也出现预期错误，均发生在原数据执行前。未跑旧suite或原模型。
- 唯一actual：session `54772`，2026-10-20 23:01—23:02 CST，**61.710967秒、exit0、1启动1完成**，无自动重启。
- 原129 actions物理CSV只完整解码一次，同时获取schema；只保留32列metadata，排除列不数值解析、不输出、不使用。原七列母表一次、原calendar一次。大input不重hash，继承accepted SHA，按size/inode/mtime前后核对一致。
- **1,552,456 action / 399,252 mother / 186,400 nochild母行 / 98产品 / 95家族 / 六所全部保留**。action连续sequence、母sequence/identity、母子映射、母内epoch唯一、母子计数守恒通过；完整action_id原字节保留，其全局唯一性继承原129接受证据，没有冒称重新计算全局ID hash。
- 一个 `action_metadata_state.csv.gz` 保存32原字段、family哈希/相关family-u身份及两个cutoff派生状态/精确age；母表单独保留全部七列身份及子计数，没有复制六份大表。新投影供独审，不再读原大源。

## 严格cutoff和状态支持

`j_c=searchsorted(原calendar,c,left)−1`；phase沿 `after_all_source_close`。行政cutoff是已有训练时间界限，不是新固定持有期。

| 原cutoff | 最后可观察源日 | index | u<cutoff全部action | u合格 | 已进入且可重建状态 | closed成熟 | alive开放 | held路径中断 | entry unknown | 已知取消 | D尚未可观察 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 2020-01-01 | 2019-12-31 | 3645 | 585716 | 255856 | 248647 | 247795 | 541 | 311 | 90 | 6950 | 169 |
| 2023-01-01 | 2022-12-30 | 4373 | 952350 | 460640 | 448639 | 445475 | 982 | 2182 | 653 | 11035 | 313 |

表中closed/alive/held/entry/cancel/intent为u合格域；2020/2023此前另有329860/491710行u不合格，原metadata及原模拟状态仍保留，均不贡献合格暴露。未来u的966740/600106行分别标为 `future_u`，没有提前算成已知信号。每个cutoff的全状态加总均等于原1,552,456行。

本数据在两个cutoff的合格历史域均没有遇到exit-cost event mark未知或其他未解析状态。代码仍将该分支与普通alive分开，**没有因为此次为0而删掉该语义门**。

精确年龄从entry按source-day计：closed事件日排除于event-free；held missing在k的观察最多至k−1；exitcost若k已触发事件，last_path=k也不将k计alive；entry unknown、intent、cancel无虚构暴露。最终cutoff后closed行可由原模拟“首个unknown即终止”的合同证明此前前缀，但其未来退出结果不进入cutoff信息。

## 额外开放前缀与原六fold角色

| cutoff | scope的训练family域 | 开放action | 相关family-u | 开放前缀源日合计 | 精确age范围 |
| --- | --- | ---: | ---: | ---: | --- |
| 2020-01-01 | main | 541 | 248 | 4019 | 1—32 |
| 2020-01-01 | holdout_0，hash!=0 | 351 | 171 | 2333 | 1—32 |
| 2020-01-01 | holdout_1，hash!=1 | 190 | 77 | 1686 | 1—29 |
| 2023-01-01 | main | 982 | 279 | 7319 | 1—24 |
| 2023-01-01 | holdout_0，hash!=0 | 647 | 189 | 4588 | 1—24 |
| 2023-01-01 | holdout_1，hash!=1 | 335 | 90 | 2731 | 1—23 |

main开放前缀分别涉及53/58家族，u与entry年份分别均为2019/2022。这不支持删去无开放前缀家族，也不证明当前全部95家族或未来年代都满足删失支持。action月份与同日family-u相关，两个cutoff亦不独立，不以大行数当独立经验；不同状态的family-u支持可能交叠，不能逐状态相加。

原130 `h(family_id)=int(sha256(str(family_id)),16)%2`，普通/F同family。holdout_j的历史训练family为 `h!=j`，其未来测试为 `h==j`。summary分别列训练历史、排除held历史、forward测试、forward其他family、部署窗外later；母/子角色均守恒，未混淆训练排除与前向测试。

两个cutoff的metadata闭合合格计数分别为main247795/445475，holdout_0为171712/297404，holdout_1为76083/148071，**与六份原130小fit_records逐格一致**。只核metadata计数及继承的原closed/finite-Y不变量，没有打开旧训练大表或重新验证Y数值，不能称新全行训练Y审计。

`exact_age_support.csv`保留每个精确source-day age的event-free、closed event、mark-unknown event、首次未观察interruption及行政censor计数，无分箱/新horizon。随后仅从新小age表复核10个训练/排除held角色积分，与summary源日总量及event/interruption数全部相等，没有再次读原源。

## 输出与实际计数

- `actual_run1/action_metadata_state.csv.gz`：112644206B，SHA `e290400d43d702bf97ba25e3bff1b0f317d9eba443d7465e06b8dfec2d824465`。
- `actual_run1/mother_identity_state.csv.gz`：22524157B，SHA `6cc5b4297035d21d22585695efaddd63326da8a23d7bfa006d7edf3e318a0e3e`。
- `actual_run1/summary.json`：21443B，SHA `650d7410506606552c5009911eaddd3c3edb2f964cb237f3abf3ec3f18671cd4`。
- `actual_run1/source_read_receipt.json`：6485B，SHA `7d56c24f3376276eaa733d777696dcaef5ce9e184bf512e637e2b3f6d4bd3f09`。
- 另有exact age、family/year coverage、anchors、空矛盾清单、started/terminal/manifest；`report_metrics.json`只汇总新小表，`fixture_terminal.json`和`execution_handle.json`保留有限验证及唯一执行身份。完整新文件bindings在actual manifest，不需为排版重跑。

原actions1/1、母表1/1、calendar1；**numericY/价格/COMMON/score/q/SQL/API/下载/fit/cash/原大input hash全部0**。累计保持466fit、254完成cash及1旧partial。新增/修改/删除策略参数均无；期末权益、总收益、最大回撤、Sharpe、总滑点、交易次数、胜率全部N/A，未跑新金融回测。

## 结束反思与交接

新增按成绩调参过拟合**否**，没有消费收益或选阈值；同史研究适应性风险**是**。本次必要条件测量已完成，**继续重复该测量价值否**；新增survival/IPCW/辅助训练或cash价值**否，尚未建立原终值目标的识别条件**。继续完整全市场高质量做多AI目标价值**是**，但不能把本结果当alpha、窄损封顶或加注证据。

下一步只交root/467独审现存新metadata与汇总、确认守恒和时钟语义；不新增Kknown训练样本、duration目标、尾部填充、horizon、weights或模型。未改LINE/registry/旧源/其他线/Git/正式策略/CTP/邮件/launchd；日常测量不追加根历史总账。
