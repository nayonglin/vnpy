# Stage232：固定K单动作收益测量的有限源码与输入可行性

- line_id：`futures_full_market_long_signal_ai`；2026-10-19 20:57 CST；非重要突破。
- 本轮仅查 registry、本线 LINE、229/217及必要小manifest/源码；没有打开129动作/母表、227大投影、132 NPZ、经济投影或数据库，没有实现或测试actual逻辑，没有fit/cash/SQL/下载行情。累计仍433fit/234cash。
- 开始判断：同史反复择题的过拟合风险是；本轮新增按数值收益挑规则否。继续价值有条件是：229已确认对象问题仍存在，值得一次有限测量，但不能由此承诺训练或资金实验。

## 可行性结论与最省I/O方案

可以保持原1,552,456动作与399,252母体身份，只单次流读129原动作的下述48列，单次读129原母表的7身份列，再单次打开132已接受NPZ且只取五个成员。复用227纯分类和156纯日历函数，不读227的103,291,057B动作投影、不重新盘点时钟，不调用132/157/219整套恢复或资金入口。

母体选择原129的19,551,936B `mothers.csv.gz`，其压缩文件比227的20,494,313B母投影小；只读7身份列便足以保全无child母体及校验动作映射。这里是源码/manifest给出的读法建议，本轮没有实际读任何一张母表。压缩CSV指定列能减少解析与内存，仍需顺序解压源文件，不能宣称只读选定列字节。

还可以省去8,146,494B经济投影：042 `adverse_quote`实际只消费`econ.contract_multiplier`和`econ.tick_size`，原129每动作已有`multiplier/tick_size`；129的原filled身份已继承经济资格。本次K报价可用这两个原字段组成的最小字典，不能据此重新宣称逐日券商费用或PIT经济认证。无需`round_lot`、margin、vendor费率、重算N或entry价格。

## 小绑定、accepted SHA与当前stat

根目录均为本线`outputs/`。下列大输入只stat，accepted SHA继承217/129/132，未重新hash；size一致不等于本轮重新认证其内容。

| 角色 | 相对位置 | bytes | accepted SHA256 | 当前 inode / mtime_ns |
| --- | --- | ---: | --- | --- |
| 原动作唯一数值读取源 | `stage129_contract_choice_dataset/actual_run1/actions.csv.gz` | 334909637 | `b5b76bd670e9bd6240ea198da4f854cee61ba5f72fd6762f071345a4c0824e7c` | `28381050 / 1792331168432874291` |
| 原母体7身份 | `stage129_contract_choice_dataset/actual_run1/mothers.csv.gz` | 19551936 | `4392e66061d77936aab4ece8aa414291f80da084a0cca0df7ca92a922da48130` | `28381222 / 1792331175853050541` |
| 原生缓存 | `stage132_contract_choice_review/cash_only1/native_store_cache.npz` | 110273488 | `d2976090f9353b071eb62e28eca843b96b4a33a33a4233a508049cfeab9360b7` | `28382923 / 1792332676342516874` |
| 小缓存manifest | `stage132_contract_choice_review/cash_only1/native_store_cache.json` | 948 | `130e340e8c91daadda7a6d9c5dc275c21c222114cfa19ca484bd89dd0eca2685` | `28382924 / 1792332676417927749` |

源日历为另一线已接受`stage265_deep_daily/rqalpha/trading_dates.npy`，44,824B，SHA `57dd7f539d1cdbefb528978a6c7bd79b118790f933ce63c37b10747b999f9585`，inode `28056911`，mtime_ns `1792232433866964291`。它是原5,587交易日索引，不是母表日期去重索引；后续如实施只需一次小文件读取/hash。所有上述stat device均16777231。

本轮小缓存JSON实读并重hash吻合；其中schema=`stage132_native_store_recovery_cache_v1`、9520 epochs/1552456 rows，`file`与217绑定完全一致。其purpose仍是原恢复缓存，不因本轮建议修改。217协议14,895B SHA `b86c21d02b70e55181b7324efc1ebb6b363ee9d842738efe0f2baedfc3747b53`；129 manifest9,137B给出经济投影绑定与原产物角色。227 manifest10,299B当前SHA `92000eb83e8c1bb9717f3b7f1701382849a4c17e49b7c67e04a5ed021a4ed098`。

## 唯一建议动作allowlist：48列

前30列逐项等于227 `ACTIONS`；调用其`classify_action`时必须投影回这30列，不能把新增数值列一起传入，因为该函数严格校验键集合。

