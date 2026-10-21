# Stage659：ESR语义审查，暂不训练Corn单列

时间：2026-10-21 13:12 CST；研究线`futures_full_market_long_signal_ai`。本次非重要突破。

结论：Corn净合同变化区别于旧WASDE产量修订，但仅支持玉米局部假设。原family-heldout若排除Corn就没有对应域训练支持，不能靠其他94族不变或回A证明通用性。目前不立即训练；先658实际release/修订边界，再由root冻结有界、经济映射明确的多商品ESR来源补齐与单一数量增量设计。没有授权新GET、特征或训练。历史研究无需等今日日线。

新增：来源语义及方法记录。新增/修改/删除策略参数均无；无删除或修改旧结果。1951行/1919周，32个Ending+Starting同周双身份，另5期只有Ending。1913个同MY相邻7日对，累计出货差分全部等于当周出货；净销售与未交付差分加出货有59处差异，未擅自修复。负净销售73/43保留。跨MY的current/next交叠不可直接相加。

规范73KB读取总2次：首次载入后错误列名KeyError，root授权一次纠正重读，成功语义遍历1次。0重读834KB、0新ESR报告GET、0金融标签/模型/行情、0SQL/特征join/fit/cash。全线563实际fit、294完成现金及1旧partial不变。期末权益、总收益、最大回撤、Sharpe、滑点、交易次数及胜率全部N/A。

网上与GitHub原资料已读：USDA法规/项目说明/2026手册，Patterson-Brorsen原1993摘要、SDK维护者ESR代码。判断：数量需相对事前可知信息和季节性识别，当前不是市场共识surprise或首发PIT；不把周报论文结论冒充国内证据。

开始及结束新增按成绩调参过拟合均否；同史长期择题风险高。继续Corn单列立刻fit价值不足；继续解决多商品可迁移测量有条件有价值。原629、646、657保持，未更改正式/生产、LINE/registry或根总账。

完整报告：[report.md](../outputs/stage659_esr_semantic_method_review/report.md)。可审计语义结果：[source_semantics.json](../outputs/stage659_esr_semantic_method_review/source_semantics.json)。
