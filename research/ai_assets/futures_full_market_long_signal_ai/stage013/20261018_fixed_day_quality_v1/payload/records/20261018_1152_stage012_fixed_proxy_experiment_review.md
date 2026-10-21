# Stage012 固定DAY代理实验的独立结果审查

- line_id：`futures_full_market_long_signal_ai`
- 当前模式：冻结结果的只读算术、身份与逻辑审查；审查者独立于Stage010作者。Stage009由本审查者编写，因此本次继承Stage011对数据的独立接受，不把自己对009的认识替代011资格。
- 记录时间：2026-10-18 11:52（Asia/Shanghai）；实际完整审查11:49:26—11:49:45。
- 阶段性质：独立验收，不是新增研究版本、重新拟合或金融回测；不是重要突破，不触发正式A/B或生产发布。
- 独占写入：本记录及`outputs/stage012_day_proxy_experiment_review/`。未改007/009/010、LINE、registry、原数据或Git；未派子agent。

## 结论先行

独立receipt为`accepted_fixed_proxy_result_arithmetic_identity_and_logic_only`；Critical/Important/Minor均为0。全部72个保存模型的训练身份、成熟截止、权重、Scaler、系数正规方程、所有预测、年度/期间指标、两套bootstrap及15项门均与010一致。**接受计算过程和失败结论；`quality_information_screen_pass=false`。** 不授予真实经济标签、金融或生产资格。

主期间2020+，M1自身代理下界点均值为正，但M1−M0配对下界点均值为负，其95%区间跨0；同参与率差的保守下界区间也跨0；同mask的1R成本预算压力下界为负。没有证据支持当前4项跨市场上下文带来通过约定门的增量信息。不能把此结论扩大为所有AI无效，也不能把它解释成已证明真实现金亏损。

## 外部调研与判断

本次沿用Stage007冻结前已浏览的primary材料及其判断：Kaminski/Lo作者研究、Backtrader官方成交/bracket语义、DeePM作者论文与GitHub。它们用于识别止损、OHLC路径、成本与不确定性的条件边界，不证明本仓库存在优势。本次按root明确范围未重复外搜、未下载、未新增模型或参数。Stage007设计不在本次重新选择。

## 变更与冻结输入

新增独立审查脚本`outputs/stage012_day_proxy_experiment_review/review_actual.py`、检查明细、真实终态和receipt。无实验参数新增/修改/删除，无交易源或结果修改。脚本不import010或sklearn，不调用fit、solve或训练API；NumPy/Pandas只用于保存系数重放及独立统计计算。

继承的合同为007 `protocol.json` SHA256 `2e5da3da4440223e3ac978256d563b80d5bd4264cec56d4085ed6062d7bad0a4`；继承011 `review_receipt.json` SHA256 `cf71e0c9a9cc570aa803ad437a117861961c64b13ec920a8b5ab573577301b4a`，其仅签`qualified_for_fixed_proxy_experiment=true`。009 manifest SHA256 `ea26675e8322bee8a3c71d4ba0c731055a52a161359c1ac456de628029a5071e`，数据CSV gzip SHA256 `9b2452fa5fc8bb0c97d702d0caffa2a2b22e46e38ea52ab4842c13d25f120a48`。

root交接的唯一010真实执行为session38894→chunk326eab、exit0、11:44:14—11:44:59、45.664339秒、72fit。收到此终态之后才审阅真实结果。本次未重跑010四测试、旧suite、009构建、SQL价格或大DB hash。

## 审查覆盖及证据

