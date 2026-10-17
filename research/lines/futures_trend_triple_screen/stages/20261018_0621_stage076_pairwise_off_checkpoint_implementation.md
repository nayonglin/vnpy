# Stage076：A_OFF/B_OFF 中性快照、真实成交身份与纯导出（Task3）

- line_id：`futures_trend_triple_screen`；记录时间：2026-10-18 06:21 CST。RED 日志06:14；新模块06:15新增，06:18末改；第三测试06:20完成最终 GREEN。
- 分支 `codex/ai-training-data-expansion`，只读 HEAD `245d3c5e352cd150baf2aa28c4336afb5c291ee6`。本 agent 未建 worktree、切分支、stage、commit 或 push。
- 阶段性质：只实施已批准 [Stage062](20261018_0546_stage062_pairwise_off_implementation_plan.md) 的 Task3；非重要 alpha 突破。先读 AGENTS、registry、062 Task3、[Stage073](20261018_0604_stage073_pairwise_off_policy_independent_review.md)、031/022 身份/快照/export helper 及冻结 847/827/028/035。
- 只新增 `tools/stage065_account_checkpoint.py`，只扩已有 integration 文件第三个具名测试及其 fixture helper；policy、旧源、LINE、registry、061/071 和其他 agent 文件未改。唯一记录为本文；证据仅在 `outputs/stage076_pairwise_off_checkpoint_implementation/`。

## 开始判断与调研结论

开始是否在过拟合：**否**。本次核对的是已固定政策下的真实成交身份、持久化和纯导出，不按收益挑规则。是否有价值：**是**。Task1/2 已被 Stage073 以 P0/P1/P2=0/0/0 接受，下一步需要证明真实 native/B 账本不会因导出错误丢失或混用账户身份。

本次遵守 root 禁止网络的边界，未重复联网/GitHub；沿用 Stage059 官方方法调研与判断：通用切分工具不能自行证明历史 PIT、标签成熟或 alpha。局部真实源码核对结论是：复用031的 actual TradeData/母单一致性及clock工具，增加新 owner 封存壳，比篡改旧 C_TS/B_TS 常量复用旧 seal 更准确。本阶段不执行旧 fixture main、旧 suite 或任何真实账户回放。

## root 的 scope ruling

本次原生真实成交 fixture 只有一个交易日，**不造1641行零额表，不把完整 A0/2020—2026 门在1日fixture上写为通过**。

root 明确要求并已实现：preflight/context/seal/summary 传递 `fixture_only=True`、`reference_calendar_scope=tiny_fixture`；中性 validation 名为 `actual_daily_dates_equal_preflight_reference`，只证明与该微型参考日历一致以及持久化机制。完整范围 `fixture_only=False` 必须提供 `full_2020_2026`、1641个有序唯一参考日；真正 runner 还须实际计算日期、设置、参数、数据和源码门，不能凭这里的fixture seal签完整金融资格。比较函数拒绝fixture，返回None。未扩展新资格体系。

## 新实现及调用责任

`stage065_account_checkpoint.py` 顶层只import stdlib；独立新进程验证 numpy/pandas/sklearn/joblib 未因导入进入 sys.modules。模块不导入061，不构造 engine、不读 DB、行情或模型。

- `new_run_context(output, arm, preflight, started_at)` 同时落盘新 context、preflight 和逐来源源码快照；其 `source_bindings` / `data_bindings` 由调用者传入真实映射（每项sha256与bytes）。本次没有虚构尚不存在的runner SHA。未来runner存在后可作为额外source binding进入同一壳；当前已绑定真实checkpoint/policy及022/031/028/035/native来源。
- context/manifest/seal 固定owner、attempt=1、run_id、精确output、writer源SHA、政策SHA、source/data映射SHA和scope。A 类身份严格是原847 native；B保留035/028类与内部B_TS producer。A raw中的 `ordered=None`，B raw是四类真实ordered审计。
- `save_raw_checkpoint` 只序列化account tables/capture/actual identities/settings/parameters/spec/preflight等，不序列化engine、strategy、分钟cache或history。检查对象单元格/attrs，避免把非account对象藏进DataFrame。**真实returned tables先落raw，再做设置/calendar/source等semantic validation/seal**；source drift检查在seal/load阶段，不能先失败而丢raw。
- `seal_checkpoint` 保留完整原门语义，改用OFF expected及中性reference-calendar名字；校验caller的完整validation证据，明确不是经济/独立账户审查通过。缺返回表的路径写 `failure_capture.pkl.gz` 与标partial的 `run_failure.json`，没有seal。
- 所有pin的JSON与gzip/pickle文件都只读一次到bytes，hash/size检查和解析/解压使用同一bytes。context、preflight、manifest、seal、raw、源码原件/快照在unpickle前全部完成绑定核验；seal另有不可覆盖的 `seal_receipt.json` 绑定其精确bytes，连只增加JSON空白也拒绝。拒symlink不是字节绑定的替代品。
- `export_checkpoint` 延迟复用031 `build_execution_clock`、022枚举/交易日、原s650 metrics；按原847 frames名称导出全部传入表。CSV/JSON保留研究账户owner，producer身份不重写。A不写虚假ordered CSV，counts与signal_machine_arm为null；B保留B_TS审计。失败只留本次 `exports/export_NNN/`，已有raw/seal不变；成功拒覆盖。
- `write_comparison_if_ready` 只处理两臂完整非fixture sealed结果，保留A0受限固定模型数值和原B真实失败/N/A行，新结论pending。当前只验证fixture拒绝分支，**未拿虚构完整结果执行正向全区间比较**；该分支还须Task4连接后独立验收。

