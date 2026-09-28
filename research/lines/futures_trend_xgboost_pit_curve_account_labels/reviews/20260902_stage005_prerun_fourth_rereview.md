# Stage005 第四次批量前独立复审

- 复审时间：2026-09-02 CST
- 结论：`ALLOW_STAGE005_BATCH`
- 严重度：`P0=0/P1=0/P2=0/P3=0`
- Git HEAD：`098ca5b99af76ab6f7fc3fb3442e4be17931caff`
- 边界：未执行 prepare campaign、run-batch、worker、回测、模型、holdout、CTP、order；未创建 authorization、consumption 或 campaign。

## Findings

未发现 P0、P1、P2 或 P3 finding。第三次 BLOCK 的 exact-type 与空命令问题已关闭，前三轮治理修复未见回归。

## 反例与指定重点

- JSON `true` 不能冒充 count：start 的 `same_campaign_revalidated_job_count=true` 被 exact-type 门拒绝。
- JSON `1.0/2.0` 不能冒充 count：start/end 的浮点 count 被 `type(value) is int` 门拒绝；相关 fresh 测试通过。
- `worker_commands=[[]]` 被拒绝；命令存在时，每条必须是至少一个元素且每个元素均为非空字符串。空字符串命令同样被源码门 `bool(part)` 拒绝。
- 合法 validate-only 使用 `worker_commands=[]`，空外层命令仍通过；fresh 测试确认生成零 worker-command attempt。
- 畸形 end receipt 被拒绝：complete 带 error、failed 缺少非空 error、completed list 未排序/重复/count 不一致均 fail closed。
- attempt sequence 缺失、重复、不连续、active 非最新均拒绝；同秒跨 PID 的旧 complete/新 failed 仍识别新 failed 并拒绝。
- 单 campaign 授权消费未见回归：scope 精确为 `one_new_stage005_campaign_only`，nonce 要求小写 64hex，消费回执以独占创建写入；第二次消费及不同 campaign 绑定均拒绝。
- Stage005A v2 四输入现场 SHA 一致：数据库 `db3342006f4220767f06e466bb40c046f372961cea41cef9a6d8bc1727fa0c4b`，主力映射 `093d3bc767c09d9e0e4f4fbeb9846a091bf25c163cc31eddfd382cc1ff5490b7`，分钟数据 `8e861633b08a82819a668c30c6799e2098d2beaa6863698351145018ea586784`，合约元数据 `24a3573e847e024411b13a3a3b775791ded57563b0a68b717d1065078201635a`。
- predecision 五文件逐 receipt 重算、精确 scope/命令树、逐操作数 `1e-6` 金额 delta、最终 model/holdout/CTP/order 字段从 observed counts 派生，均未见回归。
- Stage005 artifact root 仅有既有 `LATEST.json`；`campaigns/`、`20260902_stage005_run_authorization.json`、`authorization_consumption.json` 均不存在。Stage005A 历史 smoke authorization 不属于 Stage005 批量授权。

## Fresh 验证

- 三个相关 pytest 文件隔离 fresh 运行：`40 passed in 15.05s`。pytest cache、pyc 和临时输出均定向到 `/private/tmp`，未改写研究线产物。
- 三个相关工具文件与三个测试文件 fresh `py_compile`：exit `0`，缓存定向到 `/private/tmp/stage005-fourth-rereview-pycache`。
- 一次额外反例脚本因命令载体换行转义在 Python 解析阶段失败，未执行 Stage005 逻辑、未生成产物，且不计入通过证据；上述判断只使用成功执行的 fresh pytest、py_compile、源码与冻结产物复核。

## 当前 SHA256

- batch core：`365b50c47c8147196a8a4741475ec7613641fee99564e165374737f775b0b0bd`
- Stage005 runner：`732eeb19264cf71ade57e2a8f1bd64c702496dad0fb9847d8cc08135cb6e9281`
- Stage005A runner：`d707b6589520bf078c5eced3f9d67d2fa823fc9b3c62a6fc9d4153877c1860ee`
- core test：`a4eb68fac325564036aae2322260fe3d6e833d31e783eb1fb11b5639e47f8e6e`
- Stage005 runner test：`6c019f1e10e9c13b60613be382419db896616cfabb5b31d7b6eafeee44488d5a`
- Stage005A test：`99b7490730afa1e9c53002cca50fcb89c4c713f792d3a9053e973a0b67d037b3`
- 第三次 BLOCK 修复预注册：`3068aea1c40a1c5a14ed5fc478738754538da48fdea32486c21d518b59b49142`

## 调研与判断

- 外部调研：Python 官方 JSON 文档与 CPython decoder 源码确认 JSON integer/real/true 分别解码为 `int`/`float`/`True`；Python built-in types 文档确认 `bool` 是 `int` 子类且空序列为 false。当前采用 exact type 而不是数值等值的修复方向正确。
- 过拟合：**否**。本轮只审查治理状态机、冻结输入身份与隔离测试，没有读取新标签、挑月份/品种/rank、训练模型或比较策略收益。
- 继续价值：**是，但仅限受控完成一次冻结 Stage005 development 标签 campaign**。本次放行不是模型价值、收益改善、holdout 或实盘结论。

## 放行边界

本 review/decision 只解除批量前独立 review 门，不是 run authorization。真正运行前仍必须另建 authorization，并同时满足：绑定当前 runner/core/tests/预注册/reviews/decision 的实际 SHA，使用小写 64hex `campaign_nonce`，且 `scope=one_new_stage005_campaign_only`；该 authorization 只能原子消费一次。任何 SHA、nonce、scope、消费状态或冻结输入漂移都必须 fail closed。
