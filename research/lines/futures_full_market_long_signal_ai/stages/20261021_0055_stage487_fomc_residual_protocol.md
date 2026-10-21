# Stage487：公告前流动性与匿名宏观信息包的一次固定实验

- line_id：`futures_full_market_long_signal_ai`；冻结时间：2026-10-21 00:55 CST；非重要突破。沿当前研究分支，不改正式版，不做生产A/B晋级。
- 上一goal轮486已实际完成来源请求与独审，属于progress；本轮不是等待今日线。

## 调研与判断

英格兰银行原研究以公告前成交额解释海外商品冲击异质性，作者GitHub提供FF4/SP500原数值；两者不证明中国全市场延迟25小时后可赚钱。匿名数值规格可避免未经证实的经济正号主张，但跨年代映射、首发PIT仍未认证。判断是：只值一次固定对照，不扩大数据工程或参数扫描。

## 固定实验及实现计划

- [ ] 488：仅54,089个exact epoch/pre请求，clean单边V不二次折半；精确原结算源仅缺列允许既定RQ回退；exact现金乘数。保留zero/missing/nochild来源身份，numeric验证与规则/PIT未知分列。一次SQL/CSV各1读/H5最多2打开。
- [ ] 489：A完整原52模型和分数复用，B校准事件截距与preL，C另加FF4/SP500及两L交互；2020/2023×main/held0/held1×两臂=12个2/6参数微型头，非事件与共同缺失域逐值fallbackA；全161014forward母/98产品95family保留。
- [ ] 491：两臂×2020连续/2023冷启×base/stress最多8新现金，A157自己四账只读。0.25N/单family0.25%/总2%/保证金25%/buffer1.1/原费用滑点K全部不变，复用nativecache无新SQL；每账数值完成先checkpoint，报告失败不重跑金融。
- [ ] 490：一次独立新结果审查，核所有新mask/scaler/12方程/分数与选择/8账/CI；不重跑金融或旧套件，不重扫原大母/元数据。root结案如不支持停止固定包。

L按完整事前候选域等family/child中心化，不用Y；每fold只成熟训练样本计算权重和三scalar缩放，显式常数不罚、其余alpha1，交互后不再scale。same-sample残差而非crossfit，held只留出family标签、可见全市场事前X和相同宏观冲击。C-B是宏观数据与4个额外系数的固定包，不是纯信息因果。缺失不删母，完整政策包含沿用A，不能据可测子集宣称全部品种机制。

## 结果与参数

新增研究参数是固定残差头结构与alpha1，无修改/删除原止损/风险/资金/成本；新增、修改、删除回测结果均0。期末权益/总收益/最大回撤/Sharpe/总滑点/交易次数/胜率现在均N/A。累计481fit/258完成cash及1旧partial。

原252日/2000次配对索引复用；同时比较C-B、C-A（B-A仅披露），主stress收益/回撤/CI严格门及其他窗/held门事前固定。冲击事件数而非5.4万子行决定置信度，未知不同动作不填0。逐年/2026不完整和截至2025的同账增长单独报告，不增加重置账户。

## 反思与后续

开始按新收益调参过拟合：否，尚无actual；长期同史择题风险：高。继续价值：有条件，因为这是真实新外生观测的有限经济检验，而不是已失败模型换窗口。结束再按真实结果反思；无资格提前扩大投注。每一actual需源码/协议/输入绑定的root明确授权、fresh输出和真实进程终态。

协议：`/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage487_fomc_residual_protocol/protocol.json`；53191B，SHA256 `e8bd8f4029170a56aaf5513ce43e2bfaa931def02369f252edae5a6228066582`。仅更新本线stage，root待实际闭环再更新LINE/registry；常规实验不追加根memory/back_log。
