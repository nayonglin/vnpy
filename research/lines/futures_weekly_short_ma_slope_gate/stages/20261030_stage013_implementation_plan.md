# Stage013 10万备用金 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans. 用户已授权直接改完回测，执行方式沿本会话多agent；计划与证据放本研究线覆盖默认docs路径。

**Goal:** 仅将原C场外备用改为100000，完成23起点与150000备用同源比较。
**Architecture:** Stage012已审结构的独立Stage013衍生；四fresh/十九耦合证明，旧金融账本只读。根agent冻结金融源/数据/计划、调度和交付，独立agent验收所有输入/计算/图文。
**Tech Stack:** .py311/bin/python、vn.py、pandas、Matplotlib、自包含离线HTML；无HTTP。
**Spec:** stages/20261030_stage013_reserve100k_design.md。

## Global Constraints

- 原C风险/过滤/初始E150000不变；R100000，W250000；对照原Stage009 C_R150，非Stage011统一风险或Stage012 R50。
- 23既定起点到2026-10-29；4真实金融/19证明候选/23旧对照，46/23/70998。
- 4fresh固定2017Jan/June、2018Jan/June，canary2017Jan；先独审2015reuse+canary，再余3，max_workers2。
- 只新增Stage013文件；不改旧阶段及LINE/registry。金融源和计划commit后freeze；运行中不改冻结源/HEAD。
- 不为后处理重跑金融；失败保留。E净值含入金、R不入净值，PnL单列。总预算250k/300k不同，不套W比较门。

## Review Focus

1. 100k边界等于/不足、首次partial-T：反例拒绝超支和旧50k常量残留。
2. 19复用每次check足额、R/W仅减50k，settings/风险/全部账本SHA不变；超100k复用拒绝。
3. 原C风险和所有设置完全等价；拒绝均匀1.8%或R50候选误作控制。
4. 46/23/70998及2026观察完整；E/真实PnL/T桥、负E不裁剪、逐窗文字身份不丢失。
5. 五图及离线HTML内嵌/标题/行数/资源，最终状态改动不改数值像素；无HTTP。

### Task1 金融核心与测试（builder）
Create tools/stage013_reserve.py、stage013_reuse.py、stage013_contract.py、run_stage013.py、stage013_coordinator.py及5个test_stage013_*.py。
Interfaces沿Stage012 public API；required_financial_sources明确新10文件＋本2文档，baseline仍Stage009/010。reserve类AST只将原R150000改100000。
- [ ] 写100k边界/4fresh19reuse/错误源及checkpoint反例，运行RED。
- [ ] 实现R100/W250及新namespace、固定集合、4/19门；原交易逻辑不改。
- [ ] 定向测试GREEN并交独审，冻结10文件SHA。

### Task2 独立准入与计算审计（reviewer）
Create stage013_independent_*工具/证据；独立读取数据/源码/所有旧C账本及checks；不调用报告实现复算数字。每窗receipt接口沿stage012：status、path、source_files_sha256、metrics.rounds/open_round_net_mtm、method。先代码/复用准入，后canary gate绑定2015+2017Jan checkpoint，最后23receipt、数字/图文/根stage。
- [ ] 适配R100/W250/offset50k/4fresh19reuse，保留原raw150k审计核心。
- [ ] 反例测试，源/数据准入与代码review；金融freeze后跟随逐窗审。
- [ ] 总审46/23/70998和最终离线交付，保存不可变原尝试与最终review。

### Task3 报告与图（reporter）
Create stage013_report.py、stage013_plots.py及test_stage013_report.py/test_stage013_plots.py；沿Stage012已修复实现，C_R150/C_R100，R/W差50k，4fresh19proof。HTML自包含，无HTTP。
- [ ] 资金流/负E/导出身份/范围反例RED→GREEN。
- [ ] 只从已审账本build→pending render；data manifest冻结。
- [ ] 独立数字接受后reviewed render，图体像素只标题状态变化，保存23中文窗。

### Task4 调度与交付（root）
- [ ] 读新源码/测试与独审receipt，commit金融核心与设计，再生成freeze。
- [ ] canary、独审gate、resume3份，23全部完成。
- [ ] 输出中国文总stage及全部指标，独审事实；完成后过拟合/继续价值反思。
- [ ] 封manifest，明确4新19proof23old；只Stage013本地提交，保持旧版本。

Self-review：用户需求覆盖，纯字段金额改变与所有派生常量/标识一并隔离；API沿用已审实现，不增加其他金额或策略变化。
