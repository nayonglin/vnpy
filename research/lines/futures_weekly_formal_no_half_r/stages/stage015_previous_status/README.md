# 正式版衍生：周线指标，关闭0.5R止损

## 当前状态（Stage013，2026-10-23 16:18）

- 本轮用户指定：原19、周MA5/10/20、去MA40；全部AI选品、0.5R、C2关闭。日Kopen是主撮合模型，普通周信号次周开盘；日线风控/换月保留，退出次日日K open。无分钟依赖，minute/proxy/AI模型读取均0。
- 新同口径控制J：332410/+121.6067%/DD−17.4259%/Sharpe0.719964/108成交/17品种。用户H：979390/+552.9267%/DD−38.6075%/Sharpe0.942966/408成交/19品种。150000本金，2020-01-02—2026-10-22，手续费0。H已平净461550，未平净MTM367840（3空合约132手），闭合段胜率38.5366%、payoff2.27527、PF1.44957。
- 独审PASS_OFFLINE_RESEARCH；收益/覆盖提高伴随更深回撤、63.91%净利润来自2026、44.35%来自末未平。研究候选有继续固定规则验证价值，不自动晋级，不扫参。
- **术语勘误**：下面历史D/E/F“AI关闭”只指月度池，pairwise排序/手数倾斜当时仍启用，旧数值保留；本次J/H才是完整AI选品关闭。旧E335420不能充当本次J控制；旧F零量成交否决不变；G001—G008均未完成，无完整成绩，分钟路线已停止。
- J/H有效就绪比例34.43%→97.77%，普通就绪41→21周，容量41；周bar同源逐值相等，重复0。删除MA40与就绪变化同时发生，不拆分归因。
- 当前合同以Stage008/011/012及最终记录[20261023_1618_stage013_three_ma_original19_bar_open_result.md](stages/20261023_1618_stage013_three_ma_original19_bar_open_result.md)为准；初始合同与历史记录按当时口径保留。图/表：artifacts/stage011；独审stages/stage013_JH_independent_review.json/.md。

## 历史口径与阶段记录


本分支基于正式材料m0008/Stage037、master `e41a0a01d53b7256001e45e686acad53667ef7bf`。仅离线研究。`LINE.md`固定实验合同，`stages/`保存中文结果及独立审查；本地`outputs/`包含输入哈希、失败尝试、补片证据和最终原始表，不由Git保存私有行情。

- A：正式参数、15万元，同期同源数据对照。
- C：将所有AM/history技术指标（MA、MACD、RSI、ATR、Donchian、量仓及形态）改为完整真实合约周线，周期数值不改；关闭0.5R止损及依赖重试。
- 日线撮合、每日盯市、当日极值价格风控、C2盘中风控、月度AI和5交易日换月保留。此版本是周线指标策略，不是将撮合与风控全部改为周频。
- 41根观察门槛成为41个已接受周；缺真实会话的周不计入，未完成周不计入。同一周的交叉信号只在新封周日发出；CZCE同名合约跨十年复用不拼接。
- 历史AI含2019-12-31静态边界至2022年初，不能称全段PIT/OOS；手续费沿用正式回测0，滑点照正式设置。

## 本机复验

本地运行环境入口为`.py311/bin/python`，引用已安装的完整研究环境；vendor为交接包中的`vnpy_portfoliostrategy`。新克隆不会自动提供这些依赖、私有SQLite/分钟数据或凭据。

```sh
PYTHONPATH=. .py311/bin/python research/lines/futures_weekly_formal_no_half_r/tools/test_weekly_adapter.py
PYTHONPATH=.:/Users/mac/Documents/Codex/fian-handoff-20261014/vnpy_handoff_20261014/vendor:examples/portfolio_backtesting .py311/bin/python -m unittest discover -s tests -p 'test_stage249*.py' -q
PYTHONPATH=. .py311/bin/python research/lines/futures_weekly_formal_no_half_r/tools/run_weekly_with_minutes.py --arm C --attempt verification001
```

`run_weekly.py`保留首轮字节；`run_weekly_with_minutes.py`增加已验证分钟补片覆盖与失败暖机审计，不改策略参数。每个输出目录只允许执行一次，禁止覆盖已完成尝试。补片只填缺失时间键，重叠值不一致即拒绝；原始缓存不改。

`replay_audit_helpers.py`复用已验收Stage274导出/异常捕获工具；`daily_coverage.py`仅检查真实持仓日日线，不改变撮合。Stage249分钟校验/下载工具仍从旧研究线导入，交付依赖清单保存其SHA；真实行情读取使用本地忽略凭据，禁止回显或提交。

## 调研与判断

