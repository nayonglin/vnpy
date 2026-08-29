# Stage064：Stage037、Top9、Top10随机多周期压力测试

- line_id：`futures_trend_rollover_shape_same_volume`
- 当前模式：day
- 记录时间：2026-08-30 00:27（Asia/Shanghai）
- 工作区/分支：`.worktrees/stage056-ai-top14-plus-fu` / `codex/stage064-random-multicycle`
- 阶段性质：用户确认的离线随机起点多周期反证
- 是否重要突破：否
- 是否触发A/B：是，A=正式Stage037 Top8+fu，B=Top9+fu，C=Top10+fu

## 外部调研与判断

- 参考资料：Bailey等《The Probability of Backtest Overfitting》（https://papers.ssrn.com/sol3/Papers.cfm?abstract_id=2326253）；Politis与Romano《The Stationary Bootstrap》（https://www.tandfonline.com/doi/abs/10.1080/01621459.1994.10476870）；White《A Reality Check for Data Snooping》（https://onlinelibrary.wiley.com/doi/pdf/10.1111%2F1468-0262.00152）。
- 我的判断：随机起点可以补充固定1月/6月起点，观察候选优势出现的频率与尾部；但窗口会重叠，不能当作192个统计独立样本，也不能覆盖Stage063已经出现的固定多周期硬失败。随机窗口和门槛必须在结果前冻结，不能失败后重抽。

## 本次变更

- 新增脚本：`stage064_stage037_top9_top10_random_multicycle.py`。
- 新增测试：`test_stage064_stage037_top9_top10_random_multicycle.py`。
- 新增输入：`stage064_stage037_top9_top10_random_windows.csv`。
- 修改脚本：无策略脚本修改。
- 删除脚本：无。
- 新增参数：1/2/3年各随机64个起点；总窗口192；随机种子 `1246746679971163672`。
- 修改参数：无策略参数修改。
- 删除参数：无。

## 回测参数与冻结合同

- 数据区间：`2018-01-02` 至 `2026-08-28`，数据库SHA `ee83eae2159afec2b745a5827f73aaf9da1e71d65af2c0a624496555c08b6ebe`。
- 窗口：1/2/3年各从所有可完整覆盖的实际交易日起点中均匀无放回抽64个；三臂严格共用相同窗口。
- 窗口计划SHA：`5a0997ea77eb0f17167810f72789dc52f18a7ec71c5b42ccf03de7d2e7c5af12`。
- 账户规模：每个arm-window均为15万元、空仓、独立引擎/持仓/账户状态冷启动。
- 成本口径：沿用Stage037/Stage063既有真实引擎成本、滑点、保证金和风险参数。
- A：master/CURRENT中的Stage037 m0016 Top8+fu；B：Top9+fu；C：Top10+fu。B/C只改变AI eligibility路径和strategy标识。
- 总运行：192窗×3臂=`576`个独立真引擎回测；每臂窗成功后写SHA校验checkpoint。
- 门禁：每个1/2/3年和全部随机窗分别要求收益胜/非劣率不低于50%、收益差中位不低于0、DD非劣率不低于80%、Sharpe非劣率不低于80%、聚合滑点不超过正式版105%、账户存活且DD50/broker100失败不劣化。
- 固定边界：Stage063固定1月/6月门已经失败；即使随机窗口通过，也不能晋升或救回候选。
- 身份边界：checkout/master为Stage037，稳定生产仍为Stage021-Q；沿用用户对本连续离线研究的显式身份豁免，不允许安装、晋升、CTP或订单API。

## 运行前反思

- 是否过拟合：是，风险高。Top9/Top10来自看过Top10–19和Top9结果后的后验边界候选。
- 是否有价值继续：有，但只限这一次预冻结随机压力测试。它能衡量固定窗口结论是否只是少数起点现象；完成后不继续扫TopN、种子、样本量或窗口。

## 回测结果（2026-08-30 02:34 完成）

