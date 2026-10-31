"""Bind the existing execution control windows to the actual broker TradingDay.

Instrument tradability still requires a current real CTP quote and the native
broker capacity/price/session guards. This resolver does not generate quotes.
"""
from datetime import date,datetime,timedelta
from zoneinfo import ZoneInfo
from qmt_roll_official_live_phase_d_config import build_phase_d_config

SHANGHAI=ZoneInfo('Asia/Shanghai')
class Weekly19SessionClockError(ValueError):pass

def resolve_weekly19_session(*,now,broker_trading_date,calendar):
 if not isinstance(now,datetime)or now.tzinfo is None:raise Weekly19SessionClockError('weekly19_aware_session_clock_required')
 day=date.fromisoformat(broker_trading_date).isoformat();days=sorted({date.fromisoformat(str(d)).isoformat()for d in calendar})
 current=now.astimezone(SHANGHAI);today=current.date();selected=None
 for spec in build_phase_d_config().sessions:
  if spec.role!='market_and_execution':continue
  sh,sm=map(int,spec.start.split(':'));eh,em=map(int,spec.end.split(':'))
  starts=current.replace(hour=sh,minute=sm,second=0,microsecond=0);ends=current.replace(hour=eh,minute=em,second=0,microsecond=0)
  if ends<=starts:
   if current<ends:starts-=timedelta(days=1)
   else:ends+=timedelta(days=1)
  if starts<=current<ends:selected=(spec,starts,ends);break
 if selected is None:
  return dict(is_open=False,trading_date=day,session_id='weekly19-closed:'+day,starts_at=current.isoformat(),ends_at=current.isoformat(),
   source_kind='canonical_execution_control_window',blocked_reason='outside_execution_window')
 spec,starts,ends=selected;natural_start=starts.date().isoformat()
 expected=next((d for d in days if d>natural_start),None)if spec.name in {'night','late_night'}else natural_start
 valid=natural_start in days and day==expected
 return dict(is_open=valid,trading_date=day,session_id='weekly19:'+day+':'+spec.name+':'+natural_start,
  starts_at=starts.isoformat(),ends_at=ends.isoformat(),source_kind='canonical_execution_control_window',
  control_window=spec.name,blocked_reason=''if valid else'broker_day_or_authoritative_calendar_mismatch')
