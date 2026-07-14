# Stage001 候选边际风险贡献实现计划

## Task 1：数据合同与纯函数

- 建 current-AI 19 产品、2019-2026 严格非换月 return panel。
- 用 Stage462 三个固定 fu 分钟源补数据库缺口，不下载新数据。
- 实现 LedoitWolf、标准 RC/IC/CC、scale 与整数化纯函数。
- 测试 T-1、63共同日、换月缺失、正/负相关、long/short、零方差、NaN、排列不变性和 min1/no-amplification。

## Task 2：真实引擎 batch hook

- 子类化 Stage847，不改共享策略文件。
- override `_plan_flat_entry_candidates`，先调用 super，再对最终 opened plans 一次性缩手。
- 从 `day_contexts` 读取现有持仓和当前价格，从 plans 读取候选方向、手数、乘数和价格。
- unavailable 整批 no-op；不释放名额、不递补。
- candidate snapshot 追加完整 MRC 证据字段。

## Task 3：静态审计与 A 复现入口

- 绑定 Stage137 394-source manifest，并加入新线代码/return panel/三份 fu backfill。
- 静态模式只生成/审核数据和公式，不产生绩效。
- A/C runner 支持四锚点、同 AI、同 metadata、同成本、150k。
- 先跑单元/集成测试、py_compile、diff/whitespace check，再交独立 agent 代码终审。

## Task 4：1x canary 与独立绩效复核

- 代码终审通过后运行四锚点 1x A/C。
- 根据冻结 gate 自动决定是否允许 full/2x/3x。
- 每次回测结束立即拉独立 agent 重算数据、逻辑、统计、未来函数、会计、margin、置信度和 bug。
- canary 失败立即关闭；成功才进入逐半年和成本压力。

