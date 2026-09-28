# Stage005B 第三次BLOCK exact-type修复预注册

- line_id：`futures_trend_xgboost_pit_curve_account_labels`
- 记录时间：2026-09-02 21:19 CST
- 上游review：`reviews/20260902_stage005_prerun_third_rereview.md`
- 上游结论：`BLOCK_STAGE005_BATCH`，`P0/P1/P2/P3=0/0/1/0`
- 回测/campaign/authorization/consumption：全部禁止

## 判断

- 是否过拟合：否；只修JSON到Python类型等值造成的receipt shape漏洞。
- 是否值得继续：是；布尔或浮点count不应冒充整数，空命令不应成为合法执行证据。

## 冻结修复

- `same_campaign_revalidated_job_count`、`pending_job_count`、`completed_job_count_after`必须满足`type(value) is int`且与对应列表长度精确一致；拒绝`bool`和`float`。
- completed/pending job id必须是非空字符串、排序且去重。
- `worker_commands`允许外层为空，仅用于validate-only；只要存在命令，每条命令必须是至少一个元素的非空字符串列表。
- 其他Stage005A v2、attempt sequence、单campaign授权、predecision、scope和金额量化合同不变。

## TDD反例

- 用JSON `true`冒充count=1，必须拒绝。
- 用JSON `1.0`或`2.0`冒充整数count，必须拒绝。
- `worker_commands=[[]]`必须拒绝。

## 放行边界

- 修复后只运行fresh测试、py_compile和第四次独立批量前review。
- 新review未给结构化`ALLOW_STAGE005_BATCH`前，不得创建authorization或campaign。
