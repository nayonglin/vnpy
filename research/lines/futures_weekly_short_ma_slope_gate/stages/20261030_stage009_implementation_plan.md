# Stage009 备用金补足规则 Implementation Plan

**Goal:** 在冻结Stage008 A/C上增加15万隔离备用金，完成同源23独立起点与同30万本金对照。

**Architecture:** 新Stage009策略wrapper只在有效新开仓候选资金计算前内部转账；旧引擎账本保留，独立资金流账本连接交易权益和总权益。新增runner/checkpoint/coordinator，不改旧金融代码。报告与独审不调用金融。

**Tech Stack:** 本仓库`.py311/bin/python`、现有vn.py日线next-open引擎、pandas/matplotlib；本地隔离研究线。

**Spec:** `stages/20261030_stage009_reserve_design.md`，用户已确认超15万继续按全部交易权益动态计算。

## Global Constraints

- 仅本线Stage009新文件；46新引擎、23起点、E/R初始各150000、同10-29截止。
- 原A/C过滤差异、数据和成本不变；R不可提前参与交易，内部T不可计收益；无生产/外部下单。
- 先测试RED/GREEN，金融源码commit/hash冻结；2015Jan双canary独审后再44份，完成后46逐窗中文与最终独审。

## Review Focus

1. 未平亏损触发、获利不补及恢复后再亏重复补；备用不足/耗尽精确守恒。
2. C被底部20%拒绝、无效周止损、env_probe/换月/退出/预热不得转账。
3. 同日/重复sizing不得重复资金；多品种原顺序不改；不清空原风控历史。
4. 原始引擎PnL与交易桶/总账户双桥，转账不算净利，静态闲置对照同30万本金。
5. 源身份/窗口/冻结与全46完整性；负结果保留，不用局部或观察窗晋级。

## Tasks

- [ ] 1. 独立只读审现有equity/entry/risk入口；新增`stage009_reserve.py`与`test_stage009_reserve.py`，上述行为RED/GREEN并审wrapper。
- [ ] 2. 新增`run_stage009.py`、`stage009_contract.py`、`stage009_coordinator.py`与runner/checkpoint测试。沿Stage008独立进程模式，显式输出原始账本、资金events/daily/acceptance、候选两桶资金与总30万metrics；不改Stage008。
- [ ] 3. 数据/源码/旧manifest预检，写`stage009_freeze.json`，金融必需源本地commit后冻结SHA；运行2015Jan A_R/C_R，独立canary审全账本与T。
- [ ] 4. 批量剩余44独立回放，最多3workers，绑定checkpoint并逐窗独审；任何技术失败保留attempt停止新派发，修复后另版本，不覆盖。
- [ ] 5. 纯会计/图表工具，复用旧A/C+闲置15万作同本金对照，列46候选与46idle表、补资事件、两组23配对、年初/年中cohort和五图；先测试再实现。
- [ ] 6. 全量独立审计和视觉验收；锁最终review SHA后派生已审图，46逐窗中文及总stage和SHA总清单；最后本地保存提交，不推送。

进度与必要解释追加在本文件下方；金融freeze后不再修改本文件，后续进度另写Stage009文件。
