# Stage241 Phase B 半自动执行流程设计

- line_id：`futures_trend`
- 当前模式：`day`
- 记录时间：`2026-05-11 11:56 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：半自动执行流程与状态机设计
- 是否重要突破：是，明确“人工确认、系统执行”的落地流程
- 是否触发A/B：否，不修改 `78-1` 策略逻辑

## 外部调研与判断

- 参考资料与仓库内先验：
  - `Stage154/155` 已有 `signal_intent / order_event / fill_event / reconcile` schema，可直接拿来做 Phase B 数据面。
  - `Stage237/238` 已有部署账本和部署日报，可直接作为发单前 gate。
  - `Stage240` 已给出最小可上线执行架构，但还没有把 Phase B 的人工确认流程画细。
- 我的判断：
  - Phase B 的关键不是“人工下单”，而是“人工确认后由系统执行”。
  - 只有这样，后续才有订单状态机、成交回报、对账、异常恢复这些生产能力。

## Phase B 定义

- 信号生成：自动
- 部署判断：自动
- 委托草案生成：自动
- 最终发单动作：人工确认一次
- 委托提交：系统执行
- 成交回报跟踪：系统执行
- 对账与异常报告：系统执行

## 核心原则

1. 人工只负责“是否放行”，不负责去柜台手敲每一笔单。
2. 信号一旦冻结，不允许人工临时改方向、改手数、改合约。
3. 系统发单前必须再读一次真实账户、真实持仓、未完成委托。
4. 如果任何关键状态不一致，自动降级为 `readonly`，不发单。

## 流程图

```text
           +----------------------+
           | 盘前/触发时点到达     |
           +----------+-----------+
                      |
                      v
           +----------------------+
           | 生成 signal_intent   |
           | 冻结策略信号         |
           +----------+-----------+
                      |
                      v
           +----------------------+
           | Deployment Gate      |
           | 风险/部署/账户预算   |
           +----------+-----------+
                      |
            no        |        yes
      +---------------+---------------+
      |                               |
      v                               v
+------------------+       +----------------------+
| 记录 blocked      |       | 生成 order draft     |
| 不允许新增真实单  |       | 但暂不发单           |
+------------------+       +----------+-----------+
                                       |
                                       v
                            +----------------------+
                            | 人工确认放行         |
                            | approve / reject     |
                            +-----+-----------+----+
                                  |           |
                           reject |           | approve
                                  |           |
                                  v           v
                     +------------------+   +----------------------+
                     | 记录 rejected    |   | 发单前二次校验       |
                     | 不进入执行       |   | broker-state-first   |
                     +------------------+   +----------+-----------+
                                                        |
                                               fail     |    pass
                                         +--------------+-------------+
                                         |                            |
                                         v                            v
                              +----------------------+    +----------------------+
                              | 降级 readonly        |    | 系统提交真实委托     |
                              | 记录 exception       |    | 生成 broker_order_id |
                              +----------------------+    +----------+-----------+
                                                                     |
                                                                     v
                                                          +----------------------+
                                                          | 跟踪回报             |
                                                          | order / fill / cancel|
                                                          +----------+-----------+
                                                                     |
                                                                     v
                                                          +----------------------+
                                                          | 收盘/窗口结束对账    |
                                                          | intent vs broker     |
                                                          +----------+-----------+
                                                                     |
                                                                     v
                                                          +----------------------+
                                                          | 写部署日报/异常日报  |
                                                          +----------------------+
