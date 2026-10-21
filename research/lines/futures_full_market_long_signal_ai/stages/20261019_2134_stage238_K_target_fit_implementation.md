# Stage238：K_TARGET52目标单轴一次完成，held失败停止0cash

- line_id：`futures_full_market_long_signal_ai`；2026-10-19 21:34 CST；非重要突破。
- 237协议36,353B SHA `8aad5f5b6afefec4b078ba7a32f48b806119977156ade22da04eb4e433885c06`；21:34源码冻结时只实现工具与四项新tiny，作者未读实际大输入或执行训练/预测/资金；随后root唯一actual完成。当前累计439fit/234cash，真实结果补记如下。
- 原26值+26missing、130 scaler、218精确S/w、Ridge alpha1/intercept/cholesky及156同K选择均固定。目标先复制legacy旧Y浮点位，K前copy保留原位，只有quote_K行用新数值roundtrip替换；无1e-12训练筛选。六份9.3MB旧support缓存各一次替代六大训练CSV，原动作0读，不重算uniqueness或权重因子。
- 六折C=S、严格K clock、finite、原S/精确weights/scaler共同预检全过才允许最多六fit；模型/完成计数即刻保存。完整1,933,480前向child、main161,014及held161,014母体；针对218与COMMON52分别进行两holdout×两部署期的八格严格K held门，并比较main完整动作身份。任一失败仅结案0cash；238工具本身始终0cash，资金须另冻。
- 源码复用218/205/214/130/071/156六个已接受小工具；未修改旧工具。无新target大cache、全X复制、observer或自动恢复。

四项新tiny RED均以功能缺失断言失败，随后GREEN4/4、exit0、0.097s；0fixturefit、0旧suite。验证target解析/时钟共同域及全六折0fit门、policy0/unknown/same-action语义、八格held与双main恒同门，未重复验证旧Ridge算法。

| 产物 | bytes | SHA256 |
| --- | ---: | --- |
| `tools/stage238_K_target_fit.py` | 30736 | `73c496ae9abf565c737ce1405e36483a188bc9285c854295710ddec5b2603cb2` |
| `tools/test_stage238_K_target_fit.py` | 5927 | `c2b217c7f420713cb29f1ed0d57bdb85b3bc63acd8148d364de5670fe0576ac4` |
| `outputs/stage238_K_target_fit/implementation/source_bundle.json` | 2200 | `479737407ad44c71b29c90d510e25232c5ab7cca596bc51e60b0f5e972ce605f` |
| `outputs/stage238_K_target_fit/implementation/fixture_terminal.json` | 6031 | `3a17863aa8e1c7eb258f2748f8b74d28689a1fd260f101f255cd5427b60ddecb` |

root唯一入口为`.py311/bin/python research/lines/futures_full_market_long_signal_ai/tools/stage238_K_target_fit.py --actual --authorization <root_auth.json> --authorization-sha256 <sha> --output <237精确freshoutput>`。授权schema=`stage237_exact_root_fit_authorization_v1`，除root/fit/exactsource/protocol/output/source_bundle外，input_bindings、controls、folds均须等237。numeric_review只做静态prepass，239独立核新数学/全分数/选择/held，均不复跑作者tiny或旧控制。以下actual终态不替代239独立算术接受。

## root唯一实际运行补记（2026-10-19 21:38 CST）

root session84023 terminal=`completed`、exit0，64.392788542秒，一启动一完整、6attempt/6completed fit、6前向调用/1,933,480完整child模型行、3候选scope选择、0cash。root报告actual manifest SHA `dad8fa1a2eeae85797f6d27252d243de4e675e80fa60a12d9e3919963aaf6530`。本次只实读7,661B preflight、4,602B held_diagnostic、1,936B selection_identity、1,120B summary、1,206B terminal补记，未读大输出、重跑或改源码；仍待239完整独审及root240裁决。

