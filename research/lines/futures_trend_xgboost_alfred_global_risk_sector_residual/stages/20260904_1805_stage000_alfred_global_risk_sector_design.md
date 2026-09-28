# Stage000 ALFRED全球风险状态base-margin板块残差合同

- line_id：`futures_trend_xgboost_alfred_global_risk_sector_residual`
- 记录时间：2026-09-04 18:05 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `codex/stage130-option-probe`
- 阶段性质：新增独立PIT经济信息源的XGBoost研究线；未读标签、未训练、未回测。
- 是否重要突破：否。
- 是否触发A/B：是；本阶段只冻结未来A/B/C，Stage001不执行模型。
- 用户授权：后续研究操作默认授权；生产写入、真实报单与不可逆操作仍保持硬闸门。

## 外部调研与判断

- ALFRED官方说明明确：vintage date用于下载历史某日实际存在的数据；普通FRED当前CSV不能替代历史快照：<https://alfred.stlouisfed.org/help/downloaddata>、<https://alfred.stlouisfed.org/>。
- `DEXCHUS`是每日人民币兑美元汇率，`DTWEXBGS`是每日广义美元指数，均来自美联储H.10；`VIXCLS`是CBOE每日收盘隐含波动率：<https://fred.stlouisfed.org/series/DEXCHUS>、<https://fred.stlouisfed.org/series/DTWEXBGS>、<https://fred.stlouisfed.org/series/VIXCLS>。
- NBER发现部分商品货币对全球商品价格具有样本外预测力；BIS同时指出疫情后美元与商品价格的传统负相关发生结构变化。因此本线不预设固定方向，而使用固定浅层非线性残差模型：<https://www.nber.org/papers/w13901>、<https://www.bis.org/publications/working-paper-1083-commodity-prices-and-us-dollar>。
- 仓内旧108特征、账户上下文、市场广度、期限结构、基差/持仓、全市场单槽和CFFEX国内宏观状态均已独立审计或关闭；未发现`DEXCHUS/DTWEXBGS/VIXCLS`历史快照进入正式18品种XGBoost排序层的证据。
- 气象和电力负荷也是未覆盖机制，但需要事后选择产区、区域、作物历与产品映射，当前研究自由度高于三项统一全球状态，暂不混入本线。
- 我的判断：本线具有独立机制和可复验PIT源；收益改善并不预设成立，必须逐级过无标签合同、development OOS与真实引擎硬门。

## 正式身份与冻结输入

- 正式CURRENT SHA256：`f17c0f6bfeea4a08ec7c22a1eb63d4b51e4cfb2472f1ce07fac8ce2cc570b219`。
- 正式release：`m0005_20260901T165450+0800_1961d98ccb2b`；strategy：`ai_top10_plus_fu_official_live_v1`。
- 正式release manifest SHA256：`d62e58d01284e30b28054387592604862ffeff6e55a13c63192793e95bc55c21`。
- 正式LR代码SHA256：`7734d1768728a4e591b80e98da2b5bac90636904dad82e0fed5f331a6eb45de4`。
- 正式18品种universe代码SHA256：`8a149c49075d85d25f27146a8f3c2de3bea1971e3bd0d20a36ed9104b636997f`。
- 前序无标签fold-plan SHA256：`a14fbde27943e1c73eaa8c1e2ea14834e212616e82fe024ba193697369a25e6c`。
- 前序Stage001 summary/manifest SHA256：`63c63d729d693ac7cecb44ff3cefac2100c10dea7a2a4a13a2b3d550fffa0aa1` / `9d24f6e62ecf315af8dd3b08a7f0d444705fbfcba2752581f0942e08ad498c2d`。
- 前序XGBoost参数实现SHA256：`782d76b8620db93a5a760ba9e838333e237439b2b99ae0b65989115f99a8a1c4`。
- 以上文件只读复用；Stage001运行前后size、mtime与SHA必须一致。

## ALFRED PIT源合同