```

## 具体步骤

### Step 1. 生成并冻结信号

- 自动运行 `78-1` 信号逻辑。
- 生成 `signal_intent`。
- 必需字段至少包括：
  - `shadow_session_id`
  - `strategy_version`
  - `decision_date`
  - `plan_date`
  - `vt_symbol`
  - `direction`
  - `offset`
  - `planned_volume`
  - `theoretical_price`
  - `signal_freeze_flag=1`

### Step 2. 运行发单前 gate

- 自动检查：
  - `allow_real_new_orders`
  - 当前是否处于 `balanced_tranche_v1` 允许新增阶段
  - 当前风险等级是否为 `stop/review`
  - 当前账户预算是否足够
- 若失败：
  - 只记录信号，不生成真实委托
  - 输出 `blocked_reason`

### Step 3. 生成真实委托草案

- 系统根据 `signal_intent` 生成 `order draft`。
- 草案至少包含：
  - `intent_id`
  - `order_group_id`
  - `account_id`
  - `order_price`
  - `order_volume`
  - `time_in_force`
  - `expected_margin`
  - `risk_checks_passed`

### Step 4. 人工确认

- 人工只能做三种动作：
  - `approve`
  - `reject`
  - `defer`
- 人工不能做的事：
  - 临时改手数
  - 临时换合约
  - 临时反向
  - 绕过部署 gate
- 这一步本质上是“放行开关”，不是“人工交易决策”。

### Step 5. 发单前二次校验

- 系统在真正提交前再次读取：
  - 真实账户权益
  - 真实持仓
  - 未完成委托
  - 当前连接状态
- 若发现：
  - 已有同组未完成委托
  - 真实持仓已达到目标
  - 保证金不足
  - 连接异常
- 则本次不发单，直接转 `readonly` 或 `failed_before_submit`

### Step 6. 系统提交真实委托

- 真正调用柜台 API 的只能是系统。
- 每笔真实单必须落盘：
  - `intent_id`
  - `broker_order_id`
  - `submit_time`
  - `order_status`
  - `rejected_reason`

### Step 7. 回报跟踪

- 系统自动跟踪：
  - `submitted`
  - `partial_filled`
  - `filled`
  - `cancelled`
  - `rejected`
- 所有成交必须能回写到 `fill_event`。

### Step 8. 对账

- 收盘或窗口结束后，对账三件事：
  - `signal_intent`
  - `broker_order/fill/position`
  - `deployment_ledger`
- 若不一致：
  - 生成异常日报
  - 次日默认降级 `readonly`

## 人工和系统的边界

### 人工负责

- 看委托草案
- 点 `approve / reject / defer`
- 遇到事故时切到 `readonly`

### 系统负责

- 生成信号
- 生成委托草案
- 做发单前 gate
- 真正调用发单接口
- 跟踪成交回报
- 写对账和异常报告

## Phase B 状态机

```text
draft_created
  -> blocked_by_gate
  -> pending_manual_approval

pending_manual_approval
  -> manually_rejected
  -> deferred
  -> pre_submit_checking

pre_submit_checking
  -> failed_before_submit
  -> submitted

submitted
  -> partial_filled
  -> filled
  -> cancelled
  -> rejected

filled / cancelled / rejected
  -> reconciled

any_state
  -> readonly_fallback
```

## 最小界面形态

- 我不建议一开始做复杂 UI。
- 最小可用形态可以是：
  - 一份 `order_draft.json`
  - 一份 `approval_request.md`
  - 一个简单命令：
    - `approve_intent <intent_id>`
    - `reject_intent <intent_id>`
- 这样最容易审计，也最不容易误点。

## 当前最合理实现顺序

1. 先做 `readonly daemon`
2. 再做 `signal_intent -> order_draft` 生成
3. 再做人工 `approve/reject` 命令
4. 最后才接真实 `submit_order()`

## 当前结论

- Phase B 不是“策略出信号，你手工去柜台敲单”。
- Phase B 是“策略出信号，系统生成草案，你人工放行，系统执行并对账”。
- 这才是后续能平滑升级到 Phase C 的正确路径。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：本阶段只设计执行流程，不改策略参数。

## 继续价值反思

- 运行前判断：是。
- 运行后判断：是。
- 原因：这一步把“人工确认”从模糊概念变成了可实现的执行边界。
