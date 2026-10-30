# Stage011 Uniform Risk Implementation Plan

> 按已授权固定设计持续执行，无需再询问倍率/起点。使用测试先行、隔离实现和一次独立全程审查；研究文件位置优先于skill通用docs路径。

**Goal:** 将三类OI信号基础风险统一0.018，以相同补资机制重跑23起点A/C，比较冻结旧补资版。

**Architecture:** 新Stage011入口/冻结合同/协调器；复用已审周线与备用桶实现，仅入口覆盖三参数；旧run只读复用。报告从新金融账本和旧冻结账本分别投影，保持E/150k用户口径并列W/300k无外部现金流经济指标。

**Tech Stack:** .py311/bin/python、既有vn.py日线next-open、pandas/numpy/matplotlib、离线HTML。

**Spec:** 20261030_stage011_uniform_risk_design.md。

## Global Constraints

所有写入仅本线Stage011；原19、无加仓、无多头/MA斜率门；A/C差异只为原C空头bottom20门。三参数唯一新增delta，46新金融、46旧复用、23starts、cutoff2026-10-29；E150k+R150k；并行2；无HTTP/生产/CTP/订单/下载/外部消息。

## Review Focus

实际参数与reference只差三项、没有二次risk_multiplier；所有run独立首日与warmup不交易；已转入资金进入sizing但备用不提前进入；源hash/运行身份/checkpoint准确绑定；E含现金流不能冒作真实PnL或策略return。

## Tasks

- [ ] 1. 实现测试先行的stage011_risk/contract/runner/coordinator；验证拒绝未声明设置、冻结数据/资金/执行身份；保存RED/GREEN证据。实际设置对旧对应run逐项比较只允许三参数。
- [ ] 2. 独立agent代码/数据入场预审，冻结source commit/hash；启动2015年初A/C canary，完成真实运行和独审。接口：run目录保持Stage009账本schema，新增uniform_risk_acceptance.json。
- [ ] 3. 锁canary审查SHA继续其余44窗；逐窗checkpoint，全部46validated后停止金融进程；独审可流式逐窗。
- [ ] 4. 仅从缓存生成summary/paired/cohort/daily、五图、中文单窗和总stage、离线HTML；记录真实PnL、资金流、成本、完整round统计、风险与补资耗尽。
- [ ] 5. 独立全结果/数据/逻辑/图表/哈希复核，修实现后处理问题不救金融参数；最终封存、核验并本地commit，交付新旧对照结果与文件。

预检：runner合同与report消费run schema共享接口（需保持现有reserve_daily/trade_events/settings/entry_risk文件并新增参数delta凭据）；root只写report/plans，runner agent只写run/contract/coordinator/tests，reviewer仅写审计工具/记录，避免文件冲突。
