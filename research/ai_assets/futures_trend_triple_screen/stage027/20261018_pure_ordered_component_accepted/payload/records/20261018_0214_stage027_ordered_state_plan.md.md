# 有序入场纯状态组件 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans. 按本线唯一文件分工执行，不修改LINE/registry。

**Goal:** 实现可被真实B/C入口复用的因果FI2及准备状态，并用真实同源数据生成不含收益的潜在条件需求；最终更高收益/更低回撤目标保持active。

**Architecture:** 纯Python模块负责指标与状态，不接账户；独立builder只读固定日线、周cache和原生信号身份。真实盘中执行、预算和金融runner在下一个独立合同中接合，不能在此伪造日线条件成交。

**Tech Stack:** `.py311/bin/python`，stdlib/unittest；真实数据builder使用已冻结pandas/numpy runtime，不安装或升级依赖。

**Spec:** `20261018_0214_stage027_ordered_state_design.md`。

## Global Constraints

- 同一当前分支，无新工作树；纯特征/状态不得调用策略构造、账户、训练、网络或订单API。
- FI2固定2，两raw Force均值seed、alpha2/3、3连续有效close；零量/缺真实calendar日重暖。
- 周12/26/9、35完整周、unknown合同沿原cache；u收盘冻结D，C严格setup_day<signal_day<execution_day。
- 正式源码、旧失败attempt、原始数据及冻结工具不修改；不扫周期、阈值、品种/年份。

## Review Focus

1. 未来追加/变化不能改变过去FI及intent；缺日按真实calendar，避免周末伪缺口。
2. C同日准备与信号不得通过，B可在逆向准备当晚发次日单。
3. 换月、周方向/AI变化后不沿用旧价格/准备；新合约自有已知历史可用。
4. intent不等于成交，setup只由合法唯一D的真实fill消费；unknown回退不强制开仓。
5. 真实数据builder没有偷偷读取PnL或把潜在上界算作交易，输入字节变化必须失败。

## Task 1：纯FI2与有序状态（独立实现）

Files：新增`tools/stage027_ordered_state.py`和`tools/test_stage027_ordered_state.py`。

Interfaces：`force_index_rows(rows, calendar)->list[dict]`；`OrderedSetupMachine(arm).on_close(...) -> dict`及`.on_fill(intent_id, execution_day)`，精确关键字和字段遵循spec。

Ruling：真实target缺失时新增必要`cancel(product,day,reason)`接口，清状态而不编造OHLC；并入第4组取消行为测试，不扩alpha参数。

- [x] 先写8组必要行为测试：手算seed/递推与前缀不变；缺日/零量/双合约暖机；C严格先后/B准备当日；周/AI/epoch取消；unknown B/C；一日过期及新signal身份；合法fill一次消费/错ID错日拒绝；tick镜像和异常输入。
- [x] 用`.py311/bin/python -m unittest discover -s research/lines/futures_trend_triple_screen/tools -p 'test_stage027_ordered_state.py' -v`观察因缺实现失败并保存摘要。
- [x] 实现最小纯模块；不引入额外容错fallback、过期N日或金融字段。
- [x] 同一测试命令通过后停止重复；root与独立reviewer核关键因果行为，无需全仓无关测试。

## Task 2：真实FI缓存与潜在intent上界（root）

Files：新增`tools/stage027_build_ordered_features.py`；输出仅`outputs/stage027_ordered_features/`，拒绝覆盖。

Consumes：Task1纯函数、Stage005元数据/原生事件身份、固定SQLite与交易calendar、已冻结周cache；读取前后指纹检查。

Produces：FI派生缓存、B/C潜在intent身份及触发位、取消/unknown计数和input_manifest/summary；不产生账户/成交/PnL。

- [x] 复用原Stage005来源及accepted源SHA；小型fixture先验证真实calendar和无经济列联表，再实现读取管道。
- [x] 真实数据只构建一次；唯一实际进程71757 exit0，3.213秒，未覆盖旧输出。
- [x] 核原900 native身份全部原样保留，C intent严格有更早setup，B/C intent所有日期/合约/周asof自洽；不重算周cache、不训练AI。
- [x] 新增独立agent审查指标公式、边界、输入和真实上界，限定为本组件；P0/P1/P2=0/0/0，不要求旧全市场重清洗。

## Task 3：交接到实际执行合同

- [ ] 根据Stage025/026与已验证状态接口，固定唯一预算分配/首分钟内成交和保守止损合同，再实现小型真实hook因果测试。
- [ ] 上述通过才进入一次真实C/B账户对照及独立经济复核；完整更高收益/更低回撤目标和固定七门不变。
- [ ] 每步中文stage与本线状态，决策资产按Skill登记；不推送、不部署。Task1/2完成仅代表真实金融实验的必要准备，不宣称目标达成。

Ruling：用户已明确委托持续自主研究，沿Stage001的执行选择由代理承担；当前阶段不重复询问设计/实施许可。所有规则在新臂收益前固定，并由独立review检查，真实资金和外部发布仍在授权之外。
