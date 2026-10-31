"""Friday signal/funding mail rendering and private idempotent outbox.

Rendering does not qualify cash, create deposits or authorize an order. Real
SMTP is an injected, separately authorized transport; preview never calls it.
"""
from __future__ import annotations
import copy
from datetime import date,datetime
import fcntl,hashlib,json,os,re,stat,uuid
from pathlib import Path
from zoneinfo import ZoneInfo
import qmt_roll_weekly19_funding as funding
from qmt_roll_weekly19_broker_evidence import read_account_snapshot
from qmt_roll_official_execution_profile import WEEKLY19_15W_R150K_PROFILE
SHANGHAI=ZoneInfo('Asia/Shanghai')

class ReportError(ValueError):pass

def _sha(value):
 if not isinstance(value,str) or not re.fullmatch('[0-9a-f]{64}',value):raise ReportError('report_source_digest_invalid')
 return value

def _money(value):
 if type(value) is not int:raise ReportError('report_money_fen_required')
 return ('-' if value<0 else '')+f'{abs(value)//100:,}.{abs(value)%100:02d}'

def _canonical(value):
 return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()

def report_digest(report):
 return hashlib.sha256(_canonical({k:v for k,v in report.items() if k!='report_sha256'})).hexdigest()

def _now(now):
 if not isinstance(now,datetime) or now.tzinfo is None or now.utcoffset() is None:raise ReportError('aware_report_clock_required')
 if now.astimezone(SHANGHAI).weekday()!=4:raise ReportError('friday_report_only')
 return now

