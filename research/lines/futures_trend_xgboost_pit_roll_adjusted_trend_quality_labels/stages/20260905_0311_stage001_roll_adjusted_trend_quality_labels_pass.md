# Stage001逐合约换月调整趋势质量标签通过

- line_id：`futures_trend_xgboost_pit_roll_adjusted_trend_quality_labels`
- 当前模式：标签数据资格研究
- 记录时间：2026-09-05 03:11 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `codex/stage130-option-probe`
- 阶段性质：唯一授权的未来close读取与标签资格执行；不是模型、回测或上线。
- 是否重要突破：否；只是模型研究前置数据合同通过。
- 是否触发A/B：否；未改正式逻辑回归、策略或生产配置。

## 外部调研与判断

- AQR长期趋势研究支持多空双向时间序列动量；CME连续期货方法和Zipline开源实现均要求显式处理换月价格不连续；XGBoost官方LTR要求qid内相关性标签。
- 我的判断：逐leg同合约log return是本地已有实际合约路径下最直接、可审计的换月调整方式。主标签同时奖励净趋势幅度并扣除沿最终净趋势方向的路径最大回撤，但它仍只是市场路径代理，不能替代真实策略成交和账户回撤。

## 本次变更

- 新增核心：`tools/roll_adjusted_trend_quality.py`。
- 新增runner：`tools/stage001_roll_adjusted_trend_quality_labels.py`。
- 新增测试：`tests/test_roll_adjusted_trend_quality.py`、`tests/test_stage001_roll_adjusted_trend_quality_labels.py`。
- 新增参数：20日固定路径、5级relevance、qid最小宽度30、公式容差`1e-12`。
- 修改参数：无。
- 删除参数：无。

## 授权与冻结

- 授权nonce：`6ec60297-d6d8-4f25-aacf-61f62a1e19cc`，已唯一消费。
- 授权receipt SHA256：`981011c8fbda7f3e2ddb7a31fe4669b1ea77697837749091318812a1482f6304`。
- 核心/runner SHA256：`91ccb92f7f8668e6eb5866e161fd18f62921ede6fac20e8ac33040cd14ef6bc7` / `2dff13f11e18c7c334aa0f8f60ee00faf7c2d37b5278353d85ce52816c782ebd`。
- 核心测试/runner测试 SHA256：`23e5e15c28dc4479e9cbcf3bd309a59a11755c8ca6e65dcf19b815476938d824` / `84aac48a9007f60f171c7917595e01c1a101eb1f7e46a0701b7750efc7fb5a1b`。
- 计划/预注册 SHA256：`e51ffe9c78222bc4c5a3b891f0a7a95b181a6ee8c0bce78d2f8747c63a5c26c6` / `02699a9985aa62036e8b971138ee6f037d0a1b1fbb1cce9f3250875516525eb2`。
- 运行前无close预检：11个输入身份稳定，四层上游bundle全通过，路径/leg/特征身份门全通过。
- 测试：本线`10 passed`；全部XGBoost PIT回归`342 passed`；`py_compile`和新线`git diff --check`通过。

## 回测/归因参数

- 数据区间：标签query date覆盖上游1,046个日级qid；每条未来20个交易leg。
- 账户规模：不适用。
- 成本口径：不适用；不是可成交PnL。
- 样本过滤：不删路径、品种或qid，使用全部56,272条到期安全路径。
- 策略/归因口径：同实际合约相邻端点log return；换月处不比较旧合约与新合约；主标签为`abs(20日log return)+方向化最大回撤`。

## 结果

- 决策：`stage001_roll_adjusted_trend_quality_labels_pass_allow_model_preregistration_only`，8/8硬门通过。
- 路径/qid/leg：`56,272 / 1,046 / 1,125,440`。
- qid宽度最小/中位/最大：`49 / 53 / 61`。
- qid主标签唯一值最小：`49`；relevance等级最小：`5`。
- 逻辑close读取：`2,250,880`；缺失/无效端点`0`；跨合约价格比较`0`。
- 换月leg：`29,360`；包含换月的路径：`27,970`。
- 未来净方向：负`29,316`、零`1`、正`26,955`；方向只用于标签审计。
- 方向化最大回撤严格为负路径：`56,271`；主标签为负路径：`28,524`。
- 四类公式最大误差：均为`0`。
- 期末权益：不适用，未回测。
- 总收益：不适用，未回测。
- 最大回撤：不适用，标签中的路径回撤不是账户回撤。
- Sharpe：不适用，未回测。
- 总滑点：不适用，未回测。
- 总交易次数：不适用，未回测。
- 胜率：不适用，未回测。
- XGBoost fit/predict、策略回测、true engine、sealed holdout、CTP、订单、生产写入：全部`0`。
- 独立reviewer：不需要；本阶段没有回测数据或策略效果结果。

## 输出文件

- bundle：`artifacts/stage001_roll_adjusted_trend_quality_labels/`，约28MB。
- manifest SHA256：`284c55459ecd77f68cb4f0721659312ca9422cd720d7d48605ab0c918ac6f7a2`。
- summary SHA256：`387b3876fd334817f9be6b53239656a588b3e344d5ca832237ca8ab7fde42c52`。
- labels SHA256：`b6e40cfcafdca42de5500480f1680e167c7a862ca573501a3af1ede3a4cc054d`。
- leg returns SHA256：`59a6e46bed3238b815436535de8f0e18679ccf6a10095abd1eabe5a22883e15b`。
- qid diagnostics SHA256：`1fcd7a170b2987eb2b92787d3298ad047e887a9b034d482583f5aca53224c727`。
- `--verify-only`：7项产物、11项输入、0错误。

## 结论

- 本阶段结论：标签工程通过。它消除了固定合约到期缺失与换月跨合约伪收益，并把上涨/下跌趋势统一成方向中性的趋势质量监督目标。
- 是否进入下一步：是，只允许模型OOS预注册。
- 下一步：固定沿用既有浅层XGBRanker参数和时间序列walk-forward，不根据本阶段标签分布调参；先验证模型是否能稳定预测组内趋势质量，再决定是否允许真实引擎A/C。

## 过拟合反思

- 运行前判断：否，但后续风险高。
- 运行后判断：本阶段本身否。
- 原因：公式、窗口、全样本、门禁和失败决策均在首次close读取前冻结，唯一执行没有参数搜索、删样本或补洞。Stage001通过不降低后续模型的过拟合风险。

## 继续价值反思

- 运行前判断：是。
- 运行后判断：是，限唯一模型OOS资格实验。
- 原因：全量标签可复验且非退化，具备检验XGBoost能否预测“幅度大且路径更顺”的必要条件；尚无理由进入生产或宣称收益/回撤改善。

## 合入建议

- 是否更新本线`LINE.md`：是，已更新。
- 是否更新`research/registry.md`：是，登记标签通过但无效果结论。
- 是否追加根目录`memory.md/back_log.md`：否；不是正式候选、回测突破或跨线合入。
