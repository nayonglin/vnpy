# Stage005B 第二次BLOCK receipt自洽性修复预注册

- line_id：`futures_trend_xgboost_pit_curve_account_labels`
- 记录时间：2026-09-02 21:01 CST
- 上游review：`reviews/20260902_stage005_prerun_second_rereview.md`
- 上游结论：`BLOCK_STAGE005_BATCH`，`P0/P1/P2/P3=0/0/1/0`
- 回测/campaign/authorization/consumption：全部禁止

## 判断

- 是否过拟合：否；只加固append-only attempt receipt状态机。
- 是否值得继续：是；畸形complete receipt若能通过，会破坏失败恢复证据的可信度。

## 唯一修复范围

- start receipt必须满足：attempt id/phase/status正确，sequence为正整数且全campaign从1连续递增；completed/pending列表排序、去重、互斥，计数与列表一致，campaign contract为64位十六进制，worker commands为二维字符串列表。
- end receipt必须满足：attempt id/phase/status正确，completed列表排序去重，count与列表一致；`complete`时`error=null`，`failed`时error为非空字符串。
- active attempt必须是sequence最新项；final gate必须使用最新sequence对应end状态。
- 任一shape、count、error、sequence缺失/重复/断档均fail closed。

## TDD反例

- 写入正常complete end后，把`completed_job_count_after`改成`999`并添加error；gate必须返回false且`receipt_shape_valid=false`。
- 保留并重跑此前同秒跨PID、post-complete failure、active validation和单campaign授权反例。

## 放行边界

- 修复后只允许fresh测试、py_compile和第三次独立批量前review。
- 未得到新的结构化`ALLOW_STAGE005_BATCH`前，不得创建run authorization或campaign。