```text
sequence_index, action_sequence_index, action_id, mother_sequence_index,
mother_event_id, product_id, family_id, u_date, u_index, reference_epoch,
anchor_epoch, u_action_eligible, D_index, label_history_ready20,
participation_state, label_state, filled, trade_label_known,
entry_index, entry_date, exit_index, exit_date, unknown_index, unknown_date,
label_known_date, label_known_phase, participation_known_date,
participation_known_phase, last_path_index, cancel_reason,
N_u, R0_points, cash_risk_unit, multiplier, tick_size, entry_reference,
base_entry_fill, base_entry_fee_per_lot, base_entry_slippage_per_lot,
net_pnl_base_per_lot, net_R_base, net_R_common2N_base,
stress_entry_fill, stress_entry_fee_per_lot, stress_entry_slippage_per_lot,
net_pnl_stress_per_lot, net_R_stress, net_R_common2N_stress
```

后18列包括原Y、原入场报价、原费滑和原风险单位；base/stress各自保留，避免把原`net_R_stress`的0.25N分母和辅助`net_R_common2N_stress`的2N分母混淆；后者不是当前130/218目标。除需要比较/报价/单位断言的数值外，不解析X或其他未使用数值。closed-before-K前缀的原Y token和known-clock可直接复制，避免重新计算引入末位差异。

母表精确7列：`sequence_index,event_id,product_id,family_id,u_date,u_index,reference_epoch`。原129构造保证动作`event_id=action_id`、`actual_epoch=reference_epoch`；无需额外读这两个同义列。仍按原sequence、action id、mother sequence/id、product/u/anchor逐一核映射；母体无child不能从动作反推而丢失。

## K报价、单位与时钟临界点

156 `calendar_boundary`从完整YYYYMM名义合约月，取其前一月1日为target，再在原日历`bisect_left`取K；无K保持pending，before-calendar阻断，绝不夹到末日。227 `action_gate`保持before-calendar→D哨兵→after-calendar目标比较→D<K的原优先顺序。主域始终`u_action_eligible==1 AND calendar_allowed==1`，不加score、已选、未来闭合条件。

在主域706,910中，673,478 `closed_before_K`原Y及`label_known_date/phase`原样复制，不重新检查旧路径；16,468已知不参与保留policy状态，tradeY仍null。仅以下14,254需要K原生开盘报价：1903 `closed_on_K_priority_reprice`、11607 `closed_after_K`、682 `unknown_after_K`、62 `open_K_reached`。前两类旧Y可用于配对差，后两类旧Y本来未知，应单列潜在新增known覆盖，不填0后计算差。它们只是支持计数，尚未验证合法K报价或实际新known数量。

对K支持行，保留原D入场成交/入场费/入场滑点和截至K前的原政策前缀；K开盘force优先于K当天止损、low/close退出。129原退出循环调用042 `price_exit_reference`本身即force优先；不把原K日intraday stop的旧exit_reference直接当K强平价格。K前已出现unknown则继续吸收；`unknown_on_K`本轮按229保守合同保持null，不能因看到K.open而偷救。

缓存成员仅`epochs,offsets,days,values,valid`。132写入时epochs排序；offsets定义每epoch切片；days是原日历整数索引；values列顺序严格`open,high,low,close,volume`。`valid`已包含accepted状态、五值有限且正、OHLC边界检查，不能只看open>0。按epoch切片后`searchsorted(days,K_index)`必须精确命中且valid为真，才取values[j,0]；缺行、invalid、epoch未命中、非正报价继续null，不找下一有效报价、不延后退出。无需读取`accepted/N/low20/run`四个成员或构建EpochSeries/NativeBars全指标。

注意`.npz`的成员访问通常会把该成员完整载入内存，不能宣传`mmap_mode`可让zip成员只读单行。此方案只打开一个NPZ、加载这五个成员，再进行K点查；不解压所有9成员、不将整个110MB文件read_bytes或重hash。缓存stat前后比对并继承accepted SHA，原数据库最多核元数据stat（如根冻结要求），不SQL、不重hash数据库。

设K原始开盘`O_K`，乘数`M`，最小价位`t`。原042静态scenario参数为base：fee_min=2、fee_notional_fraction=0.0001、slip_price_fraction=0.0001、slip_ticks=1；stress为6、0.0003、0.0003、3。`slip=max(abs(O_K)*slip_price_fraction,t*slip_ticks)`，只有t有效且正才用ticks并将SELL的`O_K-slip`向下对齐tick；t缺失时沿原函数比例滑点，不擅自补tick。全部精确Decimal舍入由原042 `adverse_quote`复用，不另写浮点近似实现。

对每scenario，调用`ref.adverse_quote(O_K,'SELL',{'contract_multiplier':M,'tick_size':原tick},scenario)`，返回精确字段`fill_price,fee_per_lot,slippage_per_lot,tickized`。费用是`max(fee_min,abs(fill_price)*M*fee_notional_fraction)`，按成交价计费。单位为价格points、M=CNY/point/lot、手续费和滑点=CNY/lot。

