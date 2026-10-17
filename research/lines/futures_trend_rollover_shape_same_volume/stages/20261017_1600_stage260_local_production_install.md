# Stage260 本机正式生产迁移与安装

- 开始时间：2026-10-17 16:00 CST；研究线：futures_trend_rollover_shape_same_volume。
- 用户明确指令：“你先完成部署安装啊”；继承本机部署与公开origin/master发布授权。
- 起点：master e41a0a01d（核心正确性修复40570be4b），当前不可变m0008仍旧源码。AI研究分支已保留，现直接切codex/local-production-install推进部署，不改AI研究。
- 目标：受控迁移旧机器固定生产路径到本机/Users/mac/Desktop/person/vnpy(_production_live)，形成新不可变物料、真实本机资格、受控晋升与Stage948七任务安装闭环。
- 范围：仅执行部署所需路径和依赖修复；正式15万元、0.5R、AI Top10非fu+固定fu及Stage037规则保持。不得复制旧机器资格为本机资格、不得伪造CTP采集或绕过receipt。
- 并行分工：路径与测试；物料/资格编排；Python/CTP runtime依赖；主agent负责clean source、发布和安装。
- 研究资料：查阅Git官方clone文档（--no-local使用Git传输），Python官方venv文档（虚拟环境不能直接视为可复制迁移）；判断是用独立干净生产checkout、核验最终路径和真实runtime，不机械替换路径后宣称资格。
- 开始过拟合判断：否，属于部署迁移和代码正确性资格，不选参、不训练模型、不追加alpha回测。
- 继续价值判断：是，修复代码必须在本机形成可追溯、可运行、可回滚的正式发布。
- 新增/修改/删除策略参数：无。新回测：无；后续仅资格所需测试与正式只读账户采集。

## 执行记录

- 已启动独立生产main浅克隆；其他任务registry/个人知识目录及原始行情均保留，不进入发布。

- 16:07 CST：7份production plist已迁移到本机固定路径，Stage945/946/947/948与本机路径共103项unittest通过。候选release selector已补齐，新增candidate+readonly相关26项通过；默认active门未放宽。新增两项测试纳入生产required suites，新helper纳入显式critical files。
- 本机配置中MD/TD前置首次TCP均timeout；用户明确“因为是周末所以连不上，这是正常的”，确认无需VPN。接受该解释作为当前操作条件，停止重复连接，不补造正式只读采集，不自报qualified。
- 独立生产main已建立；本地private env、行情凭证、SQLite安全备份、4项生产数据资产已复制，0600，未连接CTP或SMTP。独立venv通过--copies创建、保留原vnpy/CTP/numpy/pandas版本，正完成真实native核验。
