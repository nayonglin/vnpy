# Stage086：OI 两臂固定训练与训练外族诊断实现

- line_id：`futures_full_market_long_signal_ai`；记录时间：2026-10-18 17:49 CST。
- 阶段性质：084冻结合同的实现交接，尚未实际训练；重要突破否、正式A/B/晋级否。
- 工作区沿 `/Users/mac/Desktop/fian` 当前checkout。只新增086源码、必要fixture测试、本文及小实施收据；不改071/070旧源、083、LINE、registry、正式版或生产。
- 原目标仍为全市场全品种高质量做多、极窄止损、成本后更高收益与更低回撤。本阶段不重训083已否决的换分母，不恢复旧Triple Screen或080预过滤。

## 冻结依据与实现范围

完整读取084中文科学合同及机器协议，并绑定实施澄清侧文件：

- 科学合同 SHA `0e59263ec479851454130648e3827e69a0a5e5aa47a79d0ba634715fdb03eb8f`。
- `protocol.json` SHA `82059f728efb70fedd54e2254f822898b6bbcf1b2ac3395cbd1c11470167cba5`。
- `implementation_clarifications.json` SHA `b72cfec8e934a9e347359f1a6f3bbb1384de2a6303c0b6b0bf5089bdab23b776`。

引用 accepted071 的 `training_slice`、前向预测切片、family并发/日期权重、有限加权统计、共同缺失与标准化纯定义。旧文件只引用、不修改、不monkeypatch；不消费旧结算实验的实际scores或现金成绩。新CONTROL/OI共享同一OI缺失指示、训练行/权重及scaler，54槽前53列完全相同，末槽分别为0与训练内标准化的OI。

main、holdout_0、holdout_1 × 两个cutoff × 两臂，实际计划恰12 fit。held训练排除该hash组后重新计算自身权重/scaler，预测只保留该组；全组联合仍分区覆盖完整161014前向母体。**161014含no-reference/not-ready/unknown，ready20只是动作门，绝不筛预测行。** 不增加目标变换、模型、窗口、阈值、控制或风险参数。

与085 owner确认完整projection接口：`oi_scalar_raw/oi_missing/oi_observed/projection_state/missing_reason`及原IDENTITY7列。合法0保留；缺失标量必须null，mask互补且与有限性一致；原顺序与身份必须完全一致。085实际完成前，086不加载实际标签/共同数组、不拟合。085终态按status/exit_code、399252投影行、1SQL及0fit/0cash/0labels核验，不虚构不存在的completed字段；manifest必须绑定084与澄清侧文件、projection及terminal。

## 输出与087接口

实际fresh目录预期为 `outputs/stage086_oi_fit/experiment/`，目前没有创建这个实际目录。

- `predictions.csv.gz`：main与两held组全体scores，合计644056行；每arm main161014、held并集161014。
- `predictions_main.csv.gz` 与 `predictions_holdout.csv.gz`：便于087只消费main；不把held模型拼主现金。
- 列含原IDENTITY7、policy=NARROW、arm、scope、cutoff、history_ready20、selected、score及oi_missing。
- 每fold保存训练ID/权重/区间、train-only scaler、规范化投影、joblib与portable Ridge、正规方程；实际拟合attempt与完成分别逐条记录，即使后续预测或写盘失败也不漏记已完成fit。
- 保存完整模型/预测manifest、终态、各scope/臂/年/family机会指标、各状态与OI缺失计数，不将MSE解释为现金价值。
- `held_diagnostic.json`、`held_daily.csv.gz`、`held_score_linkage.csv.gz`保留closed-only条件诊断、全部未知状态及动作差异。

held已知域严格为同一完整闭合标签、因果ready20、有限stress netR且label_known不晚于2026-10-16。每行 `(I_OIpos-I_CONTROLpos)*netR`，同u所有已知行（含动作相同的0差）先平均，再对有已知行的u等权；两组完整2020前向拼接名义差>=0才支持研究screen。取消不填0、不作负类；unknown/open动作差异不填0并限制资格。另报同域u等权MSE差、年度及2023重叠视图；这些不是账户收益。087使用manifest的`predictions_main`及`held_diagnostic`精确binding，执行原070预算核。

## 必要行为验证与0actual边界

使用`.py311/bin/python`；只跑`test_stage086_oi_fit.py`，没有旧suite。先观察模块缺失的5项RED，再实现GREEN；随后拟合完成计数、085终态与held MSE差各经一轮RED→GREEN。

最终命令：

```text
.py311/bin/python -m unittest discover -s research/lines/futures_full_market_long_signal_ai/tools -p 'test_stage086_oi_fit.py'
```

最后输出 `Ran 6 tests ... OK`，exit0。覆盖共享53列/合法OI零/缺失不筛母体、未来极值不污染train-only scaler、held训练排除与未知预测保留、错身份/mask拒绝、2个合成Ridge与portable全前向输出、source终态非零金融计数拒绝、closed-only未知不填0及MSE差。

作者历次测试累计产生**12次小fixture fit**，与研究actual分开记；没有实际SQL、标签构建、真实fit、cash、下载、全库hash或订单。新增/修改/删除金融结果均0；期末权益、总收益、最大回撤、Sharpe、总滑点、总交易次数、胜率全部N/A。`--help`及AST解析通过；未以fixture通过宣称实际数据/12fit或目标通过。

## 精确授权CLI与依赖风险