新/修改/删除可调alpha参数、正式策略配置、模型、月AI池、资本或成本：均0。本次仅新增持久化/导出实现；未复制036的main或改其常量。

## RED→GREEN 与真实接合证据

测试名：`PairwiseOffIntegrationTests.test_real_fill_identity_checkpoint_and_pure_export`。

```sh
.py311/bin/python -m unittest discover -s research/lines/futures_trend_triple_screen/tools -p test_stage065_pairwise_off_integration.py -k test_real_fill_identity_checkpoint_and_pure_export -v
```

- 实现前RED：exit1、1 failure，明确 `neutral account-only checkpoint/export is absent`；native冻结栈正常导入，没有以import/version错误充当RED。
- 最终GREEN：exit0，`Ran 1 test in 0.487s ... OK`。只跑新增第三测试，未扫旧suite、未重跑Task1/2或覆盖Stage070/073证据。
- 冻结数值栈沿022设置，未安装或升级依赖；模型实体未加载、未预测、未拟合。

真实fixture使用原847 native A及真实035/028 B；synthetic AM种子和长侧B T111/S99来自已审035案例的方法，未执行其旧main。唯一隔离项是给native alpha生成一个固定测试输入：A=`long_case1a`，B=原native信号为空；后续planner、T/S、激活、847 stop/retry、827 `_fill_order`、TradeData、成本和snapshot/clock均真实。

| 项目 | A_OFF | B_OFF |
| --- | --- | --- |
| strategy/engine | 原native类exact identity；无ts_machine | 原035 strategy / 028 ordered engine；内部B_TS |
| 真实827 `_fill_order` | 1次母开仓 | 1次母开仓 |
| actual成交价格 | 111/105/111/105 | 111/105/111/105 |
| actual成交量 | 120/120/120/120 | 10/10/10/10 |
| retry时点 | 下一分钟 | 下一分钟 |
| 四笔实际手续费+滑点，且仅计一次 | 5318.4 | 443.2 |
| ordered | null；无ordered CSV | decision1/fill1/execution1/pending0 |

fixture参数资金10万只服务微型真实路径，不是新金融的15万配置。两臂手数差异来自原native u-close估量与B T估量，未人为抹平；fixture spec/parameters记录真实使用的设置和engine metadata，标 `tiny_fixture`，不附未使用的正式economic overrides。

真实synthetic usage确实缺signal字段，031根据actual TradeData及真实母身份一致补齐；缺母、usage signal冲突、普通母单signal缺失均拒绝。28项预期拒绝覆盖两臂的原身份反例、raw/manifest/seal/context/preflight/current source/source snapshot字节变化、未seal、跨arm、symlink和外部复制，均在 `pickle.loads` 前失败。独立instrumentation断言每个pin文件只读一次。

另证明：设置/engine-return/日数validation拒绝时raw已经存在且无seal/summary；真实source在engine后漂移，raw仍落盘、seal拒；真实clock缺母导致导出失败，既有seal保留；metrics故障后可从原seal纯恢复到新export目录，raw和seal bytes不变。没有engine返回的partial路径只留failure capture，不伪造完整账本；隐藏非account对象也拒绝。

纯export成功和故障恢复期间，以失败sentinel覆盖：native engine/strategy构造、load_data/run_backtesting、data stack/CSV/parquet读、061 loader、DB getter/sqlite connect、minute loaders、joblib load、pairwise runtime/score、旧model smoke、Pipeline predict/predict_proba/fit。两臂各项调用计数全部0。导出恢复不是重跑账户。

## 精确源码与既往审查边界

- 新 checkpoint SHA256：`7e5a265a23b8fce871c895292e0738831604eefb9a341f7a83bd0320a68cf15b`。
- 扩展后test SHA256：`2515326d771587c5ed49459c54286bd3f5c682c39455155082fd1daf982664c0`；这是本次待独立审查身份，**不是Stage073已审test**。
- Stage073已审test历史SHA仍为 `51731fdd31bd9fe2d7ba7f04ed34fc99f3c19fddb70dd7abae839d35c5771539`。删去本次第三测试及其helper的新增区段后，按原bytes重建SHA恰好等于该旧SHA；前两个test/其原helper未改。
- policy未改，仍为 `edaa018cebe288245197dcb8b4bfba76e2a1c1691cf24c7de369a91bc62a639f`。
- `implementation_manifest.json` 绑定本次源码、旧审查身份、062/073和冻结依赖；`red.txt/green.txt/test3.json` 为本次证据。

## 结束结果与TODO

新增/修改/删除完整回测结果：0；完整期末权益、总收益、最大回撤、Sharpe、总滑点、交易次数、胜率：均 **N/A**。上表只列tiny真实成交/成本不变量。金融回放、网络、训练、模型load/predict/fit、CTP及外部订单API均0，`production_qualified=False`。

结束是否在过拟合：**否**；本次是固定工程合同及拒绝/恢复证据，不按收益选策略，既有研究选择偏差仍存在。是否值得继续：**是，Task3已具备交给root统一独立复审的有限证据。** 当前不另派reviewer，不接Task4、061数据层或真实账户，也未获金融授权。

TODO：root独立审查新Task3；Task4未来连接时需真实runner source/data bindings、固定canonical输出、fixture_only=False及完整1641日，实际计算所有setting/parameter/calendar/source/input/minute门，并在真实入口重新证明无旧model smoke与无纯export重放。数据层状态由root单独验收，本阶段既不加载061，也不替071/081/078签资格。原B真实失败及A0限制继续公开，不能只胜较弱A_OFF就宣告完整2020—2026收益更高且回撤更低的目标完成。
