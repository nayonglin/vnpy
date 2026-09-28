# Stage002 基差与会员持仓相对特征结果

## 阶段信息

- 改动时间：2026-09-03 03:11 CST
- `line_id`：`futures_trend_xgboost_pit_physical_positioning_context`
- 线上逻辑回归基准：`m0005_20260901T165450+0800_1961d98ccb2b`
- 预注册：`stages/20260903_0256_stage002_physical_feature_preregistration.md`，SHA256=`1acaacc180b778d4f311aa7f54ecb66069016423242cbac4cc91741858569ad3`。
- 独立预审：`ALLOW_STAGE002_TDD_IMPLEMENTATION_ONLY`，`P0/P1/P2/P3=0/0/0/2`；review SHA256=`08fe767a4ba382fac502be3e1aebf9f9feed679800dc282d69a4c3896b880e83`。
- 是否重要突破版本：**否**。这是无标签特征构造资格，不是模型或策略效果。
- 阶段决策：`stage002_physical_features_pass_ready_for_training_contract_preregistration`，技术门`15/15`通过。

## 本次改动

- 新增脚本：`tools/stage002_physical_features.py`。
- 新增测试：`tests/test_stage002_physical_features.py`。
- 新增参数：完整证据定义、活跃月定义、六项固定差值、挑战者唯一/非零最小值`150`、development分段`18+17+12`月。
- 修改参数：无；真实运行前后未根据特征数值调整任何门或列。
- 删除参数：仓单、rank距离、产品/交易所/年月、来源年龄、可用性和缺失指示器均明确不进入模型特征。
- 新增回测结果：无。
- 修改/删除回测结果：无。

## TDD与身份验证

- 红灯：Stage002实现不存在时专项测试在收集阶段按预期失败。
- 绿灯：实现后Stage002专项`3 passed`，整线Stage001+002共`6 passed`；两个脚本`py_compile`通过。
- 预注册、独立review、review decision SHA运行前复算一致。
- Stage001输入工件、summary、family coverage和manifest身份运行前后一致。
- 输入面板只读取13个冻结列；收益/回撤标签列读取`[]`，标签值读取`false`。

## 冻结运行结果

- 全量候选：`374`行、`47`月、`18`品种。
- 完整物理证据活跃月：`35/47`；模型资格`218=35`个rank10锚点`+183`个挑战者。
- 前18月：`13`活跃月/`62=13+49`行；后17个development月：`13`活跃月/`91=13+78`行；最后12月仅做特征身份：`9`活跃月/`65=9+56`行。
- 活跃月按年：2022/2023/2024/2025=`8/10/9/8`。
- 六项特征在218行上全部有限，35个rank10逐项精确为0；六项在183个挑战者上均为`183`个唯一值、`183`个非零值。
- 完整挑战者只覆盖`13/18`个品种；`AP.CZCE/jm.DCE/lc.GFEX/lh.DCE/si.GFEX`为0行。未来证据范围固定为完整物理信息子宇宙，不能外推全18品种。
- 218行口径两项基差Spearman=`0.8510219950`、其他最大绝对相关=`0.2925248716`；183挑战者口径分别为`0.8679615110/0.3313836911`。已按独立review P3同时披露两个分母。
- 仓单模型特征`0`；模型fit、参数搜索、策略回测、真实引擎、sealed holdout标签、CTP和订单均为`0`。

## 工件

- 输出目录：`artifacts/stage002_physical_features/`
- `candidate_physical_feature_panel.csv`：SHA256=`8cec4ad03ceb4f316feaa34c58e44e6e1c2200dae55bcb651be9820bb9555994`
- `model_eligible_feature_panel.csv`：SHA256=`12b1e6afc5b4411e0cbab9b9ea59a6137eefcd7358decd69d2c327cae1407547`
- `month_eligibility.csv`：SHA256=`26ee18e1bf9268c2bef98ac6e5138cd35a75589327443bf911ab9eef9f019853`
- `product_eligibility.csv`：SHA256=`b06c227e6e0f4f8504bd04b9797419018c0cb440c1b8dc48ed163bd7b992198f`
- `feature_degeneracy.csv`：SHA256=`93a88514e9ece64495832b8050554978ad307ce628cb5446b7867cdb11c85af2`
- `feature_correlations.csv`：SHA256=`8b9cf971be4f7b8f0be2ddbc55e943299692043980659a2d98d4e55629f1cd9a`
- `stage002_summary.json`：SHA256=`13b81dd8b0ee111a022568ceb5a4a76ea88f59e626623c2c305c34af2cc1cf7f`
- `report.md`：SHA256=`e207fc82d5ebd25603e75a0e76f253f420cd19e5cc137589aff8a17499f76e92`
- manifest自身SHA256=`41cfef41f6e4555f4886c5ec71be92637a02250ce1a50ff7499c7b31cc8557ce`，声明8项与现场8项精确一致。

## 回测指标

- 期末权益：不适用，Stage002未回测。
- 总收益：不适用，Stage002未回测。
- 最大回撤：不适用，Stage002未回测。
- Sharpe：不适用，Stage002未回测。
- 总滑点：不适用，Stage002未回测。
- 总交易次数：不适用，Stage002未回测。
- 胜率：不适用，Stage002未回测。

## 结束反思

- 是否过拟合：**Stage002本身否**。没有标签、训练或效果比较，特征和门在真实运行前冻结且运行后未修改；但35个活跃月、13个首折查询组和13/18品种覆盖说明未来模型过拟合风险很高。若以后引入缺失分支、删品种/月或根据结果加特征，就是结果后过拟合。
- 是否值得继续：**只值得进入一次Stage003训练合同预注册**。外生差值非退化且语义独立，满足继续提出可证伪模型实验的最低条件；但现在仍没有任何提高收益或降低回撤的证据。

## 后续规划和TODO

- 先冻结唯一Stage003训练/评价合同并独立预审，不直接训练。
- 保留线上逻辑回归A；XGBoost只在13个development OOS完整月份挑战第10席，其他月份机械回退A并在效果序列中记0增量。
- 模型复杂度必须低于旧Stage006，禁止参数扫描；训练标签继续使用已审计账户边际逐折后开机制，sealed holdout标签保持0访问。
- 同时冻结外生特征实际被树使用、替换月份/品种分散、收益与回撤双正、分年和leave-best-out门；任一失败即闭线，不做第二版救援。

