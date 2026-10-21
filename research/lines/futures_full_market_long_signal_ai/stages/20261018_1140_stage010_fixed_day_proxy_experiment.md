# Stage010：固定年度扩窗 M0/M1 代理效用实验

- line_id=`futures_full_market_long_signal_ai`；2026-10-18 11:40 CST；作者实现，不自签独立审查。
- 先读 registry、新 LINE、冻结 Stage007；protocol SHA `2e5da3da4440223e3ac978256d563b80d5bd4264cec56d4085ed6062d7bad0a4`。本阶段不变更目标、屏障、特征或判据，尤其 M1 只增加4列、没有interaction。
- 使用 test-driven-development 与 verification-before-completion；按root明确范围只运行新增四方法，不跑旧suite。只写本工具/测试/本文与outputs，不派agent、不改009、007、LINE、registry或Git。

## 代码与 fixture 已完成（11:40时点；最终状态以下方实际终态为准）

新增 `tools/stage010_day_proxy_experiment.py` / `test_stage010_day_proxy_experiment.py`。固定2015..2026年度扩窗，每年主样本M0/M1及两组family留出M0/M1，总72个Ridge；alpha1/cholesky/截距、训练侧加权StandardScaler、BLAS1，无调参。每日期训练行权重1/n再整体归一至均值1；u和label_known_date均严格小于当年首源日，族留出不混F。

全部feature_ready行先预测，不以未来D/label可识别性筛预测；仅评价时使用两模型共同identified子集，未知与缺D入选率另报。报告主2015+、2020+、逐年、两holdout单组及合并；配对区间使用mask差的正负端正确取界，共同mask精确抵消。参与率参考逐日同p、同mask成本1R压力；固定60源日移动块/2000次/seed20261018，同日期网格各统计共用抽样index。无可评价日保留NaN；均值/CI仅为条件proxy，不是总体现金收益。

每fit即时写并fsync记录：训练ID SHA/排序/截止、family列表与留出组、按日实际权重及float64数组SHA、scaler mean/var/scale、系数/截距、固定参数和特征次序。预测不含OHLC。`export-only`只读取保存系数数值重算，不调用fit；已有实验输出目录拒绝覆盖，失败不自动重跑。

四方法实际RED：chunk7d52bc exit1，4个断言因实现尚不存在失败，没有伪装运行完整行为测试。随后实际GREEN：最后chunk168c89 exit0，4方法/0.083秒；测试覆盖成熟截止/族留出/未来数据不改变缩放、真实sklearn加权解析结果与纯系数重放、共同mask抵消/未知日保留、参与率界/固定mask压力/共享bootstrap。两轮GREEN各3个tiny fixture fit，累计6；这不是实际实验计数。所有实际数值测试见fixture_tests.log。

最后按root要求将输入条件明确为011 `qualified_for_fixed_proxy_experiment=true` 且data_manifest SHA一致。该三行入口收紧在GREEN之后，只编译最终2源，不按流程重复suite；透明记录于implementation_receipt.json。最终源码SHA：trainer `c8ddce7c93184f793b9c42d2366ffd24b9f9651d5c4a96411bb0388098539ffa`；test `f1197d1a4417965e376705da770f14412bb17b251a0fad9eac5a2f29be10b976`。两源compile完成；源码已停编。

## 受控实际入口

仅收到root最终009 manifest和011 receipt路径/SHA后，写accepted_inputs.json，再唯一运行：

```
.py311/bin/python research/lines/futures_full_market_long_signal_ai/tools/stage010_day_proxy_experiment.py fit --bindings research/lines/futures_full_market_long_signal_ai/outputs/stage010_day_proxy_experiment/accepted_inputs.json --output research/lines/futures_full_market_long_signal_ai/outputs/stage010_day_proxy_experiment/experiment
```

