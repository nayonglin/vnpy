# Stage058：当前真实交易合约自身的已完成周K

- 时间：2026-10-19 20:09 CST。
- line_id：`futures_trend_full_market_noai_one_lot`。
- 工作树：`/Users/mac/.codex/worktrees/full-market-noai-one-lot/fian`；分支：`codex/full-market-noai-one-lot`。
- 类型：用户更正价格序列口径后的独立新实现与合成验证，不是重要突破；本阶段不运行新金融回测，不下载数据。
- 本阶段仅新增 `tools/stage058_weekly_contract.py`、`tools/test_stage058_weekly_contract.py` 与本唯一 stage；不改050/051/052、LINE、registry、旧金融源和输出、版本快照或Git状态。

## 用户口径与接口

多头门槛仍是固定严格 `周MA5 > MA10 > MA20 > MA40`，本次更正为**当前实际交易合约自身的已完成周K**。禁止用主力连续、同品种旧合约或其他近月补足40周。空头不加本条件，具体策略接入由059/060负责。

新增独立 `WeeklyContractTrend(market,contracts,calendar)`，不导入旧050模块。market要求 `date/vt_symbol/close/volume`；contracts直接接受已有contract_metadata.csv DataFrame，要求 `vt_symbol/product_vt_symbol`，`listed_date`可选。产品身份取精确合约元数据，查询只接受字符串vt_symbol，不解析品种名去借其他合约。

`lookup(vt_symbol,asof,phase='signal_close'|'open')` 返回JSON-safe plain dict，包含 `product_vt_symbol/contract_vt_symbol/week_last_session/close/volume/valid/ma5/ma10/ma20/ma40/history_weeks/valid_weeks/allowed/reason/evidence_id/asof_date/phase/export_scope`。其中signal_close只用末会话日<=查询日的完成周，open严格用<查询日的完成周。40周不足、窗口NaN或相邻均线相等均拒绝。

周末会话先从完整独立calendar求出，再按**单合约**上市日（缺上市元数据时用该合约最早行情日）至末次行情所在自然周限制；不制造上市前history，不按周中source截断判周末。每次首次查询才建立该精确合约缓存，构造器不生成4328合约×2014—2026全局笛卡尔周网格。整周无交易会话不建周bar。只需该合约真实末会话收盘，不要求该周所有日OHLC齐备。

只接受exact contract的accepted-clean正close/正volume；execution_only列若存在只接受明确布尔False，显式execution-only/expiry-only quote_class及明确禁止新开的报价拒绝。列缺失仅表示调用者已传入纯clean原始源，不把过期退出报价重新认证为训练数据。缺价和坏周保留NaN、不drop、不fill、不以其他合约代替。合约内部未复权价格照实使用，其他合约换月价格跳空完全不影响本合约。

额外fail-closed：若查询相位下，独立calendar上最新应完成周已经超过该合约本地最后一周，返回 `allowed=False/reason='missing_latest_completed_contract_week'`；不会继续沿用老周的allowed=True，也无需为所有已过期合约无限延长周表。该不可用快照的week_last_session标明应有却缺失的完成周，close/MA为None、history/valid计数为0（不可用快照标记，非更改原本地周表）；原有效历史仍保留在weekly中。

## 导出范围

`weekly`属性仅导出**实际查询过合约的完整本地周表**，不是全元数据合约全集。`export_scope='queried_contracts_complete_local_weeks'` 同时提供属性、CSV列及DataFrame attrs；`queried_contracts`提供排序后的实际查询符号清单。未知或完全无行情合约不制造周行，可由查询清单和拒绝快照证明已评估。清单不等于所有合约都有可用40周。

## 调研与判断

重新查阅 [pandas官方resample文档](https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.resample.html) 和 [backtesting.py官方仓库多周期工具](https://github.com/kernc/backtesting.py/blob/master/backtesting/lib.py)。判断：周期边界/标签应与实际可见时点匹配，但通用resample不会替用户定义“同一真实合约”，也不能证明日历完整；本模块明确锁定exact vt，再以独立交易日历确定已完成周。没有复制这些项目实现，没有增加新依赖。

“合约自身40周”会自然使上市历史短的合约长期不合格；这是用户明确口径的经济含义，不以旧主力回填、降低窗口、增加豁免去救成交或收益。元数据仍是现有vendor snapshot，不能据本模块声称解决历史PIT或生产资格。

## TDD 与验证

先编写16项纯合成行为测试，首次RED共22失败（含subtests），全部指向明确缺失：`exact-contract weekly implementation is missing`。再实现独立最小模块，GREEN：

```text
.py311/bin/python -m unittest discover -s research/lines/futures_trend_full_market_noai_one_lot/tools -p test_stage058_weekly_contract.py -v
Ran 16 tests in 0.651s
OK
```

覆盖：

- 第40周手算均线38/35.5/30.5/20.5、JSON无NaN。
- 同品种两个合约相反趋势分别通过/拒绝；新合约只有3周不能借旧合约补40周。
- 其他合约巨大换月跳空不改变本合约快照或证据hash。
- 周五开盘、周五收盘、周一以及周四假期末会话；整周停市不造bar。
- source周三截断与1900—2050宽calendar仍只建立本合约40个本地周，末周为真实周五invalid。
- 未来本合约价格扰动、增加未来其他合约、历史prefix输入不改变过去查询/evidence_id。
- 缺周保留NaN、不压缩；坏周只有自然滚出40周窗口后才恢复。
- expiry/execution-only、未知execution标记、0量、NaN/负close与缺末会话均fail-closed。
- 任意相邻均线单独等号均不允许；重复价格/合约元数据raise；未知/空/上市前/无行情合约安全拒绝；非法相位及非字符串合约raise。
- 4328额外元数据合约不触发全局周网格；weekly导出scope和查询清单可核验。
- 最新应完成周缺失时，周五open可读前一完成周，周五close/下周一open拒绝复用旧allowed结果。

本线完整 `test_stage*.py` unittest 扩展验证：**206 tests，25.551秒，OK**。既有测试导入仅输出TqSdk免责声明和并行canonical context进度；无测试失败。

源码SHA256：`546f2097b80117be1a0b0c2c29f4a39c380c9313270a6e31056bf29029eee491`。
测试SHA256：`127d47b6bbd4fbb29ed1267750793006678f747249821ee2a9f69d819df27a6b`。
050仍为`b0275cf2feb959161cb8dd1d71822829135b9f07d7fcb0a4228dc736daef7060`，未修改。

## 参数、金融结果与反思

- 新增参数：固定exact-contract周线模式与懒加载导出scope；MA窗口仍5/10/20/40、严格大于，不扫参数。
- 修改参数：本新版本的价格序列由品种因果主力变为当前真实合约自身；旧050实现和结果不改写。
- 删除参数：无。
- 新增/修改/删除金融回测结果：均无。期末权益、收益、最大回撤、Sharpe、总滑点、交易次数和胜率：本阶段均不适用。
- 没有下载行情，没有接触生产、账户、CTP、订单接口；只运行合成合同测试及本线测试套件，不进行金融回放。
- TODO：根任务接入059/060并冻结新源码/manifest；独立检查实际OPEN的product+contract双身份及两相位周线证据，之后由根任务决定授权的新金融运行和审查。
- 开始与结束过拟合判断：**否**，本阶段执行用户固定口径，不按历史收益调整窗口或例外；该假设仍属同样本后验提出，未获得样本外收益证据。
- 开始与结束继续价值判断：**是**，把“交易合约自身周K”落成可审计、可证伪合同有研究价值；不据此推断策略改善或支持正式晋级。
