# Stage586：BDI三公历月增长固定残差实验——12head完成，固定八门失败一项

- line_id：`futures_full_market_long_signal_ai`；工作区/分支沿用本机研究分支；不创建worktree。
- 本阶段时间：2026-10-21 06:49 CST（源码冻结）；性质：执行已冻结585，一次至多12个小head、0现金账户，非重要突破。
- 先读registry并完整读585协议一次；协议15,532B，SHA256 `c7c7313a8ccac4a292e31ba87c2818f12acf47b9322c4ef289fcc9f8a6a2261a`。
- root唯一actual已完成，新增12 actual fit/0cash；累计547 actual fit/282 completed cash＋1旧partial。587正在一次全面独审，源/代码/协议均未改变。

## 调研与判断

沿用本轮583/584已保存的官方Baltic方法变更、发行人价格锚与原作者/维护者资料边界，本实现不重做网络调研或数据资格工程。BDI不是SGX相对curve q、SCFI或EC成交价，来源真实不表示alpha；2018等定义断点、混合频率、坏年、周末、18处字段冲突及未知首发时钟均保留。585明确采用有条件的后续u历史重建，不宣称Sina PIT认证。

## 唯一变更与固定参数

仅新增隔离源/残差实现，旧代码、基线、参数与数据均不修改：

- `tools/stage586_bdi_core.py`：月endpoint、三公历月g、完整u连接、原训练权重统计与固定B/C小矩阵solve。
- `tools/stage586_bdi_residual_fit.py`：复用567/538纯IO、选择/K/优先级与family-u诊断，使用原538紧凑投影，不读COMMON、334MB actions、train_common_unique或native。
- `tools/test_stage586_bdi_residual.py`：8个必要合成边界。

先在每个完整公历月内部选择最后modern weekday正finite price候选，之后才查冻结冲突；落在18冲突就该endpoint unknown，绝不退到早一日。坏年/周末隔离、原始name和全部原件不修。`g_m=log(P_m/P_(m−3))`，两端来自自己的真实公历月；缺端点或跨2009-07/2018-03已知regime时g unknown，不跨月carry。当前不完整月不生成完整预测。

每原始完整u只取前一完整reference_month，未知月清掉旧g；u收盘之后才到原下一D执行，不混为更早的同日夜盘。源月与`u_calendar_month`分列；诊断月等权、2020—2022/2023+与annual都按原u日期，不能用reference_month年改OOS。

旧COMMON52保持冻结，用每own-fold原Y、sample_weight、Ahat，known训练子集w归一为1，目标Y−Ahat；g的均值/std只由同一known训练子集加权计算。B为惩罚常数，C为惩罚常数+标准化g一个斜率，全部系数lambda=1，无预设bullish符号。所有缺g行B=C=A，连负零位模式都保持。六fold统一先查M>=60个不同known成熟参考月与正scale，任何一个失败时全部0solve；通过才恰12solve，不重训练旧52。

完整98/95、161,014 forward mothers、1,933,480 main+held正负child保留；A完整选择复用不重放，B/C全池重新选择且K/普通F优先级等不变。forward标签列在全部fit与选择完成后才消费。相同action增量0，不同action而标签unknown保持NaN并披露，不补0。源/训练月、全选择、linked、年度、含零family-year及早后段诊断全部输出。

新增固定研究参数是3公历月增长、M>=60资格阈值、原w加权scaler、全coef lambda1；它们均由585收益前冻结，无搜索或待收益选择。原交易风险、stop、K、容量、成本没有新增/修改/删除；本协议cash=0。

## 必要验证与source-ready

8个新合成fixture先RED8（占位函数NotImplemented），实现后GREEN8（0.013秒）；仅运行新fixture，无旧suite或真实fit预试：末候选冲突不退前；缺月清旧/不完整月及未来同日排除；三公历月而非三行；两regime边界；错年/周末保留；原w known-only scaler；missing A bitwise fallback；六fold统一preflight前0solve。runner编译、导入及source-ready检查成功，未读任何真实大表。

| 源文件 | SHA256 |
|---|---|
| core | `1cda86df2a2f2e8e7b85675f1cfee1e1a6c8a8815795711c24f9688f2202f9d2` |
| runner | `bb15216e4245e7aed4ecd0135045a7b820bb281d2f4590cc026b0d27ccbc9012` |
| tests | `e095b69810ab9399ba59dcc2cb99509bc8a8c9a93210199027e9e93aa67903c2` |

source-ready receipt：`outputs/stage586_bdi_residual_fit/source_ready1/source_ready.json`。587已一次定向核core与8fixture、GO，薄runner关键路径也已发其一次核查；root唯一启动actual，子agent不实际执行。完整实际结果接受状态以后续587结论为准。

