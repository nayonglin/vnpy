# Stage257：一次性原始现货文本提取的有界实现合同

- line_id：`futures_full_market_long_signal_ai`；2026-10-19 22:46 CST；非重要突破；数据提取，不触发正式策略A/B。
- 上一goal回合为进展：batch002新增250实际attempt、249body与256名称候选闭包；本回合继续轮询同真实session10555，不重启collector/runner/current batch。原全市场高质量做多AI完整目标不变，稳定收益/DD及窄损加注尚未证明。
- 按registry确认本线。255仍在实际运行，因此本阶段先准备代码与少量synthetic，不提前解析真实原件/读取label或运行金融。

## 短设计与实现范围

1. 紧凑工具只沿已接受253的stdlib regex/表深度/Decimal方法，严格复用原CSV八字段及原literal_unit_text_groups，避免新解析口径变相改数据。已抽取的249body不重读，253CSV一次读取后复用。原9缓存中2空页直接继承；另7正数页只为旧收据未覆盖的完整S字段允许一次提取，明确计数，非完整性反复核验。
2. 其他保存body各至多一次：字节/SHA、标题日期、表结构、rawS、单位文本在内存同一次完成。unknown、不支持行、失败和未尝试状态保留；同名重复行不选一/平均/归并，不修改网页或补0，不下载缺页。
3. 固定3833日期每项inventory；CSV原名/原价文本/原源SHA与单位ID保持绑定。新unit文本分组，不把今天页脚当历史物理定义或首发时刻。255 terminal缺失/仍running时actual拒绝，root须先轮询真实10555确认终态后再唯一调用fresh actual_run1。若采集因限流提前停止，也仅如实提取现有内容，未请求日保持unknown，不声称完整历史。

协议：`outputs/stage257_raw_spot_extraction_protocol/protocol.json`，3563B SHA `2e0e56352ae8422a822ea8498af8d64481c66b642c135ebbfaf8f17aecd67242`。author最多3个必要新synthetic行为方法、0真实body rehearsal/fixture fit/旧套件。只对**新提取器**做一次有限source预审，不重审250，不建通用清洗系统。实际输出：原CSV、date_inventory.jsonl、unit groups、receipt/terminal/manifest；不是feature、训练样本或alpha。

## 调研和判断

沿同一来源研究的[原始日报](https://www.100ppi.com/sf/day-2020-01-02.html)及[AKShare维护者实现](https://raw.githubusercontent.com/akfamily/akshare/main/akshare/futures/futures_basis.py)，选择原始S而不直接继承成品basis符号/单位转换。当前没有新来源/新alpha尝试，继续既有冻结数据计划；不为每一批重复网上探源。对数变化未来可研究操作性vendor显示名序列，但不自动证明物理benchmark同质性或PIT；256名录仍为建议，不做join。

新增/修改/删除策略参数、模型和金融结果均0；新fit/cash/SQL/network=0，当前网络只由既有255接续任务执行。本阶段本身不发HTTP。累计439fit/234cash；权益/收益/DD/Sharpe/滑点/交易次数/胜率N/A。正式版、生产、CTP、邮件、launchd、Git远端不变。

开始新增拟合型过拟合：**否**，不读收益/不调模型或交易参数；长期同史择题风险：**高**。继续价值：**是**，采集同时准备唯一必要数据输入，缩短等待并避免后续原件反复解析；若扩成无限源资格/单位修补工程则**否**。结束以实际代码/来源终态为准，不提前宣称完成，goal active。
