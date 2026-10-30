"""Independent calendar/scope definitions. Never imports finance or a runner."""
from datetime import date
DEFAULT_MONTHS=(1,3,6,9,11)
DEFAULT_CUTOFF='2026-10-30'
def canonical_starts(months=DEFAULT_MONTHS,cutoff=DEFAULT_CUTOFF):
 months=tuple(months);end=date.fromisoformat(cutoff)
 if len(months)!=5 or len(set(months))!=5 or sorted(months)!=list(months) or any(type(m)is not int or not 1<=m<=12 for m in months):raise ValueError('five_unique_sorted_explicit_months_required')
 return [f'{y}-{m:02d}-01' for y in range(2015,end.year+1) for m in months if date(y,m,1)<=end]
def mature(start,cutoff=DEFAULT_CUTOFF):
 d=date.fromisoformat(start);return d.replace(year=d.year+1)<=date.fromisoformat(cutoff)
def completed_weeks(calendar):
 groups={}
 for day in sorted(set(calendar)):
  d=date.fromisoformat(day);groups.setdefault(d.isocalendar()[:2],[]).append(day)
 end=max(calendar);return {key:days for key,days in groups.items() if days[-1]<end or date.fromisoformat(days[-1]).weekday()==4}
def scope(f):
 months=f['start_months'];starts=canonical_starts(months,f['cutoff'])
 assert f['starts']==starts and f['arms']==['C'] and f['planned_arm_windows']==f['planned_financial_replays']==len(starts)
 assert f['engine_initial_capital']==f['reserve_initial_capital']==150000 and f['total_initial_capital']==300000
 return dict(starts=starts,start_months=months,cutoff=f['cutoff'],windows=len(starts),mature=sum(mature(s,f['cutoff']) for s in starts),observation=sum(not mature(s,f['cutoff']) for s in starts))