1. 逐一核72个`year×scope×model`保存记录，覆盖2015—2026、main/两family留出、M0/M1。独立重建训练keys，校验训练样本必须ready且已识别、`u`早于年度首源日且`label_known_date`严格早于该日；family去末尾`_F`后参与固定hash，留出族不入训练。
2. 每组重建按日反样本数权重及标准化权重SHA，所有训练日总权重一致；仅用训练集重算加权Scaler mean/var/scale。保存系数满足固定alpha=1的加权Ridge正规方程，截距加权残差正确；没有重新求解或拟合系数。
3. 用保存Scaler/coef/intercept完整重放预测：main M0/M1各161609行；holdout0各61135；holdout1各100474；共646436个标量预测。验证全ready年度预测集合，未知标签不被删除，标签/身份复制、固定`score>0`mask、r20>0参考、截距和现金参考均一致。
4. 以独立的区间中心/半径算法重算配对区间，系数为0的共同mask严格抵消；按当日共同已识别集合重算参与率基准及有符号区间；1R压力仅改变固定预算成本，不重选mask。
5. 重算4scope×全部年度/2015+/2020+的cohort、日期均值、校准、MSE、排除机会成本和8份日表；以完整源日历网格、跨品种共同日期索引重算60日块、2000次、seed20261018 bootstrap。无已识别标签日保留NaN，不填0。两期间索引SHA分别为`91e84837482c10cbad55454535baed44b9af310d5332415abb4306f88d200113`、`5c0b1b714adfa5aac8e05636efabd8d8b26606cf46693031b1dcf3a9c24321de`。
6. 全部15项门及总合取重算一致。最大保存值/重算值绝对差`6.6613381477509392e-15`；72组最大正规方程相对残差`2.9117030207991083e-14`，最大截距加权残差`1.6473331217915754e-16`。

## 真实结果（代理R，非现金收益）

下表为2020+共同已识别集合上的日期等权均值及固定预测60日块bootstrap 95%区间；1642个有限源日，2000次有效重采样。主期间107844条ready预测，107437条标签已识别、407条未知（missing_D326、right_censored81）；M1已识别选中473行、223日、80family。未知行仍保留预测，其M0/M1选中率为1.474201%/1.965602%，不能把未知收益补0。

| 指标 | 点均值 | 95%区间 |
|---|---:|---:|
| M1自身下界 | 0.001047838674 | [-0.001096991763, 0.001985412112] |
| M1−M0配对下界 | -0.000427660312 | [-0.001286296630, 0.000511929582] |
| M1−M0配对上界 | -0.000156401819 | [-0.000988103738, 0.000809637366] |
| 同参与率基准差下界 | 0.000184122801 | [-0.000796617336, 0.000791748773] |
| 同参与率基准差上界 | 0.001735631961 | [0.000497959516, 0.002512803450] |
| 固定mask、1R成本预算压力下界 | -0.002724153224 | [-0.004845349829, -0.001842795935] |

2015+有161609条ready、161105条已识别、504条未知（missing_D423、right_censored81）；M1已识别选中1082行、507日、83family。M1下界点均值0.000310445795，配对下界−0.000616785269，参与率差下界−0.000238197906，均按原门评价。2020—2025六个完整年份配对下界仅3年为正（2022/2024/2025），未达4年。2026只按未完整年度处理。

两family留出2020+的M1自身下界均为正，但配对下界分别−0.000054839848、−0.000272774916；合并留出为−0.000237616014。两组必须共同报告，不能选择较好一组挽救结论。

| 固定门 | 复算结果 |
|---|---|
| `primary_selected_dates_at_least_60` | 通过 |
| `primary_selected_families_at_least_8` | 通过 |
| `primary_M1_lower_positive` | 通过 |
| `primary_paired_lower_ci_positive` | 失败 |
| `primary_participation_lower_ci_positive` | 失败 |
| `all_2015_M1_lower_positive` | 通过 |
| `all_2015_paired_lower_positive` | 失败 |
| `all_2015_participation_lower_positive` | 失败 |
| `same_mask_cost_1R_primary_positive` | 失败 |
| `four_complete_years_paired_lower_positive` | 失败 |
| `partial_2026_M1_lower_positive` | 通过 |
| `holdout_0_primary_M1_lower_positive` | 通过 |
| `holdout_0_primary_paired_lower_positive` | 失败 |
| `holdout_1_primary_M1_lower_positive` | 通过 |
| `holdout_1_primary_paired_lower_positive` | 失败 |

7项通过、8项失败，总门false。期末权益/总收益/最大回撤/Sharpe/总滑点/实际交易次数/现金胜率均不适用；本次没有生成现金账本、真实成交或可交易策略收益。

## 实际命令与失败留痕

