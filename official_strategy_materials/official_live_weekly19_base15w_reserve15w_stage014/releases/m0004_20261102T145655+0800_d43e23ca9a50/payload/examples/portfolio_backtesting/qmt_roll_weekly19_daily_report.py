"""Pure completed-day risk notification and a separate private mail topic.

Rows are source-verified lifecycle projections supplied by the existing actor.
This renderer never infers fills from plans, queries a gateway or sends SMTP.
"""
from copy import deepcopy
from datetime import date,datetime
import re
from qmt_roll_official_execution_profile import WEEKLY19_15W_R150K_PROFILE as PROFILE
from qmt_roll_weekly19_friday_report import (FridayMailOutbox,ReportError,SHANGHAI,_sha,_canonical,format_exit_reason,report_digest)

KIND='daily_risk'
_SYMBOL=re.compile(r'[A-Za-z]+\d{3,4}\.(?:SHFE|DCE|CZCE|CFFEX|INE|GFEX)')

def _require(condition,reason):
 if not condition:raise ReportError(reason)

def _text(value,name,maximum=512):
 _require(isinstance(value,str)and 0<len(value)<=maximum and value.strip()==value and not any(ord(c)<32 for c in value),name+'_invalid')
 return value

def _day(value):
 try:
  _require(isinstance(value,str)and date.fromisoformat(value).isoformat()==value,'daily_report_date_invalid')
  return value
 except (ValueError,TypeError):raise ReportError('daily_report_date_invalid')from None

def _row(value,target):
 _require(isinstance(value,dict),'daily_risk_row_required')
 item=deepcopy(value)
 _require(isinstance(item.get('vt_symbol'),str)and _SYMBOL.fullmatch(item['vt_symbol']),'daily_risk_symbol_invalid')
 _require(isinstance(item.get('position_direction'),str)and item['position_direction']in {'long','short'},'daily_original_position_direction_required')
 signal=_day(item.get('signal_date'));execution=_day(item.get('next_execution_day'))
 _require(signal<=target and execution>signal,'daily_signal_execution_date_invalid')
 planned=item.get('planned_volume');filled=item.get('filled_volume')
 _require(type(planned)is int and planned>0 and type(filled)is int and 0<=filled<=planned,'daily_risk_volume_invalid')
 status=_text(item.get('status'),'daily_lifecycle_status',128);life=_text(item.get('close_lifecycle_id'),'daily_lifecycle_id')
 _require(status not in {'completed','filled'}or filled==planned,'daily_completed_without_actual_full_fill')
 ids=item.get('intent_ids');dates=item.get('fill_trading_dates')
 _require(isinstance(ids,list)and bool(ids)and len(ids)<=10000,'daily_intent_ids_required')
 for identity in ids:_text(identity,'daily_intent_id')
 _require(len(ids)==len(set(ids)),'daily_intent_ids_duplicate')
 _require(isinstance(dates,list)and len(dates)<=10000,'daily_fill_dates_required')
 dates=sorted(set(_day(day)for day in dates))
 _require(all(day>=execution for day in dates)and (filled>0 or not dates),'daily_fill_dates_volume_mismatch')
 coverage=item.get('fill_date_coverage','legacy_or_partial'if filled else'complete')
 _require(isinstance(coverage,str)and coverage in {'complete','legacy_or_partial'},'daily_fill_coverage_invalid')
 _require(not(filled>0 and coverage=='complete'and not dates),'daily_complete_fill_dates_missing')
 reason=format_exit_reason(item.get('reason_code'))
 new=signal==target;pending=signal<target and status not in {'completed','filled'};today=target in dates
 date_unknown=filled>0 and coverage!='complete'
 item.update(fill_trading_dates=dates,fill_date_coverage=coverage,remaining_volume=planned-filled,new_signal=new,
  historical_pending=pending,today_fill_update=today,fill_date_unconfirmed=date_unknown,
  reason_display=reason,reason_known=not reason.startswith('原因未确认'))
 return item


