# Stage538：固定行业残差截距实现与唯一actual完成，名义门失败

- line_id：`futures_full_market_long_signal_ai`；时间2026-10-21 04:23 CST；工作区`/Users/mac/Desktop/fian`。
- 非重要突破；仅实现536已冻结规格，不是新收益或正式A/B候选。完整六所98产品/95family、高质量long、更高成本后收益/更低DD、再分验窄损加注的目标不变。
- 04:27 CST补记：root唯一actual已completed，12/12 offset fit、0base/0cash；下文实现交付时状态作为历史保留，以末节actual结论为准。
- 协议：`outputs/stage536_sector_residual_protocol/protocol.json`，SHA `acd8fcbf9e738e266067179a6b1fe240e09775ade737d1616b73abf4a46cf592`；inventory537 SHA `015c814fe1298c7ee7e8808ef03330dcd14532e5f11796ee390bcba35a17ba2b`。

## 实现与冻结

新增`tools/stage538_sector_residual_fit.py`（29550B，SHA `4e2e9f956f6856040049f84f78ff8a29c22163b772c7f3d063cba8a3319ebe6b`）和`tools/test_stage538_sector_residual_fit.py`（8901B，SHA `0213d552604ca3abbc29973f07b0c47f582b7d0a811bc20ba556c679519066a5`）；原脚本、正式代码、LINE/registry、Git不改。

唯一规格为原52头/scaler/训练cohort/Y/权重冻结；只将新头权重sum归一为1。按536已定真实八类C和固定组内任意标签B构造实际centered one-hot Z，lambda1、无zscore/新global intercept，保存p/G/b/gamma/delta/df。未知映射、p0行业预测修正精确0；unknown有正训练质量时不条件归一p，不使用不成立的diag(p)-ppᵀ捷径，披露q、sumwZ和sumwdelta。df实际必须<=traceG<=1。不采用534的κ252建议。

训练只复用130的fold_slices/training_weights/design，无旧52 fit。六fold在RAM重建union/并发/等日权重，核原统计/scaler/小normal_equations；不读六套旧training_identity大表。实际一次读取actions白名单、COMMON、mothers，旧scores全流一次；gzip在这唯一内容读取中核压缩字节SHA，不另加旧大表fullhash pass。

前向不重算52，所有原负分保留。RAM内给每scope自身头加offset后调用原156 VOLUNTARY_RESELECT；held仅局部alias main并恢复scope/arm，同样K/D闸门、原普通/F优先级，母子域不得缩。三个contrast为C-A、C-B、B-A：actual chosen action的stress净R，同action差0且披露共同unresolved，不同unknown为NaN，先family-u再等u。C-A及C-B各自两个held均>=0且至少一个>0才是名义现金前提，不是未知结果/未触碰OOS或现金通过。

## 供独审的紧凑资产

- `folds/<scope>/<cutoff>/train_compact.csv.gz`：原训练24列身份/成熟/entry-exit/Y，加130权重表、normalized_weight、Ahat；`B_head.json/C_head.json`附原portable/scaler/小方程binding和训练/前向支持数。
- `train_common_unique.npz`：训练union只存一份sequence_index/raw26/columns，不存六套52矩阵。
- `forward_base_compact.csv.gz`：完整原1933480行score身份/原score/eligible及标签状态、known、R、参与状态、B/C修正；旧负分不删。`mothers_forward.csv.gz`完整161014母身份，另存小calendar。
- main/held choices、diagnostic_linked、held_daily/annual、fold/selection records，以及started/attempt/completed/terminal/exact bindings。

## 有限验证与actual状态

先写7个语义fixture，首次RED为脚本缺失的7个预期失败；核心落盘后7/7 GREEN（0.937秒）。最后增加唯一压缩IO/NPZ fixture，最终8/8 GREEN（0.758秒），CLI `--help` exit0。覆盖unknown正质量实际G、sumw1、df、p0精确回退、global不变、同product月份差值、旧负分、原156 K重选/F优先级、own-held成熟时钟、未知诊断和名义门。两次GREEN各4次纯合成闭式求解共8 fixture solves，未做实际研究fit；没有跑旧测试套件或实际输入。

source_ready：`outputs/stage538_sector_residual_fit/source_ready.json`（2042B，SHA `b06e76f5cffbc42d49bc03c311bedc3c701a4f8b3e3685a54c13d16cbbf13586`）。内含精确source_bundle和授权schema。root已收到唯一actual_run1 CLI；本agent没有启动actual。预算12新offset fit、0base refit、0cash/SQL/下载，不自动retry；遇错保存现场计数再诊断。539将定向审新代码和后续新compact cache，不重扫旧大表。

