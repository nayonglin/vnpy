# Stage018 场外备用金人工核验操作说明

2026-11-01，line_id=futures_weekly_short_ma_slope_gate。用户已选择人工核验出入金，系统不强求自动最终结算单解析或自动银行到账producer。本说明属于新候选，只有真实资格及Stage948激活完成后才是运行入口；不能以本文件存在证明安装完成。

## 实际职责

交易账户初始15万元，场外另15万元。场外余额不参与权益或手数；有原生新开信号且真实交易权益低于15万元时，周五邮件建议补差额。建议不是欠款，权益已恢复时不必强补旧建议。人工确认只核对已发生的现金事实，不发起转账、不增加券商Balance/Available、不产生交易授权。

本次明确模式是`cash_verification_mode=operator_manual_v1`。真实当前CTP账户快照、持仓、委托、报价和风险检查继续保留。系统保存的是明确`operator_manual`来源，不冒充券商自动验证或生产资格。首次启动仍需真实15万元空仓及无活动委托，不继承研究模拟仓位。

## 先看状态，再确认事实

正式安装后，在本机稳定目录使用以下入口。没有完成激活或真实来源不就绪时，命令会阻断；周末不要为了获得快照额外连接CTP。

```bash
weekly19_cash_flags=(
  --execution-profile weekly19-15w-r150k
  --context-file '/Users/mac/Library/Application Support/qmt-roll-stage179/production-live/runtime/weekly19/context.json'
  --release-manifest '/Users/mac/Library/Application Support/qmt-roll-stage179/production-live/release-manifest.json'
  --activation-receipt '/Users/mac/Library/Application Support/qmt-roll-stage179/production-live/runtime/state/activation_receipt.json'
  --production-qualification-evidence '/Users/mac/Library/Application Support/qmt-roll-stage179/production-live/qualification-bundle/qualification.json'
)
/Users/mac/Desktop/person/vnpy_production_live/.py311/bin/python \
  /Users/mac/Desktop/person/vnpy_production_live/examples/portfolio_backtesting/run_qmt_roll_weekly19_manual_cash.py \
  --action status "${weekly19_cash_flags[@]}"
```

状态会给出当前交易日、现金检查点、剩余备用金、累计补资，以及原补资request和待核对原因。没有新的现金变化且已核对同一交易日时，不必每次行情刷新再确认。新出入金或新交易日需要新的相关事实核对。

人工输入为私有JSON，文件权限0600、直接父目录0700。字段固定如下，金额全部使用整数“分”；示例字段值需替换成真实事实，不可直接提交示例：

```json
{
  "topups": [
    {
      "request_id": "从状态复制真实原request_id",
      "receipt_id": "每笔到账唯一的人工核对编号",
      "amount_fen": 1000000,
      "occurred_at": "2026-11-02T09:20:00+08:00",
      "trading_day": "2026-11-02"
    }
  ],
  "closed_days": [
    {
      "trading_day": "2026-10-30",
      "final_deposit_fen": 0,
      "final_withdraw_fen": 0,
      "closed_at": "2026-10-30T16:00:00+08:00",
      "statement_reference": "本人实际核对的账户日结或资金记录说明",
      "cashflows_complete": true
    }
  ],
  "expected_reserve_remaining_fen": 14000000,
  "notes": "本人已核对本次覆盖时段全部现金流与实际场外余额"
}
```

没有补资时`topups`为空；没有跨交易日时`closed_days`为空。跨日必须恰好覆盖检查点至当前CTP交易日之间所有已闭交易日，逐日核对gross入金与出金，不能用Balance差额代替。周末或假日不虚构交易日。提现不会恢复备用金或冲减累计补资；同笔到账编号不得换request或review再计一次。

核对后，用唯一review编号和operator标识提交：

```bash
/Users/mac/Desktop/person/vnpy_production_live/.py311/bin/python \
  /Users/mac/Desktop/person/vnpy_production_live/examples/portfolio_backtesting/run_qmt_roll_weekly19_manual_cash.py \
  --action confirm "${weekly19_cash_flags[@]}" \
  --review-input '/绝对路径/私有目录/人工核对.json' \
  --operator-id '本人标识' --review-id '本次唯一核对编号' \
  --confirm I_HAVE_MANUALLY_VERIFIED_ACTUAL_CASHFLOWS_AND_OFFSITE_RESERVE
```

`record_written_pending_actor_consumption`只说明记录及引用已发布，还没有改资金账；原运行actor将重新验证当前真实快照，再与运行状态原子提交。`reference_not_published`或`publication_unconfirmed`也不能当作已消费。可用相同编号和原字节重试，不能改写旧记录或续期；未消费且超过30分钟、来源变化或原资金状态改变时，需重新核对事实后使用新编号。已消费记录永久保留，不因受理窗口过去抹掉到账事实。

累计补资T与剩余备用金R始终满足`T+R=15000000分`。任何不一致、未知入金、现金记录不完整或真实来源过期，都会保留待核对状态；平仓和减风险仍由原实际持仓流程独立检查。

本阶段未调整策略参数或增加金融回测，不存在据此选择更好收益的调参；继续价值在真实会计和执行一致性。
