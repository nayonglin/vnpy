# Stage220：DOMAIN52训练loss实验独立审查

- line_id：`futures_full_market_long_signal_ai`；开始时间：2026-10-19 20:15 CST。
- root216决策与217协议14,895B，SHA `b86c21d02b70e55181b7324efc1ebb6b363ee9d842738efe0f2baedfc3747b53`已核。215盘点收口不重做。
- 范围：218/219新核心代码预审、必要小fixture；root实际后分模型/forward/选择/held与cash两个checkpoint独审。root唯一启动actual；不重训、重预测或重跑旧现金。不改218/219、LINE、registry或已结215。

## 方法预审

只在已成熟旧130训练域内将损失支撑限制为固定156同K日历D<K；不读目标值来筛域，不新增成熟行。原52列及旧六scaler坐标、原firstexit stressR、Ridge alpha1和选择/现金政策保持。允许行旧权重只乘固定W/W_A，保持相对比例与原总loss质量，uniqueness不重算。该单项干预有可识别差异，但可能丢有益信息、增加估计方差；不是坏label修复，也未识别此前失败原因。

全部六fold原身份、214质量/计数、X/Y/新权重有限正支撑须在第一个fit前全部通过。新模型不含q。主/held完整forward保留，旧156main与205 COMMON52 heldK直接复用；四旧157现金不回放。若完整main动作/selected/anchor相同，score大小不进入070.reserve_batch或042固定family排序，131仅要求正score，故同动作严格收益增量必不成立，正常0现金收口。

收益/DD/全部四paired CI及两个held/unknown门完全沿217；不把held原R当现金目标，不放宽门。日历为已接受历史重建，不另签历史首次公布PIT或真实执行资格。

## 当前审查状态

方法核心阻断0，218/219源未ready，尚未运行fixture或actual审查。不提前写大型observer；待冻结新源后核并给root限定可跑建议。本阶段fit/cash/SQL、金融参数与成绩变更均0，累计427fit/230cash。期末权益、收益、回撤、Sharpe、滑点、交易和胜率N/A。

## 反思

- 开始过拟合风险：**是**，同史反复择题；本包按新收益救参：**否**，单域事前固定。
- 开始继续价值：**是**，限定六fit和至多四新账本可直接反证；现阶段不支持加注、生产或整体目标完成。
- 结束状态与置信度：待预审和实际独审后补记。

## 冻结源预审与新方法fixture（2026-10-19 20:20 CST）

- 218原52/scaler/Y/相对权重与六preflight先于首fit、完整forward、旧控制选择直接复用及identical早停通过核心预审；219纯DOMAIN52/四递归账本/先raw后metadata/旧157自身source-only四本/严格217门通过，core0。作者suite均不重跑。
- 新增三个独立合成例一次3/3过，另220审查器自身两新方法fixture一次2/2过：53维含截距继承H0减excluded支撑的正规方程、独立bisect域门；无研究fit、cash、SQL或旧数据读取。
- 仅220新审查器准备完毕，模型/全forward/选择/held为一次phase，独立receipt落盘后cash phase只做未完成新账本与CI，不回放模型或旧账本。root精确授权后方可actual。

## cash追加phase冻结（2026-10-19 20:22 CST）

- 基于已接受207独立现金审查的同一158/132/102纯数学，最小适配DOMAIN52与217/218/219身份；移除上一q结果专属“必须unsupported”断言，结论由新证据决定。只承接完成model receipt，模型/预测/旧现金重跑0。
- 新schema/checkpoint/严格217 gate两个定向fixture一次2/2过，无真实新现金或旧数据读取。actual待root精确绑定219终态与220模型receipt后唯一启动。

## 模型/完整forward/选择/held phase终态（2026-10-19 20:23 CST）

- root持有唯一review session70976已exit0/core0；model receipt18,781B SHA `c984d676ee320f76a4bdb562c10e54278871af4502f2c3dab715054da46215de`，已完成checkpoint不再回放。
- 六模型按旧accepted130正规块减被排除域后缩放独立核验；完整1,933,480新预测、三scope全选择、main1,758父动作差异与两个held逐日/年汇总通过。新预测最大绝对误差0.0；最大新正规方程residual2.112938091158867e-08。
- 两held已知equal-u增量分别0.001294936754151306R / 0.0010706489401883436R，distinctunknown16/7，因此两个held门均未通过。原firstexit target与K cash不同，不以之后现金覆盖unknown门。
- 本phase旧预测/旧选择重算/模型fit/现金/SQL均0；仅一次读取actions/common/mothers与六训练cache、新score一次、两旧选择source-only。累计实际研究433fit/234cash按219终态，cash独审尚待root下一phase。

