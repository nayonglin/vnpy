# Stage001 PIT全曲线覆盖审计结果

- line_id：`futures_trend_xgboost_pit_curve_account_labels`
- 当前模式：研究隔离/标签前可行性审计
- 记录时间：2026-09-02 14:04 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `codex/stage130-option-probe`
- 阶段性质：冻结同日逐合约覆盖审计
- 是否重要突破：否
- 是否触发A/B：是；仅完成数据门，不授权策略回测

## 外部调研与判断

- Gorton、Hayashi、Rouwenhorst说明期限结构可反映库存与便利收益，但这只是经济先验，不构成当前模型alpha证据：<https://www.nber.org/papers/w13249>。
- Erb、Harvey提示商品收益高度依赖期限结构与权重方式，历史关系不能不经样本外验证直接外推：<https://www.nber.org/papers/w11222>。
- 我的判断：本地数据质量足以研究全曲线连续特征；旧Stage073阈值过滤已失败，因此后续仍禁止按carry方向或阈值挑样本。

## 本次变更

- 新增脚本：`tools/curve_coverage.py`、`tools/stage001_curve_coverage.py`。
- 修改脚本：无。
- 删除脚本：无。
- 新增参数：同日精确连接、每行至少3个合格具体合约、价格/OI/成交量严格正、3位/4位交割月PIT解析。
- 修改参数：无。
- 删除参数：无。

## 回测/归因参数

- 数据区间：`2022-01-28`至`2025-11-28`，47个决策月。
- 账户规模：不适用，未运行账户。
- 成本口径：不适用，未回测。
- 样本过滤：上市资格先于排序后的797行A面板；没有删除月份、品种或排名。
- 策略/归因口径：只读SQLite日线具体合约，`feature_date=eval_date`；无最近日回填、无未来字段。

## 结果

- 决策：`stage001_curve_coverage_pass_ready_for_feature_preregistration`。
- 技术门：`12/12`通过。
- 面板覆盖：`797/797`；月份`47/47`；品种`18/18`。
- 合格具体合约快照：`7,615`行；每个面板行最少/中位/最多合约=`4/10/12`。
- 非正价格/OI/成交量机械拒绝：`209`行；主要为`jm.DCE=114`，但没有造成覆盖缺口。
- 非法交割码、交割月重复、PIT违规、同日错配、fallback和未来标签读取均为`0`。
- 双跑逐值一致；数据库以SQLite只读模式打开。
- 期末权益：不适用，未回测。
- 总收益：不适用，未回测。
- 最大回撤：不适用，未回测。
- Sharpe：不适用，未回测。
- 总滑点：不适用，未回测。
- 总交易次数：0。
- 胜率：不适用。

## 输出文件

- `eligible_contract_snapshot.csv.gz`：SHA256=`f206370c52bd9589795f34c3c31ffc25b197d3fa02cebb55c2da721b8cb557db`。
- `coverage_by_eval_product.csv`：SHA256=`b92cf89d816fc56e3a7152ad958bea8e7d6bafae30feb8b81a6f4793388e9fcf`。
- `rejected_contract_rows.csv.gz`：SHA256=`31f3e54eb766b5b096dfae29f4e11e4da8659c7c27dd6de1b46cf3f2016b0f9d`。
- `stage001_summary.json`：SHA256=`34e749e534c0f5250f6de8f80c7cb7cc63c630868f1205bb68f30bafd50bdbbd`。
- `artifact_manifest.json`：SHA256=`02e23076e4564a3c1867b04d8c3f6e9b7973045b688d3ca5da30ed39768b275c`。
- 测试：`.py311/bin/python -m pytest research/lines/futures_trend_xgboost_pit_curve_account_labels/tests -q`，`6 passed`。

## 结论

- 本阶段结论：数据覆盖门通过；只证明全曲线/OI/成交量特征能够按决策日严格PIT构造。
- 是否进入下一步：有条件进入；必须先冻结少量无阈值连续特征，并等待账户边际标签适配审计通过。
- 下一步：完成旧Stage015到干净A候选集的只读适配与任务量审计；双门通过后预注册Stage002特征，不直接运行账户标签。

## 过拟合反思

- 运行前判断：否；只审计输入身份和覆盖。
- 运行后判断：否；未读取收益、回撤或标签，也未按品种结果改变门。
- 原因：全部797行被保留，209条非活动合约按预声明统一规则剔除。

## 继续价值反思

- 运行前判断：是，但仅限覆盖审计。
- 运行后判断：是；数据源完整且明显不同于旧108项策略损益特征。
- 原因：真实研究价值仍取决于账户标签适配和严格OOS效果；覆盖通过本身不是晋级证据。

## 合入建议

- 是否更新本线`LINE.md`：是。
- 是否更新`research/registry.md`：是。
- 是否追加根目录`memory.md/back_log.md`：否；没有回测数据或正式候选。
