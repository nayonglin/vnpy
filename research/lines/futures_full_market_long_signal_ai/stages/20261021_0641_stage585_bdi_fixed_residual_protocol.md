# Stage585 BDI固定月频残差协议

- line_id=futures_full_market_long_signal_ai；day；2026-10-21 06:41 CST；codex/ai-training-data-expansion；非重要突破，独立正式C9。
- 用户已授权自主设计。沿既有残差pipeline的有限修改，584独立设计GO，协议 /Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage585_bdi_fixed_residual_protocol/protocol.json，SHA c7c7313a8ccac4a292e31ba87c2818f12acf47b9322c4ef289fcc9f8a6a2261a。

## 调研与判断

[原作者Bakshi等](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1747345)、[原作者全文副本](https://signaltradinggroup.com/wp-content/WhitePapers/Baltic%20Dry%20Index%20as%20a%20Predictor.pdf)索引可见三公历月g定义；SSRN直接访问403，不冒称全文已读。[2013原作者新证据](https://www.mdpi.com/2227-7072/1/3/62)与[维护者接口](https://github.com/akfamily/akshare/blob/main/akshare/index/index_spot.py)不证明本策略alpha。2018最终变更和2009以来成分按584官方依据处理。

BDI并非旧52或PMI函数，但运价同时受需求与船队供给驱动，不先规定多头方向。579原额度内重复信号加仓仅条件GO且有时序/批次成本，580当前SGX夜盘领先NO_GO、581旧季节标量NO_GO；root只选BDI，不同时推进三路线。582单GET及583全行+发行人锚点核支持整体level来源：3项min/max/end精确，年均/开年差不凑精确；未认证全日/首发PIT。

## 唯一变更、参数和时钟

仅price/date。先选月内最后weekday正价候选，若在18冲突行则整月endpoint unknown，不退前找替身；坏年/周末隔离且原值保留。不用zde/zdf，缺月不carry，跨2009Jul/2018Mar定义的三个月增长unknown。g_m=log(P_m/P_m−3)，u严格晚于完整m月末，完整中国u收盘后才到原D。可得性仅条件历史重建，不是first-seen或实盘资格。

原52/目标/权重算法/选择月份顺序/止损/risk/资金/成本全固定。A复用旧预测；B known域残差常数，C同常数加一条g斜率，缺失都回A。每折原w在known子集sum1，均值/scale仅同一train子集，lambda1惩罚包括常数。fit不是月等权；来源月等权仅诊断。

新增固定参数3公历月、support60来源月、lambda1；旧参数修改删除0。六fold统一preflight后最多12小head，0原52重训/0cash/0SQL/0下载；用538 compact，0COMMON/334MBactions/57MBtrain_common。全98/95、161014母及1933480前向child、全部scope保留。

## 事前门与实际预算

主全段C-A/C-B均严格正；主2020–22及2023+ C-B均正；两held C-A/C-B均正（来源月等权已知支持机会stressR）。差动作unknown不填0、不授全母体优势。任一门失败：0CI/0cash关闭精确包，不改窗/lag/符号/端点/交互/模型/产品/stop/risk救分。通过也只允许另根授权最多4C现金和独审，非自动晋级或加注。

586先最小实现与必要小行为检查、source-ready；root唯一实际；587完整独审新源/头/选择/报告/门，不重训或回放A。当前新增fit/cash0；期末权益/收益/DD/Sharpe/总滑点/交易次数/胜率均N/A；累计535fit/282完成cash+旧partial1。

## 前后反思

运行前过拟合风险是且高，同史择题不能消失；新增收益后调参否。一次固定新观测有价值，结束仍无成绩，失败就停。完整目标active，LINE/registry待root实际结案统一更新，不动根memory/backlog、正式/生产/CTP/邮件/调度/Git。首次生成脚本含Python保留字语法错误，零文件/零实际实验；本次成功冻结一次，不是策略失败或重跑。
