# Stage136：固定正分月份排序现金对照实现，actual 尚未运行

时间：2026-10-18 22:40 CST；line_id=`futures_full_market_long_signal_ai`。非重要突破；本次仅落实冻结134，不产生新收益、标签或现金账户。

新增 `tools/stage136_month_ranking_cash.py`（32781B，SHA256 `f593e634b336508897a6f0f096974c029151ac5e7d1b50a22aac4e25b5b3ee43`）和 `test_stage136_month_ranking_cash.py`（6978B，SHA256 `47e2d160198896b269baf17f2deb84e8af868192edd8d90e8df698d2a13f57d5`）。旧源码、LINE、registry及其他研究线未改。

## 冻结行为

只消费135的实际 `stage135_month_ranking_attribution_v1` manifest及选中覆盖表。源B事前选中母行、exact product、scope/cutoff和anchor必须保持；完整父本由135覆盖表与源130 B全部父行bindings恢复。仅main进入现金；held和标签诊断不构造新现金。每个控制只把selected覆盖行及对应actions/mothers子集送入131稳定 `make_signals`，局部映B过接口，导出的signal `event_id`仍为真实child action，`mother_event_id`仍为原parent，`arm/control_id`保存真实控制名。完整mothers的canonical schedule只组织一次。

`CachedMarket(store)`只引用132已存arrays，通过 `bar(epoch,k)` 和 `indicator(epoch,k)`映射OHLCV、valid、N、low20、run；缺日/invalid不回退、不重算指标、不查SQL。恢复复用132 `restore_native_cache`：exact110MB cache/manifest、原5587源日历、缓存关联库stat；实际前后stat一致，大库不重hash。完整经济仍读128原市场协议绑定041 projection。131内核独立递推每个账户自己的权益、仓位、数量、预算与路径。

固定 `MAX_VOLUME_POS` 和 `RANDOM_POS_00..19`，两窗口×两成本，共84新账户；原AI B四账户仅exact引用summary/daily/diagnostics，绝不重播。初损.25N、100w本金、风险.0025/.02、margin .25/buffer1.1、u联合预留、D只减量、原毛容量/anchor/gap/stale规则全部不变。不允许负分Rall进入现金、追加seed、挑最好seed或失败自动重启。

## 输出与授权接口

manifest schema=`stage136_month_ranking_cash_v1`。顶层 `signals={control_id:binding}`；`accounts`每项含control_id/window/cost/account_id/directory/summary和`ledgers`九表bindings。账本名为 `NARROW_{control_id}_{window}_{cost}`，表为fills/reservations/daily/positions/closed/open/capacity_audit/entry_execution_unknown/rejections，沿131格式。保存全部84 summary、逐年、95family全年含零归因、所有seed分布、gap及unknown诊断；不因坏seed删账本。

`baseline_books`以window_cost为key，保存原B4 summary/daily/diagnostics binding和diagnostic_key；不复制原账户账本。比较 `AI_minus_MAX_VOLUME_POS`、`AI_minus_RANDOM_POS_mean20`，后者为AI每日log减20条每日log算术均值，使用原2000个252源日块indices。任一所需seed或AI的财富非正、非有限或曾破产，比较保留为`survival_failure_no_log_repair`，CI空，不丢seed、不加epsilon。有限20seed排名仅描述；133 unsupported、无正式/加注资格保持。

actual需root重新签发：schema=`stage134_exact_root_authorization_v1`，authorized_by=root，stage=cash，exact_source_authorized=true，protocol_sha256=`25ad088a36d4aa3a022e7da7e818902e62b1c7c922b85aae3c31ad960c780e62`，output为全新Stage136目录，source_bundle等于本模块 `source_bundle()`。input_bindings恰为134固定13项再加attribution_manifest/overrides；实际校验135完成终态与所有固定源bindings。不导入135、不运行131 execute、不调用132总审查入口。

最短调用：`.py311/bin/python research/lines/futures_full_market_long_signal_ai/tools/stage136_month_ranking_cash.py --protocol <134 protocol绝对路径> --protocol-sha256 25ad088a36d4aa3a022e7da7e818902e62b1c7c922b85aae3c31ad960c780e62 --authorization <root auth绝对路径> --authorization-sha256 <auth SHA> --output <全新Stage136绝对目录>`。

成功terminal为status=completed/exit_code=0，cash_accounts_started/new_cash_accounts=84，native_source_queries/actual_model_fit_calls/new_labels/downloads/whole_database_hashes/old_AI_books_replayed/old_baseline_replays=0。失败保留started、terminal和已产账本，绝不自动追加运行。

## 有限验证与反思

七个新fixture先按缺实现预期失败，随后`Ran 7 tests in 0.078s, OK`；syntax和`--help`均exit0。覆盖缓存缺日/invalid不回退、不重算；selected子集自身child及开放标签不拒绝；母身份变化/负分拒绝；20条log均值与均值权益log区别；坏seed/错日期不丢弃；保存False布尔语义；九张空表仍有可读schema。只测新边界，未扩旧suite。新实际SQL/label/fit/cash/下载均0；期末权益、收益、回撤、Sharpe、交易数、胜率、滑点均N/A，新增回测结果0、修改/删除历史结果0。

调研沿134已冻结的期限研究、LEAN合约筛选及随机政策归因思路；本次是工程落实，没有重复联网或新经济假说。开始/结束按收益调参：否；同史择题风险：是。继续有限条件排序归因有价值，可回答AI是否超过同正分池简单排序；它不能证明全部动作扩张或稳定新策略优势，更不能把最优随机seed变成alpha。下一步由root绑定135完成产物并授权一次actual，之后137仅审新增选择/84账本/比较，复用最终132与102纯检查，不重审旧6模型/标签/B4。