CLI仅接收`--output --protocol-sha256 --authorization --authorization-sha256`。协议路径固定，输出必须在086根目录内且fresh；缺root签发的`stage084_exact_root_authorization_v1`、stage=fit、精确source/test/071绑定、固定协议/澄清、8个必要input角色或输入身份时拒绝。没有自动重试或修复重跑。

必要input角色为084绑定的`common_npz/common_identity/narrow_labels/narrow_manifest`及`oi_manifest/oi_projection/oi_terminal/clarifications`。source_bundle为086源码、新test及只读071原源。root必须在085 completed、088预审后另行精确授权真实fit；本文没有签发actual权限。

尚未消除的风险：OI仍是归档重建而非首发PIT；闭合条件选择、右删失、跨family共同冲击及历史研究选择风险继续存在。主/held状态与未知动作差异如实保留；线性增量失败不扩容救参。数据实际manifest未产生，当前只能证明新接线的合成行为，不能声称真实训练数据验收或收益改善。

## 调研判断与前后反思

沿084已冻结的一手资料判断：[CME OI](https://www.cmegroup.com/education/lessons/open-interest)、[CFTC解释](https://www.cftc.gov/MarketReports/CommitmentsofTraders/ExplanatoryNotes/index.htm)与[TqSdk维护者源码](https://github.com/shinnytech/tqsdk-python/blob/master/tqsdk/api.py)支持它是持仓存量观测，而非净多资金。已有083的[SPO目标/决策区分](https://arxiv.org/abs/1710.08005)仍成立；本次不借实施改变科学假设，也不重复外部代码安装或大范围搜索。

开始与结束是否新增按金融成绩调参过拟合：**否，限定实现已冻结合同且0actual**；研究者已见历史，不能称无选择风险。开始与结束继续价值：**有，限既定一次信息增量对照与独立审查**；绿灯只证明接线可交预审，不能证明OI有效、窄损可加注或完整goal完成。作者不改LINE/registry/根总账，交root统一合入。

## 17:55补记：root精确授权后的唯一实际训练

上文17:49是实现时点；其后085真实source完成，088合并代码预审Critical/Important均0。root核对最终source/test及source终态后，签发084输出目录`fit_root_authorization.json`（4186B，SHA `a9eb3e953e4c605ca2a6ad5ddfc4d25448d8e3a2d9651f1368cd37fb1e4bb909`）。本owner严格按四参数CLI启动一次086至原fresh experiment，未改源码、未重试。

- 实际终态：completed、exit0、耗时43.872324秒；attempted12/completed12 fit。
- 预测共644056行；main每arm161014，held并集每arm161014。所有模型/权重/scaler/完整score与诊断已保存。
- 本阶段实际SQL0、cash0、new labels0、downloads0、whole DB/H5 hash0；没有自行执行087。
- 金融回测结果新增/修改/删除0，期末权益/总收益/最大回撤/Sharpe/总滑点/交易次数/胜率仍N/A。上述12研究actual fit与作者12次小fixture fit分开记；根累计账数由root统一维护。

训练外族名义已知域诊断如下（不是现金收益）：

| group | 全前向母体 | 已知闭合ready20机会 | 已知u日 | u等权gated净R增量 | u等权MSE差（OI−CONTROL） | 未决动作差异 | 名义判断 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| holdout_0 | 64077 | 39712 | 1642 | -0.0013624122948932443 | +0.0003535350109829967 | 0 | unsupported |
| holdout_1 | 96937 | 62228 | 1642 | -0.0009287227158413237 | -0.00035469820531036395 | 2 | unsupported |

两个组的名义已知增量都未达到冻结的非负门，因此**训练外族screen名义失败**；hold1另有2个未决动作差异，保留null而非填0。MSE一好一坏不能覆盖经济诊断失败。当前作者尚未做独立actual复核，不能以自生成统计代替088的数据/逻辑/置信度审查；root已收到终态与具体binding，后续cash是否仍按冻结包完成由root另行决定，作者不自启。

精确产物均位于`outputs/stage086_oi_fit/experiment/`：

- `manifest.json`：30975B，SHA `6b7f4e45b39663bcf9c356132d45bd4abc7d143b9f6846f58908ade56a27374c`。
- `actual_terminal.json`：317B，SHA `5a5d1993a7e8a63d9a81c96802183a3ed9a51879724d2175ac8b0de10c604a96`。
- `predictions_main.csv.gz`：19166153B，SHA `2d23b708cabafaadb80b0bdebdfb2f85cb4503de2e5da547f56a4e4fcc7f58bd`。
- `predictions_holdout.csv.gz`：18981958B，SHA `e4faca2640f8aaaa9087a33290f4e8421be5c377b405d3e961248e02fa9f291d`。
- `held_diagnostic.json`：6660B，SHA `5b8bf3269a83a075a77e7817eea8043300adc0a5be4eda8538bfad8bd8079bc2`。

实际结束反思：**没有新增按成绩调参过拟合**，只运行原冻结一次，负结果不换分母、窗口、方向、模型、产品、阈值或stop救援；历史选择风险与闭合条件偏差仍在。**继续完整全市场高质量long目标有价值；本固定OI线性NARROW包目前没有获得held继续证据。** 应先完成独立复核并按冻结停止条件由root结案，不能把12fit完成或MSE局部改善当成收益进展、窄损加注资格或goal完成。