完整审查命令为`/Users/mac/Desktop/fian/.py311/bin/python /Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage012_day_proxy_experiment_review/review_actual.py`。session15277→chunk8be961，exit0，耗时18.545825秒。实际runtime为原`.py311` Python3.11.5、NumPy2.2.3/Pandas2.2.3。审查者fit=0、SQL=0、金融=0、网络=0。

另保留一次**完整审查前的bootstrap失败**：11:48:56，0.038025秒，exit1。启动wrapper把venv Python符号链接`.resolve()`成base Python，脚本第8行import NumPy即`ModuleNotFoundError`，发生在数据读取与数值审查之前。root明确允许使用原venv绝对路径纠正启动。审查脚本SHA未变，随后只完成一次完整数值审查。终态明确记录`process_invocations=2`、`numeric_review_invocations=1`；保留首次stdout/stderr/terminal，没有把失败改写成通过。

## 工件与SHA256

| 文件 | SHA256 |
|---|---|
| `/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage010_day_proxy_experiment/experiment/manifest.json` | `fc1abeaffb5a15e9b782109fbbadedeab3fb56d4d40eb663d3ba3fb42f0a9b27` |
| `/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage010_day_proxy_experiment/experiment/actual_terminal.json` | `42ef5f676ac57a47b87d3e6e26663548d3e5499993747a0fceeab200cf8f7cec` |
| `/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/tools/stage010_day_proxy_experiment.py` | `c8ddce7c93184f793b9c42d2366ffd24b9f9651d5c4a96411bb0388098539ffa` |
| `/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/tools/test_stage010_day_proxy_experiment.py` | `f1197d1a4417965e376705da770f14412bb17b251a0fad9eac5a2f29be10b976` |
| `/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage010_day_proxy_experiment/experiment/fits.jsonl` | `28e5c62700127fbf9d04245b6288b70c1b589d3ac3453ba917f0f365d1167b71` |
| `/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage012_day_proxy_experiment_review/actual_review_checks.json` | `2915b744c1c5d5c8b858958cbcc43296021dd3940a64cb38e8a228f4e849b622` |
| `/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage012_day_proxy_experiment_review/actual_terminal.json` | `fcbb894975a284c893fb1c8801f4a3cfc13b51306d332a73ff925864f090268f` |
| `/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage012_day_proxy_experiment_review/review_actual.py` | `d8caf3318c9fc75a23df4c8d4290f2f4dd056b95b0c68f7215341b82c439e98a` |
| `/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage012_day_proxy_experiment_review/review_receipt.json` | `e6656decde31912f93fce6b5aaf910760a11971d4558f5e4bb0c39e5b169775f` |
| `/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage012_day_proxy_experiment_review/actual_stdout.json` | `f5a9aeaa43932d3fd709d4055753e902c3d58cc2e7a3830b0d854f81291a1dca` |
| `/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage012_day_proxy_experiment_review/bootstrap_attempt1_actual_terminal.json` | `66cd24f2926bf9c6f2d2d0a0a5207131565e515201a422ea4aa7d9ad9f352fef` |
| `/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage012_day_proxy_experiment_review/bootstrap_attempt1_actual_stderr.txt` | `8db6de3e6a3baf1c69be4154c903e743885b1ff99bd05690790089d75214b4be` |

## 边界、反思与收口

本receipt只接受冻结DAY代理结果的算术、身份和逻辑。置信区间以固定历史预测为条件，未覆盖研究者选择、重拟合不确定性、真实tick/跳空/涨跌停/费用/保证金/成交约束；family hash不消除历史重命名与行业相关性。没有授予`real_economic_labels_ready`、`financial_ready`或`production_qualified`，三者均为false。

运行前判断：**本次审查不新增过拟合，继续价值是有**；固定合同和结果后只核对身份与算术，能区分失败研究与实现bug。运行后判断：**审查本身仍不新增过拟合，当前方案继续加参救回的价值否**；配对信息门、同参与率门、年度稳定性和成本压力均未通过。接受这次有限负结论，停止当前4项跨市场特征包与既定DAY代理形状，不扫阈值、成本、stop/fraction、年份或品种救参。全市场高质量做多信号的原目标仍可保留，但本阶段不自行开启下一实验。

不更新LINE/registry/memory/back_log；提交root合入。已完成任务后暂停，无待运行fit、金融或数据重建。
