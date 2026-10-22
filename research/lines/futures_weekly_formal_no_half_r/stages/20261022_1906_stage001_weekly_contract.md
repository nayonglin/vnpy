# Stage001 周线指标/半R关闭固定合同

- 时间：2026-10-22 19:06 CST，非突破版本。所属独立新研究线见LINE.md。
- 用户已指定正式衍生分支、全部指标周线、半R关闭、2020年至今；按bounded设计直接实施既定范围。
- 新增周线聚合与重复信号抑制adapter；修改参数enable_stage847_half_r_stop_retry True→False；指标观察单位day→week，数值全部保留；删除参数0。C2、日级价格止损及执行保留。
- source baseline与缓存origin/master六身份一致；SSH实时ls-remote master=e41a0a01d。旧production路径不存在，不声明生产运行/资格。
- 工作区只读复用完整.py311、vendor依赖；数据与mapping单独复制；原checkout不改。
- 7项周线行为测试见红后通过；会计/盘中回归使用unittest；pytest在主checkout环境缺失，不安装。
- A/C均同一快照，同成本/AI/资金。独立review覆盖结果/数据/逻辑/置信度/bug。
- 开始过拟合判断：否，预设结构变化且不扫阈值；继续价值：是，验证周期变化，缺41周历史不能当无alpha证据。
- 新结果待写；旧结果修改0、删除0。TODO：固定回放、独审、统计与结束反思；不自动晋级。
