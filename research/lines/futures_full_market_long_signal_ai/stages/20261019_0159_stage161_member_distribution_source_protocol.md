# Stage161：一次离线恢复已披露会员分布

- line_id：`futures_full_market_long_signal_ai`；2026-10-19 01:59 CST；非重要突破，goal active。
- 上轮是progress：4实际新账/独审/159负结果改变后续行动，不是等待或状态复述；397fit/210cash。

## 方向与自主设计判断

160三项独立盘点/科学审查确认：原110/115只用了FC/NFC四总量，RANK1..20的exact contract双侧分布未入模型，066曾提出但未训练，不能称首次想法。相同价格/OI/类别总量下可有不同分布，属于真未测观测；不由此断言有alpha、聪明钱或客户身份。999是合计，双侧独立榜，少于20真实数量和空槽必须保留。仓单定义也独立，但本机仅3原表且新来源/单位/时钟成本高，暂作后备；基差缺匹配spot主源。

用户已授权持续自主研究，root选择不再重复刚核的6原表probe，直接一次读取既存连续3588日原始资料，确认是否有足够连续训练支持。独审原建议止于稀疏probe，本次扩大为单遍离线规范化是root明确决策，不冒称独审已批准整批或有金融优势。源不新增HTTP/大行情/模型。

网上/GitHub主源复核：[AKShare维护者cot.py](https://raw.githubusercontent.com/akfamily/akshare/main/akshare/futures/cot.py)确认CJ2/CJ3独立榜、非正rank过滤和participantID删除；但文档的旧DCE总排名说法与具体合约实现本身不一致，不能作当前/全历史资格。只参考，不执行其重试、cookie或下载逻辑。[SHFE仓单指引](https://www.shfe.cn/services/delivery/warehousewarrant1/)支持交割登记凭证语义，不支持总库存流。

## 本轮冻结与预算

协议 11728B，SHA `ce6329b0f806e69d62d34a894b3738df2a65fdcf557c873bffb37392208b73ca`。只source-only：沿119 accepted manifest3588日、3580已存raw+8未知，一次原文绑定核验/解析；不拼目录、不补8未知。真实每侧具名levels及999分别校验，不能把空槽当0、不能要求双方20人或多空总量平衡；只测可见已披露分布。H为侧内shares平方和，唯一源诊断q=H_long−H_short；不是金融方向或模型授权，不扫topN/normalize/符号。精确目录epoch/SHFE-INE映射，u只用紧前source日v同epoch，no all fallback/ffill。

完整129 action1552456和mother399252身份/顺序全部保留，只消费身份列，不读目标/score/价格/未来stale；sourceunknown保留null与reason，合法q0与missing区分。source可得性不删训练/预测/机会，新共同missing若变化不能旧控制fit复用。

独审新规范化/所有投影/汇总完整一次；原raw只24个事前日期全scope重建：6旧anchors、每其他raw年首个成功日、固定hash补足，不第二遍完整1.26GB。具体名单已协议固定。

模型/金融/SQL/下载/原生价格/旧suite/DBhash预算全0，来源actual只root一次另绑定最终源码；目前未actual。新权益、总收益、DD、Sharpe、总滑点、交易次数和胜率N/A。原参数/旧结果修改删除0，本期新增仅测量合同；不调用正式/生产/Git。

开始过拟合：新增按收益救参否，同史与source案例择题风险仍是；继续单次连续支持核有价值，无限来源/多指标工程无价值。来源算得出不是原目标完成，数据接受后才决定公平一次模型对照。
