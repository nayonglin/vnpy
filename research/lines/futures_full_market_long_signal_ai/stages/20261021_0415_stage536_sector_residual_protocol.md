# Stage536：固定产业残差截距协议

- line_id：futures_full_market_long_signal_ai；时间：2026-10-21 04:15 CST；day模式；非突破。
- 上一goal轮分类：进展；537完成精确输入与复用路径清单，但0新fit/cash。本轮执行不等今日日线。
- 独立六所98产品/95family全市场long研究，不是正式C9 A/B晋级。

## 调研与判断

533—535独立排重/科学审查支持一次受限校准。原作者[JMLR论文](https://www.jmlr.org/papers/v6/evgeniou05a.html)支持相关任务正则化，并不证明期货行业alpha；原作者[MTL-TSMOM代码](https://github.com/joelowj/mtl-tsmom/blob/b07fa1d0a3c71bef3d3614e0d8f4233477e42df1/core/model.py)共享LSTM与波动辅助任务，不是行业截距验证。本轮root实际核JMLR摘要，GitHub网页取回失败，代码细节继承534已读记录不冒充重新取回。判断：既有经济分类可成为粗先验，但只可能校准准入，不能创造月份排序或行业择时。

## 唯一冻结设计

协议：`/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage536_sector_residual_protocol/protocol.json`；SHA256 `acd8fcbf9e738e266067179a6b1fe240e09775ade737d1616b73abf4a46cf592`。A为原130冻结52头加155/156日历准入；B加一次固定任意family分组，C加研究前269八类产业分组。原六头/52/scaler/Y/成熟训练/权重/退出/风险全部冻结。每fold原权重再sum1、centered onehot、lambda1、无zscore/新全局截距，新增有效df<=1。8类不是8套模型；共12个B/C小offset fit，0原52重训。

B在原hash两组内置乱同标签多重集合，salt固定stage536-sector-placebo-v1；全局单family产业原样保留（EC），S未知不置乱，F继承family。未知或训练无该组严格delta0。具体映射已随协议落盘，禁止按结果重新抽签。

一次读取129 actions/COMMON/mothers，RAM逐fold恢复原cohort/weight；旧forward scores只流一次，所有旧负分同样参与新选择，使用当前voluntary政策。只改变加性准入，同品种月份差值必须保持。训练支持、EC/S与冷组fallback全部披露。

先模型后资金：C-A与C-B均需两held已知等u均值非负且每个对比至少一held严格正，否则关闭固定方案、0cash。distinct unknown保留NaN且披露，名义triage不是全域/OOS认证。若独审支持再最多B/C各4账共8新cash，复用157 OWN四控制，100万/.25%/2%风险/25%保证金等冻结。财务门与CI见协议，任何失败不扫分类/惩罚/seed/阈值/目标救参。

## 记录与反思

新增协议1及本中文阶段1；新增设计参数仅固定taxonomy/对照及sumw1/lambda1残差offset，原参数修改/删除0。此阶段新fit/cash/SQL/下载0，累计511fit/278完成cash及1旧partial。期末权益、总收益、最大回撤、Sharpe、总滑点、总交易次数、胜率全部N/A。actual后须独立agent全面review。

开始/结束过拟合风险均是且高（同史择题），本轮未按新收益救参；继续价值均有条件是（一次低自由度先验证伪），无边界扩容量无价值。原高收益低回撤/窄损加注完整目标未完成、goal active。下一步538实现fixtures和一次actual，539独审；root根据预声明门决定是否资金，不提交/推送/生产。
