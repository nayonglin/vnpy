# Stage001 ALFRED全球风险状态无标签合同结果

- line_id：`futures_trend_xgboost_alfred_global_risk_sector_residual`
- 记录时间：2026-09-04 18:52 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `codex/stage130-option-probe`
- 阶段性质：严格PIT公开数据源、特征表达和副作用合同；未读取标签、未训练、未回测。
- 是否重要突破：否。数据资格通过只允许Stage002预注册，不是收益证据或正式候选。
- 决策：`stage001_alfred_global_risk_contract_pass_allow_stage002_preregistration_only`。

## 本次变更

- 新增并冻结231份ALFRED历史快照、3项连续全球风险状态、4个板块和15列状态/板块交互表达。
- 新增严格vintage列、未来观察、覆盖、滞后、总字节、聚合SHA、特征唯一值、交互一致性、输入身份和副作用硬门。
- 新增nonce receipt、追加式事件账本、失败bundle、递归manifest、原子发布和离线复验。
- 新增传输参数：固定`/usr/bin/curl --http1.1`、无自定义请求头、无shell、连接上限15秒、网络上限30秒、子进程上限45秒、4并发、每份最多5次有界重试。
- 修改参数：最初`requests`与随后`urlopen`均因客户端读超时失败；在未读取标签的前提下仅替换传输实现，URL、日期、源、特征、SHA和硬门不变。
- 删除参数：删除浏览器伪装请求头；实测该请求头导致HTTP/2内部错误或HTTP/1.1零字节超时，最小请求稳定返回。

## 技术失败留痕

- `stage001_alfred_global_risk_contract_failure_3b7d774b2fc2df10`：`requests`首批请求五次读超时，完整失败manifest通过，原始快照0。
- `stage001_alfred_global_risk_contract_failure_43749de32d22a482`：`urlopen`首批请求五次读超时，完整失败manifest通过，原始快照0。
- 两次失败均未读取标签、训练模型、运行回测或产生生产副作用；失败证据未删除。

## 最终运行与数据门

- 成功nonce：`b7393c6fed3ba03b8b1910938f8ae4c39c50623bb1205db9b4074f2bd9b2f97e`。
- 正式身份：release `m0005_20260901T165450+0800_1961d98ccb2b`、strategy `ai_top10_plus_fu_official_live_v1`；运行前后8项输入身份SHA一致，mismatch 0。
- ALFRED源：`DEXCHUS/DTWEXBGS/VIXCLS`各77份，共231/231；总字节`4,624,211`；聚合SHA `7d312d36015af3e6e09d0e6b3157f2a766bbb0a31ff26b20309161784404d20f`精确命中。
- 每份有效水平数最小/最大`261/1,891`；未来观察0；重复身份0；当前FRED fallback 0；第三方fallback 0；成功运行重试0、复用0。
- 最大最新观察滞后：`DEXCHUS=10`日、`DTWEXBGS=10`日、`VIXCLS=3`日，全部命中合同。
- 正式eval-date 77个，development OOS测试月50个，与冻结fold-plan精确一致。

## 特征与表达门

- 月度状态表77行、3特征；唯一值`77/77/62`，样本标准差`1.0843181031/1.0793566178/0.3271312950`，非有限值0。
- 交互面板1,386行、18品种、15特征，每月18品种；板块计数固定`4/4/4/6`。
- 有效`month x sector`状态精确308；静态板块one-hot列0；所属/非所属板块交互错配单元0。
- 7类硬门`identity/source/eval/feature/expression/side_effect/durability`全部通过，失败门为空。
- 离线manifest复验：241个文件，mismatch 0，未登记文件0。

## 副作用与回测指标

- 标签读取、model fit、model predict、策略回测、holdout读取、CTP连接、订单API、生产写入均为0。
- 期末权益：不适用。
- 总收益：不适用。
- 最大回撤：不适用。
- Sharpe：不适用。
- 总滑点：不适用。
- 总交易次数：不适用。
- 胜率：不适用。
- 新增、修改、删除的回测结果：均无。

## 过拟合反思

- 运行后判断：Stage001本身否；Stage002开始风险高。
- 原因：本阶段只验证标签前冻结的公开PIT源与表达，传输修订不参考标签；但77个月只有308个有效月板块状态，后续任何看结果后改窗口、板块、树参数、阈值、月份或年份都会形成强烈多重试验偏差。

## 继续价值反思

- 运行后判断：有，限一次冻结的Stage002 development OOS模型合同。
- 原因：源、PIT、覆盖和表达门全部通过，且是既有国内行情/持仓/账户特征之外的独立经济状态；但它是否能改善排序尚未知，必须由固定A/B/C和联合收益/回撤代理门证伪，失败即闭线。

## 后续规划和TODO

- 在读取标签前另写Stage002预注册，固定A=正式LR、B=15特征standalone浅树诊断、C=正式LR raw margin作为`base_margin`的15特征浅树残差；C是唯一晋级候选。
- 沿用前序固定32棵深度1参数、50个PIT development folds和900行OOS，不扫描、不early-stop、不改标签。
- 同时要求加权logloss、月均Rank IC、未来利润代理、未来路径回撤代理改善，并通过Top10变化、跨年、leave-best-out和联合命中门；效果结果产生后拉独立reviewer。
- 只有Stage002全门通过并完成review，才允许预注册Stage003真实引擎A/C；当前不得称收益已提高或回撤已降低。
