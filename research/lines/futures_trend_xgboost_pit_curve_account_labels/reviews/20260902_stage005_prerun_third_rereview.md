# Stage005 第三次批量前独立复审

- 复审时间：2026-09-02 21:15 CST
- 结论：`BLOCK_STAGE005_BATCH`
- 严重度：`P0=0/P1=0/P2=1/P3=0`
- Git HEAD：`098ca5b99af76ab6f7fc3fb3442e4be17931caff`
- 边界：未执行prepare campaign、run-batch、worker、回测、模型、holdout、CTP、order；未创建authorization、consumption或campaign。

## Finding

### P2-1：receipt count未校验JSON exact integer，畸形类型可通过gate

`tools/stage005_development_label_batch.py:1312-1314`与`:1338-1339`只用`== len(...)`校验start/end count，没有要求`type(value) is int`。独立临时目录反例：

- end的`completed_job_count_after=true`或`1.0`对应一项completed list时，均返回`passed=true/receipt_shape_valid=true`；
- start的`same_campaign_revalidated_job_count=false`、`pending_job_count=true`，或`0.0/1.0`，均返回`passed=true/receipt_shape_valid=true`。

Python JSON将`true`解码为`True`、real number解码为`float`，且`bool`是`int`子类，所以数值相等不证明count是整数形状。这违反本轮completed list/count及start lists/counts形状自洽要求。未发现它能改变最终状态或绕过270项聚合，定为P2；但P0/P1/P2未全零，必须BLOCK。另有`worker_commands=[[]]`被空集合真值接受，建议同次要求每条命令为非空字符串列表。

## 反例与不变量

- `completed_job_count_after=999`且complete带error：失败，`receipt_shape_valid=false`。
- complete带error、failed无非空error、completed list未排序/重复/count不一致：均失败。
- sequence缺失、重复、从1断档、active非最新：均失败；同秒跨PID旧complete/新failed识别新failed并失败。
- 非64hex contract、非二维commands失败；exact count类型是剩余缺口。
- 单campaign scope、小写64hex nonce、文件模式`x`原子消费及authorization SHA/nonce/scope/campaign_id的worker/resume绑定未见回归。
- v2四输入现场SHA一致：数据库`db334200...0c4b`、映射`093d3bc...490b7`、分钟`8e861633...6784`、元数据`24a3573e...35a`。
- predecision五文件、逐操作数1e-6 delta、scope及最终model/holdout/CTP/order零字段机械派生未见回归。
- Stage005仅有既有`LATEST.json`；campaigns、Stage005 run authorization、authorization consumption均不存在。

## Fresh验证

- 三个相关pytest文件：`39 passed in 25.40s`。
- 三个工具和三个测试文件`py_compile`：exit 0。
- pytest改写的`LATEST.json`已恢复到运行前SHA256 `33313af818c3e29e356e6613e44d422945e0e5ec9f46a94043500d5a592480cf`。

## SHA256

- 第二次BLOCK修复预注册：`68c791301435f5619489ca8ed9191629e0441beb3ee16c9d85a29e1fa7756793`
- batch core：`365b50c47c8147196a8a4741475ec7613641fee99564e165374737f775b0b0bd`
- Stage005 runner：`4306f4e8796a81d333364267a4058effe74d6eba38adf91d520e2f7729780395`
- Stage005A runner：`d707b6589520bf078c5eced3f9d67d2fa823fc9b3c62a6fc9d4153877c1860ee`
- core/Stage005/Stage005A tests：`a4eb68fa...f8e6e` / `90d312b2...259` / `99b74907...37b3`

## 最终判断

- 过拟合：**否**。只审计治理状态机和冻结身份，未读取新标签、选样本或训练模型。
- 继续价值：**是，但仅限修复本P2并再次独立复审**。当前不得创建authorization或campaign。
- 决策：`BLOCK_STAGE005_BATCH`。
