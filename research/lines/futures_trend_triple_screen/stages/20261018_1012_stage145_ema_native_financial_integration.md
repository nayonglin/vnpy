# Stage145：固定EMA真实账户接合实施账本（进行中）

line_id=futures_trend_triple_screen；2026-10-18 10:12 CST开始。执行140（root144采纳），按TDD与executing-plans有界实施。只拥有checkpoint/runner/independent-review与本文件三组合测试四源；146作者独占wait及其一方法。仅本中文145与outputs145，不改LINE/registry/Git/旧源，不派子agent。

开始已读registry、140、144、实际142manifest，以及127、031、065、095/106接口；调研沿121/123/138原来源，不新外搜。固定EMA primary、150000、2020-01-01..2026-10-14、原月AI10非fu+fu、OFF八键、原recipe/退出/0.5R/retry、原1800/7200/840/570/600/4全部保留。真实金融累计11attempt/4accepted，本实施新增真实金融/模型/provider/network=0；不实际prepare、不发readiness。

## 接缝裁决与进度

- 先落三个组合方法契约RED，真实chunk d7e174/exit1，三新模块缺实现；这是类型骨架前置RED，不冒称完整行为测试已通过。BoundAsset/EmaRun已以stdlib-only骨架落盘，同146共享唯一类型源。
- 接口约定：新context/preflight/readiness schema均stage140_ema前缀；context在run.output/run_context.json，preflight复制在preflight_used.json，固定account_id=EMA_LIMIT/mechanism_id=stage124_ema_limit_v1/attempt1。source/data绑定为ABS→{sha256,bytes}；readiness另绑实际integration review与root当时global_attempt。真实CLI --run --preflight ABS --preflight-sha256 SHA --readiness ABS --readiness-sha256 SHA --global-attempt N；export-only先dispatch。
- fixture须显式fixture_only=true，issued_by=fixture_only/fixture_execution_authorized=true/financial_execution_authorized=false，不造root真实金融资格。公开真实CLI和146真实owner/provider入口拒fixture。
- Ruling：start_run输入为Mapping，故preflight复制及root readiness的preflight SHA统一采用checkpoint.json_bytes的canonical序列化；以此消除同对象不同缩进产生的文件身份歧义，成本是root实际preflight须使用该已明示序列化器。
- checkpoint复用原065 `_account_only`无身份数学/递归guard，另建140身份/raw/seal/export合同；不调用其旧_owned/_context/金融入口。capture与独立会计算法尚在接合，不把骨架作为ready。

## 当前限制与反思

此账本随真实测试和接合进度追加；现无完整GREEN或新账户结果。权益/收益/DD/Sharpe/滑点/交易数/胜率N/A。新增过拟合：否，规则在EMA收益未知时已固定；继续价值：是，有限接合能取得未来真实可验账证据，基础设施通过不等于alpha或目标完成。最终只做三方法加146一方法的组合GREEN/compile及root一次整体独审，禁止循环micro-review。


## 2026-10-18 10:31：候选接合、有限测试与一次统一GREEN收口

三新生产源与一个三方法测试已实现；146两源已冻结后参与统一运行，未改动其源码。当前交给root/148一次整体独立审查，**不是金融ready或完整实现资格收据**，尚有下述计划覆盖边界待该整体审查统一裁定。

### 已实施接缝