def build_daily_risk_report(*,decision,data_receipt,account_key,material_release_id,rows,now,preview=True,blocking_reasons=()):
 """Render one completed day; cumulative fills never become today's fill qty."""
 _require(isinstance(now,datetime)and now.tzinfo is not None and now.utcoffset()is not None,'aware_daily_report_clock_required')
 _require(type(preview)is bool,'preview_boolean_required');_sha(account_key);_text(material_release_id,'daily_release')
 _require(isinstance(decision,dict)and decision.get('schema')=='weekly19.runtime-decision.v1'and decision.get('production_qualified')is False,'daily_completed_decision_required')
 _require(decision.get('account_fingerprint')==account_key and decision.get('material_release_id')==material_release_id,'daily_decision_identity_mismatch')
 _require(decision.get('execution_profile',PROFILE.profile_key)==PROFILE.profile_key,'daily_decision_profile_mismatch')
 target=_day(decision.get('trading_date'));_require(target<=now.astimezone(SHANGHAI).date().isoformat(),'daily_future_completed_target')
 source=_sha(decision.get('data_receipt_sha256'))
 _require(isinstance(data_receipt,dict)and data_receipt.get('target_date')==target and data_receipt.get('material_release_id')==material_release_id
  and data_receipt.get('sha256')==source,'daily_data_receipt_binding_mismatch')
 _require(isinstance(blocking_reasons,(tuple,list)),'daily_blocking_reasons_invalid')
 blockers=[_text(reason,'daily_blocking_reason')for reason in blocking_reasons]
 decision_not_evaluated=decision.get('bars_queued')is True or decision.get('blocked_reason')=='unresolved_execution_lifecycle'
 if decision_not_evaluated:blockers.append('daily_strategy_not_evaluated')
 if data_receipt.get('status')!='ready':blockers.append('daily_data_not_ready')
 source_complete=not blockers
 _require(isinstance(rows,list)and len(rows)<=10000,'daily_risk_rows_required')
 items=[];seen={}
 for raw in rows:
  item=_row(raw,target)
  previous=seen.setdefault(item['close_lifecycle_id'],item)
  _require(_canonical(previous)==_canonical(item),'daily_duplicate_lifecycle_conflict')
  if previous is not item:continue
  if not(item['new_signal']or item['historical_pending']or item['today_fill_update']or item['fill_date_unconfirmed']):continue
  items.append(item)
  if not item['reason_known']:blockers.append('exit_reason_unknown:'+item['close_lifecycle_id'])
  if item['fill_date_unconfirmed']:blockers.append('fill_date_coverage_incomplete:'+item['close_lifecycle_id'])
 risk_status='risk_actions'if items else('no_risk_actions'if source_complete else'unconfirmed')
 has_risk=True if items else(False if source_complete else None)
 cluster_count=sum(item['new_signal']and item.get('reason_code')in {'risk_cluster_heat_deleverage','long_risk_cluster_heat_deleverage','short_risk_cluster_heat_deleverage'}for item in items)
 unknown_count=sum(item['new_signal']and not item['reason_known']for item in items)
 cluster_status='unconfirmed'if not source_complete or unknown_count else('present'if cluster_count else'none')
 lines=[f'周线19｜{target} 每日风险平仓与降仓',f'行情完成日：{target}；报告时间：{now.astimezone(SHANGHAI):%Y-%m-%d %H:%M:%S}（北京时间）']
 if preview:lines.append('候选预览：未发送邮件，不代表生产已激活或获准委托。')
 if cluster_status=='unconfirmed':lines.append(f'今日风险组压力降仓新信号：未确认（已识别 {cluster_count} 项；当日原因未确认 {unknown_count} 项；数据来源'+('已核对'if source_complete else'待核对')+'）。')
 else:lines.append('今日风险组压力降仓新信号：'+(f'有 {cluster_count} 项。'if cluster_count else'无。'))
 if decision_not_evaluated:lines.append('执行生命周期尚未解决，当天策略尚未推进；今日新风险信号未评估，不能据此认定无信号。下列历史待执行和实际成交明细仍可核对。')
 if not source_complete:lines.append('数据或执行来源待核对，不能确认风险事项是否已完整覆盖；不得据此认定没有风险。')
 elif not items:lines.append('本完成交易日无新增风险平仓/减仓计划，无历史待执行项，也未见当日已确认成交更新。')
 if items:
  lines.append(f'风险事项 {len(items)} 项：当日新计划 {sum(x["new_signal"]for x in items)} 项；历史待执行 {sum(x["historical_pending"]for x in items)} 项；当日有已确认成交回报更新 {sum(x["today_fill_update"]for x in items)} 项。分类可重叠，同一生命周期只展示一次。')
 statuses={'pending':'待执行','working':'执行中','partially_filled':'部分成交','retry_required':'待重试','completed':'已完成','filled':'已完成',
  'blocked':'执行受阻','cancelled':'已撤，剩余待核验','rejected':'已拒，剩余待核验','needs_reconciliation':'待来源对账'}
 for item in items:
  side='持仓多头→卖平'if item['position_direction']=='long'else'持仓空头→买平'
  tags=[]
  if item['new_signal']:tags.append('当日新计划')
  if item['historical_pending']:tags.append('历史待执行')
  if item['today_fill_update']:tags.append('当日有实际成交回报更新（手数下列为累计值）')
  if item['fill_date_unconfirmed']:tags.append('成交日期证据不完整，不据此推定今日成交')
  status_display=statuses.get(item['status'],'执行状态未确认')
  if 0<item['filled_volume']<item['planned_volume']:
   status_display='部分成交；剩余'+status_display
  lines.extend(['',f'{item["vt_symbol"]}｜{side}｜'+item['reason_display'],
   f'信号日 {item["signal_date"]}；原下一执行日 {item["next_execution_day"]}；'+ ' / '.join(tags),
   f'计划 {item["planned_volume"]} 手；累计已成交 {item["filled_volume"]} 手；剩余 {item["remaining_volume"]} 手；状态：'+status_display+f'（{item["status"]}）',
   f'生命周期 {item["close_lifecycle_id"]}；关联意图 {len(item["intent_ids"])} 个（重试不重复累加计划手数）。'])
 lines += ['', '规则说明：风险簇 pressure 是标准化综合压力；固定规则0.4是压力阈值，不是保证金占比40%。',
  '累计成交仅取已核验生命周期的实际filled_volume；不能把计划手数、订单状态或累计量当作今日新增成交量。',
  '本邮件仅披露已完成日的计划与执行状态，不生成或授权任何委托；实际持仓、资金、报价和交易时段仍由原执行门核验。']
 if blockers:lines.append('待核对：'+'；'.join(dict.fromkeys(blockers)))
 report=dict(schema='weekly19.daily-risk-report.v1',report_kind=KIND,execution_profile=PROFILE.profile_key,account_key=account_key,
  material_release_id=material_release_id,target_date=target,generated_at=now.isoformat(),data_receipt_sha256=source,
  subject=f'周线19｜{target}｜每日风险'+('待核对'if blockers else('事项'if items else'无新增事项')),
  body='\n'.join(lines)+'\n',preview=preview,production_qualified=False,source_complete=source_complete,has_risk=has_risk,risk_status=risk_status,
  items=items,blockers=list(dict.fromkeys(blockers)),actionable=False,today_cluster_signal_status=cluster_status,
  today_cluster_signal_count=cluster_count,today_unknown_reason_count=unknown_count)
 report['report_sha256']=report_digest(report);return report


class DailyMailOutbox(FridayMailOutbox):
 """One attempt per profile/account/release/completed day/daily-risk topic."""
 REPORT_SCHEMA='weekly19.daily-risk-report.v1'
 OUTBOX_SCHEMA='weekly19.daily-risk-mail-outbox.v1'
 def _validate_report(self,report):
  super()._validate_report(report)
  _require(report.get('report_kind')==KIND,'daily_mail_topic_invalid');_sha(report.get('account_key'));_day(report.get('target_date'))
  _text(report.get('material_release_id'),'daily_release')
 def _key_fields(self,report):
  return [report['execution_profile'],report['account_key'],report['material_release_id'],report['target_date'],report['report_kind']]
 def _record_fields(self,report):
  return {key:report[key]for key in('execution_profile','account_key','material_release_id','target_date','report_kind')}
