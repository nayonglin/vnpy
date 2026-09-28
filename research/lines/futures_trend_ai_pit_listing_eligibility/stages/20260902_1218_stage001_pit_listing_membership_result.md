# Stage001 PIT上市资格成员审计结果

- line_id：`futures_trend_ai_pit_listing_eligibility`
- 记录时间：2026-09-02 12:18 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `codex/stage130-option-probe`
- 当前线上：`m0005_20260901T165450+0800_1961d98ccb2b` / `ai_top10_plus_fu_official_live_v1`
- 阶段性质：标签前成员资格审计；不训练、不回测
- 是否重要突破：否；但确认旧账户边际标签的上游历史成员基准存在PIT资格缺口
- 是否触发A/B：Stage001本身否；已允许冻结Stage002 A/C

## 外部调研与判断

- QuantConnect文档把期货合约集合、连续合约映射和价格归一化分开，并在每个交易时点的实际合约链中选择；LEAN源码也显式按当前时间构建有效chain。
- 我的判断：先限定当时实际存在的品种，再在其上做正式分数排序，是可交易资格修正；让XGBoost通过缺失值分支处理尚未上市品种不成立。

## 本次变更

- 新增核心：`tools/pit_listing_eligibility.py`。
- 新增入口：`tools/stage001_pit_listing_membership.py`。
- 新增测试：`tests/test_pit_listing_eligibility.py`、`tests/test_stage001_pit_listing_membership.py`。
- 新增参数：无等待期的`first_available_date <= eval_date`、Top10、固定`fu`第11名。
- 修改参数：无。
- 删除参数：无。

## 结果

- 决策：`stage001_pit_listing_membership_pass_allow_frozen_ac_design`。
- 完整正式排序：55个月 × 18品种。
- 正式/候选 eligibility：634/634行。
- 发生修正：16个月，`2022-01-28`至`2023-08-31`。
- 正式Top10尚未上市席位：35个；`SH=16`、`lc=14`、`si=5`。
- 候选尚未上市席位：0。
- `2023-09-28`及之后成员变化：0个月。
- 最早普通合约日线：`si.GFEX=2022-12-22`、`lc.GFEX=2023-07-21`、`SH.CZCE=2023-09-15`。
- 读取日线键：250,685行；SQLite为query-only。
- 账户边际标签读取：0；sealed holdout读取：0；模型训练：0；策略回测：0。

## 回测指标

- 期末权益：不适用；未回测。
- 总收益：不适用；未回测。
- 最大回撤：不适用；未回测。
- Sharpe：不适用；未回测。
- 总滑点：不适用；未回测。
- 总交易次数：不适用；未回测。
- 胜率：不适用；未回测。

## 验证

- TDD RED：核心与runner测试均先因实现文件不存在而失败。
- 专项测试：`12 passed in 0.26s`。
- 输入运行前后SHA一致；数据库SHA256=`7e2633909f73d77c3b0b044199418d7c1ed2989afde480596aefbb18a83b724a`。
- 产物：`artifacts/stage001_pit_listing_membership/`；manifest SHA256=`a8d28e6b5e8ec4aa34352b3e049298bb2751c3b4c0068e70490047033e5b4976`。

## 决策

- Stage001技术门全部通过，允许进入唯一一次冻结的Stage002 A/A/C。
- 旧Stage015账户边际标签以含未上市席位的Top9/Top10为基准，后续不得直接复用；只有Stage002效果和路径门通过后才重建。
- 禁止按16个月中的收益表现挑月份、品种或等待天数，禁止修改TopN或正式分数。

## 过拟合反思

- 运行前：整个XGBoost序列风险高；本阶段规则自身否，因为资格只由日线是否已经存在决定。
- 运行后：本阶段否。没有读取收益标签或回测结果，所有结构门按预注册执行。

## 继续价值反思

- 运行前：有，只值得一次全量正式月份审计。
- 运行后：有，值得进入唯一一次同引擎A/A/C；原因是16个月、35个席位是系统性历史资格问题，而非单一弱窗口。
