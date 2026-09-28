# Stage000 CFFEX宏观状态base-margin残差合同

- line_id：`futures_trend_xgboost_cffex_macro_state_residual`
- 当前模式：day；用户已明确授权本设计及后续同线操作默认授权。
- 记录时间：2026-09-04 17:10 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `codex/stage130-option-probe`
- 阶段性质：新增独立经济信息源的新XGBoost研究线；未读标签、未训练、未回测。
- 是否重要突破：否。
- 是否触发A/B：是；只冻结未来A/B/C，Stage001不执行模型。

## 外部调研与判断

- 中金所公开历史下载页：<https://www.cffex.com.cn/lssjxz/>；月度ZIP固定形状为`/sj/historysj/YYYYMM/zip/YYYYMM.zip`，内部日行情为`YYYYMMDD_1.csv`。
- 公开参考实现同时使用中金所单日CSV与月度ZIP：<https://github.com/304341047-cmyk/futures_exchange_daily_data/blob/main/crawlers/cffex.py>。
- XGBoost官方说明已有模型raw margin可作为`base_margin`，二分类任务必须使用log-odds：<https://xgboost.readthedocs.io/en/stable/tutorials/intercept.html>。
- 商品与股票、债券的相关结构会随周期变化，跨资产状态具有独立经济机制：<https://www.nber.org/papers/w10595>、<https://www.nber.org/papers/w21243>。
- 仓内CFFEX简单动量直接overlay曾出现全周期漂亮但留一贡献日和任意起点不稳；本线不交易CFFEX、不复用Stage115组合形状，只把跨资产状态用于商品选品残差。
- 我的判断：继续调前一108特征浅树属于结果后救参；新增CFFEX状态并冻结低维交互，才是可证伪的新机制。

## 正式身份与冻结输入

- 正式CURRENT SHA256：`f17c0f6bfeea4a08ec7c22a1eb63d4b51e4cfb2472f1ce07fac8ce2cc570b219`。
- 正式release：`m0005_20260901T165450+0800_1961d98ccb2b`；strategy：`ai_top10_plus_fu_official_live_v1`。
- 正式LR代码SHA256：`7734d1768728a4e591b80e98da2b5bac90636904dad82e0fed5f331a6eb45de4`。
- 正式18品种universe代码SHA256：`8a149c49075d85d25f27146a8f3c2de3bea1971e3bd0d20a36ed9104b636997f`。
- 前序无标签fold-plan SHA256：`a14fbde27943e1c73eaa8c1e2ea14834e212616e82fe024ba193697369a25e6c`。
- 前序Stage001 summary/manifest SHA256：`63c63d729d693ac7cecb44ff3cefac2100c10dea7a2a4a13a2b3d550fffa0aa1` / `9d24f6e62ecf315af8dd3b08a7f0d444705fbfcba2752581f0942e08ad498c2d`。
- 前序XGBoost参数实现SHA256：`782d76b8620db93a5a760ba9e838333e237439b2b99ae0b65989115f99a8a1c4`。
- 以上文件只读复用；运行前后size/mtime/SHA必须一致。

## 官方源冻结合同

- 月份精确为`201906..202605`，共84个月；只允许中金所月度ZIP，不允许TqSdk主力日历、共享`.vntrader`数据库或第三方补值。
- 预审冻结：84/84下载成功、日CSV `1,695`、ZIP总字节`26,066,955`、原始行`847,781`、核心合约行`35,595`、重复键0。
- 聚合身份算法按月份升序执行`sha256(month_bytes || sha256(zip_bytes).digest())`，冻结值`6309d58c005e4409d9961c2197ae67e2a31a9c1c7904a1254f5656ddd00e5e39`。
- 原始84个ZIP必须持久化到本线final artifact；每月记录URL、字节数、日文件数和SHA256，支持断点复用但复用前必须重验SHA/ZIP结构。
- 只保留`IF/IH/IC/T/TF/TS`期货合约；期权、`IM/TL`和其他产品全部排除。

## PIT主力与收益

- 日期`t`的合约只能依据该合约在前一中金所交易日`t-1`的持仓量选择；持仓量并列时依次按`t-1`成交量降序、合约代码升序。
- 候选合约的`prior_date`必须精确等于全市场前一交易日；禁止用更早的陈旧持仓量。
- 换月日和每个产品首日收益固定为0；同合约连续日才使用收盘价涨跌，禁止把换月价差当收益。
- 六个产品均须精确`1,694`个选择日，首日`2019-06-04`、末日`2026-05-29`；未来行、fallback、重复键均为0。