实际I/O符合冻结预算：233 labels一次、129母身份一次、COMMON一次、calendar一次、六support各一次、六原scaler、四控制choices各一次。原129动作、旧六大训练CSV、native cache、旧模型fit/prediction/selection/cash、SQL、下载、大源hash均0。两个main均保留161,014母体、anchor和完整身份相同；新动作相对COMMON52改变1,030母体（selected标志改变724），相对DOMAIN52改变1,297（selected改变1164）。main非恒同门通过，不能覆盖held门。

六折全在首个fit前通过C=S、clock、精确权重和旧scaler资格；表中T为原成熟域、S为218固定可行动域，C逐行等于S；各fold重叠，不把行数相加成独立样本。

| scope / cutoff | T行 | S=C行 | 目标实际数值改变行 |
| --- | ---: | ---: | ---: |
| main / 2020 | 247795 | 216443 | 4218 |
| main / 2023 | 445475 | 390340 | 7675 |
| holdout0 / 2020 | 171712 | 150511 | 2923 |
| holdout0 / 2023 | 297404 | 261338 | 5136 |
| holdout1 / 2020 | 76083 | 65932 | 1295 |
| holdout1 / 2023 | 148071 | 129002 | 2539 |

新target替换后严格K stress held结果如下；“2020段”为2020≤u<2023，“2023段”为2023≤u≤2026-10-16。增量是完整family-u政策先聚合再等u的已知部分平均窄R，不是现金收益；distinct unknown不填0。同action未决只允许差值恒0，仍披露其自身未决。

| 必要控制 | held / 部署段 | 已知等u增量R | distinct unknown | 同action未决 | 门 |
| --- | --- | ---: | ---: | ---: | --- |
| COMMON52 | h0 / 2020段 | +0.0011721041 | 3 | 8 | FAIL |
| COMMON52 | h0 / 2023段 | -0.0011300790 | 3 | 3 | FAIL |
| COMMON52 | h1 / 2020段 | -0.0027727851 | 7 | 13 | FAIL |
| COMMON52 | h1 / 2023段 | -0.0015866543 | 3 | 3 | FAIL |
| DOMAIN52 | h0 / 2020段 | -0.0039882327 | 5 | 8 | FAIL |
| DOMAIN52 | h0 / 2023段 | +0.0000969433 | 3 | 4 | FAIL |
| DOMAIN52 | h1 / 2020段 | -0.0012847731 | 3 | 16 | FAIL |
| DOMAIN52 | h1 / 2023段 | -0.0027143070 | 3 | 3 | FAIL |

八格已知增量6负2正，全部存在不同动作未决，因此八格均未通过预设门。各held0早/后段有效日期728/915、完整family-u27664/34770；held1为728/915日、41496/52155 family-u，两控制同人口。总体`cash_eligible=false`、reason=`held_or_main_gate_failed_zero_cash`，依237停止，未运行任何候选资金账本。

实际结果支持关闭这个固定K_TARGET52/COMMON52/Ridge/K包，尚待239确认算术。它不否定测得的收益对象差异，也不证明所有目标对齐方法无效；只对该固定有限学习干预不支持稳定增量。不能选两格正值救门、把unknown变0，或继续修改K/duration/特征/模型/权重/scaler/阈值/止损/风险。完整用户goal仍active，窄损与加注资格均未完成。

新增/修改/删除策略参数0；本次新增六模型及完整预测/选择/同K held结果，无资金回测结果新增/修改/删除。权益、收益、DD、Sharpe、滑点、交易次数、胜率N/A。调研判断沿本轮已核SPO原文/作者GitHub与237固定Ridge文档：对象对齐值得有限证伪，不证明要换学习器或必有alpha。开始/结束过拟合风险是历史择题复用，本轮未按结果救参；有限实验已完成必要反证，继续本包调参无价值，继续等待239独审/root240裁决有价值，完整研究目标继续。不改LINE/registry、其他线、生产或Git。
