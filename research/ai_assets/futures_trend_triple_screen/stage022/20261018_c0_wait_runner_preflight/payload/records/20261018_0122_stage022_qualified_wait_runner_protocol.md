# Stage022：C0 attempt3 已签数据栈与同引擎按需等待

- 时间：2026-10-18 01:22 CST；line_id=futures_trend_triple_screen。
- 本阶段只实现、测试和保存来源diff；020/021独立review未齐不得完整preflight，不启动真实金融或网络。root统一决定唯一账户执行时点，目标仍为2020-01-01—2026-10-14的完整同一C0候选，不将数据准备当终点。
- 原001 runner逐字节另存为outputs/stage022_qualified_wait/source_stage001_original.py，SHA `928df4baae38548ba54126efc157d04174cec1bbe641cdb5e7be38cfd26969d4`；新runner独立复制，保留可审查diff。旧001、正式四源码SHA、原C0周门/unknown fallback、正式AI池、参数/实际settings、成本/滑点/资金、模型字节/冻结runtime smoke均不变。

## 最小数据接合

1. stdlib阶段只读取manifest、配置和SHA；仍先configure_runtime再导入pandas/numpy及数据工具，禁止本地数值库抢先导入。四源码、AI/weekly/model及参数实际值门原样保留。
2. 数据栈固定：原base → 已签002 → 已签011 → 已签015 → 已签020的append-only键 → 最外层016四完整session修正。每个summary/overlay/input_manifest/独立receipt/工具协议和相关实际源SHA加入recorder.extra；所有读取在结束verify。原数据不写，不以ready总数声称全局价格重新认证。
3. 021门安装到真实Stage847继承的_stage827_order_context；Stage502已安装当前batch datetime/bars，此时数据不足则在原context调用处等待：OPEN须完整session且full资格；普通CLOSE须真实canonical首分钟且anchor资格。原context资格通过后只调用一次，成交、strategy.update_trade、847扫描/retry、on_bars和dailyclose均在门后；不重放bar、不skip、不重启原engine、不先成交再验证。
4. 既有资格分用途：full_existing=当前冻结栈真实键减残余minute_source=stage859_tqsdk_backtest，再加016完整1500scope；anchor_existing=full_existing加Stage010 requirement_kind=anchor对应实际存在canonical首键。两集合独立传入021，anchor-only键绝不借给OPEN full；FG209旧冲突只保留已接受首open的anchor用途，不改其余旧值。不因source246名称推断未完成。该承诺是继承已接受基准＋用途受限859，不是全表逐价新认证。

## 文件等待合同

- 021 resolver(request)->QualifiedDelivery(receipt_path,receipt_sha256)，request自身按021 canonical规则带request_sha256与当前订单批量requirements。本runner原子写C0_attempt3/data_wait/request_<request_sha>/request.json；同时原子保存request_fingerprint.json（request_sha256/request_file_sha256/绝对request_path）并立即发布waiting audit，供023核磁盘身份；外部完成真实补数与独立review后原子写同目录response.json：schema=stage022_delivery_pointer_v1、request_sha256、绝对receipt_path、receipt_sha256。
- 独立receipt须schema=stage021_independent_minute_delivery_v1、independent_review=true、qualified_research_data=true、reviewer非空、P0/P1=0、原request_sha256、绝对data_path与data_sha256及source_fingerprints绑定；accepted_requirements须精确scope。021核合法7字段、完成/日线资格声明、哈希和已有键七字段完全相等，仅append真正缺键，不覆盖/删除。真实完成/原CSV7/独立review由外部数据包提供，runner不自签、不自动连接或下载。
- 每次等待1800秒、全运行7200秒，超时严格失败并保留request；不自动重试金融。resolver返回前逐文件验证SHA并显式record，再交021读入；未签、错scope、变更旧值、错误数据SHA一律失败。新的资格输入纳入最终input_manifest和等待审计。
- reserve后回放前保存新runner真实字节runner_used.py、原001来源SHA/source_diff及固定data_stack_manifest；provenance.source_adapter_sha256绑定真实新runner副本，明确数据适配层改变、alpha仍原C0。独立失败记录链必须保留C0 attempt1/2，不伪装attempt2或覆盖旧产物。

## 验证与反思

- 必要纯控制测试：正常已签指针在交付前hash/record，错request拒绝、1800秒超时保留、相同hash请求内容改变拒绝；另检查继承alpha/helpers未变和full/anchor的859隔离。配合021有限合成测试，不创建真实账户。
- 沿用已核Elder与官方TqSDK来源，不新增网络调研；[TqSDK官方API](https://doc.shinnytech.com/tqsdk/latest/reference/tqsdk.api.html)只说明数据接口，不证明候选alpha。旧失败、经典方法及历史收益均不用于选择本次数据适配参数。
- 是否过拟合：否，本阶段仅固定数据身份与严格等待，没有按候选收益改参；原候选的历史选择风险保留。是否有价值：是，避免对8075个overapprox需求无差别预补以及逐缺口重启账户，直接服务一次完整候选检验。
- 新增alpha参数/修改/删除参数：无；数据等待上限仅工程资源门。期末权益、总收益、最大回撤、Sharpe、总滑点、总交易次数、胜率全部N/A；实际金融attempt计数不增加。未授权生产、正式发布或网络。
