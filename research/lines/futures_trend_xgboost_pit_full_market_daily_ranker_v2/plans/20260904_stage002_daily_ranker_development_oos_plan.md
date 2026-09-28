# Stage002 日级XGBRanker Development OOS执行计划

**目标：** 在冻结52,484条固定合约20日标签上，运行37折单一浅树XGBRanker，先封存预测和一席选择，再读取72条测试效果行，判断是否值得进入真实引擎A/C回测。

## Task 1：标签与模型纯函数

- [x] 写RED测试：同合约close读取、五分位relevance、qid连续、严格PIT训练折。
- [x] 实现标签生成、训练数组、主/重复模型确定性和单槽selector。
- [x] 写RED测试：效果指标、leave-best、回撤方向和七项门。

## Task 2：状态机与发布

- [x] 写RED测试：seal前禁止测试标签、固定74 fits、授权SHA漂移、final不可覆盖。
- [x] 实现单次runner、pre-effect seals、模型与产物manifest、verify-only。
- [x] 跑V2/V1/source回归、编译和无真实标签runtime smoke。

## Task 3：授权、唯一执行与评审

- [x] 生成绑定输入、实现、测试、预注册和runtime的单次授权receipt。
- [x] 唯一执行Stage002并verify-only，不因结果重跑。
- [x] 有效果数据后启动独立reviewer，记录中文结果并更新LINE/registry。
