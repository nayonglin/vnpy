"""完整真实合约周线指标；保留正式日线执行、换月和非半R风控。"""
from copy import copy
from datetime import date
import math

def completed_weeks(trading_dates):
    days=sorted({str(d)[:10] for d in trading_dates})
    groups={}
    for d in days:
        key=date.fromisoformat(d).isocalendar()[:2]
        groups.setdefault(key,[]).append(d)
    result={}
    for group in groups.values():
        last=group[-1]
        # Future session dates are calendar knowledge only; terminal partial week stays open.
        if last!=days[-1] or date.fromisoformat(last).weekday()==4:
            result[tuple(date.fromisoformat(last).isocalendar()[:2])]=tuple(group)
    return result

class WeeklyArrayManager:
    def __init__(self,inner,weeks):
        self.inner=inner;self.weeks=weeks;self.pending={};self.key=None;self.fresh=False
        self.rejected=[];self.completed=[];self.last_real_date=None;self.max_count=0
    def __getattr__(self,name):return getattr(self.inner,name)
    def update_bar(self,bar):
        self.fresh=False
        d=bar.datetime.date();day=d.isoformat();key=tuple(d.isocalendar()[:2])
        if self.key!=key:self.pending={};self.key=key
        prices=[float(getattr(bar,x)) for x in ['open_price','high_price','low_price','close_price']]
        if float(bar.volume)<=0 or not all(math.isfinite(x) and x>0 for x in prices):return
        if self.last_real_date is not None and (d-self.last_real_date).days>366:
            # CZCE three-digit names are reused after a decade; never splice separate contracts.
            self.inner=type(self.inner)(self.inner.size);self.pending={}
        self.last_real_date=d
        self.pending[day]=copy(bar)
        expected=self.weeks.get(key)
        if not expected or day!=expected[-1]:return
        if set(self.pending)!=set(expected):
            self.rejected.append(dict(week_end=day,expected=list(expected),actual=sorted(self.pending)))
            return
        ordered=[self.pending[x] for x in expected];weekly=copy(ordered[-1])
        weekly.open_price=ordered[0].open_price
        weekly.high_price=max(x.high_price for x in ordered);weekly.low_price=min(x.low_price for x in ordered)
        weekly.volume=sum(x.volume for x in ordered);weekly.turnover=sum(getattr(x,'turnover',0.) for x in ordered)
        self.inner.update_bar(weekly);self.fresh=True;self.max_count=max(self.max_count,self.inner.count)
        self.completed.append(dict(week_end=day,open=weekly.open_price,high=weekly.high_price,low=weekly.low_price,
            close=weekly.close_price,volume=weekly.volume,open_interest=weekly.open_interest,source_days=list(expected)))

def weekly_strategy_class(base,weeks):
    class WeeklyIndicatorsStrategy(base):
        def __init__(self,*args,**kwargs):
            super().__init__(*args,**kwargs)
            self.ams={symbol:WeeklyArrayManager(am,weeks) for symbol,am in self.ams.items()}
            self.weekly_readiness=[]
        def on_bars(self,bars):
            # No filling of missing contract dates. Base engine supplies actual bars to on_bars.
            result=super().on_bars(bars)
            day=next(iter(bars.values())).datetime.strftime('%Y-%m-%d') if bars else ''
            if day>='2020-01-01':
                targets=self.daily_mapping.get(day,{})
                self.weekly_readiness.append(dict(date=day,mapped_products=len(targets),
                    ready_target_contracts=sum(bool(self.ams.get(s) and self.ams[s].inited) for s in targets.values()),
                    newly_completed_targets=sum(bool(self.ams.get(s) and self.ams[s].fresh) for s in targets.values())))
            return result
        def _generate_signal(self,am,history):
            result=dict(super()._generate_signal(am,history))
            if not am.fresh:result.update(signal='',breakout=False)
            return result
    return WeeklyIndicatorsStrategy