## cash追加phase终态与最终意见（2026-10-19 20:26 CST）

- root唯一cash-review session71431 exit0，31.1869055秒，四新账本全部审查通过、core0。receipt31,245B SHA `f41b5ba311951859b24cbbfbe9df83bd869aa49bdb40b9f55a319e7eff7dea2a`，路径`outputs/stage220_training_domain_loss_review/cash2/review_receipt.json`。`cash2`只是沿模型/现金阶段区分的目录名，**本轮没有cash1失败，也没有重跑四本**。
- 模型checkpoint直接继承；新增模型fit/新现金执行/旧现金回放/旧现金重审/SQL均0，只读132 native cache一次核新账本原价、边界、预算/容量、全部记账及统计，原070索引作四paired CI，未重新生成索引。研究累计433fit/234cash。

| 新DOMAIN52账本 | 期末权益 | 总收益 | 最大回撤 | Sharpe | 手续费 | 总滑点 | 已闭交易 | fills | 净胜率 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| primary_2020 base | 2,133,245.62 | 113.324562% | -17.048641% | 0.889222 | 66,024.38 | 181,052.86 | 1641 | 3284 | 0.12492383 |
| primary_2020 stress | 1,545,284.00 | 54.528400% | -13.831021% | 0.762467 | 82,906.00 | 208,263.30 | 1178 | 2362 | 0.12054329 |
| cold_2023 base | 1,742,914.06 | 74.291406% | -13.084681% | 1.172309 | 24,195.94 | 62,779.99 | 599 | 1200 | 0.12353923 |
| cold_2023 stress | 1,453,839.49 | 45.383949% | -13.369355% | 1.009409 | 39,130.51 | 91,488.75 | 481 | 964 | 0.12266112 |

胜率按已闭根事件扣费用/滑点的净盈亏计算，表内为比例；fills不是独立完整交易。四本末尾各2个open、terminal stale0，主2020 base/stress分别7/3个历史stale日；容量/实际入场仍有unknown，不能把研究估值当券商实际清算资格。

| 对旧157自身账本 | 收益差pp | 回撤差pp（正为更浅） | paired mean-daily-log 95%CI |
| --- | ---: | ---: | --- |
| primary_2020 base | -9.602460 | -1.421221 | [-0.000238496004, 0.000227038331] |
| primary_2020 stress | 1.686429 | -2.471721 | [-0.000149635151, 0.000168395631] |
| cold_2023 base | -8.252249 | -3.182532 | [-0.000256174211, 0.000215374066] |
| cold_2023 stress | -7.280633 | -6.946593 | [-0.000217969579, 9.50988774e-05] |

- 四收益自身均正，但3/4低于旧157，只有主stress收益点增1.686429pp；四回撤均更深、四CI均跨零，两个held虽已知小正但distinctunknown16/7未过。217整体门unsupported，不覆盖unknown、不加注、不晋级。
- 数学误差：新账户主指标/年度表/容量表与逐账本复算差0；CI分位数最大记录差1.87025e−18；新原价N值差3.63798e−12。accepted132预算/原价核验记录最大差5.820766091346741e-11，保持原接受容差，没有新epsilon、截断或放宽。模型阶段继承式H最大误差4.96512e−08、正规方程残差2.11294e−08、全forward误差0。
- 最终置信度：对本冻结算法与历史重建输入的实现、数学、四新现金和配对结论可接受；旧COMMON模型/控制数学沿已接受证据，未独立重新审旧账本。历史多次择题、原firstexit目标与K现金不一致、首次发布PIT/真实成交容量均未被本审查消除。
- 结束是否过拟合：**是，历史选择风险仍在**；本轮新结果后救参：**否**。继续本固定DOMAIN52 loss包：**否**，严格门失败应关闭；继续全市场高质量long总体目标：**是**，需结构不同且可检验的下一问题。总体goal保持active。
