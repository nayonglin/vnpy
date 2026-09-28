# Stage025-027 早期来源追溯及原生合约链获取

- line_id：futures_trend_xgboost_history_compatible_root_utility。
- 记录时间：2026-09-06 06:46 CST。
- 工作区/分支：/Users/bytedance/Desktop/person/vnpy / codex/stage130-option-probe。
- 性质：数据来源资格与重建，不是重要突破；无新策略回测，不触发候选A/B或reviewer。
- 前一目标轮分类：仅确认评审门槛，没有新增研究证据，属无进展。本轮恢复已有Stage025证据后完成新目录与行情获取，为实质进展。目标未达到，不缩短区间或修改成功标准。

## 外部调研与判断

- 官方GitHub：https://github.com/shinnytech/tqsdk-python/blob/master/tqsdk/api.py 。本地TqSdk 3.9.4的api.py第280/550/3590-3605行确认现代合约服务对早期合约使用expired_quotes.json.lzma；第664-665行明确open_oi/close_oi分别为K线起始/结束持仓量。公开最新文档为不同版本，不声称本地与master字节相同。
- Tushare官方HTTP和合约字段：https://tushare.pro/document/1?doc_id=130 、https://tushare.pro/document/2?doc_id=135 。此前Stage025只向官方HTTPS端点发一次fut_basic请求，HTTP200但API40101，消息“您的token不对，请确认。”；没有重试、换凭证、降级HTTP或绕过限制。
- 判断：合约目录失败不能等同于历史行情不存在；原生接口与SDK本地历史缓存提供了合法的新来源证据。只修来源，不复活已失败的模型参数或旧静态OI占比/HHI阈值。

## Stage025 早期源探针复核

- 实际执行06:21:52-06:21:57，事前合同为stages/20260906_0621_stage025_early_source_probe_contract.md。该执行早于本次目标继续消息，本轮没有重发请求，只复核冻结产物。
- SHFE.rb2005原生日线在2020-05-15完成后复制；2019-11-01至2020-05-15共130天。日期集、OHLC、成交量与旧库130/130精确一致。
- 旧库open_interest与Tq open_oi为130/130精确一致；与close_oi仅1/130相同，最大差152,304。此证据仅证明该合约的字段含义和数据内容匹配，不证明所有旧库导入链条相同。
- 本轮用标准库CSV/Decimal另算法复算一致。9输入、6输出身份通过；summary SHA：5476101f4da1d718600de92855f8011f55e25fbcdacf82a35d031c43ebb73fea。
- 保留原Tushare失败body、错误和来源脚本身份；原A和生产数据库不改。

## Stage026 目录补充

- 06:28事前合同；06:30:36-06:30:37唯一离线生成。新增tools/stage026_sdk_cache_catalog.py和18项测试，测试先缺实现失败、后18通过。
- SDK缓存14,246记录中，非FUTURE 11,758、其他品种1,900、起点之前457；相关完整早期链131合约。与Stage024重叠6条十项字段均相同，实际新增125，联合目录1,325。
- 原189个实际合约和276事件全部通过品种/到期关系检查，原13缺失均补回。不是只把回测选中的13个合约塞回目录。
- 标准库LZMA/JSON/CSV/Decimal与时区日期另算法复算131投影、1325并集及276事件，精确一致。10输入、6输出身份通过。
- summary SHA：71ac2c4ce8ea527fd51f60b940d789c78ec5ca7afca286428e95dc32a55918db；catalog SHA：bb6b7fd68228a5074328e3cc8a2001e4e4c1b0bba86632a7158d9b9d0cb4679c。
- Stage024原失败记录不追改；新缓存来源资格不证明历史发布版本或当日上市集合。

## Stage027 原生日线获取

- 06:33事前合同；新增tools/stage027_native_chain_source.py及18项测试，先RED后GREEN。新增固定获取参数：asof=2026-08-28、duration_seconds=86400、data_length=10000、首13探针后按符号每40个一批、每批300秒超时、不自动重试。没有新增/修改/删除策略参数。
- 实际06:36:19-06:44:10完成34/34批，1,325/1,325合约、272,649有效日线，空合约0、失败批次0。首13在统一截止日下均非空，才允许后续扩批。
- 每批全部订阅、推进BacktestFinished后深拷贝。原始id/datetime/OHLC/volume/open_oi/close_oi全部保留；仅明确排除初始化空槽和起点之前的真实历史。范围内坏行、重复日、到期/截止之后记录不能静默剔除。
- 每合约独立原始和规范化gzip，34份批次回执；输入9项，输出2,687项。summary SHA：1cc361ac370fa3d300eaa86d51ac9f151d063b0c7668242e426d7067192969c4。
- 06:45:52标准库CSV/Decimal/时区另算法复核13,250,000原始槽位、全部1325合约的日期集、逐字段数值、空槽/起点前排除计数、272649有效行及输入输出SHA，全部一致。首批rb2005的130行与Stage025所有共同原生字段精确相同。
- 复核回执：artifacts/stage027_independent_verification/summary.json。采集状态仍为acquired_pending_chain_qualification，full_chain_qualified=false，historical_vintage_proven=false。
- “全部合约非空”不等于每交易日全链完整，不证明上市日、历史修订版本或严格决策前可用性。此处不生成持仓迁移特征。

## 结果与验证边界

- 全套相关测试：340 passed in 31.59s。新代码/数据功能检查由本任务完成；独立reviewer为0。
- 新标签读取/生成、历史fit/predict、策略回测、真实订单、CTP、生产写入均0；TqSim只是SDK行情历史容器，没有委托。
- 新期末权益、总收益、最大回撤、Sharpe、总滑点、总交易次数和胜率：均不适用，本轮无新回测；Stage009/016失败绩效与原A不变。
- 生产目录本轮已复查，HEAD仍d492ee072aa5a9d71477235d79f17d2a5db59db3且干净；本轮无commit/push。源DB在Stage025输入复核时仍为冻结SHA a683e8d99c1925ef2af546e62b61f62c9946d21ea4e5be4af42737a80f77eef5。
- 采集、独立复核和测试进程均正常退出，无尚在执行的本轮任务。

## 下一步与反思

1. 先做新源逐交易日/合约生命周期/完整A日历与276事件的严格前一完成日覆盖资格，不按PnL选样，不把未上市历史填零。不修改旧A的OI字段口径。
2. 来源通过后才预声明实际合约的换月持仓迁移速度表达，明确与旧静态占比/HHI/期限结构失败形状的区别，再进入唯一固定模型和完整C验证；不据源成功直接宣称有效。
3. Stage009/016、会员来源、固定误差余量、朴素扩样等既有停止结论保留；不扫参数、窗口、品种和年份救援。
4. 运行前后过拟合判断：本轮否，未读新源与收益关系、未按收益调参；整体长期历史研究的选择偏差仍存在，不能称为未见样本。
5. 运行前后继续价值判断：是。真实补齐早期目录及原生close_oi，为不同信息表达提供必要条件；仍无模型价值证据，完整收益提升且回撤下降的目标未达到。
6. 只更新本线LINE.md；不改其他线、registry、根总账或生产。reviewer仅在有价值候选同时满足全周期双目标和基础稳健性门后启动。