- series精确为`DEXCHUS/DTWEXBGS/VIXCLS`；日期精确为前序fold-plan重建的77个正式eval-date，最早`2020-01-23`、最晚`2026-05-29`。
- 每个`series + eval_date`只能请求一次独立历史快照，共`3 x 77 = 231`份。URL固定为`https://alfred.stlouisfed.org/graph/alfredgraph.csv?id={series}&cosd=2019-01-01&coed={eval_date-1日}&vintage_date={eval_date}`。
- 响应列必须精确为`observation_date,{series}_{YYYYMMDD}`；只允许观察日期严格早于eval-date，禁止普通FRED当前值、当前修订值、跨快照回填和本地手工补值。
- 无标签内存预审为231/231成功、总字节`4,624,211`。聚合SHA算法按eval-date升序、series固定顺序执行`sha256((date + '|' + series + '|').encode() || sha256(content).digest())`，冻结值`7d312d36015af3e6e09d0e6b3157f2a766bbb0a31ff26b20309161784404d20f`。
- 每份原始CSV必须持久化；每份记录URL、字节数、SHA256、首末有效观察日、有效行数和最新观察滞后。
- 预审最新观察滞后：`DEXCHUS`和`DTWEXBGS`最小/中位/最大`3/6/10`日，`VIXCLS`为`1/1/3`日；三个series均77/77快照至少有253个有效历史水平值，未来行0。
- 获取并发固定为4，单份快照允许最多五次有界线性退避。预审曾观察到一次瞬时HTTP 404，同一URL随后返回200，因此每次失败与重试都必须写事件账本；五次耗尽即技术失败，不得换到当前FRED或第三方源。
- 已有快照只可在URL、SHA、列名和CSV语义全部复验后复用。

### 标签前传输实现补充（2026-09-04 18:48 CST）

- 首次`requests`实现与第二次Python标准库`urlopen`实现均在首批4个请求连续五次读超时；两次运行分别原子发布技术失败包`stage001_alfred_global_risk_contract_failure_3b7d774b2fc2df10`和`stage001_alfred_global_risk_contract_failure_43749de32d22a482`，manifest复验通过，原始快照、标签、模型与回测输出均为0。
- 同一URL用系统`curl`最小请求可立即返回；带浏览器伪装请求头会出现HTTP/2 `INTERNAL_ERROR`或HTTP/1.1零字节超时。根因限定在客户端传输兼容性，不是URL、vintage或数据缺失。
- 在未读取标签的前提下，正式传输实现固定为`/usr/bin/curl --http1.1`，不发送自定义请求头，不经shell，连接上限15秒、单请求网络上限30秒、子进程上限45秒；HTTP错误、非零返回、空响应继续失败关闭。获取并发仍为4、每份最多五次，URL、源、日期、SHA、特征与全部硬门不变。
- 修订后单份正式URL验证为4,876字节、261个有效观察、最新观察严格早于eval-date；4并发无标签小样本为4/4成功、21,472字节、1,090个有效观察、约9.3秒。该验证只证明传输可用，不构成特征或收益证据。

## 冻结三项状态特征

所有窗口都在各eval-date独立历史快照内计算，`n日`表示最后`n`个有效观察，不是自然日；不得跨快照拼接修订版本。根据标签前独立审阅，本线删除60日重复窗口、相关项和VIX裸变化，避免77个月样本承载过宽表达。

1. `cny_depreciation_shock_20d`：`log(DEXCHUS_last / DEXCHUS_lag20) / (sample_std(last252 daily log returns) * sqrt(20))`；正值表示人民币相对美元走弱。
2. `broad_usd_shock_20d`：`log(DTWEXBGS_last / DTWEXBGS_lag20) / (sample_std(last252 daily log returns) * sqrt(20))`。
3. `vix_stress_percentile_252d`：最新VIX在最后252个有效水平值中的经验分位，定义为`mean(window <= latest)`；只表示严格滞后的全球风险压力，不预设对任一板块的固定方向。

无标签预审中三项均77/77有限，唯一值依次为`77/77/62`，样本标准差依次约为`1.0843181/1.0793566/0.3271313`，取值范围依次约为`[-2.06785,3.30190]/[-1.97150,3.08177]/[0.015873,1]`。这些只用于证明表达可行，不代表与标签相关。

## 板块与模型表达

