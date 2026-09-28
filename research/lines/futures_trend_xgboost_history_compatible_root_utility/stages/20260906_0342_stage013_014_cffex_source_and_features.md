# Stage013-014 中金所原始日数据与五项跨资产特征冻结

- line_id：`futures_trend_xgboost_history_compatible_root_utility`
- 当前模式：隔离研究，原始数据资格与无标签特征实现；未训练候选。
- 记录时间：2026-09-06 03:42 CST。
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `codex/stage130-option-probe`。
- 阶段性质：数据与机械验证，不是模型效果验证。
- 是否重要突破：否。解决覆盖条件不等于获得alpha。
- 是否触发A/B：本轮无策略回放；后续真实C必须重新冻结其输入和执行合同。
- reviewer：0。遵循用户最新要求，仅真实全路径C同时提高收益、降低回撤且通过事前基本稳健性门时才启动。

## 外部调研与判断

- [中金所历史数据下载](https://www.cffex.com.cn/lssjxz/)是原始月档案入口。页面工具访问失败不代表月档案不存在。
- [AKShare公开实现](https://github.com/akfamily/akshare/blob/main/akshare/futures/futures_daily_bar.py)的`get_cffex_daily`及本机1.18.55源码使用原站HTTP月ZIP地址，与旧84月成功请求记录一致。本轮不升级依赖，不使用模拟浏览器、认证接口或付费行情。
- 判断：旧CFFEX模型停于表达资格门且没有训练，不证明原始跨资产信息无用；但不能重启旧39特征/月度LR残差表达。新尝试只检验实际根入场是否可从少量跨资产状态获得增量信息。
- 同一发行月份档案是在现在下载的历史快照；严格前一交易日使用只是保守时间假设，不能证明历史发布时间或没有修订。HTTP无TLS认证，SHA仅保证取得后的字节一致性，不能补足传输身份认证或历史版本证据。未来结果仍只属于有这些限制的历史开发验证。

## 变更与时间线

1. 03:17，Stage013先冻结原始ZIP审计、严格过去选约、同合约收益和覆盖合同，再实现与测试。9项新增测试先失败后通过。
2. Stage013复核84份旧ZIP并解析。202606唯一HTTPS请求在443端口失败，`Errno65 No route to host`，HTTP状态为空，没有响应体；7月和8月没有请求。保留`source_not_qualified`结果及请求回执，不覆盖原脚本或失败输出。应用层重试0；异常库的“Max retries exceeded”不是本工具重复请求的证据。
3. 03:25，根据旧成功请求和AKShare实现冻结Stage013B协议修正。新适配器只改变公开地址的HTTP协议和私有输出路径，复用相同解析、选择、收益及覆盖函数，不放松科学门。3项新增测试先失败后通过。
4. 03:27，HTTP的202606、202607、202608各一次请求全部完成，无重试、跳转或绕过。原始响应、URL、状态、头信息、UTC取回时间和SHA保存于本线私有目录。
5. 03:30，另写独立重建逻辑，从原始规范化行情按前日持仓量、成交量、合约排序重新选约，逐条复核10,548条合约选择及同合约收益，全部一致。
6. 03:32，在读取新增特征与标签关系之前冻结Stage014五项特征公式。6项新增测试先失败后通过；只读取事件身份列，不读取目标值。
7. 03:39，Stage014唯一执行完成，冻结118输入、5输出及摘要，状态`features_qualified_no_models`。未启动历史模型拟合、预测、标签或回放。
8. 03:41，全套219项测试通过，独立窗口计算核对所有1,614决策日及276事件，数值误差小于9e-15。生产目录只读检查仍干净，HEAD不变。

## 参数与语义

- 新增脚本：`tools/stage013_cffex_root_source.py`、`tools/stage013b_cffex_http_transport.py`、`tools/stage014_macro_features.py`及各自测试。
- 修改脚本：无；删除脚本：无。旧失败候选及旧数据线不修改。
- 数据范围：原始2019-06-03至2026-08-28；完整策略决策日历2020-01-02至2026-08-28。
- 品种固定：IF、IH、IC、T、TF、TS，旧档案84月加新增3月，共87月。
- 先以严格前一源交易日的可用正收盘价、正持仓量、非负成交量及未过到期月份的合约为候选，按持仓量降序、成交量降序、合约字典序确定唯一合约，再读取该合约当日价格；不能从当日仍存活合约倒选。收益为同合约两端价格之比减1。
- 换月不填0，当前合约缺价阻断，不换成另一可用合约。旧源代码的换月置0和先筛当日存活合约均不复用，也不修改旧冻结模型。
- 每个决策只使用严格上一A交易日数据，要求120条完整六品种收益；缺失不填零，不能向未来或陈旧日期回退。
- 股指序列为IF/IH/IC等权日收益；国债序列为T/TF/TS等权日收益。固定新增五项：方向乘20日复合股指动量、方向乘20日复合国债动量、股指20/120日样本标准差比、国债20/120日样本标准差比、股债60日Pearson相关性。只有前两项随多空翻转。
- 新增参数：窗口20/60/120、标准差`ddof=1`；全部事前固定，无窗口扫描、品种ID、日期ID或板块交互。
- 修改参数：候选特征数10变15，其余模型配置逐字段不变。双头目标、最少60成熟事件、月度扩展窗口、80棵树、深度2、种子、动作条件等不改。
- 删除参数：无。原10特征以后仍从原始冻结标签快照按原精度读取，不能经本轮CSV重算或转写；新CSV只含事件身份、源日期和5项新增特征。
- 账户规模及成本：本轮不运行账户回测；未来沿用150,000本金与固定A成本口径，不将手续费0解释为真实成本。

## 结果

- 新增/修改/删除回测结果：均无。
- 期末权益、总收益、最大回撤、Sharpe、总滑点、总交易次数、胜率：本阶段不适用，无新候选绩效；旧Stage009失败结论保留，不能由数据覆盖提升改写。
- 87份月档案包含1,759个源交易日、36,939条纳入分析的核心行情；2026-08-31的21条记录因晚于固定终点在选择/覆盖前排除。
- 1,758天各6条选择，共10,548条同合约收益；335条换月观察，只有4条自然零收益，不是人为填零。
- 276/276根事件与1,614/1,614完整A决策日满足严格前日及120日完整覆盖；最早60成熟可用事件月份2021-03-01，与原训练时间门一致。
- 新5特征在276事件中均为有限值，唯一值数依次251、251、249、249、249；这只描述输入，不据此声称预测能力。
- 独立计算最大绝对误差：日历上下文8.881784197001252e-15，事件特征8.43769498715119e-15。276身份和1,614源日期精确一致；新模型JSON除追加5项特征外逐字段一致。
- Stage013B的100输入和13输出身份复核通过；Stage014的118输入和5输出身份复核通过。
- 验证命令：`.py311/bin/python -B -m pytest -q research/lines/futures_trend_xgboost_history_compatible_root_utility/tests research/lines/futures_trend_xgboost_formal_signal_marginal_utility_v4/tests/test_stage005_event_lifecycle_audit.py research/lines/futures_trend_xgboost_formal_signal_marginal_utility_v4/tests/test_stage007_objective_headroom_audit.py research/lines/futures_trend_xgboost_formal_signal_marginal_utility_v4/tests/test_stage003_frozen_baseline_event_qualification.py`。
- 结果：219 passed in 29.63s。独立数值复核由当前agent使用另一套计算逻辑完成，不是启动reviewer，也不冒称独立人员评审。
- 生产目录`/Users/bytedance/Desktop/person/vnpy_production_live`干净，HEAD `d492ee072aa5a9d71477235d79f17d2a5db59db3`；没有连接CTP、报单、生产写入或commit/push。

## 冻结输出

| 产物 | SHA256 |
| --- | --- |
| `artifacts/stage013_cffex_root_source/summary.json`，HTTPS失败保留 | `517865975d3c1814f27bb08551d862c2291ac67d25ce5be41ae954b4f90c234b` |
| `artifacts/stage013b_cffex_root_source_http/summary.json` | `2214130f71e7ce115d1a16953500d444ac5900a9f895ec4ac6c2628a393b466c` |
| `artifacts/stage013b_cffex_root_source_http/same_contract_returns.csv.gz` | `497aae55b1ad34ccaf26921d80987a4086de07ad7a89a2b237b4ecaafe288606` |
| `artifacts/stage014_macro_features/summary.json` | `60be4114f96f5eb147bb9b05e2c0eb042038dab7312100b1ef34429443c4595e` |
| `artifacts/stage014_macro_features/input_manifest.json` | `9832a1b7fa86909aa475080f0bf11514d0e6d4d561804cb15d4cb9378e8c0043` |
| `artifacts/stage014_macro_features/event_macro_features.csv` | `9fa5878b0f1e50cb97eb3872ec378d003607b7d05104cb9acc6ccad4299f9956` |
| `artifacts/stage014_macro_features/decision_context.csv` | `f074faaf203dd027ea138c4f030057be819fb431bca62a8c550d0e8ba5bc1f9d` |
| `artifacts/stage014_macro_features/candidate_model_spec.json` | `40461ee42cdb7ad73d9a2fcfbfb27a2171de3a735d92007e82aa5d63993b61a9` |

原始6/7/8月ZIP分别483,762、535,917、477,030字节；SHA为`de56df1e96fe12f837985ffbd793b8996ab0ae10d28773b2df3f1ef428bd9fdb`、`abeff1a696ab0f717bead36a736b77bb1346b4a0ee8abbd11b433b4c5ffe98f7`、`887147411a5c56c74aa548400cddbb74566da7f5d69f1aa39cafd6e617cb90d7`。完整身份见Stage013B摘要和请求回执。

## 结论与下一步

- 数据和无标签特征条件通过，尚未证明模型预测能力或策略收益；总目标没有达到。
- 下一步先为唯一15特征候选冻结训练/推理/真实C执行合同，再合并原始精度的10特征及标签，执行既定逐月双头训练；新增适配器提供C当期状态加严格前日跨资产特征，不能使用A账户特征替代当前C。
- 保留原失败模型和全部旧产物，不改变树参数、阈值、样本下限或完整区间，不逐年选模型。不能相加A路径上的单事件边际收益代替真实完整C。
- 仅全路径主门成功后执行原预声明稳健性检查；未成功就停止该固定候选，不启动reviewer。任何历史研究通过也不自动授权上线或真实交易。

## 过拟合反思

- 运行前：本轮是否在收益调参，否。先检查独立信息可得性并事前固定少量机制特征，不读取新特征与标签的关系再选窗口。
- 运行后：本轮是否按回测结果救参，否，没有新增回测或关系筛选。但整个研究已反复查看历史，存在研究选择偏差；未来这些历史结果不能叫真正未见数据验证，数据版本风险也仍在。

## 继续价值反思

- 运行前：是。低成本判断公开跨资产原始信息能否覆盖实际根入场全区间；不合格就不训练。
- 运行后：是，限定为一次事前固定模型与真实完整路径的可证伪检验。覆盖及数值验证已通过，具备执行条件；继续窗口搜索、旧参数救援或提前reviewer没有价值。

## 合入建议

- 更新本线`LINE.md`：是，仅当前进度和结果索引。
- 更新`research/registry.md`：否，由合入者统一处理。
- 追加根目录`memory.md/back_log.md`：否，不是重要突破或正式候选。
- 不修改其他研究线、共享源缓存、正式策略、生产或券商状态。