[Backtesting.py官方多周期示例](https://kernc.github.io/backtesting.py/doc/examples/Multiple%20Time%20Frames.html)和[GitHub重采样实现](https://github.com/kernc/backtesting.py/blob/master/backtesting/lib.py)强调高周期指标的因果对齐。这里采用完成周后才发布的原则；不直接复制其交易引擎。周指标更慢不等于更稳，且真实合约41周历史可能不足，必须结合有效覆盖和全窗结果判断，不能缩短窗口救结果。

## Stage003 后续指定配置

用户要求关闭半R、C2和AI选品；实际关闭月度资格门，原19基础池不扩市场。三开关False、AI disabled且0快照、所有盘中事件0；真实首分钟成交校验仍保留。新入口：

```sh
PYTHONPATH=. .py311/bin/python research/lines/futures_weekly_formal_no_half_r/tools/run_stage003_with_anchors.py --arm D --attempt verification001
```

需要本机outputs/stage003_anchor_catalog及stage003_minute_patches证据；原C/A的runner、输入及成果均不覆盖。最新D与C比较图、年度表、审查和报告已保存artifacts/stage003_*及stages/Stage004。

## Stage005—007 全市场覆盖实验

**最新结论：REJECT_EXECUTION_ZERO_VOLUME。** 全91资格池完整回放F016记录49个模型成交品种、240笔；2021-05-06 eb2105零分钟量平7手，执行审查否决。212500/+41.67%/DD−35.40%/Sharpe0.3412只保留为诊断，不是合格可交易收益。E同源19池通过研究审查。最终中文报告：`stages/20261023_0040_stage007_full_market_rejected_execution.md`；独审：`stages/stage007_F_independent_review.md`。

E保持原19基础池，F扩为2020年以来91个国内期货产品家族（含8个金融、3个月均价产品家族）；两者同数据、同15万、同完整周线、半R/C2/AI均关闭，其他数值参数和最多4个同时持仓等资金约束不改。完整合同在`stages/20261022_2247_stage005_full_market_contract.md`。候选覆盖数与实际成交品种数分别统计，缺行情、周线未就绪、无信号或资金不足均不会强制成交。

正式预热入口沿用2019-06-01，首个真实周源日2019-06-03；41个已接受观察周后才就绪，因此2020年初存在预热空窗，不能称整个2020年均已充分周线预热。缺真实交易日或零成交量会话的周不补造；终点2026-10-22为周四，不当作完成周。日线撮合、真实首分钟成交锚、每日盯市、其他价格风控和换月保留。

数据在独立SQLite副本只补缺，原键不覆盖；全市场mapping补齐，月均价三家族按前一会话已知正量/正OI排序选约。新增产品的合约乘数/tick取观察快照，缺真实保证金时沿用0.15模型默认，原有元数据不按收益修改；手续费为0、固定滑点，合约规格未逐日PIT还原。冷门产品仍有6364个mapping合约日缺真实日线，不能把91候选解释成91条完整可执行时间序列；实际持仓/成交日另有真实日线与正量硬闸。详见数据独立审查。

冻结离线回放入口是`run_stage005_full_market_v3.py`，其completed_pending_independent_review只说明引擎完成，不能替代最终执行审查。此前版本、失败尝试和下载/快照工具保留为冻结证据，不能用失败目录里的局部表作为成绩。`stage005_merge.py`仅把重复concat/merge改为一次批量合并，保持原优先级及冲突容差；冻结真实样本每值/类型/索引相等，19品种E010桥接另与E009逐笔/账户精确相等。新产品首分钟适配只允许在半R/C2/AI均关闭时安装，禁止拿首分钟补片冒充完整盘中扫描。

复验需先恢复本机忽略的完整数据、分钟原始来源、证明文件及最终`input_manifest.json`所指全部依赖，再逐文件核SHA；克隆本分支不会取得私有行情或凭据。现有本机完整冻结资料可用唯一新目录复跑：

```sh
PYTHONPATH=. .py311/bin/python research/lines/futures_weekly_formal_no_half_r/tools/run_stage005_full_market_v3.py --arm E --attempt verification001
PYTHONPATH=. .py311/bin/python research/lines/futures_weekly_formal_no_half_r/tools/run_stage005_full_market_v3.py --arm F --attempt verification001
```

`stage005_signal_anchor_plan.py`只扫描原始周线信号来规划下载，不创建账户/持仓/订单，不计算资金成绩。缺真实分钟时停止，补真实完成行情后从头重跑，不使用日线open近似。`stage005_snapshot_anchors_fast.py`首次全验来源、后续以多层SHA收据验不变性，任何原始文件或证明变化立即拒绝。

成果命名统一为`artifacts/stage007_*`，包括权益/回撤图、逐年表、91品种成交与每日MTM净盈亏表、比较摘要和相关测试证据。产品表中data-only原始信号计数与实际成交分开；0成交不能推断成0信号。最终仍是单历史窗研究，非完整PIT/OOS；未授权自动晋级。

最终展示使用新增`stage007_build_reviewed_artifacts.py --review-json <F_audit.json>`，要求明确的独审拒绝状态，并核对预审artifact字节备份后生成醒目诊断标识。原`stage007_build_artifacts.py`和预审artifact保留为冻结证据，不直接代表审查通过。最终摘要的qualified_executable_trade_count/product_count为null，不能从49/240简单扣除一笔得到获准数字。