- `stage140_ema_checkpoint.py`保持stdlib导入；类型、root readiness与独立身份、绑定文件读取、account-only递归guard、新140 raw/manifest/seal、错误捕获、同raw纯导出与export-only最先dispatch均独立于旧B身份。等值源绑定与原065无身份递归guard/原031 clock/原650 metrics按函数级复用，没有调用旧prepare/main、旧_owned或旧金融审查CLI。
- `stage140_run_ema_account.py`提供142实际schema的薄标量reader（真实refs/qualified keys/严格bool/有限数值/唯一u-contract/下一真实D/不可交易末日未知值），没有重建EMA/FI/weekly。prepare代码只使用原数值runtime、metadata/正式参数/月池/OFF政策和真实已接受数据；按002/016→两anchor→旧190→071→新159的物理顺序安装loader，再两次compose精确资格，completed_keys不借159提前救坏859。**actual prepare没有执行**。
- 新127类的真实add_strategy返回即设置strategy.ema_limit_run_id，任何bar前核新身份；扩展capture保留EMA decision/fill/execution/final budget/scalar pending及实际TradeData mechanism/economic_mother字段。真实run返回先raw，再校完整settings/参数/1641日/分钟/源/空shared后seal；provider不会从账户CLI启动。
- `stage140_independent_ema_review.py`先核新root真实exit0/context/raw/seal/summary；实际data_runtime/data_scope全部JSON侧证在未来completion.data_tool_bindings签入，零未来hash预造。原独立030/033/095 source SHA原样验证，用冻结AST读取原成本/现金/权益计算语句，复用库存/metrics/母链函数；仅将CONDITIONAL在独立namespace绑定真实127 source，不改价格标签、不复制重写PnL。新EMA evidence核fill/native逐值、quantity、母ID、tick/penetration/V、gap负R为N/A且无retry、合法retry原母链、gross不回填prefix。

### 真实有限命令与终态

| 阶段 | 实际tool | exit | 覆盖/结果 |
| --- | --- | ---: | --- |
| 类型契约RED | d7e174 | 1 | 三新源缺失；仅契约前置RED |
| 完整接合初查 | e32eaa/13578→3d5c0b | 1 | fixture临时路径经过macOS /var symlink、测试传set给原031 callable API；失败全保留 |
| fixture API修正后 | 95128e/87433→81f1ed | 1 | layer组合已过；真实021 gate拒fixture minute缺vt_symbol |
| native方法GREEN | 898869/1124→35ef17 | 0 | 一个方法，18.356秒，genuine127/native及同raw恢复 |
| 独立账本方法GREEN | f3fa6d/95711→9b3c06 | 0 | 一个方法，18.690秒，原账本及六类篡改反例 |
| **唯一四方法整体GREEN＋六源compile** | **33b042/59677→78e21a** | **0** | **4 tests、20.267秒、0 failure/error；compile六源一次** |

例行修正只把fixture路径resolve、按照原031 callable接口传值、给真实021 minute补上真实合约列；未放宽旧guard或runtime。测试中的非法validation被拒、故意export失败被保留，是测试内预声明反例，不计为新真实账户。Matplotlib font-cache信息写在测试自己的临时runtime目录；TqSdk模块import仅输出免责声明，没有实例化网络API或读取凭证。

统一命令：`.py311/bin/python research/lines/futures_trend_triple_screen/outputs/stage145_ema_native_financial_integration/run_final_combination.py`。该命令只discover `test_stage140_ema*.py`，先断言恰为4个新方法，然后六源各compile一次；旧127/131六方法、旧190数据suite与任何旧suite均未执行。146输出常量仅在测试进程重定向到145/combined_wait_evidence，未覆盖146已闭合的命令及sidecar证据，也未改146源码。

### 同一个微型native账户的实际证据

统一测试进程只有一台fixture native engine，run `ab83889cb4c240e4862210698b9efa1a`，显式fixture_only=true；fixture global_attempt=12仅用于类型/身份反例，**不增加真实金融总账**。

- AP605：真实native四次fill价格100→98→103→98，合法retry103可越初始L=100且同economic mother。
- au2606：错侧gap初开90，真实即时保护88；同母两fill，两次原native成本，actual R为N/A，无retry。
- rb2605：预挂q=3而V不足，DAY未成，预算未回填；cu2606初开后经原_handle_rollover/原ordinary native订单路径换至cu2607，原独立母链确认roll连接。
- 共9次真实TradeData，最终native settled cash `149499.68999999997`，原native trade_costs_total `230.31`；它们只是手工微型市场fixture的经济证据，不是策略回测绩效或新收益结论。
- 先故意错误validation拒seal，再正确fixture validation封同一个raw；故意export001失败后，export002从同一sealed raw恢复，prepare/native入口/joblib.load均被毒化而没有触发。raw SHA始终`71587d488bb59906524bbcace976d8161341f9292540f768880dc6cb62380919`（18420 bytes），native engine仍一台。
- 独立组合从同一raw做原现金、库存、逐fill成本、每日权益、开放MTM、retry/普通roll母链；成本、库存、mother、执行价、未知方向类型、非法正R六类篡改在各自匹配的fixture CSV之后仍拒绝，未借hash不符替代算术/语义检查。

