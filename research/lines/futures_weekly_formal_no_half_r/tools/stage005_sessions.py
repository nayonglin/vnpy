"""全市场离线研究的首分钟锚适配器（2020+，不是完整盘中日历）。

原19品种逐次委托冻结实现，完全保留其历史行为。新增品种只返回一个
canonical首分钟；必须关闭halfR、C2和AI才允许安装，新增品种任何entry_session
扫描均拒绝，防止将首分钟集合误报为完整分钟覆盖。真实分钟不存在仍由原引擎
严格报错，绝不由本工具把无数据夜盘切换成日盘。

交易所一次性停盘/临时延迟不在通用规则内；实际请求首分钟必须另有原始行情证据。
"""
from __future__ import annotations
from typing import Any, Iterable
import re
import pandas as pd
import qmt_roll_intraday_execution as execution

_LEGACY_SESSION_MINUTES = execution.session_minutes
_LEGACY_ENTRY_SESSION = execution.entry_session

# 原19产品身份也验证交易所，防止产品前缀在错误交易所被错误匹配。
LEGACY_PRODUCTS = {
    'AP.CZCE','CF.CZCE','FG.CZCE','MA.CZCE','OI.CZCE','SA.CZCE','SH.CZCE','SM.CZCE',
    'jm.DCE','lh.DCE','si.GFEX','lc.GFEX','au.SHFE','cu.SHFE','fu.SHFE',
    'hc.SHFE','rb.SHFE','ru.SHFE','sp.SHFE',
}
PRODUCTS_BY_EXCHANGE = {
    'CFFEX': {'IC','IF','IH','IM','T','TF','TL','TS'},
    'CZCE': {'AP','CF','CJ','CY','FG','JR','LR','MA','OI','PF','PK','PL','PM','PR','PX','RI','RM','RS','SA','SF','SH','SM','SR','TA','UR','WH','ZC'},
    'DCE': {'a','b','bb','bz','c','cs','eb','eg','fb','i','j','jd','jm','l','lg','lh','m','p','pg','pp','rr','v','y','l_F','v_F','pp_F'},
    'GFEX': {'lc','ps','si','pd','pt'},
    'INE': {'bc','ec','lu','nr','sc'},
    'SHFE': {'ad','ag','al','ao','au','br','bu','cu','fu','hc','ni','op','pb','rb','ru','sn','sp','ss','wr','zn'},
}
DAY_ONLY = {
    'CZCE': {'AP','CJ','JR','LR','PK','PM','RI','RS','SF','SM','UR','WH'},
    'DCE': {'bb','fb','jd','lg','lh'},
    'GFEX': {'lc','ps','si','pd','pt'},
    'INE': {'ec'},
    'SHFE': {'wr'},
}
# 精确自然上市日；月均价在10-28晚上上市，首归属交易日为10-29。
# 原19产品仍保持冻结行为，不用这些值改写过去已验收结果。
LISTING_DATES = {
    'IM.CFFEX':'2022-07-22','TL.CFFEX':'2023-04-21',
    'PF.CZCE':'2020-10-12','PK.CZCE':'2021-02-01','PL.CZCE':'2025-07-22',
    'PR.CZCE':'2024-08-30','PX.CZCE':'2023-09-15',
    'pg.DCE':'2020-03-30','lg.DCE':'2024-11-18','bz.DCE':'2025-07-08',
    'l_F.DCE':'2025-10-29','v_F.DCE':'2025-10-29','pp_F.DCE':'2025-10-29',
    'ps.GFEX':'2024-12-26','pd.GFEX':'2025-11-27','pt.GFEX':'2025-11-27',
    'bc.INE':'2020-11-19','lu.INE':'2020-06-22','ec.INE':'2023-08-18',
    'ao.SHFE':'2023-06-19','br.SHFE':'2023-07-28','ad.SHFE':'2025-06-10','op.SHFE':'2025-09-10',
}
# 对日盘上市并在当晚开展夜盘的新品种，前一自然日绝不提前开夜盘。
NIGHT_FIRST_NATURAL_DATE = {
    key: value for key,value in LISTING_DATES.items()
    if key.split('.')[0] not in DAY_ONLY.get(key.split('.')[1],set()) and key.split('.')[1]!='CFFEX'
}
NIGHT_FIRST_NATURAL_DATE.update({key:'2025-10-28' for key in ['l_F.DCE','v_F.DCE','pp_F.DCE']})