本阶段截至记录时实际fit/cash/SQL/行情下载/旧大表内容读取均0；累计仍511fit、278完成cash及1旧partial。期末权益、总收益、最大回撤、Sharpe、总滑点、交易次数、胜率全部N/A。actual结果须由root启动终态与539独审另行确认，不能把fixture通过写成alpha或金融成功。

## 调研与反思

沿本轮已实际核读的[JMLR原作者共享正则结构](https://www.jmlr.org/papers/v6/evgeniou05a.html)及[Ong/Herremans原作者代码](https://github.com/joelowj/mtl-tsmom/blob/b07fa1d0a3c71bef3d3614e0d8f4233477e42df1/core/model.py)，只接受有界共享结构，不声称其证明sector alpha；本阶段仅落实536，不追加模型/分类/强度候选或重复文献工程。

开始/结束过拟合反思：同史自适应择题风险**是且高**；本轮按新收益调参**否**，df<=1也不能清除511次历史fit的选择风险。开始/结束继续价值：**是，仅一次冻结残差先验证伪**；无边界扫描taxonomy、seed、lambda、共同头、目标或退出**否**。只要actual失败便保留结果，不靠其他COMMON字段重训救分。完整目标未完成、production_qualified=false。

## 唯一actual结果补记（2026-10-21 04:27 CST）

root单次启动`outputs/stage538_sector_residual_fit/actual_run1/`，原live session3510，终态实际`completed/exit0`、`182.72898858302506`秒、12次attempt/12次complete，automatic_retry=false；0base refit、0cash、0SQL、0下载。原actions、COMMON、mothers、fullscores各一次内容读取，旧六训练大表读取0。保留全399252母表/161014前向母表/1933480主与held前向score行；旧非正分main944504、held0 377399、held1 558554，未先筛去。该补记只读取small summary/terminal/held/head JSON，未重读新旧大cache、未改冻结源码或测试。

主诊断为实际事前选择action的stress净R增量，先family-u再等u；**不是现金收益、胜率或账户DD**：

| scope | C-A | C-B | B-A | 前瞻已知源日 |
| --- | ---: | ---: | ---: | ---: |
| main | +0.000292331272132 | +0.000429956784685 | −0.000137625512553 | 1643 |
| holdout_0 | +0.000114203497568 | +0.000555341683812 | −0.000441138186244 | 1643 |
| holdout_1 | −0.001096434136472 | −0.001097507353830 | +0.000001073217359 | 1643 |

两held family-u母体分别62434/93651。C-A/C-B不同action未知数held0均1，held1分别2/5，未填0；共同相同action未解结果C-A为27/36、C-B为27/35，仅增量按合同为0并披露。main C-A/C-B也各有1个不同action未知。未知存在，不能把known-support均值写成完整全域结果。各scope实际入选A/B/C：main4365/4397/4404，held0 2111/2116/2138，held1 3766/3800/3792。

12个head文件报告有效df范围`0.6113648514532811`—`0.6842070566287337`，均<1；本次实际训练unknown行均0、mapped质量为1的浮点近邻，sumwZ约在1.6e−14以内、sumwdelta约在9.0e−17以内。八类中的EC在这些旧cutoff训练均p0，严格回A；不能因事前知道EC单例就宣称有训练支持。上述是small head记录的读取，不冒充539对训练cache的独立重算。

**按536冻结门：nominal_cash_prerequisite=false。** held1的C-A和C-B同时负，不能用main或held0的正增量覆盖它。root据此停止这一固定taxonomy/sumw1/lambda1/centered-onehot/seed/固定52头规格，**0新cash**；不改类别粒度、收缩、窗口、标签、共同头、stop或风险去救参。本结果否决这个明确实现的现金前提，不证明行业信息普遍无效，也不把未跑现金写成现金亏损。

本线累计实际研究fit更新为**523=511+12**；**278完成cash+1旧partial**不变。新增/修改/删除回测结果均0；本次新增的是预测/选择诊断。期末权益、总收益、最大回撤、Sharpe、总滑点、总交易次数、胜率仍全部N/A。完整高质量long/更高成本后收益/更低DD/窄损加注目标未完成，production_qualified=false。

539独立agent正在按新compact cache全面复核结果、数据、权重/时刻/留族/选择逻辑、置信度与bug，**此时尚未收到其通过结论**；实现者不代签review通过。如其发现material错误，先冻结经济结论并保留现场，不能自动修复重跑。作者未重新扫cache替代独审。

结束反思：历史自适应择题过拟合风险**仍是且高**；本次新成绩后调参救分**否**。这次有界检验的继续价值**已兑现为停止依据**；继续此固定规格或为其跑现金的价值**否**，因为它未越过自己冻结的两组held门。完整全市场long目标仍有价值，后续须是新的可辨识信息或不同经济动作，不给此规格更名重训。
