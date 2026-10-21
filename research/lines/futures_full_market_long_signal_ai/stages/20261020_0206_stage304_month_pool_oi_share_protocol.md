# Stage304：真实成交月份池lag1 OI份额一次固定实验

- line_id=`futures_full_market_long_signal_ai`；2026-10-20 02:06 CST；当前分支`codex/ai-training-data-expansion`；研究only、非重要突破、非正式晋级。上一goal turn为progress：298完整独审/299结案与300/301去重已完成，新增6fit/4cash、累计447/242。
- 用户目标原样保持：全市场全部品种的高质量做多识别，再独立检验极小止损和增加投注；不以正式月池为母体。

## 调研与判断

302已限定GO的新观测：旧084/085只保留代表epoch两lag的deltaOI/V；新的跨月存量份额无法由旧52或该差分恢复。[Hong2001作者原文](https://www.columbia.edu/~hh2679/hong-futures.pdf)支持OI期限分布可反映套保期限/基差风险，但不提供统一long收益符号；[CME官方roll示例](https://www.cmegroup.com/trading/paceoftheroll/user-guide.html)只是机制背景。GitHub/既有代码复用判断沿302的原source接口核对，不复制外部策略。源已有，当前不下载新行情。

root判断：有一次有限证伪价值。它不是重开旧deltaOI/V、299reopening或已关闭log曲率包，也不是OI越高越看多的规则。现有clean排除零成交填充，故只回答accepted真实成交月份池份额；全上市OI总份额/真实资金迁移不在本实验可识别范围。若实际失败，不沿该单量换池、lag、分母或模型救参。

## 唯一量与缺失

`v=source_calendar[u_index−1]`，P为精确同产品(含普通/F独立身份)、同v、accepted且正成交量的原真实月份行。q=query在v的canonical OI除P内OI总和；P不以当前u feature-ready、D有价、经济资格、容量、未来是否闭合或最后是否选中筛。P内任一OI/单位未知或负数使整个pool unknown；query缺v不carry；sumOI0 unknown；query真OI0且sum正为合法q0；单月池q1合法。不除二、不加epsilon/log/winsor/排名/近远月/滚动窗。

305最多一次必要native窄字段SELECT及一次129三身份字段流，不读价格/标签；输出全1552456 aligned q和新紧凑OI来源证据，0旧OHLCV复制/大库hash/重资格。全98/399252母体保留，q缺失外部z0回到原52分数，无新learned missing/ID/交易拒绝门。lag1仍是历史归档假设，不冒充first-seen PIT。

## 唯一模型与金融合同

130原6fold的52coef/intercept/scaler、成熟ID、原sample_weight和net_R_stress完全固定。每fold只对训练finite q按原w定中心/尺度，缺z0；唯一无截距Ridge1残差系数`gamma=sum(w*z*(y-s52))/(sum(w*z*z)+1)`，不重归一available-subset目标，不强迫符号。最多6新fit，禁止旧52 refit。

完整1933480前向分数，main与held并集各161014母行；156同K先D<K再positive argmax及普通/F family priority。control主156/held205直接复用；允许新选、取消及换月份，不能只过滤旧4365。held原129first-exit stressR按family-u再equal-u，未知不同动作保留；它不是K资金目标，因此main动作变化仍完整做原4新cash，不因heldR符号跳过经济检验。

最多4新cash=2020连续/2023独立空仓×base/stress，100万，截至2026-10-16。0.25N/20low/K/anchor/容量/费用滑点/预留与D仅减量不变；family.0025、total.02、margin.25、buffer1.1。旧157四控制只引用0回放，0新label/下载。完全执行等价须独立核过才skip候选cash。两stress都必须权益严格更高且DD严格更浅；base描述，held已知不害必要，unknown/时点/依赖另限制。CI沿070固定252日块/2000次每日log配对，2026partial、费用/滑点/净胜率/集中/open/stale/执行unknown全披露。

308只一次有限静态审查及实际后完整新源/模型/全选择/新资金/置信度独立审查，不重训/重放/重hash旧大数据。实际每phase须root精确新代码和绑定授权，当前仅允许实施新305/306/307及必要tiny边界，实际尚未开始。若失败关闭固定包，不改sign/pool/denominator/lag/window/normalizer/product/year/model/threshold/target/stop/risk救参。

## 记录与反思

本阶段尚0新actual fit/cash/SQL，447/242不变。新增实施参数仅q定义及六个将来scalar；旧止损/风险/手续费/资金参数修改删除0，回测结果新增修改删除0，财务指标均N/A。完整机器协议SHA `729aa21945cc9dc0f446485dd2671a970cec443f1c32783a083b99ce10ffe6a4`，bytes 27686。

开始新增按成绩调参过拟合：否；同史适应性研究风险：是。继续这个不同观测的单次反证：有价值；补全上市OI资格工程、重跑旧基准或扫描参数：无价值。目标仍active，尚无稳定alpha/窄损封顶/加注/正式资格。不改其他线、正式版、生产、CTP、邮件、launchd或Git。
