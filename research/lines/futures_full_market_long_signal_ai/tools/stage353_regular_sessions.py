"""Pure, bounded operational date expansion; no loader, SDK, T0 or finality.

Only350's three dates are supported. The caller supplies actual quote metadata,
confirmed calendar and regular-day evidence. Outputs are clock candidates, not
source_completed_at or a claim that all temporary exceptions were excluded.
"""
from copy import deepcopy
from datetime import date,datetime,time,timedelta
import math
import re
from zoneinfo import ZoneInfo

CHINA=ZoneInfo('Asia/Shanghai')
ANCHORS={'2026-10-19':'2026-10-16','2026-10-20':'2026-10-19','2026-10-21':'2026-10-20'}


def expand_sessions(metadata,trade_date,*,calendar,night_anchors,evidence,last_day_override=None):
    """metadata: symbol,metadata_received,day,night,expire_datetime,source_receipt.

    evidence has policy='operational_regular_schedule' and source_receipt.
    Last-day override, if supplied, has explicit day/night/source_receipt.
    Expiry=None is genuinely unknown, not permission to assume no expiry.
    Empty night is observed_empty only after real metadata and valid day parse.
    first_open is the original continuous-session execution-open convention;
    auction is separate and never inferred by subtracting five minutes.
    """
    out=dict(schema='stage353_regular_session_candidates_v1',symbol=metadata.get('symbol'),
        trade_date=trade_date,state='unknown',reasons=[],intervals=[],first_open=None,
        session_end=None,night_state='unknown',expiry_state='unknown',auction=None,
        source_receipt=deepcopy(metadata.get('source_receipt')),evidence=deepcopy(evidence),
        assurance='operational candidates;not exhaustive exception exclusion or vendor finality')
    def unknown(reason):
        out['reasons'].append(reason);return out
    fields={'symbol','metadata_received','day','night','expire_datetime','source_receipt'}
    if not fields<=metadata.keys():return unknown('metadata_fields_missing')
    if not isinstance(metadata['symbol'],str) or not metadata['symbol']:return unknown('symbol_invalid')
    if metadata['metadata_received'] is not True:return unknown('metadata_not_received')
    if not metadata['source_receipt']:return unknown('metadata_receipt_missing')
    if (not isinstance(evidence,dict) or evidence.get('policy')!='operational_regular_schedule'
            or not evidence.get('source_receipt')):return unknown('regular_schedule_evidence_missing')
    try:
        target=date.fromisoformat(trade_date)
        if target.isoformat()!=trade_date or trade_date not in ANCHORS:raise ValueError()
    except (ValueError,TypeError):return unknown('date_outside_fixed_scope')
    if calendar.get(trade_date) is not True:return unknown('trade_date_not_confirmed')
    expiry=metadata['expire_datetime']
    if isinstance(expiry,bool) or not isinstance(expiry,(int,float)) or not math.isfinite(expiry):
        return unknown('expiry_unknown_or_unparseable')
    try:expiry_day=datetime.fromtimestamp(expiry,CHINA).date()
    except (OverflowError,OSError,ValueError):return unknown('expiry_unknown_or_unparseable')
    if target>expiry_day:
        out.update(state='expired',expiry_state='after_expiry_day');return out
    day,night=metadata['day'],metadata['night']
    out['expiry_state']='before_expiry_day'
    if target==expiry_day:
        if (not isinstance(last_day_override,dict) or not {'day','night','source_receipt'}<=last_day_override.keys()
                or not last_day_override['source_receipt']):return unknown('last_day_override_missing')
        day,night=last_day_override['day'],last_day_override['night']
        out['expiry_state']='last_day_override_applied';out['last_day_override']=deepcopy(last_day_override)
    elif last_day_override is not None:return unknown('override_not_on_expiry_day')

    def parsed(periods,kind):
        if not isinstance(periods,list) or (kind=='day' and not periods):raise ValueError('template_missing_'+kind)
        result=[]
        for pair in periods:
            if not isinstance(pair,(list,tuple)) or len(pair)!=2:raise ValueError('template_pair_invalid')
            values=[]
            for literal in pair:
                if not isinstance(literal,str) or not re.fullmatch(r'\d{1,2}:\d{2}:\d{2}',literal):
                    raise ValueError('template_time_unparseable')
                h,m,s=map(int,literal.split(':'))
                if h>47 or m>59 or s>59 or (kind=='day' and h>23):raise ValueError('template_time_invalid')
                values.append(h*3600+m*60+s)
            if values[0]>=values[1] or (kind=='night' and values[0]<18*3600):
                raise ValueError('template_order_or_night_anchor_invalid')
            result.append(values)
        result.sort()
        if any(a[1]>b[0] for a,b in zip(result,result[1:])):raise ValueError('template_conflict')
        return result
    try:day,night=parsed(day,'day'),parsed(night,'night')
    except ValueError as error:return unknown(str(error))
    anchor=None
    if night:
        literal=night_anchors.get(trade_date)
        if literal!=ANCHORS[trade_date] or calendar.get(literal) is not True:
            return unknown('night_anchor_not_confirmed')
        anchor=date.fromisoformat(literal)
        between=anchor+timedelta(days=1)
        while between<target:
            flag=calendar.get(between.isoformat())
            if flag is True or (between.weekday()<5 and flag is not False):
                return unknown('intervening_session_or_holiday_unknown')
            if flag is not None and not isinstance(flag,bool):return unknown('calendar_boolean_required')
            between+=timedelta(days=1)
    intervals=[]
    for kind,base,periods in [('night',anchor,night),('day',target,day)]:
        if not periods:continue
        start=datetime.combine(base,time(),CHINA)
        intervals.extend((start+timedelta(seconds=a),start+timedelta(seconds=b),kind) for a,b in periods)
    intervals.sort()
    if any(a[1]>b[0] for a,b in zip(intervals,intervals[1:])):return unknown('concrete_interval_conflict')
    out.update(state='operational_regular_schedule',night_state='observed_intervals' if night else 'observed_empty',
        night_anchor=anchor.isoformat() if anchor else None,first_open=intervals[0][0].isoformat(),
        session_end=max(v[1] for v in intervals).isoformat(),
        intervals=[dict(kind=k,start=a.isoformat(),end=b.isoformat()) for a,b,k in intervals])
    return out