def build_friday_report(*, funding_state,broker_account,recommendation,decision,data_receipt,now,preview=True,blocking_reasons=()):
 """Build the week mail; an unpaid historical suggestion is never a debt.

 Data/cash origins are admitted by the production pipeline, not by this pure
 renderer. This component always records production_qualified=False.
 """
 now=_now(now)
 if type(preview) is not bool:raise ReportError('preview_boolean_required')
 funding.validate_state(funding_state)
 release=funding_state['material_release_id'];account_key=funding_state['account_key']
 week=now.astimezone(SHANGHAI).date().isoformat();target=week
 blockers=list(blocking_reasons)
 decision=decision or {};data_receipt=data_receipt or {}
 for obj in (decision,data_receipt):
  if obj.get('material_release_id',release)!=release:raise ReportError('report_release_mismatch')
 if decision.get('target_date'):
  target=date.fromisoformat(decision['target_date']).isoformat()
  if target>week:raise ReportError('future_completed_target')
 if data_receipt.get('target_date',target)!=target:raise ReportError('report_target_mismatch')
 data_hash=decision.get('data_receipt_sha256')
 if data_hash is not None:
  _sha(data_hash)
  if data_receipt.get('sha256')!=data_hash:raise ReportError('report_data_receipt_mismatch')
 if data_receipt.get('status')!='ready' or not decision or not data_hash:blockers.append('daily_data_not_ready')
 current_week=date.fromisoformat(target).isocalendar()[:2]==date.fromisoformat(week).isocalendar()[:2]
 if not current_week:blockers.append('report_target_not_current_week')
 acct=None
 try:
  acct=read_account_snapshot(broker_account,expected_account_key=account_key,material_release_id=release,now=now)
 except (ValueError,TypeError,KeyError):blockers.append('account_evidence_not_ready')
 provided_amount=recommendation.get('amount_fen',0)
 if type(provided_amount) is not int or provided_amount<0 or provided_amount>funding_state['reserve_remaining_fen']:raise ReportError('recommendation_amount_invalid')
 ids=decision.get('funding_admitted_ids',[])
 amount=min(max(15000000-acct['equity_fen'],0),funding_state['reserve_remaining_fen'])if acct is not None and ids else 0
 assessed=None
 if acct is not None and data_hash:
  try:assessed=funding.recommend_topup(funding_state,broker_account,week,ids,data_hash,now)['recommendation']
  except (ValueError,TypeError,KeyError):blockers.append('funding_evidence_not_current')
 if provided_amount!=amount:blockers.append('recommendation_not_current')
 active=[]
 for rid,r in funding_state['requests'].items():
  if r['status'] in {'pending','partially_confirmed'}:
   remaining=r['amount_fen']-r['confirmed_fen'];expires=datetime.fromisoformat(r['expires_at'])
   active.append(dict(request_id=rid,remaining_fen=remaining,expires_at=expires.isoformat(),expired=now>=expires))
 historical=sum(r['remaining_fen']for r in active)
 expired=any(r['expired']for r in active)
 funding_ready=False;funding_reason=None
 try:funding.assert_open_funding_ready(funding_state,broker_account,now);funding_ready=True
 except (ValueError,TypeError,KeyError)as exc:funding_reason=type(exc).__name__+':'+str(exc)
 if acct is not None and acct['equity_fen']>=15000000:amount=0
 request=funding_state['requests'].get(recommendation.get('request_id'))
 advice_bound=bool(request and request['status']in{'pending','partially_confirmed'} and request['target_week_end']==week and request['source_sha256']==data_hash and set(request['admitted_entry_ids']).intersection(ids) and request['amount_fen']-request['confirmed_fen']==amount)
 advice_explicit=recommendation.get('actionable')is True and assessed is not None and assessed.get('actionable')is True and assessed.get('amount_fen')==amount and assessed.get('request_id')==recommendation.get('request_id')
 if amount>0 and (not advice_bound or not advice_explicit):blockers.append('recommendation_request_not_current_or_actionable')
 actionable=not preview and not blockers and not expired and amount>0 and advice_bound and advice_explicit
 lines=[f'周线19品种｜{week} 周五信号与场外补资',f'行情完成日：{target}；报告时间：{now.astimezone(SHANGHAI):%Y-%m-%d %H:%M:%S}（北京时间）']
 if preview:lines.append('当前为候选预览，不代表已发送、已到账或已获实盘资格。')
 lines += ['', '一、真实资金与场外备用金']
 if acct is None:lines.append('账户证据未通过，无法可靠计算当前权益和补资金额；请先对账。')
 else:
  lines += [f'交易账户权益 E：{_money(acct["equity_fen"])} 元（已含未平仓价格变动）',f'可用资金：{_money(acct["available_fen"])} 元；已用保证金：{_money(acct["margin_fen"])} 元',f'账户快照：{acct["observed_at"]}；归属交易日：{acct["trading_day"]}']
  lines.append('未平仓盈亏：'+(_money(acct['unrealized_pnl_fen'])+' 元' if acct['unrealized_pnl_fen']is not None else '未取得独立浮盈亏字段；不在E上再次加减'))
 lines += [f'仍在场外的备用金：{_money(funding_state["reserve_remaining_fen"])} 元',f'累计已确认补入：{_money(funding_state["confirmed_topup_fen"])} 元',f'本次按当前缺口计算的建议额：{_money(amount)} 元（仅建议，未计入E或可用资金）']
 if active:
  lines.append(f'历史尚未到账的建议上限合计：{_money(historical)} 元；建议不是欠款。')
  for r in active:lines.append(f'历史请求 {r["request_id"][:12]}：尚余 {_money(r["remaining_fen"])} 元；有效至 {r["expires_at"]}'+('，已过期，需先对账/更新建议。' if r['expired']else '。'))
 if acct is not None and acct['equity_fen']>=15000000:lines.append('当前真实权益已达到15万元，不必补足旧建议；未用备用金继续留在场外。')
 elif not decision.get('funding_admitted_ids') and not active:lines.append('本周没有有效新开候选，不因账户低于15万元单独请求补资。')
 elif funding_state['reserve_remaining_fen']==0:lines.append('场外备用金已用尽；后续按实际剩余正权益和原规则计算，不虚增额度。')
 if 'recommendation_not_current'in blockers or 'recommendation_request_not_current_or_actionable'in blockers or recommendation.get('actionable')is False or recommendation.get('status')=='request_refresh_required':lines.append('当前缺口与历史请求不一致，须先完成对账并更新请求；不要按旧请求金额照付。')
 lines += ['', '二、本周信号']
 intents=decision.get('intents',[]) if current_week else []
 if not current_week:lines.append('尚无本周已完成行情对应的信号，上期记录仅供对账，不据旧信号新增补资或开仓。')
 if not isinstance(intents,list):raise ReportError('intent_list_required')
 if not intents:lines.append('本周没有待展示的执行计划。')
 for item in intents:
  symbol=item.get('vt_symbol',item.get('symbol',''));direction=item.get('direction');offset=item.get('offset');volume=item.get('volume',item.get('selected_volume',0))
  if not re.fullmatch(r'[A-Za-z]+\d{3,4}\.(?:SHFE|DCE|CZCE|CFFEX|INE|GFEX)',str(symbol)) or direction not in {'long','short'} or offset not in {'open','close'} or type(volume)is not int or volume<0:raise ReportError('report_intent_invalid')
  lines.append(f'{symbol}｜'+('多'if direction=='long'else'空')+'｜'+('开仓'if offset=='open'else'平仓/减仓')+f'｜参考 {volume} 手'+('，待到账确认后重新计算与核验'if offset=='open'and not funding_ready else '，执行前仍须实时核验'))
 lines += ['', '三、资金与执行状态']
 if 'daily_data_not_ready'in blockers:lines.append('行情数据尚未通过完整性检查，本次不形成可操作的补资/开仓结论。')
 if blockers:lines.append('当前存在数据或账户阻断；以上计算仅供核对，不能据此认定可以开仓。')
 if expired:lines.append('存在过期的未完成建议，请先完成现金流对账；不自动恢复或重复扣减备用金。')
 if not funding_ready:lines.append('新开仓资金条件未满足；未到账的建议不得当作资金使用。原有平仓/减风险仍独立核验。')
 else:lines.append('本次资金闸核对通过；新开仓仍需执行前真实持仓、风险手数、报价和交易时段检查。')
 lines += ['场外转入须以券商真实现金流与账户回报确认；邮件发送本身不证明到账。','已到账后按真实E重新计算开仓手数；不会自动调用银行转账。','净值如按E/150000展示，包含已到账资金，不能把补资当成交易利润。']
 body='\n'.join(lines)+'\n';subject=f'周线19｜{week}｜'+('资金待核对'if blockers or expired else '场外补资与信号')
 result=dict(schema='weekly19.friday-report.v1',execution_profile=WEEKLY19_15W_R150K_PROFILE.profile_key,material_release_id=release,account_key=account_key,week_key=week,target_date=target,generated_at=now.isoformat(),subject=subject,body=body,preview=preview,production_qualified=False,equity_fen=acct['equity_fen']if acct else None,unrealized_pnl_fen=acct['unrealized_pnl_fen']if acct else None,reserve_remaining_fen=funding_state['reserve_remaining_fen'],current_recommendation_fen=amount,historical_pending_fen=historical,expired_request=expired,funding_ready=funding_ready,actionable=actionable,blockers=blockers,funding_blocker=funding_reason,data_receipt_sha256=data_hash,account_raw_sha256=acct['raw_sha256']if acct else None)
 result['report_sha256']=report_digest(result);return result