009的 `model_ready=false/real_economic_labels_ready=false` 不等同拒绝这次统计实验；资格来源是011限定的fixed proxy接受，不扩成真实经济标签资格。生成器manifest分类协议/模型复现/预测指标/终态证据/外部缓存角色，本地精确登记交root，不建设通用登记系统。

## 当前结论与反思

截至本节：真实实验fit=0，金融/native/prepare/下载/网络/生产=0，模型效用/全部筛查门尚无结果。权益、收益率、Sharpe、最大回撤、滑点、交易次数、胜率N/A。

调研继承007实际阅读的Kaminski/Lo、Backtrader官方执行/bracket说明及DeePM作者论文/GitHub，不新增外搜。判断：固定proxy比较可证伪跨市场信息增量，但连续屏障区间、研究成本预算、缺真实历史tick/fees的边界不变。即便筛查通过，也不证明更高真实收益与更低回撤，不能直接窄止损加注。

开始/当前新增选参过拟合：否；按冻结协议实现，没有改变阈值/成本/年份/特征包；历史反复观察和研究选择风险仍在。继续价值：是；在全市场新母体上比较同一学习器的信息增量，比扩大旧池或复活失败风险加分更接近新目标。目标active，尚无新alpha；后续实际终态与门结果在本文同一阶段补记。

## 实际唯一实验终态与结果（2026-10-18 11:46 CST）

Root提供并实际绑定009 manifest `ea26675e8322bee8a3c71d4ba0c731055a52a161359c1ac456de628029a5071e`、011 receipt `cf71e0c9a9cc570aa803ad437a117861961c64b13ec920a8b5ab573577301b4a`；011 qualified_for_fixed_proxy_experiment=true 且同data_manifest，之后才启动真实命令。

原handle从chunk1180c7/session38894一直观察到chunk326eab **exit0**。实际11:44:14.098235—11:44:59.762574 CST，45.664339秒，恰72个Ridge fit，原72模型全部保存、没有重fit/恢复重跑。numpy2.2.3、pandas2.2.3、sklearn1.6.1、scipy1.17.1；BLAS/threadpool限制1。没有运行export-only，因为本次原导出已正常闭合。

**quality_information_screen_pass=false。按收益前合同停止本次跨市场四特征包＋固定DAY代理政策，不调屏障、interaction、成本、阈值或年份救参。** 本作者尚未自签独立正确性；最终产物交Stage012审模型/数据/逻辑/置信度。

### 主结果及分母

以下均为“先共同可识别品种等权、再源日期等权”的归一化proxy-R，没有账户本金、复利、权益或真实成交。

| 固定统计 | 2015+ | 2020+主区间 |
| --- | ---: | ---: |
| M0自身lower均值 | 0.0006435125 | 0.0014201341 |
| M1自身lower均值 | 0.0003104458 | 0.0010478387 |
| M1−M0配对lower均值 | -0.0006167853 | -0.0004276603 |
| M1−M0配对upper均值 | -0.0000923304 | -0.0001564018 |
| M1−参与率参考lower均值 | -0.0002381979 | 0.0001841228 |
| 同mask成本1R的M1lower | -0.0058468032 | -0.0027241532 |

2020+ paired lower的95% block CI为[-0.0012862966, 0.0005119296]；参与率lower CI为[-0.0007966173, 0.0007917488]；M1自身lower CI亦跨零[-0.0010969918,0.0019854121]。所以自身lower点均值略正不是可靠识别增量证明，更不是加注依据。历史固定预测的配对均值区间两端都负，但抽样CI跨零，不夸大为已统计证明所有情形M1更差。

2015+预测161,609、共同identified161,105、unknown504＝missing_D423+right_censored81；2020+预测107,844、identified107,437、unknown407＝missing_D326+right_censored81。009总ready194,709中，2010—14仅为前置训练期，不冒称已做这五年的年度测试预测。未知ready均保留预测，未填结果0；评价仅是identified条件结果。