- `metals`：`au.SHFE/cu.SHFE/lc.GFEX/si.GFEX`。
- `ferrous`：`SM.CZCE/rb.SHFE/jm.DCE/hc.SHFE`。
- `agriculture`：`OI.CZCE/AP.CZCE/CF.CZCE/lh.DCE`。
- `chemicals_materials`：`MA.CZCE/SA.CZCE/FG.CZCE/SH.CZCE/ru.SHFE/sp.SHFE`。
- 面板特征固定为3个全球状态值和12个`状态 x 板块`显式交互，共15项、77月、18品种、1,386行。静态板块one-hot被明确删除，避免模型借本线学习与全球状态无关的永久板块偏置。
- 由于同一月同一板块的状态特征相同，Stage001必须明确报告有效`month x sector`状态为`77 x 4 = 308`，不得把1,386产品行宣称为1,386个独立宏观样本。
- 禁止产品ID、年份、月份、标签、正式108特征、CFFEX特征、气象、电力或事后新增字段。共享状态本身不改变横截面排名，只有预声明板块交互可以在保留LR产品内排序时改变板块残差。

## Stage001硬门

1. 正式身份、前序fold-plan/summary/manifest/参数实现运行前后SHA一致；正式release和strategy精确匹配。
2. 231/231原始快照成功；总字节`4,624,211`、聚合SHA精确匹配；每份URL、列名、日期与vintage suffix精确。
3. 每个series 77/77快照、每份至少253个有效水平观察；观察日期严格早于eval-date，未来行、当前FRED fallback、第三方fallback、重复身份均为0。
4. 77个正式eval-date和50个OOS测试月与前序fold-plan精确一致；最新观察滞后分别不超过`10/10/3`自然日。
5. 月度状态表77行/3特征；交互面板1,386行/18品种/15特征；非有限值0，每月18品种，每板块计数固定4/4/4/6，有效`month x sector`状态精确308。
6. 三项状态特征唯一值精确`77/77/62`且样本标准差大于0；所属板块交互逐值等于状态值，非所属板块交互为0；静态板块one-hot列数为0。
7. 标签值、模型fit/predict、策略回测、holdout、CTP、订单API和生产写入全部为0；nonce绑定receipt、追加式事件账本、失败bundle、递归manifest和原子发布必须可耐久复核。

通过：`stage001_alfred_global_risk_contract_pass_allow_stage002_preregistration_only`。

失败：`stage001_alfred_global_risk_contract_fail_close_no_labels`。失败后不删日期、不放宽滞后/窗口、不改序列、特征、板块或源，不进入Stage002。

## 未来Stage002与Stage003边界

- A：正式LR；B：15特征standalone XGBoost，仅作信息量诊断；C：同一XGBoost以A raw margin作为`base_margin`，C为唯一晋级候选。
- B/C沿用前序固定32棵深度1参数，不扫描、不early-stop；A/C使用同一50个PIT development folds和900行OOS预测。
- Stage002必须相对A同时改善加权logloss、月均Rank IC、未来策略利润代理与未来路径回撤代理；Top10变化至少8个月且跨至少3年，leave-best-out收益增量、变化年份、联合收益/回撤命中均严格为正。任一失败即闭线，不跑真实引擎。
- Stage002跑出效果结果后必须拉独立reviewer。只有全门通过，才允许预注册Stage003真实A/C。
- Stage003不得改正式C9、风险、成本、保证金、整数手、相关性、最多持仓或固定`fu`；要求C相对A全周期收益严格提高、最大回撤严格降低，并通过年度、多起点、成本和leave-best-period稳健门，才能讨论holdout或正式接入。
- development全部属于已观察历史，任何通过都不能称独立holdout或线上收益保证。

## 回测记录占位

- 期末权益、总收益、最大回撤、Sharpe、总滑点、总交易次数、胜率：Stage001均不适用。

## 过拟合反思

- 运行前判断：Stage001否；Stage002/003高风险。
- 原因：当前只冻结独立源和表达；77个月样本较少，后续任何看结果后换窗口、序列、板块、树参数、阈值、年份或产品都会迅速过拟合。

## 继续价值反思

- 运行前判断：有，限Stage001。
- 原因：231份严格历史快照已无标签预审通过覆盖与连续性，机制与既有国内价格/持仓/账户特征不同；只有持久化身份、PIT、表达和副作用证据全部通过后，模型研究才有继续价值。