## 实际结果（2026-10-21 06:51补录）

root session75136唯一 `actual_run1` 已exit0，耗时 **79.473902秒**。12个新head attempted/completed均12，旧52重训、旧A回放、cash、SQL、下载、CI均0；没有失败重启。root终态确认六fold不同known成熟参考月M为2020 cutoff各117、2023 cutoff各153，全部通过统一preflight后才solve。没有降低M门或选择性跳过某fold。

本次只读五个已落小结果（terminal、summary、gate、held_diagnostic、projection_summary）补记录，不读上游raw/COMMON/actions/native/compact或大结果，不重算或改源。

来源投影：全5,587个u保留，known g的u为4,718，另869个u精确A fallback。245个月记录含243个known endpoint、1个冻结冲突endpoint、1个当前不完整月；g已知233月，跨regime unknown 6月、base缺失4月、冻结冲突1月、不完整1月。没有回退到冲突前一日；时钟仍为条件历史重建，首发PIT未认证。

完整161,014 forward母机会、1,933,480 main+held正负child保留；IO真实计数：raw1、train6（各一次）、forward1、mothers1、旧A choices2（各一次），无大源回读。

以下是**u公历月等权、已知结果支持域**的stress机会R增量，82个OOS决策月；不是资金收益、胜率或独立样本均值。

| scope | C−A 月等权增量R | C−B 月等权增量R | C−A/C−B差动作未知family-u | 固定门 |
|---|---:|---:|---:|---|
| main | +0.001254418826 | +0.001257028790 | 2 / 2 | 两项通过 |
| holdout_0 | +0.002038052728 | +0.002049239022 | 1 / 1 | 两项通过 |
| holdout_1 | **-0.000041246093** | +0.000191642252 | 1 / 1 | **C−A失败** |

main早段（u年2020—2022，36月）C−B=+0.002295362142；后段（u年2023起，46月）C−B=+0.000444420079，两时间门通过。对应main C−A为+0.002392272769/+0.000363924436。reference_month仍单列，没有把跨年机会按其前一月归入前一年。

八门7真1假，`continuation_gate.status=unsupported`、`nominal_cash_prerequisite=false`。**有正向信息线索，但固定的全域/跨族一致性资格未过，按585关闭本精确包，0CI/0cash。** 不将负数因小而当0，不删除常数头或改窗口/符号来使held1过线。

对照常数头B−A月等权增量：main -0.000002609963、held0 -0.000011186294、held1 -0.000232888346。这解释为什么“C比B好”不能替代“C比原A好”；尤其held1的C−B虽正，仍略差于原A。不能据此事后去掉常数、更换控制或换成功标准。

主/held0/held1完整family-u数为156,085/62,434/93,651，C差动作unknown为2/1/1，必须保留NaN及条件支持说明，不填0。same-action共同未决数为51/27/38，其差异为同一动作的0，并未当作已知单腿结果。全母域未缩，`all_population_identified=false`、`unconditional_full_policy_supported=false`、`cash_authorized=false`；不能把已知域正向增量推广为完整政策或账户优势。

期末权益、总收益、最大回撤、Sharpe、总滑点、资金交易次数与胜率仍N/A，因为本协议没有cash回测。新增实际结果是上述12head、完整选择/诊断和固定门，不能把机会R写成现金收益率。全部源、模型、选择、linked、年度和含零family-year结果留在 `outputs/stage586_bdi_residual_fit/actual_run1/`；587正独立全面审查，不在本作者记录中预签通过。

必须同时满足main全期C−A/C−B、main早段与后段C−B，以及两个held各C−A/C−B全部严格正的八门。按全family-u→已知源日→u公历月等权；unknown和来源缺失状态不缩域。失败则停止这个精确BDI包，0CI/0cash，不扫窗口/endpoint/符号/交互/模型/品种/止损/风险救分。通过也仅允许root另行授权cash，不自动晋级或加注。

- 开始是否按新收益过拟合：否；运行结束仍未救参或改门，长期同史自适应择题风险仍高，新源不归零。不能因7项通过就在看到结果后放宽第8项。
- 继续价值：本次固定单斜率反证有价值且已完成；继续此精确包的近邻/去常数/窗口救参没有价值。正向线索保留为有限证据，不等于稳定优势已证或完整目标完成。
- 下一步：只等587完整独审新源、head、全选择、诊断和门，0A/模型重放。随后由root统一裁决；本子任务不重跑、改源或自动进入cash。
- 只改本唯一stage和586新工具/输出，不改LINE/registry、根总账、正式/生产/任务/Git。`goal_complete=false`、`production_qualified=false`、`increased_betting_qualified=false`。