- 运行事实：192个随机窗口、576个arm-window全部为新引擎冷启动；checkpoint复用0、首次生成576、失败0、补跑0，结果后未重抽窗口。
- A全周期参考：期末权益 `16,859,940.60`，总收益 `11139.9604%`，最大回撤 `-39.9147%`，Sharpe `1.538821`，总滑点 `1,659,555`，总交易次数 `734`，胜率 `53.2310%`。
- B全周期参考：期末权益 `16,871,625.40`，总收益 `11147.7503%`，最大回撤 `-39.9147%`，Sharpe `1.517586`，总滑点 `1,762,115`，总交易次数 `766`，胜率 `53.3650%`。
- C全周期参考：期末权益 `21,870,488.80`，总收益 `14480.3259%`，最大回撤 `-39.9147%`，Sharpe `1.586976`，总滑点 `2,163,390`，总交易次数 `798`，胜率 `53.7348%`。
- B对A全部192窗：收益胜/非劣率 `78.65%`，收益差中位 `+0.0000pp`，DD非劣率 `84.90%`，Sharpe非劣率 `88.02%`，滑点比 `104.59%`；分周期只有2年DD非劣率 `78.12%<80%`，因此随机门失败。
- B对A分周期收益胜/非劣率为1年 `76.56%`、2年 `81.25%`、3年 `78.12%`；候选最差收益分别 `-15.7633%/-8.7732%/+25.4100%`。最弱收益差为3年 `2023-06-15` 起点的 `-88.1975pp`。
- C对A全部192窗：收益胜/非劣率 `84.38%`，收益差中位 `+9.9733pp`，DD非劣率 `72.92%`，Sharpe非劣率 `92.71%`，滑点比 `113.66%`；DD、成本和broker100失败，随机门失败。
- C对A分周期收益胜/非劣率为1年 `84.38%`、2年 `82.81%`、3年 `85.94%`；DD非劣率仅 `75.00%/68.75%/75.00%`，滑点比 `112.71%/115.13%/113.21%`。最弱收益差为3年 `2019-11-28` 起点的 `-143.9567pp`。
- 576条summary已从130MB逐日curve独立反算期末权益、收益、回撤、Sharpe、滑点、交易数、胜率与账户存活；12条aggregate再计算一致，Stage064测试 `8 passed`。

## 输出文件

- report：`artifacts/stage064_stage037_top9_top10_random_multicycle/stage064_random_multicycle_report.md`。
- summary/comparison/aggregate/curve：同目录 `stage064_random_window_summary.csv`、`stage064_random_window_comparison.csv`、`stage064_random_cycle_aggregate.csv`、`stage064_random_equity_curves.csv.gz`；逐日curve由121.5MB CSV无损gzip为8.17MB，避免Git单文件过大，pandas可直接读取。
- 五图：全周期参考、1年随机带、2年随机带、3年随机带、随机稳健性汇总，均位于同一产物目录并由decision记录SHA256。
- decision：`artifacts/stage064_stage037_top9_top10_random_multicycle/stage064_decision.json`。

## 结论

- 本阶段结论：`random_stress_diagnostic_only_keep_stage037_stop_topn_scan`。
- B的收益多数窗口不劣于A，但2年回撤稳定性低于冻结门槛，且Stage063已有全周期Sharpe/成本与固定起点失败；不能晋升。
- C的收益优势更强，但这是用约 `13.66%` 额外滑点、较弱DD路径和新增broker100失败换来；不能晋升。
- 是否进入下一步：否。随机压力测试没有推翻Stage063，正式离线基线继续保持Stage037；停止TopN、随机种子、样本量和窗口扫描。

## 运行后反思

- 是否过拟合：是，风险高。B/C本来就是看到既有TopN结果后的后验候选；随机窗口只增加反证覆盖，重叠窗口并不形成192个独立样本外观察。
- 是否有价值继续：本次有一次性价值，因为它证明固定1月/6月失败不是唯一风险来源；继续扫描没有价值，下一步只接受预先独立定义的容量/成本问题或自然forward样本。

## 独立评审与运行后修正

- 独立review初审发现一个P2：runner原先把 `new_engine_run_count` 固定写576；本次恰好新跑576所以当前结论不受影响。按review先新增失败测试，再改为实际 `checkpoint_generated`，目标测试通过。
- 第一次修正后快速复核又发现发布合同P1/P2：当前runner与旧checkpoint runtime未分层，且121.5MB curve只被手工gzip，fresh发布仍会产生明文大CSV。按系统化调试定位为“引擎执行、图表生成、产物发布三层身份混写”，未重跑引擎。
- 最终修正：fresh `_publish` 原子写确定性 `gzip(mtime=0)`，不生成明文curve；decision分层保存engine checkpoint runtime `9dfac9ba...`、current runner runtime `2d09595a...`、实际render generator与当前publisher SHA，并记录curve压缩/解压SHA、大小、279,420行和576臂窗。
- 最终独立review：`PASS`，P0/P1/P2/P3=`0/0/0/0`。压缩curve SHA `fc4843fc...`、解压SHA `8faede77...`、大小 `8,162,665` bytes；576条summary核心指标0差异，publication payload SHA一致，fresh publisher临时测试通过。
- 运行后修正不改变随机计划、策略、引擎、checkpoint、逐日数值、指标、门槛或本次决策；关联回归最终 `47 passed`，Stage064聚焦 `10 passed`。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加Stage064随机压力结论。
- 是否更新 `research/registry.md`：否，研究线不变。
- 是否追加根目录 `memory.md/back_log.md`：否，除非出现改变研究政策的重要突破；本阶段预期仅为稳健性反证。