## 冻结宏观与板块特征

七项月度宏观特征：

1. `cffex_equity_momentum_60d`：IF/IH/IC等权日收益的60日复合收益。
2. `cffex_rates_momentum_60d`：T/TF/TS等权日收益的60日复合收益。
3. `cffex_equity_vol_ratio_20_120`：股指因子20日波动率/120日波动率。
4. `cffex_rates_vol_ratio_20_120`：国债因子20日波动率/120日波动率。
5. `cffex_equity_rates_corr_60d`：股指与国债因子60日相关系数。
6. `cffex_equity_breadth_60d`：IF/IH/IC中60日复合收益为正的比例。
7. `cffex_equity_dispersion_60d`：IF/IH/IC各自60日复合收益的横截面标准差。

四个固定板块及正式18品种：

- `metals`：`au.SHFE/cu.SHFE/lc.GFEX/si.GFEX`。
- `ferrous`：`SM.CZCE/rb.SHFE/jm.DCE/hc.SHFE`。
- `agriculture`：`OI.CZCE/AP.CZCE/CF.CZCE/lh.DCE`。
- `chemicals_materials`：`MA.CZCE/SA.CZCE/FG.CZCE/SH.CZCE/ru.SHFE/sp.SHFE`。

模型特征固定为7个宏观值、4个板块one-hot和28个`宏观×板块`显式交互，共39项；禁止产品ID、年份、月份、标签、正式108特征或事后新增字段。

## Stage001硬门

1. 正式身份、前序fold-plan/summary/manifest/参数实现运行前后SHA一致；正式release和strategy精确匹配。
2. 官方源84个月、1,695日文件、26,066,955字节、847,781原始行、35,595核心行、重复0、聚合SHA精确匹配。
3. 六个PIT主力各1,694日，首末日精确；未来、陈旧prior-date、fallback、换月非零收益均为0。
4. 前序fold-plan重建出77个正式eval-date和50个OOS测试月；77/77精确有因子日且120日窗口完整，50/50 OOS完整。
5. 月度宏观表77行/7特征；交互面板1,386行/18品种/39特征；非有限值0，每月18品种，每个板块计数固定4/4/4/6。
6. 七项宏观特征各自唯一值不少于20且标准差大于0；每行one-hot和为1；交互值与对应宏观值逐值一致，非所属板块交互为0。
7. 标签值、模型fit/predict、策略回测、holdout、CTP、订单API和生产写入全部为0；nonce绑定receipt、运行事件账本、失败bundle和原子发布必须可耐久复核。

通过：`stage001_cffex_macro_contract_pass_allow_stage002_preregistration_only`。

失败：`stage001_cffex_macro_contract_fail_close_no_labels`。失败后不删月、不降覆盖、不改窗口/板块/特征或换源救援。

## 未来Stage002与晋级边界

- A：正式LR；B：39特征standalone XGBoost，仅诊断；C：同一XGBoost以A raw margin作为`base_margin`，唯一晋级候选。
- B/C沿用前序固定32棵深度1参数，不扫描、不early-stop；A/C使用同一50个PIT development folds和900行OOS。
- C必须相对A同时改善加权logloss与月均Rank IC，Top10变化至少8个月/3年，收益和回撤代理、leave-best、联合命中和每个变化年份全部严格通过。
- 代理通过后先独立review，再运行development真实C9 A/C；真实引擎要求全周期收益严格提高、最大回撤严格降低，并通过多起点、年度、成本和留一贡献期稳健性，才能讨论holdout或正式接入。

## 回测记录占位

- 期末权益、总收益、最大回撤、Sharpe、总滑点、总交易次数、胜率：Stage001均不适用。

## 过拟合反思

- 运行前判断：Stage001否；未来Stage002高风险。
- 原因：源、月份、特征、板块、模型参数和效果门均在标签前冻结；历史只有77个月，任何失败后改窗口、板块或参数都属于结果后过拟合。

## 继续价值反思

- 运行前判断：有，限Stage001。
- 原因：84个月官方源的内存预审已证明77/77月末可覆盖；持久化身份、PIT和表达合同仍必须独立通过。
