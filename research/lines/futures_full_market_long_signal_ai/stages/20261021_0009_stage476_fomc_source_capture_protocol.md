# Stage476：仅取得作者FOMC原始事件观测的有界协议

- line_id：`futures_full_market_long_signal_ai`；时间：2026-10-21 00:09 CST；非重要突破；当前完整目标六所98历史品种/95家族高质量long保持。当前为source capture，非候选策略或新回测。
- 上一轮473为progress，15新fit/4C现金及472独审真实完成且固定annual包unsupported；不重跑、不改频率/模型/目标/风险救参。累计481fit/258完成cash及1旧partial。

## 问题、备选和决定

本轮排重分工474/475只读科学审查。K目标对齐、log效用、DOMAIN和事后实际贡献回贴已被旧实验/反事实缺口否决，不能换名复活。精确source-day runway逻辑上是未显式提供的身份状态，但涉及u之后完整交易日历的当时可知性，当前不开发、不做103MB metadata重扫；不是宣称所有期限状态无用。基差动量原论文与GitHub例子有经济依据，但12月滚动两曲线策略与本短期全98识别/执行并不相同，本轮不复制或调窗口。

优先一项独立观测：FOMC公告周围利率和权益原始意外变动，可区分单纯紧缩与经济信息；只先核原表覆盖和时钟，不把海外论文收益或日内公告价差当作中国入场后alpha。未来若检验须保留全母体并有事前异质暴露，Stage270反对同日宏观共同scalar替代全市场排序的边界继续生效。

## 收益前冻结的有限实际预算

JSON protocol SHA `7abe9a1373c09dd107616905b8b9ae4947cb0331b73ac50f74eb9f3fb3a1225b`（2922B）已于实际请求前写入。只请求作者repo提交API一次，解析40hex commit后两个独立raw文件README和source_data/fomc_surprises_jk.csv各一次；3总请求、0retry、25秒timeout、单文件最多2MB。提交失败即停，不回退未锁定main、第三方2025延展或另央行。只解析schema/覆盖/缺失/许可，不下载分钟K线、fit/cash/SQL或旧大输入；不取最终整样本PCA/rotation和月度聚合shock。

作者README描述post测量端窗[t+15min,t+25min)，稀疏时可额外延长最多24h，所以t+24h不一定已终结；未来保守计算窗口上限先取t+25h，此为窗口结束约束，不是GitHub当时首发PIT证明。timestamp时区在README未明确，不能直接赋UTC或纽约；源取得不等于训练就绪。不同时间/窗口的缺值保留未知，不用最终pc1补原始FF4。

## 调研、反思及结果状态

已核[AEA原论文](https://www.aeaweb.org/articles?id=10.1257/mac.20180090)和[作者README](https://github.com/marekjarocinski/jkshocks_update_fed/blob/main/README.md)；它们支持新观测及上文原始定义，不证明全市场异质传导/延迟执行收益。成熟效应广样本证据混合，也不证明长runway一定高收益。没有安装或执行外部代码。

开始新增按收益调参过拟合：否，尚无新收益；同史长期择题风险：是。继续价值：一次小原始观测捕获有条件的是；只有明确新信息及可执行时钟后才设计一次经济反证，不能无限资格工程。当前无新策略/训练/止损/资金参数，无新回测，权益、收益、DD、Sharpe、滑点、交易/胜率N/A。完整目标active未完成，无生产/CTP/邮件/launchd/Git变更，不写根memory/back_log。