```text
net_K_per_lot = M*(K_sell.fill_price - original_entry_fill)
                - original_entry_fee_per_lot - K_sell.fee_per_lot
Y_K_common2N  = net_K_per_lot/(2*N_u*M)
Y_K_narrowR   = net_K_per_lot/cash_risk_unit  # 原0.25*N_u*M
total_slip_K  = original_entry_slippage_per_lot + K_sell.slippage_per_lot
```

净收益已从adverse fill之差包含买卖滑点，`total_slip_K`仅分解披露，不能再次扣除。必须有原filled入场、正N/M/cash_risk_unit、有限entryfill/entryfee；缺失或单位不一致应停或明确unknown，不由未来K报价修补原入场证据。K结果成熟时钟保守使用`K_date / after_all_source_close`，和129旧合同一致；不因为模拟在open成交就提前到盘前或开盘可知。复制前缀保持原known-clock。其他blocked、cancel、unknown-before/on、intent、open-pending都保留身份与原政策状态，tradeY null，不填0。

base/stress必须独立求quote并各自保存`known/state/date/phase/PnL/common2N_R/narrow_R`；K.open为正仍可能因stress三tick/比例滑点使SELL fill非正。base可quote而stress不可quote时，保留base结果与stress unknown，不能用一次双cost字典推导异常使两者一起unknown。closed-before-K则精确复制原两个cost的R、对应per-lot PnL及原clock。

## 可复用纯函数与小产物建议

- 227 `classify_action/action_gate/clock/integer`与其30列常量；当前代码29,989B SHA `377f9e56e4881d89d7ee16f72d3d3f0abaa4e71635f0dd58cff195da65a692c1`，与227接受bundle相同。
- 156 `calendar_boundary`；当前17,062B SHA `4c56ad2f0e812a10aca9a153e3328c8a8aa6e8df1a1b588f3aecf898713f7200`，与227接受bundle相同。边界按epoch缓存一次，不对每动作反复bisect。
- 042 `adverse_quote/fee_at/positive`；当前50,405B SHA `ca40a4cf7b761b34f70d973a943723601d0ecf5fc355da3559d5bcbeff36661d`，等于070内固定accepted042 SHA。042顶层定义没有数据加载；不需要经129→070导入链或调用其actual/资金函数。

未来233源码bundle可只包括新`233工具+233新fixtures`以及上述227/156/042三个小模块；现阶段不存在233代码，本文不提前赋予其SHA或授权。无需把129/070/132资金审查器或任何恢复脚本纳入执行依赖。

后续若另获冻结授权，建议一张保留全部动作id/顺序、母id、primary/timing/K状态、原Y、新Y与known-clock的紧凑结果，不再复制30列metadata宽表；一张全399,252母身份/child及known状态计数；小summary、source-read receipt、terminal/manifest即可。summary先报告全部主域、全部状态和known覆盖，再分别报告原已知配对差与新增known；按原year/family/product分区只披露，不挑组训练，不直接累加一手PnL声称账户收益。是否增加母内排序反转等测量需由根另冻，不能顺手扩展。

需要为独审保存的窄quote证据：真实epoch、K原日历index/date、缓存epoch序号、局部bar位置及全局flat-row位置、K.open和valid；每cost原entryfill/entryfee/entryslip及新sellfill/sellfee/sellslip/tickized、N/M/tick/原cash_risk_unit、原/新结果clock及branch。这样独审可同一cache五member按K点核价，不重放任何D到K路径。summary可以全局披露closed-primary中stress可quote/成熟是否支配旧clock；六个train-cache未来共享资格本轮不读取、不承诺。

本轮未新增/修改/删除参数或回测结果；权益、收益、DD、Sharpe、总滑点、交易次数、胜率均N/A。未写actual工具或测试；230冻结及233实施不由本文自动授权。不改旧工具、LINE、registry、其他线、生产或Git。

## 网上原文核证与独立判断

本轮实际读取[SPO原文§2式(1)](https://arxiv.org/html/1710.08005v5)与[原作者GitHub](https://github.com/paulgrigas/SmartPredictThenOptimize)。原文讨论已知固定可行集合下线性成本目标的条件均值及决策误差；作者仓库用于复现实验。我的判断：先核预测payoff是否对应执行政策是合理的，但本线K单动作结果仍不等于有资金占用/整数手数/相互排斥的账户目标，不能由此断言原均值头有bug或必须上SPO。未安装/运行/复制作者库。首选web工具两次连接失败，随后search_service成功取得两原页及定点正文，未无限重试。

结束反思：同史适应性过拟合风险仍是；本轮没有数值收益读取、调参或新增alpha。继续本固定有限测量有条件是，价值是直接辨别对象差异及新known覆盖；重复时钟盘点、恢复大系统、直接训练/资金或救DOMAIN52无价值。整体目标active，尚无加注/晋级/生产资格。