真实raw与导出持续保存在outputs145/fixture_native_k0qmpmbl/EMA_LIMIT/ab83889cb4c240e4862210698b9efa1a/。`final_native_evidence.json`绑定该raw、同母实际TradeData、EMA审计、cash/cost与失败及恢复路径，SHA `3475e24fe5f86381497aa62ae45d8d91fbcef8bf0aa47ad7132f174480e7b6d2`。

### 冻结源码与证据

六源最终SHA在`final_combined_command.json`完整列出：checkpoint `d01d4e2d5d26eb456a09f241f4c6dfccd28818c66d968c6c2792b77a57a0776c`；runner `7e69b7378ba3606ae89535a375f9a47dd254d82660d168b859ac2226364701a7`；独审adapter `c0501a933372856765937999da06635e98d839fc5001d51eadc4baa2bd3146c9`；三方法test `c58c7c05fc2d6ec191b8990208b10ab86eb801e55793aaf6d1fa534e190c9dfd`。146 wait/test仍为`c313e92058e516f089951bdbde3ba8a0a0fa00f0025911e72de9ac536dc39e8b`和`c207f3c2b6f8281dbda6667cbe4c8bc8050f8dd0adb30f081d90b4f33a2ea0ef`。

- final_combined_command.json SHA `b560ed630ea5a8736c189dd02ebe4c0a8433c4e835b63a557867290a9bb4ab66`。
- final_combined.log SHA `99f2a7beabaf0ded478ad1316daafa8a8af24e412895bed861153388a7bc1fa6`。
- combined_wait_evidence/finite_test_evidence.json SHA `91a040e7ce143777e50fe9883983dd032fdaca9ae0702c43ed313f001d907f68`。
- actual_tool_terminals.json保留上述全部真实终态；不是伪造的P0/P1收据，作者没有签独立资格。

### 必须如实交整体独审的未覆盖项

1. 按root禁止，actual142 reader/full prepare/真实1641日账户、provider网络与实际owner签发均未执行；不能以fixture GREEN表示这些真实输入闭包已运行通过。
2. 已识别计划覆盖差异：start_run目前保存源SHA闭包，**尚未复制源码快照**。这是140要求的缺项，已向root/148明确交接，不隐去、不自动宣称完整实现。
3. EMA独审已核上述实际价格/q/母链/volume/gap与gross prefix，但**尚未逐项重算全部预测/实际risk-margin差与最终q各上界**。该部分由148一次整体审查统一裁定/一轮修复，不趁审查反复微改冻结源。
4. 完整盘口排队/部分成交、每历史minute volume单位的独立证明、分钟PIT保证金峰值仍无；继承143/144研究假设及原已知零佣金/日收盘保证金限制，没有因fixture通过取消这些边界。

新增/修改/删除策略参数=0；新增完整回测结果=0，修改/删除旧结果=0；真实金融仍11attempt/4accepted，训练0，本次actual prepare、金融、provider、network、模型load/fit均0。真实期末权益、总收益、DD、Sharpe、滑点、交易数与胜率N/A。

开始/结束新增过拟合：否，规则和失败处理在收益未知时固定；多重研究选择风险仍在。继续价值：是，已取得实际接合反例和同raw恢复证据；下一步仅一次整体独审与必要集中修复，不是重复全市场回测或新参数扫描。当前阶段暂停实施供root审查，非目标暂停、非生产或金融ready。