2020+ M1在identified上入选473行，223日期、80family；满足预声明支持门，但不能补救效用门。全部ready M1入选率0.4460146%，unknown子集1.9656020%（8/407），M0相应0.3384518%与1.4742015%；不能用已知子集结果代表未知行。主source日期网格1643日，其中1日无identified而保留NaN；2015+2862日同样有1日NaN，未删掉后按新网格抽块。

2020+两组留出M1lower分别0.0008316435、0.0006490603，paired lower分别-0.0000548398、-0.0002727749，两个增量门均失败。两组完整合并后M1lower0.0007128250、paired lower -0.0002376160、同mask压力 -0.0035724864；没有挑较好组报告。留出排除的是该组family全部历史训练行，M1冻结的市场上下文本身仍是当时可观察其他family信息，不宣称行业无相关或彻底信息隔离。

2020—2025完整年paired lower>0只有2022、2024、2025，共3/6，未达4年门；2026部分年自身lower>0。截距参考实际全现金，proxy0；固定正20日动量参考2020+lower=-0.11070255。右尾未选机会成本区间与MSE/固定分数分箱完整保存在metrics，诊断不用于调参或重新挑mask。

### 全部门逐项

- `primary_selected_dates_at_least_60`：true。
- `primary_selected_families_at_least_8`：true。
- `primary_M1_lower_positive`：true。
- `primary_paired_lower_ci_positive`：false。
- `primary_participation_lower_ci_positive`：false。
- `all_2015_M1_lower_positive`：true。
- `all_2015_paired_lower_positive`：false。
- `all_2015_participation_lower_positive`：false。
- `same_mask_cost_1R_primary_positive`：false。
- `four_complete_years_paired_lower_positive`：false。
- `partial_2026_M1_lower_positive`：true。
- `holdout_0_primary_M1_lower_positive`：true。
- `holdout_0_primary_paired_lower_positive`：false。
- `holdout_1_primary_M1_lower_positive`：true。
- `holdout_1_primary_paired_lower_positive`：false。

### 最终产物、复现与后续

- `experiment/manifest.json` SHA `fc1abeaffb5a15e9b782109fbbadedeab3fb56d4d40eb663d3ba3fb42f0a9b27`，绑定所有预测/日统计/模型/输入/终态。
- `experiment/metrics.json` SHA `fd1d389573399709619ab9ac3172af422afc7c6195af4a0661e8efdf4559ddfc`。
- `experiment/actual_terminal.json` SHA `42ef5f676ac57a47b87d3e6e26663548d3e5499993747a0fceeab200cf8f7cec`。
- `experiment/fits.jsonl` 72条、6,355,793B，SHA `28e5c62700127fbf9d04245b6288b70c1b589d3ac3453ba917f0f365d1167b71`。
- 主/两holdout预测gzip不含OHLC；每模型按固定特征、输入manifest和已存权重/scaler/系数可纯数值重算。无实际export-only追加运行、无重fit。
- root本地登记会将作者role别名 `model_reproduction_asset→model_artifact`、`reproduction_asset→feature_contract` 显式映射；未为登记改源码或重跑。原模型输入不变，登记规范化X/y移除非输入atr20仅为资产边界，不是实验重建。

结束新增选参过拟合：**否**，失败后参数与筛查门未改；bootstrap不覆盖长期研究选择偏差，历史不是全新OOS。继续这组跨市场特征＋代理政策救参：**否**，固定门多项失败。继续原全市场高质量做多的更高收益/更低回撤目标：**是**，应保留本次反证与执行边界，由root另行判断结构不同的新信息，而非直接窄损加注。

实际金融/native/账户/下载/网络/生产仍0；72次是同一冻结信息增量实验的年度模型，不是72次金融策略搜索。真实权益、收益率、最大回撤、Sharpe、胜率均N/A；`real_economic_labels_ready=false`、`financial_ready=false`、`production_qualified=false`，原目标未完成。