class FridayMailOutbox:
 """At-most-once attempt per release/week; ambiguous SMTP never retries itself."""
 def __init__(self,parent):
  self.parent=Path(parent)
  if not self.parent.is_absolute() or self.parent.is_symlink() or self.parent.resolve(strict=True)!=self.parent:raise ReportError('private_outbox_path_required')
  p=self.parent
  while p!=p.parent:
   if p.is_symlink():raise ReportError('outbox_symlink_forbidden')
   p=p.parent
  st=self.parent.stat()
  if not stat.S_ISDIR(st.st_mode)or st.st_uid!=os.geteuid()or stat.S_IMODE(st.st_mode)!=0o700:raise ReportError('private_outbox_mode_required')
 def _directory(self):
  fd=os.open('/',os.O_RDONLY|os.O_DIRECTORY)
  try:
   for part in self.parent.parts[1:]:
    child=os.open(part,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=fd);os.close(fd);fd=child
   st=os.fstat(fd)
   if st.st_uid!=os.geteuid()or stat.S_IMODE(st.st_mode)!=0o700:raise ReportError('private_outbox_mode_required')
   return fd
  except Exception:
   os.close(fd);raise
 def _open(self,name,flags,dirfd,create=False):
  # macOS openat(O_CREAT) can spuriously return ENOENT on a cold race.
  # Create exclusively, then open an existing file without O_CREAT.
  try:
   base=flags|os.O_NOFOLLOW
   if not create:fd=os.open(name,base,0o600,dir_fd=dirfd)
   elif flags&os.O_EXCL:fd=os.open(name,base|os.O_CREAT,0o600,dir_fd=dirfd)
   else:
    for attempt in range(8):
     try:
      fd=os.open(name,base|os.O_CREAT|os.O_EXCL,0o600,dir_fd=dirfd);break
     except FileExistsError:
      try:fd=os.open(name,base,0o600,dir_fd=dirfd);break
      except FileNotFoundError:
       if attempt==7:raise
    else:raise ReportError('outbox_lock_race_exhausted')
  except OSError as exc:raise ReportError('outbox_open_failed')from exc
  st=os.fstat(fd)
  if st.st_uid!=os.geteuid()or st.st_nlink!=1 or not stat.S_ISREG(st.st_mode)or stat.S_IMODE(st.st_mode)!=0o600:os.close(fd);raise ReportError('outbox_file_mode_invalid')
  return fd
 def _write(self,name,obj,dirfd):
  tmp='.'+uuid.uuid4().hex+'.tmp';fd=self._open(tmp,os.O_WRONLY|os.O_EXCL,dirfd,True)
  try:
   with os.fdopen(fd,'wb')as f:f.write(_canonical(obj));f.flush();os.fsync(f.fileno())
   os.replace(tmp,name,src_dir_fd=dirfd,dst_dir_fd=dirfd);os.fsync(dirfd)
  finally:
   try:os.unlink(tmp,dir_fd=dirfd)
   except FileNotFoundError:pass
 def deliver(self,report,sender):
  if report.get('schema')!='weekly19.friday-report.v1'or report.get('execution_profile')!=WEEKLY19_15W_R150K_PROFILE.profile_key or report_digest(report)!=report.get('report_sha256'):raise ReportError('report_digest_or_identity_invalid')
  if '\r'in report['subject']or'\n'in report['subject']:raise ReportError('mail_header_invalid')
  if report['preview']:return dict(status='preview_only',report_sha256=report['report_sha256'])
  key=hashlib.sha256(_canonical([report['execution_profile'],report['material_release_id'],report['week_key']])).hexdigest();name=key+'.json'
  dirfd=self._directory();lock=None
  try:
   lock=self._open('.lock',os.O_RDWR,dirfd,True);fcntl.flock(lock,fcntl.LOCK_EX)
   try:
    fd=self._open(name,os.O_RDONLY,dirfd)
    with os.fdopen(fd,'rb')as f:
     def unique(pairs):
      d={}
      for k,v in pairs:
       if k in d:raise ReportError('duplicate_outbox_key')
       d[k]=v
      return d
     previous=json.loads(f.read(1000000),object_pairs_hook=unique)
    if previous['key']!=key:raise ReportError('outbox_key_mismatch')
    if previous['status']=='sent':return dict(status='already_sent',report_sha256=previous['report_sha256'])
    if previous['status']in{'sending','delivery_unknown'}:return dict(status='delivery_unknown',report_sha256=previous['report_sha256'])
    if previous['status']not in{'blocked_before_send','preview_written'}:raise ReportError('outbox_state_invalid')
   except ReportError as exc:
    if not isinstance(exc.__cause__,FileNotFoundError):raise
   record=dict(schema='weekly19.friday-mail-outbox.v1',key=key,material_release_id=report['material_release_id'],week_key=report['week_key'],report_sha256=report['report_sha256'],status='sending')
   self._write(name,record,dirfd)
   try:
    response=sender(copy.deepcopy(report));mail_status=response.get('email_status')if isinstance(response,dict)else None
    status={'sent':'sent','disabled':'blocked_before_send','blocked_missing_config':'blocked_before_send','dry_run_written':'preview_written'}.get(mail_status,'delivery_unknown')
   except Exception:status='delivery_unknown';mail_status='exception'
   record.update(status=status,transport_status=mail_status);self._write(name,record,dirfd)
   return dict(status=status,report_sha256=report['report_sha256'])
  finally:
   if lock is not None:
    fcntl.flock(lock,fcntl.LOCK_UN);os.close(lock)
   os.close(dirfd)