SOURCES = {
    'SHFE_current_times':'https://www.shfe.com.cn/services/calenderandholidays/tradinghours/',
    'CFFEX_bond_20200720_change':'http://www.cffex.com.cn/jysdt/20200612/24519.html',
    'DCE_201904_night_session_report':'https://www.dce.com.cn/dalianshangpin/resource/cms/2019/05/2019051410181769090.pdf',
    'CZCE_PF_launch':'https://www.czce.com.cn/cn/rootfiles/2020/10/19/1597089064856174-1597089064867882.pdf',
    'CZCE_UR_day_only_rules':'https://www.czce.com.cn/cn/uploadfile/2024/02/07/20240207112158603.pdf',
    'CZCE_PR_launch':'http://www.czce.com.cn/cn/gyjys/jysdt/ggytz/webinfo/2024/08/1715239664760267.htm',
    'CZCE_PL_launch':'http://www.czce.com.cn/cn/gyjys/jysdt/ggytz/webinfo/2025/07/1750860252014637.htm',
    'SHFE_AD_launch':'https://www.shfe.com.cn/publicnotice/notice/202505/t20250526_827862.html',
    'SHFE_OP_launch':'https://www.shfe.com.cn/publicnotice/notice/202508/t20250818_828697.html',
    'DCE_BZ_launch':'http://www.dce.com.cn/dalianshangpin/ywfw/jystz/ywtz/8637864/index.html',
    'DCE_LG_launch':'http://www.dce.com.cn/dalianshangpin/ywfw/jystz/ywtz/8617136/index.html',
    'DCE_average_price_launch':'http://www.dce.com.cn/dce/content/2025/ywggytz/18623631.html',
    'DCE_average_price_rules':'https://www.investor.org.cn/information_release/news_release_from_authorities/qhjysfb/202504/t20250425_839040.shtml',
    'GFEX_PD_contract':'https://www.gfex.com.cn/gfex/pqqhy/202511/6ee85884edc8497695ccb8adcaea67eb.shtml',
    'GFEX_day_only_contract':'https://www.gfex.com.cn/gfex/sytslqhhy/202307/9ad927b8ec4c458594e172fd1ada2a9b.shtml',
}


def product_symbol(vt_symbol: str) -> str:
    match = re.fullmatch(r'([A-Za-z]+)([0-9]{3,4})(F?)\.([A-Z]+)',str(vt_symbol))
    if match is None:
        raise ValueError(f'intraday_unsupported_session:{vt_symbol}')
    prefix,_,suffix,exchange = match.groups()
    product = prefix + ('_F' if suffix else '')
    if product not in PRODUCTS_BY_EXCHANGE.get(exchange,set()):
        raise ValueError(f'intraday_unsupported_session:{vt_symbol}')
    return product + '.' + exchange


def _calendar(day: pd.Timestamp, vt_symbol: str, calendar: Iterable[Any]):
    dates = sorted({execution.local_timestamp(value).normalize() for value in calendar})
    if day not in dates:
        raise ValueError(f'intraday_calendar_missing:{vt_symbol}:{day.date()}')
    return dates


def canonical_open_timestamp(vt_symbol: str, trading_date: Any, calendar: Iterable[Any]) -> pd.Timestamp:
    product_vt = product_symbol(vt_symbol)
    dates = list(calendar)
    if product_vt in LEGACY_PRODUCTS:
        return _LEGACY_SESSION_MINUTES(vt_symbol,trading_date,dates)[0]
    day = execution.local_timestamp(trading_date).normalize()
    dates = _calendar(day,vt_symbol,dates)
    if day < pd.Timestamp('2020-01-01'):
        raise ValueError(f'intraday_research_date_out_of_scope:{vt_symbol}:{day.date()}')
    if day < pd.Timestamp(LISTING_DATES.get(product_vt,'2020-01-01')):
        raise ValueError(f'intraday_before_listing:{vt_symbol}:{day.date()}')
    product,exchange = product_vt.split('.')
    if exchange=='CFFEX':
        if product in {'T','TF','TS'} and day < pd.Timestamp('2020-07-20'):
            return day + pd.Timedelta(hours=9,minutes=15)
        return day + pd.Timedelta(hours=9,minutes=30)
    if product in DAY_ONLY.get(exchange,set()):
        return day + pd.Timedelta(hours=9)
    earlier = [value for value in dates if value < day]
    if not earlier:
        raise ValueError(f'intraday_previous_trading_date_missing:{vt_symbol}:{day.date()}')
    previous=earlier[-1]
    gap=(day-previous).days
    active = gap==1 or (previous.weekday()==4 and day.weekday()==0 and gap==3)
    active = active and not (pd.Timestamp('2020-02-03') <= previous < pd.Timestamp('2020-05-06'))
    active = active and previous >= pd.Timestamp(NIGHT_FIRST_NATURAL_DATE.get(product_vt,'2019-12-31'))
    return previous+pd.Timedelta(hours=21) if active else day+pd.Timedelta(hours=9)


def session_minutes(vt_symbol: str, trading_date: Any, calendar: Iterable[Any]) -> pd.DatetimeIndex:
    product = product_symbol(vt_symbol)
    if product in LEGACY_PRODUCTS:
        return _LEGACY_SESSION_MINUTES(vt_symbol,trading_date,calendar)
    return pd.DatetimeIndex([canonical_open_timestamp(vt_symbol,trading_date,calendar)])


def install_open_anchor_adapter(settings: dict[str,Any]):
    """本研究进程内安装；返回恢复函数。不得供开启盘中模块的运行使用。"""
    keys = ['enable_stage847_half_r_stop_retry','enable_stage827_intraday_c2_stop','enable_ai_product_pool_filter']
    if any(settings.get(key) is not False for key in keys):
        raise ValueError('stage005_adapter_requires_halfR_C2_AI_disabled')
    previous_session, previous_entry = execution.session_minutes, execution.entry_session
    def guarded_entry(strategy,trade):
        if product_symbol(str(trade.vt_symbol)) not in LEGACY_PRODUCTS:
            raise ValueError('stage005_anchor_only_not_full_intraday_scan:'+str(trade.vt_symbol))
        return _LEGACY_ENTRY_SESSION(strategy,trade)
    execution.session_minutes=session_minutes
    execution.entry_session=guarded_entry
    def restore():
        execution.session_minutes=previous_session
        execution.entry_session=previous_entry
    return restore
