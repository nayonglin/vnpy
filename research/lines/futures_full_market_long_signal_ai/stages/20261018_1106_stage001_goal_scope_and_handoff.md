# Stage001：全市场全品种做多目标与跨线交接

line_id=`futures_full_market_long_signal_ai`；2026-10-18 11:06 CST；重要突破版本：否，本次为用户目标变更后的范围冻结与工作重定向。

用户明确新研究版在全市场全品种寻找超高质量**做多**信号，不限正式 AI 月池。原线 19 产品多空事件表不能满足此母体；因此新建独立线，继承已有数据/失败记录而不覆盖正式策略或旧线历史。分支仍为 `codex/ai-training-data-expansion`，无工作树。

本次按 brainstorming 完成目标回述及有限数据研究设计：先核六所全市场清洗资料实际存在和读取覆盖，随后定义品种×决策日做多/不做的事前机会空间。用户已持续授权自主设计和研究，本次不重复形式性审批；不因原方案已经做了工程而继续旧 12/24 混合多空 pilot。实现新候选前，路径/执行/标签定义另作有限冻结。

## 本次实际读到的来源及判断

- 读取 `research/registry.md`，未有对应全市场 long-only AI 研究线；已有 `futures_trend_full_market_ai_filter_002risk` 是关闭的旧分数/veto 路线，不借新名称复活它。
- Stage265 原范围/结果和旧线 LINE 明确六所真实合约、退市与 DCE F 历史，不能将当日目录或主连当完整市场。本机确实存在 `outputs/stage265_deep_daily`、`stage266_clean_daily`、`stage266_independent_validation`、`stage267_*` 和 `stage269_*`；已实际列目录并读取 catalog 小清单，尚未在本线重新消费全量清洗数据。
- Stage265 记载 10,547 真实交割合约、97 有行情历史代码及截至 2026-10-16 的补尾，这是既有来源报告，不在本阶段冒称已复验训练/交易资格。Stage266/267 已有清洗及读取合同可复用，原数据库/大档案不重下、不全量重 hash。
- 旧155唯一导出真实 exit0；156独立审查真实 exit0，C/I/M=0/0/0，只接受旧身份层。独立 receipt 路径 `../futures_trend_triple_screen/outputs/stage156_native_event_linkage_review/review_receipt.json`，交接 SHA `86216ef93bc2a51301a2f0439a700c45ccef39d5e8d896ad37855f7a0c5c54f6`。root 在接受新线实际数据前仍按产物核具体范围，不拿该 receipt 代全市场数据审查。

## 网页/GitHub调研与独立判断

已重新查交易所规则与 GitHub 的六所日线接口说明；[SHFE 交易规则](https://edu.shfe.com.cn/TradingAssistant/RulesIntroduction/518.html)将期货/期权分别定义；[AKShare 官方仓库](https://github.com/akfamily/akshare)可作为来源接口参考，现有官方/固定归档和清洗资料优先复用，不安装网络上同名“下载 skill”。

本轮已读 [Mlfin.py 标签实现文档](https://mlfinpy.readthedocs.io/en/latest/Labelling.html)及[并发标签源码](https://mlfinpy.readthedocs.io/en/doc-staging/_modules/mlfinpy/sampling/concurrent.html)：首触达和事件结束区间是有用参考，但 close-series 示例不替代真实分钟先后、gap、费用、换月、整数部分退出或本仓库 native 退出。官方 [MlFinLab 标签源码页面](https://github.com/hudson-and-thames/mlfinlab/blob/master/mlfinlab/labeling/labeling.py)当前为公开接口骨架，多处 pass，不称完整可运行实现；未下载/安装/运行第三方代码。

判断：全市场数据提供更多机会与产品留出空间，不能靠增加行数证明预测优势。新机会母体不以 C9 原信号或正式月池预筛；之后须固定可执行目标和信息集，识别能力、止损和投注分别检验。

## 变更、指标和下一步

新增本线 LINE 与本文、registry 单行发现入口；不新增策略/模型/交易参数，不改正式代码/配置。金融/训练/下载/订单均0；新增/修改/删除回测结果0，期末权益、收益、最大回撤、Sharpe、总滑点、交易次数、胜率均N/A。

上一轮目标推进性质：旧155完成的真实身份证据与156独立审查属于进展，但不等于新目标母体完成。当前新目标已改变下一步：转本机六所 clean reader 全市场覆盖和 long-only 机会设计，原旧池 pilot 取消。

开始/结束新增过拟合：否，本次范围来自用户而非历史收益选择；后续稀有信号/极窄分母/杠杆联合寻优风险高。继续价值：是，现有全市场资料可直接验证范围和可用状态。当前无 alpha，目标保持 active，`production_qualified=false`。
