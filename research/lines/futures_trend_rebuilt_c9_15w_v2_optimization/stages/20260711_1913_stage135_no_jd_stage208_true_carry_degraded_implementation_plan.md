# Stage135 no-JD Stage208 真成交账本降级证伪实现计划

**目标：** 用冻结 C9 路径、无 JD xsmom 整数手目标、真实分钟成交和聚合保证金闸门完成一次可审计的 A/B/C 证伪。

**边界：** 只写当前研究线、对应测试与研究输出；不修改正式策略和任何执行入口。

## 任务

- [x] 新增失败测试，覆盖无 JD 不递补、严格规格、shift(1) scale、真实成交优先级、无 fallback、carry PnL、保证金闸门与会计恒等式。
- [x] 新增 `tools/stage135_no_jd_stage208_true_carry_degraded.py`，把数据准备、目标账本、真实重放、汇总和闸门拆成可测试纯函数。
- [x] 运行静态输入审计，确认 Stage020、Stage167、非 JD 规格和分钟窗口满足冻结合同。
- [x] 只跑 `2020-01` canary，输出 A/B/C daily、target/order ledger、summary、reconciliation、fill source、margin audit、decision 和图表。
- [x] 每个实验完成后交给独立 agent 重算数字、检查时序/会计/成交/保证金语义并评估置信度。
- [x] 只有 canary 全通过才跑 13 起点、1x/2x/3x、2022 路径和 Stage009 严格窗口审计；本次 canary 失败，已按预注册规则跳过 full 并关闭路线。
- [x] 最后重新跑聚焦测试、相关回归、`py_compile`、`git diff --check`，更新 stage、LINE、registry 和必要的 back_log 摘要。
