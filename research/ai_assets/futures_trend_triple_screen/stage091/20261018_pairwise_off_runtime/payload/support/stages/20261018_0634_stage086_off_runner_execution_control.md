# Stage086：完整OFF入口接线实施控制与root裁定

- line_id：`futures_trend_triple_screen`；2026-10-18 06:34 CST；root。
- 前轮分类：**progress**。已真实冻结190包/44614键，081数据资格、078隔离及079中性快照有限独立通过；74项复现资产登记并本地提交`e59055face49e2eda17bfcdd11d834905b987c42`。不是状态复述或未执行计划。
- 当前沿`codex/ai-training-data-expansion`，无worktree。已实际读取Git HEAD/status及registry，用户其他线/registry脏改保留，index空。原B exit1不重启；本轮尚无金融账户或provider启动。
- 目标保持全2020-01-01—2026-10-14、150000本金、扣原成本收益更高且最大回撤更低，随后PIT/成本/固定多起点/弱段验证。没有达标候选，不缩小成功定义。

## 调研判断

继续核对[Backtrader原始执行说明](https://www.backtrader.com/docu/order-creation-execution/order-creation-execution/)与[LEAN原始fill源码](https://github.com/QuantConnect/Lean/blob/master/Common/Orders/Fills/EquityFillModel.cs)：信号时已经完成的数据不能事后用其收盘成交，Stop遇不利开盘跳空按实际开盘而非原stop价格成交。这支持保留035的u已知T定量、固定q与真实D成交风险披露；不据开源机制宣称中国期货alpha，也不引入另一引擎或改原冻结规则。

## 当前分工

1. `pairwise_off_policy_impl`：执行062 Task4，新增`tools/stage065_run_pairwise_off.py`并仅在原三具名集成测试内扩dispatch子场景；唯一Stage084。复用已审政策/快照/061/071，不修改它们，不启动全历史preflight/金融/网络。交付后root安排独立接合复核。
2. `ordered_execution_review`：唯一Stage085只读审原044/048/052/037/041的数据响应通路新owner接线，给最小wrapper绑定清单，不实施/取数/改旧字节。与084无共享编辑文件。
3. root：统一裁定真实API/owner、审查边界、后续最小wrapper、金融readiness与实际工具终态。不存在金融工具等待句柄，不用旧journal冒称活跃任务。

## root routine rulings

- 新owner输出根固定`LINE/'outputs/stage065_pairwise_off_account'`，恰`A_OFF/`和`B_OFF/`、各attempt1，无自由`--output`/重试参数。此项明确替代062最初示意的`outputs/stage065_pairwise_off/`，只是研究目录命名；不改旧062/083字节、策略或经济参数。纯导出只恢复这个owner的合法seal。
- 061/071/Task3的真实接口和固定manifest/review沿083。新runner source bindings须包含自身、061、071及冻结旧依赖；数据与代码审查资格分别绑定，不能拿077代码receipt代081数据资格。
- `new_run_context`自行写context/preflight/source快照；runner不要重复写。A原native、ordered=None；B原035/028内部B_TS producer身份保留，账户owner为B_OFF。
- FULL参数在正式live overrides完全合入后仅允许共同八项OFF投影。直接原847 `_run_profile`，不调用会重启旧True的`_run_live_c9`；旧model smoke禁用，月AI池仍保留。
- 完整金融前实际计算原资本/参数/日期/设置/source/minute门，fixture_only=False、真实1641日reference；不能复制单日fixture布尔值。原1800/7200限额明确沿用，不因旧非timeout失败延长。
- 统一来源隔离在061之外，061先等值合并。完成值proof只来自已审016、已审061、原两个真实完成anchor；该proof不自动授予full交易权。原021七值门不修改，未来新请求仍真实独立资格，不继承失败末包191的已commit权利。
- exporter走stdlib先分支、冻结数值runtime，仅合法sealed account导出。不得进入data/DB/minute/engine/model prepare。原账户返回立即raw落盘，实际语义门后seal；未返回只有failure_capture，不称完整账本。
- 本轮完成真实接线后仅验证新增三个具名tests和必要源绑定/有限反例，不重扫旧suite、全市场真值或为原始审查证据尾空格修复。遇真实影响数据/资金/生命周期的缺陷才修。

## 当前结果、风险与反思

新增/修改/删除策略参数与金融结果均0；权益、收益、最大回撤、Sharpe、滑点、交易次数、胜率N/A。累计仍8次金融attempt/3个完整验账，模型训练0。原A0/C0/C_TS账本和057/058历史模型PIT限制保留，A_OFF相对胜出不自动达到绝对原目标。production_qualified=false，无推送、部署、CTP或委托。

开始新增过拟合判断：**否**，当前修接线/来源与时间一致性，不依据收益选参数；既有选择偏差仍存在。继续价值：**是**，这些是取得公平完整对照的最后必要接合；工程通过不能冒称策略优势，下一步应推进实测而非扩大审计。本文件先记录实施开始事实，实际交付/终态另续stage。

## 2026-10-18 06:50 CST：084交付与非阻塞问题裁定

084已交付固定两臂runner，最终源码SHA `d83b4cc20c09e07e9bcecfd541ba223fbf602db194430e6ed307a80e5e25ed09`，扩test SHA `ffba7e347075cc966a71f3177e5f853eb4ea13062963ff74b2b37f93639d0719`。独立089已在该最终版本上真实单次运行三个具名测试，exit0、0.669秒；截至审者本次完整问题消息，剩余P0/P1=0/0，正式receipt正在落盘，本文不替代它。

root接受一项非阻塞P2，不为此修改冻结runner或重跑：若引擎在calculate_result前异常，失败capture没有纳入shared collector已收集的actual_trade_identities，A的ordered=None可能使这类失败缺少部分fill身份取证。失败仍无完整成功seal/绩效，不能用残余文件计算或声称完整收益；成功raw/导出路径不受此项影响。用户已要求只修影响整体正确性的问题，本轮不扩展失败取证格式。

087统一数据scope仍在原三项测试内收尾，尚未独立接受；无真实owner、provider、金融、preflight或训练启动。研究目标及原限额不变，下一步仅为087交付后的有限独立复核和真实两臂准备。

### 06:55 CST 后续实证

089正式receipt已落盘，SHA `55b72c489dfcc282aaa4c3122e2e9d74215fa243d1242265461d6a5c887015ab`；中文记录为 `20261018_0650_stage089_off_runner_independent_review.md`。上述P0/P1=0及P2裁定正式保留，未追加修复或重跑。

087实现已冻结：scope `7c65bb01147a687529e27901d82b74ff4284a4dc1c84be2c7fe22e8f3aa5d737`/49864 bytes；provider `d8ecebf5b27ebb4179f81f7b960165a14ddbe9ce8655837bbf58ff1ecbf4706f`/16482 bytes；test `629f81cb4ce3880e96f52756f8fd33c62e7f104b18803356d33b92d89fbe8e2f`/24721 bytes，root已实测三身份。实现receipt `59fdd0fe6346cd7c1b057c37d537af73e8986db2371db0cc8e93f8f5c4da83f2` 明确不是独立接受。

原三具名测试在作者修正真实main必要接合期间共5轮/15方法执行，均属单位/接合fixture，金融和网络0；每轮变更在087的execution_history.json保留，没有冒称15次账户回测。root已要求停止非阻塞修补和全组三测循环，作者确认最终冻结。090改由非087作者一次有限独立复核；纯文档补齐不阻塞按已验证三SHA开始审查，不因此重复验证。真实preflight和金融须等090实际接受。

### 07:00 CST：090真实反例与唯一修复波次

090正式receipt SHA `91ea83235b9cbc6f2c13240fbc31d3a97a64e145b2de17aa39227fd723a774da`，P0/P1/P2=0/2/0，状态不接受。三具名tests独立fresh一次exit0、0.600秒不能覆盖下列已实证问题：

1. owner分别hash了context/preflight/readiness，却未将它们的内部readiness身份、实际argv及原始started_at相互绑定。严格非fixture校验分支的临时反例中，已运行3小时context被owner新时钟和另一B_OFF dummy readiness包裹仍接受，报约1800秒余量；真实context 7200秒余量已为−3600秒。
2. driver有余量门，公开provider parent的run_once没有；fake child反例在余量0时仍启动一个假worker，剩余预算检查调用0。没有真实网络、provider或金融启动。

原始探查脚本/真实输出/evidence均保留在090输出，不为落盘重复执行。root只授权原087作者Stage093一波必要修复，先保存原三源字节；随后同一独立审者Stage094只复核这两项和直接改动的边界，不重跑旧suite或整组三测。非阻塞取证P2不在修复范围。090不改写成通过，任何新的完整preflight、owner、金融授权仍须等待真实修复接受。

root只读确认原失败191的旧052真实receipt路径/SHA仍为 `274190b95b9c1ff18cdee2743730ddec0a89b6ad4f035e108f69f269701327bf`，来源闭包30文件/25,236,449 bytes；它只能进入未来owner明确白名单后按新真实R重资格，不能取得061继承commit权。没有读取原始行情数值、重审旧190包或扩大数据资格。

### 094闭环：接合可进入真实准备

093一波必要修复已冻结：scope `5919f098af14ea9819cee3445e2555f9a740ebc2c808af1afdafa508235d01fb`/52670 bytes，provider `33b6bca67115e3c8438de768b6e180d055139470fa2b7069b7a4459b1d101b46`/16901 bytes，test `17863dd4ec07ee43128c9ef606cb131fc07fd9fae79df2c917680062dd29dd6a`/35924 bytes，root已实测。旧087三源/16对象及090失败/原反例字节保留；093只运行两个新增回归RED和GREEN各一次，没有重跑原三测。

094独立receipt SHA `48bc517989da434e22db70fbb7d603ff09c7f52581f67c868cb0ca736aae2684`，P0/P1/P2=0/0/0，恰绑定这两新源SHA+bytes。新增两回归独立一次exit0、0.030秒；补充只用fake验证0/839拒绝、恰840可启动、SDK后余量跌至839或current改变不启动、launch后不以840再次杀合法worker。原context时钟约−3600仍不能重置，readiness/context/preflight/argv负例拒绝。094只关闭090两P1并继承其他已述有限验证；090保持原失败，089非阻塞P2仍保留。

root接受上述有限接合，下一步登记源码/失败/修复/独立复核复现资产并保存本地Git检查点，再真实prepare两臂；当前尚未签金融readiness、创建真实owner、启动provider或账户。095另由非065/084账户作者准备薄会计审计适配，不自审其071/087来源资格；实际每臂审计仍须真实工具终态及raw/export路径SHA齐。没有改变alpha、八项OFF、成本或限额，模型训练0，目标尚未达成。
