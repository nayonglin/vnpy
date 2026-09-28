# Stage049B冻结格式兼容修复合同

- 时间：2026-09-07 05:51 CST；line_id：futures_trend_xgboost_history_compatible_root_utility。
- 05:44原Stage049冻结9558输入，file contract 7b8bd6ffc519b888b7839075b57725c7a794e652e01a44a7bdadc1526ad463d5；05:48完整C入口在创建输出、私有runtime或策略worker前失败：frozen_input_contract_schema_invalid。
- 根因：旧通用冻结格式要求严格8字段，Stage049另外写了training_summary_sha256，形成9字段。原代码、测试、冻结文件保留，不修改通用验证器、不回写旧冻结、不把832测试通过当作已覆盖此真实集成边界。
- Stage049B不是新科学候选，只修冻结格式与worker入口定位。新冻结只用既有8字段，模型summary SHA固定为69e4e9bd8dab96be26288ea51a76fca5cc834c773a92b0408dbf957b63b71a5a；入口仍要求显式一致SHA，模型产物仍由原Stage045逐项核验并纳入新文件合同。
- 新适配器复用原Stage049策略、模型、来源、父校验与成功标准，绑定原失败冻结、本合同、新适配器/测试及原17:06科学合同，独立输出stage049b_holding_full_replay。原Stage049没有策略回放或收益结果，不需要重训标签或模型。
- 先测试原9字段失败和新8字段通过真实通用验证，再冷启动配置、新入口自身调用路径、固定模型与科学函数不变测试。新C只运行一次；失败保留，不跳过资金/动作/源门。
- 新增/修改/删除科学参数与回测结果均无；期末权益、总收益、最大回撤、Sharpe、滑点、成交数及胜率暂无新完整C数值。
- 调研判断沿用Stage049官方XGBoost/vn.py/sklearn资料；本次错误来自本地既有严格schema，以源码为直接证据，不以新文档覆盖本地冻结协议。
- 过拟合判断：否，这是执行前格式错误，尚未看见C收益，不调参救结果。继续价值：是，修正后才能验证已冻结假设。reviewer0，生产/CTP/订单不改。
