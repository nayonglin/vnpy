# Stage264 完整 pre-main 日线补齐 manifest

- line_id：`futures_trend_rollover_shape_same_volume`；day 模式。
- 时间：2026-10-17 17:29 CST；分支：`codex/ai-training-data-expansion`。
- 性质：固定池真实合约身份与数据缺口整理；是否重要突破：否。
- A/B：不触发，未提出策略候选；未改正式源码、策略、主库、registry、LINE 或其他研究线。

## 调研与判断

已读取 registry、Stage263 扩样结果、独立审查和 pre-main 修复建议。核对 Stage196 本地源码：其旧入口只补主力日缺口，不能用来补完整 pre-main。独立脚本采用日期锚定的交割年身份，并添加合理区间与失败闭锁。

网上与 GitHub 调研：[RQData 合约 API](https://www.ricequant.com/doc/rqdata/python/generic-api)、[郑商所数据约定](https://www.ricequant.com/doc/rqdata/python/futures-mod#郑商所相关数据约定)、[Tushare 代码规则](https://tushare.pro/document/2?doc_id=134)、[fut_basic](https://tushare.pro/document/2?doc_id=135)、[TQ 代码规范](https://doc.shinnytech.com/tqsdk/latest/usage/mddatas.html)、[TQ GitHub 下载器](https://github.com/shinnytech/tqsdk-python/blob/master/tqsdk/tools/downloader.py)。判断：规范化格式、历史代码变更、数据口径和真实可用范围必须分别验收；现成代码不能证明有权限或老合约存在，不能将宽窗口假称上市日。

## 变更

- 新增：本线 tools/stage264_build_daily_manifest.py 与 test_stage264_daily_manifest.py。
- 新增参数：仅固定清单口径，2015—2019、实际 18 产品声明中具有映射的 14 产品、AM120、探测宽窗口 730 自然日。
- 修改/删除策略参数：无；新增/修改/删除回测结果：无。
- 脚本不导入执行引擎或行情 SDK，SQLite `mode=ro` + query_only，输入前后 SHA 与文件属性一致。

## 结果与口径

- 231 个合约 epoch、14 产品、14,187 个真实非空主力映射日；77 个主力缺日全部为 SM，已在逐日清单显式标记。
- 首主力日使用全 mapping 同 epoch 首次日期，另列范围内首主力日；11 个 epoch 早于 2015。
- 全 mapping 首主力日已有 AM120：13/231；计数缺口下界 25,953 条。
- Stage263 可比 preload2015 + 范围内首主力日：13/231，缺口下界 25,942 条。11 条差异来自上述 2014 合约的研究起点时钟，不是修数或数据变化。
- 期内同代 OHLC 无无效行，重复日 0。不同 decade 的同名 CZCE 原码没有相互借历史。
- 全部 231 条上市/最后交易日期仍为 unknown，完整寿命下载起止也保持 unknown。必须先用供应商 metadata 验证，再采用上市日到最后交易日；730 日前到交割月末仅作标注清楚的 probe 窗口。
- RQData/Tushare 代码标为文档格式、catalog 未查；TQ YYMM 别名未被官方确认，保持 unverified。MA≤1505 的旧产品更名边界已测试，实际队列最早是 MA1506，未自动引入 ME 历史。
- 先写身份/实际 bar 边界测试，再生成脚本；7 项新增测试通过（具体覆盖跨 decade、0 年份、全局时钟、无效/重复 OHLC、未来排除、只读数据库与 MA 更名）。

本阶段无新增账户或模型回测，因此期末权益、总收益、最大回撤、Sharpe、总滑点、总交易次数、胜率均不适用；不得挪用 Stage263 数值当本阶段结果。

## 产物与下一步

本线 `outputs/stage264_pre_main_daily/`：manifest_contracts.csv/.json、manifest_main_dates.csv、download_state_template.csv、summary_daily_manifest.json、manifest_readme.md。下载状态以 vt_symbol@YYYYMM 为键，状态模板需复制为独立 mutable checkpoint，原始文件按 vendor/交易所/原码_交割年月隔离。

交付 root 消费清单并由独立来源探针核 vendor；建议身份样本为 CF505、AP001、MA506、rb1505、jm1505、SM501。先取 metadata，再对重叠日验 OHLC/OI/volume、记录参数/原始文件 SHA，最后独立验收同代历史与缺日。当前没有下载、训练、回放、主库导入或策略信号修改。

运行前过拟合判断：否，固定池数据修复，未根据收益挑参数。运行后：否，计算只输出实际输入缺口，未缩 AM120、未按模型结果挑合约；既有后验源风险不会因此消失。

运行前继续价值：是，真实同代预热是必要条件。运行后：是，清单明确区分计数缺口、日期身份和未知寿命边界，使后续补数可验收；不保证补齐成功或 AI 能泛化。

本子任务不改 LINE、registry、memory 或 back_log，由 root 合并者统一决定。无需晋升，尚未启动完整数据再实验。
