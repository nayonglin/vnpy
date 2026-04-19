# -*- coding: gbk -*-
# 期货多空排布策略 - 多合约优化版本
# 上期所	SHFE	SF
# 大商所	DCE	    DF
# 郑商所	CZCE	ZF
# 中金所	CFFEX	IF
# 能源中心	INE  	INE
# 广期所	GFEX	GF

# 分层仓位管理说明：
# 1. 每个合约的初始开仓作为一个独立的仓位层
# 2. 每次加仓都会创建一个新的仓位层，记录加仓价格、手数和时间
# 3. 每个仓位层独立计算盈亏，独立判断是否触发止损条件
# 4. 当某个仓位层触发止损时，只平仓该层的仓位，不影响其他层
# 5. 移动止损基于整个持仓的加权平均成本价计算，但每个层可以独立触发止损

# 持仓记录结构说明：
# G['open_positions'][contract_code] = {
#     'direction': 'long' or 'short',           # 持仓方向
#     'price': initial_entry_price,             # 初始开仓价格
#     'volume': initial_volume,                 # 初始开仓手数
#     'time': open_time,                        # 开仓时间
#     'avg_price': weighted_average_price,      # 加权平均成本价
#     'total_volume': total_current_volume,     # 总持仓手数
#     'add_positions': [                        # 加仓记录列表
#         {
#             'price': add_price,               # 加仓价格
#             'volume': add_volume,             # 加仓手数
#             'time': add_time,                 # 加仓时间
#             'type': 'first_add' or 'second_add'  # 加仓类型
#         },
#         ...
#     ],
#     'add_count': number_of_adds,             # 旧盈利加仓次数
#     'donchian_add_positions': [              # 独立唐奇安加仓层
#         {
#             'price': add_price,
#             'volume': add_volume,
#             'time': add_time,
#             'type': 'donchian_add_1',
#             'trailing_stop_price': stop_price
#         },
#         ...
#     ],
#     'donchian_add_count': number_of_adds     # 唐奇安加仓次数
# }

# 移动止损记录结构说明：
# G['max_profit_tracking'][contract_code] = {
#     'max_profit_pct': max_profit_percentage,  # 历史最大盈利比例
#     'trailing_stop_price': trailing_stop_price,  # 当前移动止损价格
#     'last_update_time': last_update_time     # 最后更新时间
# }


import numpy as np
import pandas as pd
import datetime
import time
import logging
import os
import csv
import re
import json
import math
import pickle
import smtplib
import ssl
from email.message import EmailMessage

# 全局变量，用于存储策略参数和状态
G = {}

DOMESTIC_FUTURES_VARIETIES = {
    'SF': [
        'ag', 'al', 'ao', 'au', 'bu', 'cu', 'fu', 'hc', 'ni', 'pb', 'rb', 'ru', 'sn', 'sp', 'ss', 'zn', 'br', 'ad',
    ],
    'DF': [
        'a', 'b', 'c', 'cs', 'eb', 'eg', 'i', 'j', 'jd', 'jm', 'l', 'lh', 'lg', 'm', 'p', 'pg', 'pp', 'rr', 'v', 'y',
    ],
    'ZF': [
        'ap', 'cf', 'cj', 'cy', 'fg', 'jr', 'lr', 'ma', 'oi', 'pf', 'pk', 'pm', 'px', 'ri', 'rm', 'rs', 'sa', 'sf',
        'sh', 'sm', 'sr', 'ta', 'ur', 'wh', 'zc',
    ],
    'CF': [
        'IC', 'IF', 'IH', 'IM', 'T', 'TF', 'TL', 'TS',
    ],
    'INE': [
        'bc', 'ec', 'lu', 'nr', 'sc',
    ],
    'GF': [
        'lc', 'ps', 'si',
    ],
}


def build_all_domestic_futures_base_codes():
    out = []
    for ex, syms in (DOMESTIC_FUTURES_VARIETIES or {}).items():
        if not syms:
            continue
        for s in syms:
            if not s:
                continue
            out.append(f"{str(s)}.{str(ex)}")
    return out


def _ai_sigmoid(x):
    try:
        x = float(x)
    except Exception:
        return 0.5
    if x >= 0:
        z = math.exp(-x)
        return 1.0 / (1.0 + z)
    z = math.exp(x)
    return z / (1.0 + z)


def _ai_get_base_dir():
    try:
        return os.path.dirname(__file__)
    except Exception:
        return os.getcwd()


def _ai_load_position_model():
    cached = G.get('ai_position_model_cache')
    if isinstance(cached, dict) and cached.get('feature_names'):
        return cached

    model_path = G.get('ai_position_model_path')
    if not model_path:
        model_path = os.path.join(_ai_get_base_dir(), 'ai_position_model.json')
        G['ai_position_model_path'] = model_path

    try:
        if not os.path.isfile(model_path):
            return None
        with open(model_path, 'r', encoding='utf-8') as f:
            model = json.load(f)
        if not isinstance(model, dict):
            return None
        if not model.get('feature_names'):
            return None
        G['ai_position_model_cache'] = model
        return model
    except Exception as e:
        try:
            if G.get('logger'):
                G['logger'].warning(f"AI模型加载失败: {e}")
        except Exception:
            pass
        return None


def _ai_build_features_from_bar(direction, market_data_df, current_macd, current_rsi, is_bullish_alignment, is_bearish_alignment):
    close = market_data_df['close'] if market_data_df is not None and 'close' in market_data_df else None
    volume = market_data_df['volume'] if market_data_df is not None and 'volume' in market_data_df else None
    high = market_data_df['high'] if market_data_df is not None and 'high' in market_data_df else None
    low = market_data_df['low'] if market_data_df is not None and 'low' in market_data_df else None
    try:
        if close is not None:
            close = pd.to_numeric(close, errors='coerce')
        if volume is not None:
            volume = pd.to_numeric(volume, errors='coerce')
        if high is not None:
            high = pd.to_numeric(high, errors='coerce')
        if low is not None:
            low = pd.to_numeric(low, errors='coerce')
    except Exception:
        pass

    ret_1 = 0.0
    ret_5 = 0.0
    vol_5 = 0.0
    vol_ratio_20 = 1.0
    ma_slope_20 = 0.0
    ma_slope_10 = 0.0
    price_to_ma20 = 0.0
    price_to_ma10 = 0.0
    price_to_ma5 = 0.0
    er_20 = 0.0
    atr_pct_14 = 0.0
    bb_width_20 = 0.0
    flip_rate_20 = 0.0
    donchian_width_20 = 0.0

    try:
        if close is not None and len(close) >= 2:
            ret_1 = float(close.iloc[-1] / close.iloc[-2] - 1.0)
        if close is not None and len(close) >= 6:
            ret_5 = float(close.iloc[-1] / close.iloc[-6] - 1.0)
        if close is not None and len(close) >= 6:
            rets = close.pct_change().iloc[-6:]
            vol_5 = float(rets.std(ddof=0))
    except Exception:
        pass

    try:
        if volume is not None and len(volume) >= 2:
            v_now = float(volume.iloc[-1])
            v_mean = float(volume.tail(20).mean()) if len(volume) >= 20 else float(volume.mean())
            if v_mean > 0:
                vol_ratio_20 = v_now / v_mean
    except Exception:
        pass

    try:
        if close is not None:
            ma20 = close.rolling(window=int(G.get('ma_long', 20) or 20)).mean()
            ma10 = close.rolling(window=int(G.get('ma_mid', 10) or 10)).mean()
            ma5 = close.rolling(window=int(G.get('ma_short', 5) or 5)).mean()
            if len(ma20) >= 2 and not pd.isna(ma20.iloc[-1]) and not pd.isna(ma20.iloc[-2]):
                ma_slope_20 = float((ma20.iloc[-1] - ma20.iloc[-2]) / close.iloc[-1]) if float(close.iloc[-1]) != 0 else 0.0
            if len(ma10) >= 2 and not pd.isna(ma10.iloc[-1]) and not pd.isna(ma10.iloc[-2]):
                ma_slope_10 = float((ma10.iloc[-1] - ma10.iloc[-2]) / close.iloc[-1]) if float(close.iloc[-1]) != 0 else 0.0
            if len(ma20) >= 1 and not pd.isna(ma20.iloc[-1]) and float(ma20.iloc[-1]) != 0:
                price_to_ma20 = float(close.iloc[-1] / ma20.iloc[-1] - 1.0)
            if len(ma10) >= 1 and not pd.isna(ma10.iloc[-1]) and float(ma10.iloc[-1]) != 0:
                price_to_ma10 = float(close.iloc[-1] / ma10.iloc[-1] - 1.0)
            if len(ma5) >= 1 and not pd.isna(ma5.iloc[-1]) and float(ma5.iloc[-1]) != 0:
                price_to_ma5 = float(close.iloc[-1] / ma5.iloc[-1] - 1.0)
    except Exception:
        pass

    direction_sign = 1.0 if str(direction) == 'long' else -1.0
    try:
        if close is not None and len(close) >= 21:
            w = 20
            num = float(abs(close.iloc[-1] - close.iloc[-1 - w]))
            den = float(close.diff().abs().tail(w).sum())
            if den > 0:
                er_20 = num / den
    except Exception:
        pass

    try:
        if close is not None and len(close) >= 21:
            rets = close.pct_change().tail(20).to_numpy(dtype=float)
            if len(rets) >= 2:
                s = np.sign(rets)
                flips = (s[1:] * s[:-1] < 0).astype(float)
                flip_rate_20 = float(np.nanmean(flips)) if len(flips) > 0 else 0.0
    except Exception:
        pass

    try:
        if close is not None and len(close) >= 21:
            ma = close.rolling(20).mean()
            sd = close.rolling(20).std(ddof=0)
            if not pd.isna(ma.iloc[-1]) and float(ma.iloc[-1]) != 0 and not pd.isna(sd.iloc[-1]):
                bb_width_20 = float((4.0 * float(sd.iloc[-1])) / float(ma.iloc[-1]))
    except Exception:
        pass

    try:
        if close is not None and high is not None and low is not None and len(close) >= 15 and len(high) >= 15 and len(low) >= 15:
            prev_close = close.shift(1)
            tr = pd.concat([(high - low).abs(), (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)
            atr = tr.rolling(14).mean()
            if not pd.isna(atr.iloc[-1]) and float(close.iloc[-1]) != 0:
                atr_pct_14 = float(float(atr.iloc[-1]) / float(close.iloc[-1]))
    except Exception:
        pass

    try:
        if close is not None and high is not None and low is not None and len(close) >= 21 and len(high) >= 21 and len(low) >= 21:
            hi = high.rolling(20).max()
            lo = low.rolling(20).min()
            if not pd.isna(hi.iloc[-1]) and not pd.isna(lo.iloc[-1]) and float(close.iloc[-1]) != 0:
                donchian_width_20 = float((float(hi.iloc[-1]) - float(lo.iloc[-1])) / float(close.iloc[-1]))
    except Exception:
        pass

    return {
        'direction': float(direction_sign),
        'macd_value': float(current_macd) if current_macd is not None else 0.0,
        'rsi_6': float(current_rsi) if current_rsi is not None else 50.0,
        'align_bull': 1.0 if bool(is_bullish_alignment) else 0.0,
        'align_bear': 1.0 if bool(is_bearish_alignment) else 0.0,
        'ret_1': float(ret_1),
        'ret_5': float(ret_5),
        'vol_5': float(vol_5),
        'vol_ratio_20': float(vol_ratio_20),
        'ma_slope_20': float(ma_slope_20),
        'ma_slope_10': float(ma_slope_10),
        'price_to_ma20': float(price_to_ma20),
        'price_to_ma10': float(price_to_ma10),
        'price_to_ma5': float(price_to_ma5),
        'er_20': float(er_20),
        'atr_pct_14': float(atr_pct_14),
        'bb_width_20': float(bb_width_20),
        'flip_rate_20': float(flip_rate_20),
        'donchian_width_20': float(donchian_width_20),
    }


def ai_predict_position_multiplier(direction, market_data_df, current_macd, current_rsi, is_bullish_alignment, is_bearish_alignment):
    if not bool(G.get('ai_position_enabled', False)):
        return float(G.get('ai_position_fallback_multiplier', 1.0) or 1.0)

    try:
        min_mult = float(G.get('ai_position_min_multiplier', 0.3) or 0.3)
    except Exception:
        min_mult = 0.3
    try:
        max_mult = float(G.get('ai_position_max_multiplier', 1.5) or 1.5)
    except Exception:
        max_mult = 1.5
    if min_mult < 0:
        min_mult = 0.0
    if max_mult < min_mult:
        max_mult = min_mult

    model = _ai_load_position_model()
    if not model:
        return float(G.get('ai_position_fallback_multiplier', 1.0) or 1.0)

    feats = _ai_build_features_from_bar(direction, market_data_df, current_macd, current_rsi, is_bullish_alignment, is_bearish_alignment)
    feature_names = model.get('feature_names') or []
    weights = model.get('weights') or []
    means = model.get('means') or []
    stds = model.get('stds') or []
    try:
        bias = float(model.get('bias', 0.0) or 0.0)
    except Exception:
        bias = 0.0

    if len(feature_names) != len(weights):
        return float(G.get('ai_position_fallback_multiplier', 1.0) or 1.0)

    z = bias
    contribs = []
    for i, name in enumerate(feature_names):
        try:
            x_raw = float(feats.get(name, 0.0) or 0.0)
        except Exception:
            x_raw = 0.0
        if not math.isfinite(x_raw):
            x_raw = 0.0
        x = x_raw
        if i < len(means) and i < len(stds):
            try:
                mu = float(means[i])
                sd = float(stds[i])
            except Exception:
                mu, sd = 0.0, 1.0
            if sd and sd > 0:
                x = (x - mu) / sd
        try:
            w = float(weights[i])
        except Exception:
            w = 0.0
        if not math.isfinite(w):
            w = 0.0
        c = w * x
        z += c
        contribs.append((str(name), float(x_raw), float(x), float(w), float(c)))

    p = _ai_sigmoid(z)
    if not math.isfinite(p):
        return float(G.get('ai_position_fallback_multiplier', 1.0) or 1.0)

    mode = str(G.get('ai_position_mapping_mode', 'tier') or 'tier').lower()
    tier = None
    if mode == 'linear':
        qs = model.get('p_quantiles') if isinstance(model, dict) else None
        if not isinstance(qs, dict):
            qs = {}
        q25 = qs.get('q25', None)
        q50 = qs.get('q50', None)
        q75 = qs.get('q75', None)
        try:
            q25 = float(q25) if q25 is not None else None
        except Exception:
            q25 = None
        try:
            q50 = float(q50) if q50 is not None else None
        except Exception:
            q50 = None
        try:
            q75 = float(q75) if q75 is not None else None
        except Exception:
            q75 = None

        try:
            center_mult = float(G.get('ai_position_linear_center_mult', 1.0) or 1.0)
        except Exception:
            center_mult = 1.0
        try:
            target_q25 = float(G.get('ai_position_linear_target_q25', 0.8) or 0.8)
        except Exception:
            target_q25 = 0.8
        try:
            target_q75 = float(G.get('ai_position_linear_target_q75', 1.2) or 1.2)
        except Exception:
            target_q75 = 1.2

        if q25 is None or q50 is None or q75 is None or not (q25 < q50 < q75):
            mult = min_mult + p * (max_mult - min_mult)
        else:
            if p >= q50:
                denom = (q75 - q50)
                slope = (target_q75 - center_mult) / denom if denom > 1e-12 else 0.0
            else:
                denom = (q50 - q25)
                slope = (center_mult - target_q25) / denom if denom > 1e-12 else 0.0
            mult = center_mult + slope * (p - q50)
    else:
        qs = model.get('p_quantiles') if isinstance(model, dict) else None
        if not isinstance(qs, dict):
            qs = {}
        low_thr = G.get('ai_position_low_p_threshold', None)
        high_thr = G.get('ai_position_high_p_threshold', None)
        if low_thr is None:
            low_thr = qs.get('q25', 0.40)
        if high_thr is None:
            high_thr = qs.get('q75', 0.60)
        try:
            low_thr = float(low_thr)
        except Exception:
            low_thr = 0.40
        try:
            high_thr = float(high_thr)
        except Exception:
            high_thr = 0.60
        if high_thr < low_thr:
            high_thr = low_thr

        try:
            low_mult = float(G.get('ai_position_low_multiplier', 0.7) or 0.7)
        except Exception:
            low_mult = 0.7
        try:
            mid_mult = float(G.get('ai_position_mid_multiplier', 1.0) or 1.0)
        except Exception:
            mid_mult = 1.0
        try:
            high_mult = float(G.get('ai_position_high_multiplier', 1.2) or 1.2)
        except Exception:
            high_mult = 1.2

        if p >= high_thr:
            mult = high_mult
            tier = 'HIGH'
        elif p <= low_thr:
            mult = low_mult
            tier = 'LOW'
        else:
            mult = mid_mult
            tier = 'MID'

    if not math.isfinite(mult):
        return float(G.get('ai_position_fallback_multiplier', 1.0) or 1.0)
    if mult < min_mult:
        mult = min_mult
    if mult > max_mult:
        mult = max_mult

    try:
        if G.get('logger') and bool(G.get('ai_position_log_enabled', True)):
            top = []
            try:
                top = sorted(contribs, key=lambda t: abs(float(t[4])), reverse=True)[:3]
            except Exception:
                top = []
            top_s = ",".join([f"{t[0]}:{t[4]:+.3f}" for t in top]) if top else ""
            if tier:
                G['logger'].info(f"AI动态仓位: p={p:.3f} 倍率={mult:.3f} 档位={tier} (范围 {min_mult:.2f}-{max_mult:.2f}) {top_s}")
            else:
                G['logger'].info(f"AI动态仓位: p={p:.3f} 倍率={mult:.3f} (范围 {min_mult:.2f}-{max_mult:.2f}) {top_s}")
    except Exception:
        pass

    return float(mult)


def train_ai_position_model_from_market_data_csv(csv_path, output_path=None, horizon_days=5, max_rows=None, max_drawdown=0.06, min_profit=0.0, profit_quantile=0.7):
    df = pd.read_csv(csv_path)
    if max_rows is not None:
        try:
            df = df.head(int(max_rows))
        except Exception:
            pass

    needed = [
        'contract', 'bt_date', 'open', 'high', 'low', 'close', 'volume',
        'macd_value', 'rsi_6',
        'ma_short_t', 'ma_mid_t', 'ma_long_t',
        'ma_short_y', 'ma_mid_y', 'ma_long_y',
        'align_bull', 'align_bear',
    ]
    for col in needed:
        if col not in df.columns:
            raise ValueError(f"缺少字段: {col}")

    df = df.sort_values(['contract', 'bt_date']).reset_index(drop=True)
    df['open'] = pd.to_numeric(df['open'], errors='coerce')
    df['high'] = pd.to_numeric(df['high'], errors='coerce')
    df['low'] = pd.to_numeric(df['low'], errors='coerce')
    df['close'] = pd.to_numeric(df['close'], errors='coerce')
    df['volume'] = pd.to_numeric(df['volume'], errors='coerce')

    feature_names = [
        'direction', 'macd_value', 'rsi_6',
        'align_bull', 'align_bear',
        'ret_1', 'ret_5', 'vol_5', 'vol_ratio_20',
        'ma_slope_20', 'ma_slope_10',
        'price_to_ma20', 'price_to_ma10', 'price_to_ma5',
        'er_20', 'atr_pct_14', 'bb_width_20', 'flip_rate_20', 'donchian_width_20',
    ]

    rows = []
    labels = []

    try:
        h = int(horizon_days)
    except Exception:
        h = 5
    if h <= 0:
        h = 5
    try:
        max_dd = float(max_drawdown)
    except Exception:
        max_dd = 0.06
    if max_dd < 0:
        max_dd = 0.0
    try:
        min_p = float(min_profit)
    except Exception:
        min_p = 0.0
    try:
        pq = float(profit_quantile)
    except Exception:
        pq = 0.7
    if pq <= 0:
        pq = 0.7
    if pq >= 1:
        pq = 0.7

    for _, g in df.groupby('contract', sort=False):
        g = g.copy()
        g['ret_1'] = g['close'].pct_change()
        g['ret_5'] = g['close'] / g['close'].shift(5) - 1.0
        g['vol_5'] = g['ret_1'].rolling(5).std(ddof=0)
        g['vol_ratio_20'] = g['volume'] / g['volume'].rolling(20).mean()

        g['ma_slope_20'] = (g['ma_long_t'] - g['ma_long_y']) / g['close']
        g['ma_slope_10'] = (g['ma_mid_t'] - g['ma_mid_y']) / g['close']

        g['price_to_ma20'] = g['close'] / g['ma_long_t'] - 1.0
        g['price_to_ma10'] = g['close'] / g['ma_mid_t'] - 1.0
        g['price_to_ma5'] = g['close'] / g['ma_short_t'] - 1.0

        g['abs_diff_1'] = g['close'].diff().abs()
        g['sum_abs_diff_20'] = g['abs_diff_1'].rolling(20).sum()
        g['er_20'] = (g['close'] - g['close'].shift(20)).abs() / g['sum_abs_diff_20']

        prev_close = g['close'].shift(1)
        tr = pd.concat([(g['high'] - g['low']).abs(), (g['high'] - prev_close).abs(), (g['low'] - prev_close).abs()], axis=1).max(axis=1)
        g['atr_14'] = tr.rolling(14).mean()
        g['atr_pct_14'] = g['atr_14'] / g['close']

        ma20 = g['close'].rolling(20).mean()
        sd20 = g['close'].rolling(20).std(ddof=0)
        g['bb_width_20'] = (4.0 * sd20) / ma20

        sgn = np.sign(g['ret_1'].fillna(0.0))
        flip = ((sgn.shift(1) * sgn) < 0).astype(float)
        g['flip_rate_20'] = flip.rolling(20).mean()

        g['donchian_width_20'] = (g['high'].rolling(20).max() - g['low'].rolling(20).min()) / g['close']

        g = g.dropna(subset=['open', 'high', 'low', 'close', 'volume'])
        if len(g) <= h:
            continue

        close_arr = g['close'].to_numpy(dtype=float)
        low_arr = g['low'].to_numpy(dtype=float)
        high_arr = g['high'].to_numpy(dtype=float)

        macd_arr = g['macd_value'].to_numpy(dtype=float)
        rsi_arr = g['rsi_6'].to_numpy(dtype=float)
        align_bull_arr = g['align_bull'].to_numpy()
        align_bear_arr = g['align_bear'].to_numpy()
        ret_1_arr = g['ret_1'].to_numpy(dtype=float)
        ret_5_arr = g['ret_5'].to_numpy(dtype=float)
        vol_5_arr = g['vol_5'].to_numpy(dtype=float)
        vol_ratio_20_arr = g['vol_ratio_20'].to_numpy(dtype=float)
        ma_slope_20_arr = g['ma_slope_20'].to_numpy(dtype=float)
        ma_slope_10_arr = g['ma_slope_10'].to_numpy(dtype=float)
        price_to_ma20_arr = g['price_to_ma20'].to_numpy(dtype=float)
        price_to_ma10_arr = g['price_to_ma10'].to_numpy(dtype=float)
        price_to_ma5_arr = g['price_to_ma5'].to_numpy(dtype=float)
        er_20_arr = g['er_20'].to_numpy(dtype=float)
        atr_pct_14_arr = g['atr_pct_14'].to_numpy(dtype=float)
        bb_width_20_arr = g['bb_width_20'].to_numpy(dtype=float)
        flip_rate_20_arr = g['flip_rate_20'].to_numpy(dtype=float)
        donchian_width_20_arr = g['donchian_width_20'].to_numpy(dtype=float)

        records = []
        profits_long = []
        profits_short = []
        n = len(g)
        for i in range(0, n - h):
            entry = float(close_arr[i])
            if not math.isfinite(entry) or entry <= 0:
                continue
            exit_close = float(close_arr[i + h])
            if not math.isfinite(exit_close) or exit_close <= 0:
                continue

            future_lows = low_arr[i + 1:i + h + 1]
            future_highs = high_arr[i + 1:i + h + 1]
            if len(future_lows) != h or len(future_highs) != h:
                continue
            min_low = float(np.nanmin(future_lows))
            max_high = float(np.nanmax(future_highs))
            if not math.isfinite(min_low) or not math.isfinite(max_high):
                continue

            profit_long = float(exit_close / entry - 1.0)
            profit_short = float(-(exit_close / entry - 1.0))
            dd_long = float((entry - min_low) / entry) if min_low < entry else 0.0
            dd_short = float((max_high - entry) / entry) if max_high > entry else 0.0
            if not math.isfinite(dd_long):
                dd_long = 0.0
            if not math.isfinite(dd_short):
                dd_short = 0.0
            if math.isfinite(profit_long):
                profits_long.append(float(profit_long))
            if math.isfinite(profit_short):
                profits_short.append(float(profit_short))

            macd_v = float(macd_arr[i]) if math.isfinite(float(macd_arr[i])) else 0.0
            rsi_v = float(rsi_arr[i]) if math.isfinite(float(rsi_arr[i])) else 50.0
            ab = 1.0 if bool(align_bull_arr[i]) else 0.0
            ae = 1.0 if bool(align_bear_arr[i]) else 0.0
            f_ret_1 = float(ret_1_arr[i]) if math.isfinite(float(ret_1_arr[i])) else 0.0
            f_ret_5 = float(ret_5_arr[i]) if math.isfinite(float(ret_5_arr[i])) else 0.0
            f_vol_5 = float(vol_5_arr[i]) if math.isfinite(float(vol_5_arr[i])) else 0.0
            f_vr20 = float(vol_ratio_20_arr[i]) if math.isfinite(float(vol_ratio_20_arr[i])) else 1.0
            f_ms20 = float(ma_slope_20_arr[i]) if math.isfinite(float(ma_slope_20_arr[i])) else 0.0
            f_ms10 = float(ma_slope_10_arr[i]) if math.isfinite(float(ma_slope_10_arr[i])) else 0.0
            f_pma20 = float(price_to_ma20_arr[i]) if math.isfinite(float(price_to_ma20_arr[i])) else 0.0
            f_pma10 = float(price_to_ma10_arr[i]) if math.isfinite(float(price_to_ma10_arr[i])) else 0.0
            f_pma5 = float(price_to_ma5_arr[i]) if math.isfinite(float(price_to_ma5_arr[i])) else 0.0
            f_er20 = float(er_20_arr[i]) if math.isfinite(float(er_20_arr[i])) else 0.0
            f_atr14 = float(atr_pct_14_arr[i]) if math.isfinite(float(atr_pct_14_arr[i])) else 0.0
            f_bbw20 = float(bb_width_20_arr[i]) if math.isfinite(float(bb_width_20_arr[i])) else 0.0
            f_flip20 = float(flip_rate_20_arr[i]) if math.isfinite(float(flip_rate_20_arr[i])) else 0.0
            f_dc20 = float(donchian_width_20_arr[i]) if math.isfinite(float(donchian_width_20_arr[i])) else 0.0
            records.append((
                macd_v, rsi_v, ab, ae,
                f_ret_1, f_ret_5, f_vol_5, f_vr20, f_ms20, f_ms10, f_pma20, f_pma10, f_pma5,
                f_er20, f_atr14, f_bbw20, f_flip20, f_dc20,
                float(profit_long), float(profit_short), float(dd_long), float(dd_short),
            ))

        if not records:
            continue
        if not profits_long or not profits_short:
            continue
        try:
            thr_long = float(np.quantile(np.asarray(profits_long, dtype=float), pq))
            thr_short = float(np.quantile(np.asarray(profits_short, dtype=float), pq))
        except Exception:
            continue

        for rec in records:
            (
                macd_v, rsi_v, ab, ae,
                f_ret_1, f_ret_5, f_vol_5, f_vr20, f_ms20, f_ms10, f_pma20, f_pma10, f_pma5,
                f_er20, f_atr14, f_bbw20, f_flip20, f_dc20,
                profit_long, profit_short, dd_long, dd_short,
            ) = rec
            for dsign in (1.0, -1.0):
                if dsign > 0:
                    y = 1.0 if (profit_long >= min_p and profit_long >= thr_long and dd_long <= max_dd) else 0.0
                else:
                    y = 1.0 if (profit_short >= min_p and profit_short >= thr_short and dd_short <= max_dd) else 0.0
                x = [
                    float(dsign),
                    macd_v,
                    rsi_v,
                    ab,
                    ae,
                    f_ret_1,
                    f_ret_5,
                    f_vol_5,
                    f_vr20,
                    f_ms20,
                    f_ms10,
                    f_pma20,
                    f_pma10,
                    f_pma5,
                    f_er20,
                    f_atr14,
                    f_bbw20,
                    f_flip20,
                    f_dc20,
                ]
                rows.append(x)
                labels.append(y)

    if not rows:
        raise RuntimeError("没有可用于训练的数据样本")

    X = np.asarray(rows, dtype=float)
    y = np.asarray(labels, dtype=float)

    means = X.mean(axis=0)
    stds = X.std(axis=0)
    stds = np.where(stds > 1e-12, stds, 1.0)
    Xs = (X - means) / stds

    w = np.zeros(Xs.shape[1], dtype=float)
    b = 0.0
    lr = float(G.get('ai_position_train_lr', 0.1) or 0.1)
    l2 = float(G.get('ai_position_train_l2', 1e-3) or 1e-3)
    iters = int(G.get('ai_position_train_iters', 400) or 400)

    for _ in range(iters):
        z = Xs.dot(w) + b
        p = 1.0 / (1.0 + np.exp(-np.clip(z, -50, 50)))
        diff = (p - y)
        grad_w = Xs.T.dot(diff) / float(len(y)) + l2 * w
        grad_b = float(diff.mean())
        w -= lr * grad_w
        b -= lr * grad_b

    z_all = Xs.dot(w) + b
    p_all = 1.0 / (1.0 + np.exp(-np.clip(z_all, -50, 50)))
    try:
        q25 = float(np.quantile(p_all, 0.25))
        q50 = float(np.quantile(p_all, 0.50))
        q75 = float(np.quantile(p_all, 0.75))
        q90 = float(np.quantile(p_all, 0.90))
    except Exception:
        q25, q50, q75, q90 = 0.40, 0.50, 0.60, 0.70

    model = {
        'version': 1,
        'horizon_days': int(horizon_days),
        'label_max_drawdown': float(max_dd),
        'label_min_profit': float(min_p),
        'label_profit_quantile': float(pq),
        'label_name': 'profit_quantile_and_max_drawdown',
        'p_quantiles': {'q25': q25, 'q50': q50, 'q75': q75, 'q90': q90},
        'feature_names': list(feature_names),
        'weights': [float(x) for x in w.tolist()],
        'bias': float(b),
        'means': [float(x) for x in means.tolist()],
        'stds': [float(x) for x in stds.tolist()],
        'trained_at': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'train_samples': int(len(y)),
    }

    if output_path is None:
        output_path = os.path.join(_ai_get_base_dir(), 'ai_position_model.json')

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(model, f, ensure_ascii=False, indent=2)

    return model, output_path


def send_email_via_smtp(subject, body, logger=None):
    smtp_host = os.getenv('QMT_SMTP_HOST', 'smtp.qq.com')
    smtp_port = int(os.getenv('QMT_SMTP_PORT', '465'))
    smtp_user = os.getenv('QMT_SMTP_USER', '2422807651@qq.com')
    smtp_pass = os.getenv('QMT_SMTP_PASS', 'gsbowcycbolkebef')
    mail_from = os.getenv('QMT_EMAIL_FROM', smtp_user)
    mail_to = os.getenv('QMT_EMAIL_TO', '896559147@qq.com')

    if not (smtp_user and smtp_pass and mail_from and mail_to):
        if logger:
            logger.warning('启动邮件未发送：缺少QMT_SMTP_USER/QMT_SMTP_PASS/QMT_EMAIL_TO配置')
        return False

    msg = EmailMessage()
    msg['Subject'] = subject
    msg['From'] = mail_from
    msg['To'] = mail_to
    msg.set_content(body)

    context = ssl.create_default_context()
    with smtplib.SMTP_SSL(smtp_host, smtp_port, context=context, timeout=15) as server:
        server.login(smtp_user, smtp_pass)
        server.send_message(msg)
    return True


def _get_contract_type_label(contract_code):
    try:
        base_code = get_base_code(contract_code)
        vip_set = set([str(x).lower() for x in (G.get('contract_codes_backtest') or [])])
        if base_code and str(base_code).lower() in vip_set:
            return 'VIP'
    except Exception:
        pass
    return '普通'


def _log_structured(tag, payload):
    try:
        logger = G.get('logger')
        line = f"{tag}|" + json.dumps(payload, ensure_ascii=False, separators=(',', ':'), default=str)
        if logger:
            logger.info(line)
        else:
            print(line)
    except Exception:
        pass


def _risk_snapshot(ContextInfo=None):
    r = {
        'total_assets': float(G.get('total_assets', 0) or 0),
        'total_assets_effective': float(G.get('total_assets_effective', 0) or 0),
        'available_balance': float(G.get('available_balance', 0) or 0),
        'limited_available_balance': float(G.get('limited_available_balance', 0) or 0),
        'current_risk_per_trade': float(G.get('current_risk_per_trade', 0) or 0),
        'risk_multiplier': float(G.get('risk_multiplier', 1.0) or 1.0),
        'risk_tier': int(G.get('risk_tier', 0) or 0),
        'loss_streak': int(G.get('loss_streak', 0) or 0),
        'annual_trading_capital': float(G.get('annual_trading_capital', 0) or 0),
        'annual_withdrawal_offset': float(G.get('annual_withdrawal_offset', 0) or 0),
        'annual_withdrawal_year': int(G.get('annual_withdrawal_year', 0) or 0),
        'nav_baseline_total_assets': float(G.get('nav_baseline_total_assets', 0) or 0),
        'nav_peak_total_assets': float(G.get('nav_peak_total_assets', 0) or 0),
        'nav_ratio': float(G.get('nav_ratio', 0) or 0),
        'nav_drawdown': float(G.get('nav_drawdown', 0) or 0),
        'nav_risk_state': G.get('nav_risk_state'),
        'max_capital_usage_ratio': float(G.get('max_capital_usage_ratio', 0) or 0),
        'risk_ratio_of_total_assets': float(G.get('risk_ratio_of_total_assets', 0) or 0),
        'risk_ratio_breakout': float(G.get('risk_ratio_breakout', 0) or 0),
        'risk_ratio_ma_cross_breakout': float(G.get('risk_ratio_ma_cross_breakout', 0) or 0)
    }
    try:
        r['barpos'] = int(getattr(ContextInfo, 'barpos', -1)) if ContextInfo is not None else -1
    except Exception:
        r['barpos'] = -1
    try:
        r['do_back_test'] = bool(getattr(ContextInfo, 'do_back_test', False)) if ContextInfo is not None else False
    except Exception:
        r['do_back_test'] = False
    return r


def _update_nav_state(total_assets):
    ta = float(total_assets or 0)
    if ta <= 0:
        return
    baseline = float(G.get('nav_baseline_total_assets', 0) or 0)
    if baseline <= 0:
        baseline = ta
        G['nav_baseline_total_assets'] = baseline

    peak = float(G.get('nav_peak_total_assets', 0) or 0)
    if peak <= 0:
        peak = ta
    if ta > peak:
        peak = ta
    G['nav_peak_total_assets'] = peak

    nav_ratio = ta / baseline if baseline > 0 else 0.0
    dd = (peak - ta) / peak if peak > 0 else 0.0
    G['nav_ratio'] = float(nav_ratio)
    G['nav_drawdown'] = float(dd)

    state = 'mid'
    try:
        if dd >= float(G.get('probe_enter_drawdown', 0.12) or 0.12):
            state = 'high'
        elif dd <= float(G.get('probe_exit_drawdown', 0.06) or 0.06):
            state = 'low'
    except Exception:
        state = 'mid'
    G['nav_risk_state'] = state


def _ensure_annual_withdrawal_state():
    if 'annual_withdrawal_enabled' not in G:
        G['annual_withdrawal_enabled'] = False
    if 'annual_withdrawal_capital' not in G:
        G['annual_withdrawal_capital'] = 1000000.0
    if 'annual_withdrawal_year' not in G:
        G['annual_withdrawal_year'] = 0
    if 'annual_withdrawal_offset' not in G:
        G['annual_withdrawal_offset'] = 0.0
    if 'annual_trading_capital' not in G:
        G['annual_trading_capital'] = 0.0
    if 'annual_withdrawn_by_year' not in G or not isinstance(G.get('annual_withdrawn_by_year'), dict):
        G['annual_withdrawn_by_year'] = {}


def _apply_annual_withdrawal_cap(ContextInfo, current_dt, current_total_assets):
    _ensure_annual_withdrawal_state()
    if not bool(getattr(ContextInfo, 'do_back_test', False)):
        return float(current_total_assets or 0), 0.0
    if not bool(G.get('annual_withdrawal_enabled', False)):
        return float(current_total_assets or 0), float(G.get('annual_withdrawal_offset', 0) or 0)

    try:
        year = int(getattr(current_dt, 'year', 0) or 0)
    except Exception:
        year = 0
    if year <= 0:
        return float(current_total_assets or 0), float(G.get('annual_withdrawal_offset', 0) or 0)

    try:
        cap = float(G.get('annual_withdrawal_capital', 1000000.0) or 1000000.0)
    except Exception:
        cap = 1000000.0
    if cap <= 0:
        cap = 1000000.0

    try:
        ta = float(current_total_assets or 0)
    except Exception:
        ta = 0.0

    try:
        last_year = int(G.get('annual_withdrawal_year', 0) or 0)
    except Exception:
        last_year = 0

    if year != last_year:
        withdrawn = 0.0
        offset = 0.0
        trading_capital = ta
        if ta > cap:
            withdrawn = ta - cap
            offset = withdrawn
            trading_capital = cap

        G['annual_withdrawal_year'] = year
        G['annual_withdrawal_offset'] = float(offset)
        G['annual_trading_capital'] = float(trading_capital)
        try:
            G['annual_withdrawn_by_year'][str(year)] = float(withdrawn)
        except Exception:
            pass

        logger = G.get('logger')
        if logger:
            try:
                date_s = current_dt.strftime('%Y-%m-%d')
            except Exception:
                date_s = str(current_dt)
            logger.info(
                f"🏦 年度出金模拟: year={year} date={date_s} actual_assets={ta:.2f} cap={cap:.2f} "
                f"locked_trading_capital={trading_capital:.2f} withdrawn={withdrawn:.2f}"
            )

    offset = float(G.get('annual_withdrawal_offset', 0) or 0)
    effective_assets = ta - offset
    if effective_assets < 0:
        effective_assets = 0.0
    return float(effective_assets), float(offset)


def _refresh_account_and_risk_state(ContextInfo, current_dt=None):
    account_info = get_trade_detail_data(G['accountid'], 'FUTURE', 'ACCOUNT')
    if not account_info:
        raise RuntimeError("无法获取账户资金信息")

    account = account_info[0]
    current_total_assets = float(getattr(account, 'm_dBalance', 0) or 0)
    available_balance = float(getattr(account, 'm_dAvailable', 0) or 0)
    position_profit = float(getattr(account, 'm_dPositionProfit', 0) or 0)

    if current_dt is None:
        try:
            current_dt = get_context_datetime(ContextInfo)
        except Exception:
            current_dt = datetime.datetime.now()

    effective_total_assets, _annual_offset = _apply_annual_withdrawal_cap(ContextInfo, current_dt, current_total_assets)
    G['total_assets_effective'] = float(effective_total_assets or 0)

    max_usable_capital = float(effective_total_assets or 0) * float(G.get('max_capital_usage_ratio', 1.0) or 1.0)
    limited_available_balance = min(float(available_balance or 0), float(max_usable_capital or 0))

    dynamic_risk_per_trade = float(limited_available_balance) * float(G.get('risk_ratio_of_total_assets', 0.04) or 0.04)
    if dynamic_risk_per_trade < float(G.get('min_risk_per_trade', 0) or 0):
        dynamic_risk_per_trade = float(G.get('min_risk_per_trade', 0) or 0)
    elif dynamic_risk_per_trade > float(G.get('max_risk_per_trade', dynamic_risk_per_trade) or dynamic_risk_per_trade):
        dynamic_risk_per_trade = float(G.get('max_risk_per_trade', dynamic_risk_per_trade) or dynamic_risk_per_trade)

    _ensure_streak_risk_state()
    try:
        _m = float(G.get('risk_multiplier', 1.0) or 1.0)
    except Exception:
        _m = 1.0
    if _m < 0:
        _m = 0.0
    if _m > 1:
        _m = 1.0
    dynamic_risk_per_trade = float(dynamic_risk_per_trade) * float(_m)

    G['current_risk_per_trade'] = float(dynamic_risk_per_trade)
    G['limited_available_balance'] = float(limited_available_balance)
    G['total_assets'] = float(current_total_assets)
    G['available_balance'] = float(available_balance)
    G['position_profit'] = float(position_profit)

    return account_info, current_total_assets, available_balance, limited_available_balance, position_profit, effective_total_assets, _annual_offset


def _flatten_history_trade_detail_result(result):
    if not result:
        return []
    flat = []
    for item in result:
        if isinstance(item, (list, tuple)):
            if len(item) >= 2 and isinstance(item[1], list):
                _, data_list = item[0], item[1]
                for x in data_list or []:
                    flat.append(x)
                continue
        if isinstance(item, list):
            for x in item:
                flat.append(x)
            continue
        flat.append(item)
    return flat


def _list_callable_names_by_keyword(obj, keywords):
    out = []
    if obj is None:
        return out
    try:
        if isinstance(obj, dict):
            names = list(obj.keys())
        else:
            names = dir(obj)
    except Exception:
        return out
    for n in names:
        try:
            s = str(n)
        except Exception:
            continue
        ss = s.lower()
        ok = True
        for kw in keywords:
            if kw not in ss:
                ok = False
                break
        if not ok:
            continue
        try:
            if isinstance(obj, dict):
                v = obj.get(n)
            else:
                v = getattr(obj, n)
        except Exception:
            continue
        if callable(v):
            out.append(s)
    out.sort()
    return out


def _discover_possible_history_apis(ContextInfo):
    keywords_sets = [
        ['history'],
        ['his'],
        ['deal'],
        ['trade', 'detail'],
        ['history', 'deal'],
        ['history', 'trade'],
    ]
    seen = set()
    found = []
    scopes = [('globals', globals())]
    bi = __builtins__
    if bi is not None:
        scopes.append(('__builtins__', bi))
    if ContextInfo is not None:
        scopes.append(('ContextInfo', ContextInfo))

    for scope_name, scope_obj in scopes:
        for kws in keywords_sets:
            for n in _list_callable_names_by_keyword(scope_obj, kws):
                key = (scope_name, n)
                if key in seen:
                    continue
                seen.add(key)
                found.append(f"{scope_name}.{n}" if scope_name == 'ContextInfo' else n)
    found.sort()
    return found


def _fetch_deals_from_trade_detail_cache(accountid, start_date, end_date, logger=None, strategy_name=None):
    try:
        if strategy_name:
            raw = get_trade_detail_data(accountid, 'FUTURE', 'DEAL', strategy_name)
        else:
            raw = get_trade_detail_data(accountid, 'FUTURE', 'DEAL')
    except Exception as e:
        if logger:
            logger.error(f"❌ 成交缓存查询失败(get_trade_detail_data/DEAL): {e}")
        raise

    deals = []
    earliest = None
    latest = None
    for d in raw or []:
        td = _norm_date8(safe_get_attr(d, ['m_strTradeDate'], None))
        if not td:
            td = _norm_date8(safe_get_attr(d, ['m_strTradeTime', 'm_strTime'], None))
        if not td:
            continue
        if earliest is None or td < earliest:
            earliest = td
        if latest is None or td > latest:
            latest = td
        if start_date and td < start_date:
            continue
        if end_date and td > end_date:
            continue
        deals.append(d)

    return deals, earliest, latest, int(len(raw or []))


def _get_position_statistics_map(accountid):
    try:
        stats = get_trade_detail_data(accountid, 'FUTURE', 'POSITION_STATISTICS')
    except Exception:
        return {}
    out = {}
    for s in stats or []:
        inst = getattr(s, 'm_strInstrumentID', '')
        exch = getattr(s, 'm_strExchangeID', '')
        if not inst or not exch:
            continue
        contract = f"{inst}.{exch}"
        out[contract] = s
    return out


def _build_layers_from_position_only(meta, stat_obj, today_key):
    want_dir = meta.get('direction')
    total_vol = int(meta.get('volume') or 0)
    avg_price = float(meta.get('avg_price') or 0)
    open_date = str(meta.get('open_date') or '')[:8] or str(today_key)

    today_pos = None
    yest_pos = None
    if stat_obj is not None:
        try:
            today_pos = int(getattr(stat_obj, 'm_nTodayPosition', 0) or 0)
        except Exception:
            today_pos = None
        try:
            yest_pos = int(getattr(stat_obj, 'm_nYestodayPosition', 0) or 0)
        except Exception:
            yest_pos = None

    if today_pos is None or yest_pos is None:
        today_pos = 0
        yest_pos = max(0, total_vol)

    if today_pos + yest_pos <= 0:
        today_pos = 0
        yest_pos = max(0, total_vol)

    if today_pos + yest_pos != total_vol:
        yest_pos = max(0, total_vol - max(0, today_pos))

    lots = []
    if yest_pos > 0:
        lots.append({'price': float(avg_price), 'volume': int(yest_pos), 'date': open_date, 'time': '00:00:00'})
    if today_pos > 0:
        lots.append({'price': float(avg_price), 'volume': int(today_pos), 'date': str(today_key), 'time': '00:00:00'})

    if not lots and total_vol > 0:
        lots.append({'price': float(avg_price), 'volume': int(total_vol), 'date': open_date, 'time': '00:00:00'})

    return lots, int(today_pos or 0), int(yest_pos or 0), str(open_date), str(want_dir or '')

def _resolve_history_trade_detail_api(ContextInfo):
    candidates = [
        'get_history_trade_detail_data',
        'get_history_trade_detail_data2',
        'get_history_trade_detail',
        'get_his_trade_detail_data',
        'get_his_trade_detail',
    ]

    for name in candidates:
        fn = globals().get(name)
        if callable(fn):
            return fn, name, 'globals'

    bi = __builtins__
    if isinstance(bi, dict):
        for name in candidates:
            fn = bi.get(name)
            if callable(fn):
                return fn, name, '__builtins__'
    else:
        for name in candidates:
            fn = getattr(bi, name, None)
            if callable(fn):
                return fn, name, '__builtins__'

    if ContextInfo is not None:
        for name in candidates:
            fn = getattr(ContextInfo, name, None)
            if callable(fn):
                return fn, name, 'ContextInfo'

    return None, None, None


def _ensure_dir(path):
    try:
        os.makedirs(path, exist_ok=True)
        return True
    except Exception:
        return False


def _safe_float(x, default=None):
    try:
        v = float(x)
        return v
    except Exception:
        return default


def _write_replay_kline_csv(out_path, rows):
    fieldnames = [
        'idx', 'date', 'open', 'high', 'low', 'close', 'volume',
        'mark', 'contract', 'layer', 'direction',
        'entry_price', 'exit_price', 'pos_volume', 'volume_multiple',
        'pnl_points', 'pnl_pct', 'pnl_money', 'close_reason',
        'rsi_6', 'ts', 'ts_reason'
    ]
    try:
        with open(out_path, 'w', encoding='utf-8', newline='') as f:
            w = csv.DictWriter(f, fieldnames=fieldnames)
            w.writeheader()
            for r in rows:
                out = {k: r.get(k) for k in fieldnames}
                w.writerow(out)
        return True
    except Exception:
        return False


def _norm_date8(x):
    if x is None:
        return None
    s = str(x)
    m = re.findall(r'(\d{8})', s)
    return m[-1] if m else None


def _norm_time_hms(x):
    if x is None:
        return ''
    s = str(x).strip()
    m = re.findall(r'(\d{2}:\d{2}:\d{2})', s)
    return m[-1] if m else ''


def _infer_deal_open_close(deal_obj):
    opt_name = safe_get_attr(deal_obj, ['m_strOptName'], '')
    if isinstance(opt_name, str) and opt_name:
        if '平今' in opt_name:
            return 'close_today'
        if '平昨' in opt_name:
            return 'close_yesterday'
        if '平' in opt_name:
            return 'close'
        if '开' in opt_name:
            return 'open'
    off = safe_get_attr(deal_obj, ['m_nRealOffsetFlag', 'm_nOffsetFlag'], None)
    try:
        off_i = int(off)
    except Exception:
        off_i = None
    if off_i == 0:
        return 'open'
    if off_i in (3, 5, 6):
        return 'close_today'
    if off_i == 4:
        return 'close_yesterday'
    if off_i in (1, 2):
        return 'close'
    return None


def _pos_dir_from_deal(deal_obj, open_close):
    try:
        d = int(safe_get_attr(deal_obj, ['m_nDirection'], 0) or 0)
    except Exception:
        d = 0
    is_buy = (d == 48)
    if open_close == 'open':
        return 'long' if is_buy else 'short'
    if isinstance(open_close, str) and open_close.startswith('close'):
        return 'short' if is_buy else 'long'
    return None


def _get_kline_date_key(idx_val):
    if idx_val is None:
        return None
    try:
        if hasattr(idx_val, 'strftime'):
            return idx_val.strftime('%Y%m%d')
    except Exception:
        pass
    return _norm_date8(idx_val)


def _replay_update_trailing_stop_for_layer(direction, entry_price, close_price, max_profit, trailing_stop, stop_loss_pct):
    try:
        cp = float(close_price)
    except Exception:
        return max_profit, trailing_stop, False, ""
    try:
        ep = float(entry_price)
    except Exception:
        return max_profit, trailing_stop, False, ""
    if ep <= 0:
        return max_profit, trailing_stop, False, ""

    if direction == 'long':
        pnl = (cp - ep) / ep
    else:
        pnl = (ep - cp) / ep

    try:
        pnl = float(pnl)
    except Exception:
        return max_profit, trailing_stop, False, ""

    if pnl <= float(max_profit or 0.0):
        return max_profit, trailing_stop, False, ""

    layer_max = float(pnl)
    layer_ts = trailing_stop
    try:
        layer_ts = float(layer_ts) if layer_ts is not None else None
    except Exception:
        layer_ts = None

    if layer_ts is None:
        if direction == 'long':
            layer_ts = ep * (1 - stop_loss_pct)
        else:
            layer_ts = ep * (1 + stop_loss_pct)

    new_ts = layer_ts
    reason = ""
    if direction == 'long':
        if layer_max >= 0.30:
            new_ts = max(new_ts, ep * 1.20)
            reason = "max_profit>=30% 锁定20%"
        elif layer_max >= 0.20:
            new_ts = max(new_ts, ep * 1.15)
            reason = "max_profit>=20% 锁定15%"
        elif layer_max >= 0.10:
            new_ts = max(new_ts, ep * 1.08)
            reason = "max_profit>=10% 锁定8%"
        elif layer_max >= 0.05:
            new_ts = max(new_ts, ep * 1.03)
            reason = "max_profit>=5% 锁定3%"
        elif layer_max >= 0.03:
            new_ts = max(new_ts, ep * 1.01)
            reason = "max_profit>=3% 锁定1%"
        elif layer_max >= 0.02:
            new_ts = max(new_ts, ep * 1.001)
            reason = "max_profit>=2% 锁定0.1%"
    else:
        if layer_max >= 0.30:
            new_ts = min(new_ts, ep * 0.80)
            reason = "max_profit>=30% 锁定20%"
        elif layer_max >= 0.20:
            new_ts = min(new_ts, ep * 0.85)
            reason = "max_profit>=20% 锁定15%"
        elif layer_max >= 0.10:
            new_ts = min(new_ts, ep * 0.92)
            reason = "max_profit>=10% 锁定8%"
        elif layer_max >= 0.05:
            new_ts = min(new_ts, ep * 0.97)
            reason = "max_profit>=5% 锁定3%"
        elif layer_max >= 0.03:
            new_ts = min(new_ts, ep * 0.99)
            reason = "max_profit>=3% 锁定1%"
        elif layer_max >= 0.02:
            new_ts = min(new_ts, ep * 0.999)
            reason = "max_profit>=2% 锁定0.1%"

    changed = False
    try:
        changed = abs(float(new_ts) - float(layer_ts)) > 1e-9
    except Exception:
        changed = False

    return layer_max, float(new_ts), bool(changed and reason), reason


def replay_rebuild_state_from_api(ContextInfo, only_contracts=None):
    if bool(getattr(ContextInfo, 'do_back_test', False)):
        return False
    if not bool(G.get('prefer_api_replay_recovery', False)):
        return False

    logger = G.get('logger')
    if logger:
        logger.info("\n========== API历史回放重建状态 ==========")

    try:
        positions = get_trade_detail_data(G['accountid'], 'FUTURE', 'POSITION')
    except Exception as e:
        if logger:
            logger.warning(f"⚠️ 查询当前持仓失败，跳过API回放: {e}")
        return False

    if not positions:
        if logger:
            logger.info("✅ 当前无持仓，跳过API回放")
        return False

    targets = {}
    for p in positions:
        try:
            v = int(getattr(p, 'm_nVolume', 0) or 0)
        except Exception:
            v = 0
        if v <= 0:
            continue
        inst = getattr(p, 'm_strInstrumentID', '')
        exch = getattr(p, 'm_strExchangeID', '')
        if not inst or not exch:
            continue
        contract = f"{inst}.{exch}"
        try:
            nd = int(getattr(p, 'm_nDirection', 0) or 0)
        except Exception:
            nd = 0
        direction = 'long' if nd == 48 else 'short'
        avg_price = float(getattr(p, 'm_dOpenPrice', 0) or 0)
        open_date = _norm_date8(getattr(p, 'm_strOpenDate', None))
        if contract in targets:
            if targets[contract]['direction'] != direction:
                if logger:
                    logger.warning(f"⚠️ 同一合约检测到多空同时持仓，当前策略不支持，跳过回放: {contract}")
                continue
            prev_v = int(targets[contract].get('volume', 0) or 0)
            new_v = prev_v + int(v)
            prev_ap = float(targets[contract].get('avg_price', 0) or 0)
            merged_ap = prev_ap
            try:
                if new_v > 0:
                    prev_cost = prev_ap * prev_v if prev_ap > 0 and prev_v > 0 else 0.0
                    add_cost = avg_price * v if avg_price > 0 and v > 0 else 0.0
                    if prev_cost + add_cost > 0:
                        merged_ap = (prev_cost + add_cost) / float(new_v)
            except Exception:
                merged_ap = prev_ap if prev_ap > 0 else avg_price

            targets[contract]['volume'] = int(new_v)
            targets[contract]['avg_price'] = float(merged_ap) if merged_ap else float(prev_ap or avg_price or 0)
            if open_date:
                od0 = targets[contract].get('open_date')
                if not od0 or str(open_date) < str(od0):
                    targets[contract]['open_date'] = open_date
            try:
                targets[contract]['merge_count'] = int(targets[contract].get('merge_count', 1) or 1) + 1
            except Exception:
                targets[contract]['merge_count'] = 2
        else:
            targets[contract] = {
                'direction': direction,
                'volume': int(v),
                'avg_price': float(avg_price) if avg_price else 0.0,
                'open_date': open_date,
                'merge_count': 1
            }

    if logger:
        for c, m in targets.items():
            try:
                mc = int(m.get('merge_count', 1) or 1)
            except Exception:
                mc = 1
            if mc > 1:
                logger.info(f"ℹ️ 合并持仓明细: {c} rows={mc} vol={m.get('volume')} avg={m.get('avg_price')}")

    if only_contracts:
        oc = set(str(x) for x in only_contracts)
        targets = {k: v for k, v in targets.items() if str(k) in oc}

    if not targets:
        if logger:
            logger.info("✅ 无需回放的目标持仓，跳过")
        return False

    try:
        lookback_days = int(G.get('api_replay_lookback_days', 90) or 90)
    except Exception:
        lookback_days = 90
    if lookback_days < 7:
        lookback_days = 7
    if lookback_days > 365:
        lookback_days = 365

    now_dt = datetime.datetime.now()
    end_date = now_dt.strftime('%Y%m%d')
    today_key = end_date
    pos_stats_map = _get_position_statistics_map(G['accountid'])
    min_open = None
    for v in targets.values():
        od = v.get('open_date')
        if od:
            if min_open is None or od < min_open:
                min_open = od
    if min_open is None:
        min_open = (now_dt - datetime.timedelta(days=lookback_days)).strftime('%Y%m%d')
    start_date = min_open

    if logger:
        logger.info(f"回放窗口: {start_date} ~ {end_date} | 合约数: {len(targets)}")

    fn, used_name, used_from = _resolve_history_trade_detail_api(ContextInfo)
    deals = []
    deals_source = None
    if callable(fn):
        if logger:
            logger.info(f"历史成交接口: {used_name} (from {used_from})")
        hist = fn(G['accountid'], 'FUTURE', 'DEAL', start_date, end_date)
        deals = _flatten_history_trade_detail_result(hist)
        if logger:
            logger.info(f"成交数据来源: {used_name}")
        deals_source = 'history_api'
    else:
        avail = _discover_possible_history_apis(ContextInfo)
        if logger:
            logger.warning("⚠️ 未发现历史交易明细接口，尝试使用成交缓存(get_trade_detail_data/DEAL)回放（要求覆盖回放窗口）")
            if avail:
                logger.warning(f"可用history相关函数: {', '.join(avail[:50])}")

        deals, earliest, latest, raw_n = _fetch_deals_from_trade_detail_cache(
            G['accountid'], start_date, end_date, logger=logger, strategy_name=None
        )
        if logger:
            logger.info(f"成交数据来源: get_trade_detail_data(DEAL) | cache_total={raw_n} filtered={len(deals)} range={earliest}~{latest}")
        deals_source = 'deal_cache'
        if earliest is None and logger:
            logger.warning("⚠️ 成交缓存为空或缺少日期字段，后续将尝试使用持仓+行情推断回放")
        if earliest is not None and str(earliest) > str(start_date) and logger:
            logger.warning(f"⚠️ 成交缓存无法覆盖回放窗口：cache_earliest={earliest} > start_date={start_date}，后续将尝试使用持仓+行情推断回放")

    by_contract = {}
    for dt in deals:
        inst = safe_get_attr(dt, ['m_strInstrumentID'], '')
        exch = safe_get_attr(dt, ['m_strExchangeID'], '')
        if not inst or not exch:
            continue
        contract = f"{inst}.{exch}"
        if contract not in targets:
            continue
        by_contract.setdefault(contract, []).append(dt)

    try:
        kline_count = int(G.get('api_replay_kline_count', 260) or 260)
    except Exception:
        kline_count = 260
    try:
        sd_dt = datetime.datetime.strptime(str(start_date), '%Y%m%d')
        ed_dt = datetime.datetime.strptime(str(end_date), '%Y%m%d')
        diff = (ed_dt - sd_dt).days + 5
        if diff > kline_count:
            kline_count = diff
    except Exception:
        pass
    if kline_count < 60:
        kline_count = 60
    if kline_count > 1000:
        kline_count = 1000

    sl_pct = float(G.get('stop_loss_pct', 0.02) or 0.02)

    rebuilt_any = False
    for contract, meta in targets.items():
        contract_deals = by_contract.get(contract, [])
        use_position_only = False
        if not contract_deals:
            use_position_only = True
            if logger:
                logger.warning(f"⚠️ {contract} 未找到可用成交记录，使用持仓+行情推断回放")

        typed = []
        rsi_reduce_today = False
        if not use_position_only:
            for d in contract_deals:
                oc = _infer_deal_open_close(d)
                pos_dir = _pos_dir_from_deal(d, oc)
                if not oc or not pos_dir:
                    continue
                td = _norm_date8(safe_get_attr(d, ['m_strTradeDate'], None))
                tt = _norm_time_hms(safe_get_attr(d, ['m_strTradeTime', 'm_strTime'], ''))
                if not td:
                    td = _norm_date8(safe_get_attr(d, ['m_strTradeTime', 'm_strTime'], None))
                if not td:
                    continue
                try:
                    vol = int(safe_get_attr(d, ['m_nVolume'], 0) or 0)
                except Exception:
                    vol = 0
                if vol <= 0:
                    continue
                try:
                    price = float(safe_get_attr(d, ['m_dPrice', 'm_dTradedPrice'], 0) or 0)
                except Exception:
                    price = 0.0
                if price <= 0:
                    continue
                remark = safe_get_attr(d, ['m_strRemark'], '')
                if isinstance(remark, str) and remark and 'RSI超热减仓' in remark and str(td) == str(today_key):
                    rsi_reduce_today = True
                typed.append((td, tt, oc, pos_dir, price, vol, remark))

        typed.sort(key=lambda x: (x[0], x[1]))

        lots = {'long': [], 'short': []}
        open_dates_by_dir = {'long': [], 'short': []}

        def reduce_lots(arr, qty, close_kind, close_date):
            if qty <= 0 or not arr:
                return

            def _reduce_with_pred(pred):
                nonlocal qty
                i = len(arr) - 1
                while qty > 0 and i >= 0:
                    lot = arr[i]
                    if not pred(lot):
                        i -= 1
                        continue
                    lv = int(lot.get('volume', 0) or 0)
                    if lv <= 0:
                        arr.pop(i)
                        i -= 1
                        continue
                    take = lv if lv <= qty else qty
                    lot['volume'] = lv - take
                    qty -= take
                    if int(lot.get('volume', 0) or 0) <= 0:
                        arr.pop(i)
                    i -= 1

            if close_kind == 'close_today' and close_date:
                _reduce_with_pred(lambda x: str(x.get('date', '')) == str(close_date))
            elif close_kind == 'close_yesterday' and close_date:
                _reduce_with_pred(lambda x: str(x.get('date', '')) < str(close_date))

            if qty > 0:
                _reduce_with_pred(lambda x: True)

        if not use_position_only:
            for td, tt, oc, pos_dir, price, vol, remark in typed:
                if oc == 'open':
                    lots[pos_dir].append({'price': float(price), 'volume': int(vol), 'date': td, 'time': tt})
                    open_dates_by_dir[pos_dir].append(str(td))
                elif isinstance(oc, str) and oc.startswith('close'):
                    arr = lots.get(pos_dir) or []
                    reduce_lots(arr, int(vol), oc, td)
                    lots[pos_dir] = arr

        want_dir = meta['direction']
        want_vol = int(meta['volume'])
        if use_position_only:
            stat_obj = pos_stats_map.get(contract)
            remain_lots, today_pos, yest_pos, open_date, _ = _build_layers_from_position_only(meta, stat_obj, today_key)
            remain_total = sum(int(x.get('volume', 0) or 0) for x in remain_lots)
            open_dates_by_dir = {'long': [open_date], 'short': [open_date]}
            if today_pos > 0 and yest_pos > 0:
                open_dates_by_dir[want_dir] = [open_date, str(today_key)]
        else:
            remain_lots = [x for x in lots.get(want_dir, []) if int(x.get('volume', 0) or 0) > 0]
            remain_total = sum(int(x.get('volume', 0) or 0) for x in remain_lots)

        if remain_total != want_vol or remain_total <= 0:
            if logger:
                logger.warning(
                    f"⚠️ {contract} 回放剩余手数不一致/为空: replay={remain_total} pos={want_vol} dir={want_dir}，使用持仓均价初始化"
                )
            ap = float(meta.get('avg_price', 0) or 0)
            od = meta.get('open_date') or start_date
            remain_lots = [{'price': ap if ap > 0 else 0.0, 'volume': want_vol, 'date': od, 'time': '00:00:00'}]
            remain_total = want_vol

        if remain_total > want_vol:
            extra = remain_total - want_vol
            while extra > 0 and remain_lots:
                last = remain_lots[-1]
                lv = int(last.get('volume', 0) or 0)
                take = lv if lv <= extra else extra
                last['volume'] = lv - take
                extra -= take
                if int(last.get('volume', 0) or 0) <= 0:
                    remain_lots.pop()

        remain_lots.sort(key=lambda x: (str(x.get('date', '')), str(x.get('time', ''))))
        if not remain_lots:
            continue

        total_cost = 0.0
        total_qty = 0
        for x in remain_lots:
            q = int(x.get('volume', 0) or 0)
            p = float(x.get('price', 0) or 0)
            if q <= 0 or p <= 0:
                continue
            total_cost += p * q
            total_qty += q
        avg_price = total_cost / total_qty if total_qty > 0 else float(meta.get('avg_price', 0) or 0)

        first = remain_lots[0]
        init_price = float(first.get('price', 0) or 0)
        init_vol = int(first.get('volume', 0) or 0)
        init_date = str(first.get('date') or '')[:8]
        init_time = str(first.get('time') or '')
        init_dt_str = f"{init_date} {init_time}".strip()

        if 'trade_id_seq' not in G:
            G['trade_id_seq'] = 0
        try:
            G['trade_id_seq'] = int(G.get('trade_id_seq', 0) or 0) + 1
        except Exception:
            G['trade_id_seq'] = 1
        trade_id = int(G.get('trade_id_seq', 1) or 1)

        pos = {
            'trade_id': trade_id,
            'root_trade_id': trade_id,
            'entry_date': init_date if init_date else start_date,
            'entry_barpos': -1,
            'direction': want_dir,
            'price': init_price if init_price > 0 else float(meta.get('avg_price', 0) or 0),
            'initial_price': init_price if init_price > 0 else float(meta.get('avg_price', 0) or 0),
            'volume': init_vol,
            'time': init_dt_str if init_dt_str.strip() else datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'open_reason': 'position_only_replay' if use_position_only else 'api_replay',
            'risk_mode': 'position_only_replay' if use_position_only else 'api_replay',
            'open_macd': None,
            'open_rsi': None,
            'add_positions': [],
            'donchian_add_positions': [],
            'total_volume': remain_total,
            'avg_price': float(avg_price) if avg_price else float(meta.get('avg_price', 0) or 0),
            'add_count': max(len(remain_lots) - 1, 0),
            'donchian_add_count': 0,
            'sync_source': 'position_only_replay' if use_position_only else 'history_replay',
            'initial_layer_max_profit_pct': 0.0
        }
        if rsi_reduce_today and want_dir == 'long':
            pos['rsi_overheat_reduce_day'] = str(today_key)

        try:
            if 'last_add_date' not in G or not isinstance(G.get('last_add_date'), dict):
                G['last_add_date'] = {}
            od = open_dates_by_dir.get(want_dir) or []
            if len(od) >= 2:
                G['last_add_date'][contract] = str(od[-1])[:8]
        except Exception:
            pass

        for lot in remain_lots[1:]:
            d8 = str(lot.get('date') or '')[:8]
            tstr = str(lot.get('time') or '')
            pos['add_positions'].append({
                'trade_id': int(trade_id),
                'price': float(lot.get('price', 0) or 0),
                'volume': int(lot.get('volume', 0) or 0),
                'time': f"{d8} {tstr}".strip(),
                'date': d8,
                'barpos': -1,
                'type': 'replay_add',
                'max_profit_pct': 0.0,
                'trailing_stop_price': float(lot.get('price', 0) or 0) * (1 - sl_pct) if want_dir == 'long' else float(lot.get('price', 0) or 0) * (1 + sl_pct)
            })

        kline = ContextInfo.get_market_data_ex(
            fields=['open', 'close', 'low', 'high', 'volume', 'openInterest'],
            stock_code=[contract],
            period='1d',
            count=kline_count,
            dividend_type='front_ratio',
            subscribe=True
        )
        df = kline.get(contract) if isinstance(kline, dict) else None

        if df is not None and not df.empty:
            bars = []
            for idx, row in df.iterrows():
                dk = _get_kline_date_key(idx)
                if not dk:
                    continue
                try:
                    c = float(row.get('close'))
                except Exception:
                    continue
                try:
                    lo = float(row.get('low')) if 'low' in row else None
                except Exception:
                    lo = None
                try:
                    hi = float(row.get('high')) if 'high' in row else None
                except Exception:
                    hi = None
                try:
                    op = float(row.get('open')) if 'open' in row else None
                except Exception:
                    op = None
                try:
                    volu = float(row.get('volume')) if 'volume' in row else 0.0
                except Exception:
                    volu = 0.0
                try:
                    oi = float(row.get('openInterest')) if 'openInterest' in row else 0.0
                except Exception:
                    oi = 0.0
                bars.append((dk, op, hi, lo, c, volu, oi))
            bars.sort(key=lambda x: x[0])

            def find_bar(entry_date_key):
                for dk, _, hi, lo, _, _, _ in bars:
                    if dk == entry_date_key:
                        return lo, hi
                return None, None

            def calc_smart_stop(entry_date_key, entry_price):
                entry_date_key = str(entry_date_key or '')[:8]
                ep = float(entry_price or 0)
                if ep <= 0:
                    return None, None
                idx = None
                for i, (dk, _, _, _, _, _, _) in enumerate(bars):
                    if dk == entry_date_key:
                        idx = i
                        break
                if idx is None:
                    return None, None
                start_i = max(0, idx - 2)
                window = bars[start_i:idx + 1]
                lows = [float(x[3]) for x in window if x[3] is not None]
                highs = [float(x[2]) for x in window if x[2] is not None]
                min_low_3 = min(lows) if lows else None
                max_high_3 = max(highs) if highs else None
                basic_long = ep * (1 - sl_pct)
                basic_short = ep * (1 + sl_pct)
                long_stop = basic_long
                short_stop = basic_short
                if min_low_3 is not None:
                    long_stop = max(long_stop, float(min_low_3))
                if max_high_3 is not None:
                    short_stop = min(short_stop, float(max_high_3))
                entry_low, _ = find_bar(entry_date_key)
                if entry_low is not None:
                    long_stop = float(entry_low)
                return float(long_stop), float(short_stop)

            init_entry_low, init_entry_high = find_bar(pos.get('entry_date'))
            if want_dir == 'long':
                init_ts = init_entry_low if init_entry_low is not None else pos['initial_price'] * (1 - sl_pct)
            else:
                init_ts = pos['initial_price'] * (1 + sl_pct)
            pos['initial_layer_trailing_stop_price'] = float(init_ts)
            pos['overall_trailing_stop_price'] = float(init_ts)
            _append_trailing_stop_trace(pos, 'initial', pos.get('entry_date'), -1, float(init_ts), "回放初始化")

            init_max = 0.0
            init_ts_cur = float(init_ts)
            for dk, _, _, _, c, _ in bars:
                if dk < pos.get('entry_date'):
                    continue
                init_max, init_ts_cur, upd, rsn = _replay_update_trailing_stop_for_layer(want_dir, pos['initial_price'], c, init_max, init_ts_cur, sl_pct)
                if upd:
                    _append_trailing_stop_trace(pos, 'initial', dk, -1, float(init_ts_cur), rsn)
            pos['initial_layer_max_profit_pct'] = float(init_max)
            pos['initial_layer_trailing_stop_price'] = float(init_ts_cur)

            agg_max = float(init_max)
            agg_ts = float(init_ts_cur)
            _prev_overall = float(agg_ts)

            for ap in pos.get('add_positions', []):
                ap_date = str(ap.get('date') or '')[:8]
                ap_price = float(ap.get('price', 0) or 0)
                ap_entry_low, ap_entry_high = find_bar(ap_date)
                if want_dir == 'long':
                    ap_ts = ap_entry_low if ap_entry_low is not None else ap_price * (1 - sl_pct)
                else:
                    ap_ts = ap_price * (1 + sl_pct)
                ap_max = 0.0
                ap_ts_cur = float(ap_ts)
                layer_name = None
                try:
                    layer_name = f"add_{int(pos.get('add_positions', []).index(ap)) + 1}"
                except Exception:
                    layer_name = "add_1"
                _append_trailing_stop_trace(pos, layer_name, ap_date, -1, float(ap_ts_cur), "回放初始化")
                for dk, _, _, _, c, _ in bars:
                    if dk < ap_date:
                        continue
                    ap_max, ap_ts_cur, upd, rsn = _replay_update_trailing_stop_for_layer(want_dir, ap_price, c, ap_max, ap_ts_cur, sl_pct)
                    if upd:
                        _append_trailing_stop_trace(pos, layer_name, dk, -1, float(ap_ts_cur), rsn)
                ap['max_profit_pct'] = float(ap_max)
                ap['trailing_stop_price'] = float(ap_ts_cur)
                agg_max = max(agg_max, float(ap_max))
                if want_dir == 'long':
                    agg_ts = max(agg_ts, float(ap_ts_cur))
                else:
                    agg_ts = min(agg_ts, float(ap_ts_cur))

            pos['overall_trailing_stop_price'] = float(agg_ts)
            if abs(float(agg_ts) - float(_prev_overall)) > 1e-9:
                _append_trailing_stop_trace(pos, 'overall', today_key, -1, float(agg_ts), "移动止损更新")
            if 'max_profit_tracking' not in G:
                G['max_profit_tracking'] = {}
            G['max_profit_tracking'][contract] = {
                'max_profit_pct': float(agg_max),
                'trailing_stop_price': float(agg_ts),
                'last_update_time': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }

            ss_long, ss_short = calc_smart_stop(pos.get('entry_date'), pos.get('initial_price'))
            if ss_long is not None:
                G[f"smart_stop_loss_{contract}_long"] = float(ss_long)
            if ss_short is not None:
                G[f"smart_stop_loss_{contract}_short"] = float(ss_short)

            if bool(G.get('enable_replay_kline_export', True)):
                out_dir = G.get('replay_kline_export_dir')
                if not out_dir:
                    base = G.get('log_dir') or '.'
                    out_dir = os.path.join(str(base), 'replay_kline')
                if _ensure_dir(out_dir):
                    overall_series = {}
                    layers = []
                    layers.append({
                        'name': 'initial',
                        'entry_date': str(pos.get('entry_date') or '')[:8],
                        'entry_price': float(pos.get('initial_price', 0) or 0),
                    })
                    for i, ap in enumerate(pos.get('add_positions', []) or []):
                        layers.append({
                            'name': f"add_{i+1}",
                            'entry_date': str(ap.get('date') or '')[:8],
                            'entry_price': float(ap.get('price', 0) or 0),
                        })

                    layer_state = {}
                    for ly in layers:
                        ed = ly['entry_date']
                        ep = ly['entry_price']
                        if want_dir == 'long':
                            lo, _ = find_bar(ed)
                            ts0 = lo if lo is not None else ep * (1 - sl_pct)
                        else:
                            ts0 = ep * (1 + sl_pct)
                        layer_state[ly['name']] = {'max': 0.0, 'ts': float(ts0), 'entry_date': ed, 'entry_price': ep}

                    prev_overall = None
                    for dk, _, _, _, c, _ in bars:
                        active_ts = []
                        reasons = []
                        for name, st in layer_state.items():
                            if dk < st['entry_date']:
                                continue
                            st['max'], st['ts'], upd, rsn = _replay_update_trailing_stop_for_layer(
                                want_dir, st['entry_price'], c, st['max'], st['ts'], sl_pct
                            )
                            active_ts.append(float(st['ts']))
                            if upd:
                                reasons.append(f"{name} {rsn}")
                        if not active_ts:
                            continue
                        if want_dir == 'long':
                            ov = max(active_ts)
                        else:
                            ov = min(active_ts)
                        reason = ""
                        if prev_overall is None or abs(float(ov) - float(prev_overall)) > 1e-9:
                            if reasons:
                                reason = " ; ".join(reasons)
                        overall_series[dk] = {'ts': float(ov), 'reason': reason}
                        prev_overall = float(ov)

                    rows = []
                    entry_date_key = str(pos.get('entry_date') or '')[:8]
                    entry_price_f = float(pos.get('initial_price', 0) or 0)
                    total_qty = int(pos.get('total_volume', 0) or 0)
                    for i, (dk, op, hi, lo, cl, volu) in enumerate(bars):
                        s = overall_series.get(dk) or {}
                        ts_val = s.get('ts')
                        ts_reason = s.get('reason') or ""
                        mark = 'ENTRY' if dk == entry_date_key else ''
                        rows.append({
                            'idx': i,
                            'date': dk,
                            'open': _safe_float(op, cl),
                            'high': _safe_float(hi, cl),
                            'low': _safe_float(lo, cl),
                            'close': _safe_float(cl, 0.0),
                            'volume': _safe_float(volu, 0.0),
                            'mark': mark,
                            'contract': contract,
                            'layer': 'overall',
                            'direction': want_dir,
                            'entry_price': entry_price_f,
                            'exit_price': '',
                            'pos_volume': total_qty,
                            'volume_multiple': '',
                            'pnl_points': '',
                            'pnl_pct': '',
                            'pnl_money': '',
                            'close_reason': '',
                            'rsi_6': '',
                            'ts': '' if ts_val is None else float(ts_val),
                            'ts_reason': ts_reason,
                        })

                    file_name = f"replay_{contract}_{want_dir}.csv"
                    out_path = os.path.join(out_dir, file_name)
                    _write_replay_kline_csv(out_path, rows)
                    if logger:
                        logger.info(f"📁 回放K线已导出: {out_path}")
        else:
            if want_dir == 'long':
                pos['initial_layer_trailing_stop_price'] = pos['initial_price'] * (1 - sl_pct)
            else:
                pos['initial_layer_trailing_stop_price'] = pos['initial_price'] * (1 + sl_pct)
            pos['overall_trailing_stop_price'] = float(pos['initial_layer_trailing_stop_price'])
            _append_trailing_stop_trace(pos, 'initial', pos.get('entry_date'), -1, float(pos['initial_layer_trailing_stop_price']), "回放初始化")
            if 'max_profit_tracking' not in G:
                G['max_profit_tracking'] = {}
            G['max_profit_tracking'][contract] = {
                'max_profit_pct': 0.0,
                'trailing_stop_price': float(pos['overall_trailing_stop_price']),
                'last_update_time': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            try:
                if want_dir == 'long':
                    G[f"smart_stop_loss_{contract}_long"] = float(pos['initial_price']) * (1 - sl_pct)
                else:
                    G[f"smart_stop_loss_{contract}_short"] = float(pos['initial_price']) * (1 + sl_pct)
            except Exception:
                pass

        G['open_positions'][contract] = pos
        rebuilt_any = True

        if logger:
            logger.info(
                f"✅ 回放重建完成: {contract} {want_dir} total={pos.get('total_volume')} avg={float(pos.get('avg_price', 0) or 0):.2f} "
                f"maxp={float(G['max_profit_tracking'][contract].get('max_profit_pct', 0) or 0)*100:.2f}% "
                f"ts={float(G['max_profit_tracking'][contract].get('trailing_stop_price', 0) or 0):.2f} layers={1+len(pos.get('add_positions') or [])}"
            )

    if logger:
        if rebuilt_any:
            logger.info("✅ API历史回放重建完成")
        else:
            logger.info("⏸️ 未重建任何合约")
    return rebuilt_any


def _ensure_streak_risk_state():
    if 'risk_multiplier' not in G:
        G['risk_multiplier'] = 1.0
    if 'risk_tier' not in G:
        G['risk_tier'] = 0
    if 'loss_streak' not in G:
        G['loss_streak'] = 0
    if 'recent_nonzero_results' not in G or not isinstance(G.get('recent_nonzero_results'), list):
        G['recent_nonzero_results'] = []
    if 'streak_risk_multipliers' not in G:
        G['streak_risk_multipliers'] = [1.0, 0.7, 0.5, 0.3]


def _get_streak_risk_multipliers():
    _ensure_streak_risk_state()
    raw = G.get('streak_risk_multipliers')
    if not isinstance(raw, (list, tuple)):
        raw = [1.0, 0.7, 0.5, 0.3]
    vals = []
    for x in raw:
        try:
            v = float(x)
        except Exception:
            continue
        if v < 0:
            v = 0.0
        if v > 1:
            v = 1.0
        vals.append(v)
    if len(vals) < 4:
        vals = [1.0, 0.7, 0.5, 0.3]
    return [float(vals[0]), float(vals[1]), float(vals[2]), float(vals[3])]


def _tier_from_loss_streak(loss_streak):
    try:
        ls = int(loss_streak or 0)
    except Exception:
        ls = 0
    if ls <= 2:
        return 0
    if ls <= 4:
        return 1
    if ls <= 6:
        return 2
    return 3


def _update_streak_risk_state_on_close(realized_pnl):
    _ensure_streak_risk_state()
    try:
        pnl = float(realized_pnl or 0)
    except Exception:
        pnl = 0.0

    is_win = pnl > 1e-9
    is_loss = pnl < -1e-9

    if is_loss:
        try:
            G['loss_streak'] = int(G.get('loss_streak', 0) or 0) + 1
        except Exception:
            G['loss_streak'] = 1
    elif is_win:
        G['loss_streak'] = 0

    if is_win or is_loss:
        arr = G.get('recent_nonzero_results') or []
        arr.append(1 if is_win else 0)
        if len(arr) > 2:
            arr = arr[-2:]
        G['recent_nonzero_results'] = arr

    target_tier = _tier_from_loss_streak(G.get('loss_streak', 0))
    try:
        cur_tier = int(G.get('risk_tier', 0) or 0)
    except Exception:
        cur_tier = 0

    if target_tier > cur_tier:
        cur_tier = target_tier
    elif target_tier < cur_tier:
        arr = G.get('recent_nonzero_results') or []
        if len(arr) >= 2 and arr[-1] == 1 and arr[-2] == 1:
            cur_tier = max(cur_tier - 1, target_tier)

    tiers = _get_streak_risk_multipliers()
    cur_tier = max(0, min(3, int(cur_tier)))
    next_m = float(tiers[cur_tier])

    prev_m = float(G.get('risk_multiplier', 1.0) or 1.0)
    G['risk_tier'] = cur_tier
    G['risk_multiplier'] = next_m

    if abs(next_m - prev_m) > 1e-12:
        logger = G.get('logger')
        if logger:
            logger.info(f"🧯 风险乘数更新: m {prev_m:.2f} → {next_m:.2f} | loss_streak={int(G.get('loss_streak', 0) or 0)} | recent={G.get('recent_nonzero_results')}")


def _get_barpos(ContextInfo):
    try:
        return int(getattr(ContextInfo, 'barpos', -1) or -1)
    except Exception:
        return -1


def _schedule_trade_kline_dump(item):
    if 'kline_dump_queue' not in G or not isinstance(G.get('kline_dump_queue'), list):
        G['kline_dump_queue'] = []
    G['kline_dump_queue'].append(item)

def _base_code_from_contract(contract_code):
    try:
        parts = str(contract_code or '').split('.')
        if len(parts) != 2:
            return None
        sym = re.sub(r'\d+', '', parts[0]).lower()
        ex = parts[1].upper()
        if not sym or not ex:
            return None
        return f"{sym}.{ex}"
    except Exception:
        return None

def _kline_cache_path(base_code):
    d = G.get('kline_cache_dir')
    if not d:
        return None
    name = re.sub(r'[^0-9A-Za-z_.\\-]+', '_', str(base_code or ''))
    if not name:
        return None
    return os.path.join(str(d), f"{name}.csv")

def _load_kline_cache_df(base_code):
    path = _kline_cache_path(base_code)
    if not path or not os.path.exists(path):
        return None
    try:
        mtime = os.path.getmtime(path)
    except Exception:
        mtime = None
    if 'kline_cache_mem' not in G or not isinstance(G.get('kline_cache_mem'), dict):
        G['kline_cache_mem'] = {}
    mem = G['kline_cache_mem']
    cached = mem.get(base_code)
    if cached and isinstance(cached, dict) and cached.get('mtime') == mtime and cached.get('df') is not None:
        return cached.get('df')
    try:
        df = pd.read_csv(path, dtype={'date': str})
    except Exception:
        return None
    if df is None or df.empty or 'date' not in df.columns:
        return None
    try:
        df['date'] = df['date'].astype(str).str.replace(r'\\D+', '', regex=True).str[:8]
        df = df[df['date'].astype(str).str.len() == 8]
        df = df.sort_values('date')
        df = df.reset_index(drop=True)
    except Exception:
        return None
    mem[base_code] = {'mtime': mtime, 'df': df}
    return df


def _append_trailing_stop_trace(position, layer, date, barpos, stop_price, reason):
    if position is None:
        return
    if 'layer_trailing_stop_trace' not in position or not isinstance(position.get('layer_trailing_stop_trace'), dict):
        position['layer_trailing_stop_trace'] = {}
    layer_key = str(layer or 'overall')
    if layer_key not in position['layer_trailing_stop_trace'] or not isinstance(position['layer_trailing_stop_trace'].get(layer_key), list):
        position['layer_trailing_stop_trace'][layer_key] = []
    try:
        stop_f = float(stop_price)
    except Exception:
        return
    try:
        barpos_i = int(barpos) if barpos is not None else None
    except Exception:
        barpos_i = None
    date_s = str(date or '')
    reason_s = str(reason or '')
    trace = position['layer_trailing_stop_trace'][layer_key]
    if trace:
        last = trace[-1]
        try:
            last_p = float(last.get('price'))
        except Exception:
            last_p = None
        last_d = str(last.get('date') or '')
        if last_p is not None and abs(last_p - stop_f) <= 1e-9 and last_d == date_s:
            return
    trace.append({
        'date': date_s,
        'barpos': barpos_i,
        'price': stop_f,
        'reason': reason_s,
    })


def _get_donchian_add_positions(position, create=False):
    if not isinstance(position, dict):
        return []
    layers = position.get('donchian_add_positions')
    if not isinstance(layers, list):
        layers = []
        if create:
            position['donchian_add_positions'] = layers
    elif create:
        position['donchian_add_positions'] = layers
    return layers


def _recalculate_position_totals(position):
    if not isinstance(position, dict):
        return 0, 0.0
    try:
        base_volume = int(position.get('volume', 0) or 0)
    except Exception:
        base_volume = 0
    try:
        base_price = float(position.get('initial_price', position.get('price', position.get('avg_price', 0))) or 0)
    except Exception:
        base_price = 0.0

    total_volume = max(base_volume, 0)
    total_cost = float(base_price) * float(max(base_volume, 0)) if base_price > 0 else 0.0

    add_positions = position.get('add_positions') or []
    if not isinstance(add_positions, list):
        add_positions = []
    position['add_positions'] = add_positions

    donchian_add_positions = _get_donchian_add_positions(position, create=True)

    for layer_key, layers in (('add_count', add_positions), ('donchian_add_count', donchian_add_positions)):
        valid_layers = []
        for layer in layers:
            if not isinstance(layer, dict):
                continue
            try:
                lv = int(layer.get('volume', 0) or 0)
            except Exception:
                lv = 0
            if lv <= 0:
                continue
            valid_layers.append(layer)
            try:
                lp = float(layer.get('price', 0) or 0)
            except Exception:
                lp = 0.0
            total_volume += lv
            if lp > 0:
                total_cost += float(lp) * float(lv)
        if layer_key == 'add_count':
            position['add_positions'] = valid_layers
        else:
            position['donchian_add_positions'] = valid_layers
        position[layer_key] = len(valid_layers)

    position['total_volume'] = int(total_volume)
    if total_volume > 0 and total_cost > 0:
        position['avg_price'] = float(total_cost) / float(total_volume)
    elif total_volume > 0:
        try:
            position['avg_price'] = float(position.get('price', position.get('avg_price', 0)) or 0)
        except Exception:
            position['avg_price'] = 0.0
    else:
        position['avg_price'] = 0.0
    return int(position.get('total_volume', 0) or 0), float(position.get('avg_price', 0) or 0)


def _reduce_position_volume(position, reduce_volume):
    if not isinstance(position, dict):
        return 0
    try:
        remaining = int(reduce_volume or 0)
    except Exception:
        remaining = 0
    if remaining <= 0:
        return 0
    requested = remaining

    for layer_key in ('donchian_add_positions', 'add_positions'):
        layers = _get_donchian_add_positions(position, create=True) if layer_key == 'donchian_add_positions' else (position.get('add_positions') or [])
        if not isinstance(layers, list):
            layers = []
        while remaining > 0 and layers:
            last_idx = len(layers) - 1
            try:
                layer_vol = int(layers[last_idx].get('volume', 0) or 0)
            except Exception:
                layer_vol = 0
            if layer_vol <= 0:
                layers.pop(last_idx)
                continue
            take = layer_vol if layer_vol <= remaining else remaining
            layers[last_idx]['volume'] = layer_vol - take
            remaining -= take
            if int(layers[last_idx].get('volume', 0) or 0) <= 0:
                layers.pop(last_idx)
        if layer_key == 'donchian_add_positions':
            position['donchian_add_positions'] = layers
        else:
            position['add_positions'] = layers

    if remaining > 0:
        try:
            base_vol = int(position.get('volume', 0) or 0)
        except Exception:
            base_vol = 0
        take = base_vol if base_vol <= remaining else remaining
        position['volume'] = max(base_vol - take, 0)
        remaining -= take

    _recalculate_position_totals(position)
    return max(requested - remaining, 0)


def _schedule_block_kline_dump(item):
    if 'block_kline_dump_queue' not in G or not isinstance(G.get('block_kline_dump_queue'), list):
        G['block_kline_dump_queue'] = []
    G['block_kline_dump_queue'].append(item)


def _dump_trade_kline_if_ready(ContextInfo, current_date_str):
    queue = G.get('kline_dump_queue')
    if not queue:
        return
    if not getattr(ContextInfo, 'do_back_test', False):
        return
    post_days_default = int(G.get('kline_post_days', 20) or 20)
    cur_barpos = _get_barpos(ContextInfo)
    is_last_bar = False
    try:
        _ = ContextInfo.get_bar_timetag(cur_barpos + 1)
    except Exception:
        is_last_bar = True
    remaining = []
    for item in queue:
        try:
            post_days = int(item.get('post_days', post_days_default) or post_days_default)
        except Exception:
            post_days = post_days_default
        try:
            exit_barpos = int(item.get('exit_barpos'))
        except Exception:
            remaining.append(item)
            continue
        if exit_barpos < 0:
            remaining.append(item)
            continue

        effective_post_days = post_days
        if is_last_bar:
            try:
                effective_post_days = min(post_days, max(0, cur_barpos - exit_barpos))
            except Exception:
                effective_post_days = 0
        use_cache = bool(G.get('use_kline_cache', False)) and bool(G.get('kline_cache_dir'))
        contract_code = item.get('contract_code')
        if not contract_code:
            continue
        pre_days = int(item.get('pre_days', 20) or 20)
        post_days_item = int(item.get('post_days', post_days_default) or post_days_default)
        entry_idx = None
        exit_idx = None
        df = None
        entry_date = str(item.get('entry_date') or '')
        exit_date = str(item.get('exit_date') or '')
        if use_cache and entry_date and exit_date:
            base_code = item.get('base_code') or _base_code_from_contract(contract_code)
            df_all = _load_kline_cache_df(base_code) if base_code else None
            if df_all is not None and not df_all.empty and 'date' in df_all.columns:
                try:
                    dates_int = df_all['date'].astype(int).to_numpy()
                    e_int = int(re.sub(r'\\D+', '', entry_date)[:8])
                    x_int = int(re.sub(r'\\D+', '', exit_date)[:8])
                    entry_pos = int(np.searchsorted(dates_int, e_int, side='left'))
                    if entry_pos >= len(dates_int):
                        entry_pos = len(dates_int) - 1
                    if dates_int[entry_pos] != e_int and entry_pos > 0:
                        if abs(int(dates_int[entry_pos - 1]) - e_int) <= abs(int(dates_int[entry_pos]) - e_int):
                            entry_pos -= 1
                    exit_pos = int(np.searchsorted(dates_int, x_int, side='left'))
                    if exit_pos >= len(dates_int):
                        exit_pos = len(dates_int) - 1
                    if dates_int[exit_pos] != x_int and exit_pos > 0 and int(dates_int[exit_pos]) > x_int:
                        exit_pos -= 1
                    if exit_pos < entry_pos:
                        exit_pos = entry_pos
                    start_i = max(0, entry_pos - pre_days)
                    end_i = min(len(df_all), exit_pos + post_days_item + 1)
                    df = df_all.iloc[start_i:end_i].copy()
                    df = df.reset_index(drop=True)
                    entry_idx = entry_pos - start_i
                    exit_idx = exit_pos - start_i
                except Exception:
                    df = None

        if df is None:
            if use_cache and effective_post_days > post_days_default:
                effective_post_days = post_days_default
                post_days_item = post_days_default
                post_days = post_days_default
            if cur_barpos < exit_barpos + effective_post_days:
                remaining.append(item)
                continue
            try:
                entry_barpos = int(item.get('entry_barpos'))
            except Exception:
                entry_barpos = None
            if entry_barpos is None or entry_barpos < 0:
                remaining.append(item)
                continue
            need_count = int((exit_barpos - entry_barpos) + pre_days + effective_post_days + 1)
            if need_count < 5:
                need_count = 5
            market_map = ContextInfo.get_market_data_ex(
                fields=['open', 'high', 'low', 'close', 'volume', 'openInterest'],
                stock_code=[contract_code],
                period=G['period'],
                end_time=current_date_str,
                count=need_count,
                dividend_type='front_ratio',
                subscribe=False
            )
            if contract_code not in market_map or market_map[contract_code].empty:
                continue
            df = market_map[contract_code]
            if len(df) < need_count:
                need_count = len(df)
            bars_after_exit = max(0, cur_barpos - exit_barpos)
            bars_after_entry = max(0, cur_barpos - entry_barpos)
            entry_idx = (need_count - 1) - bars_after_entry
            exit_idx = (need_count - 1) - bars_after_exit
            if entry_idx < 0:
                entry_idx = 0
            if entry_idx >= need_count:
                entry_idx = need_count - 1
            if exit_idx < 0:
                exit_idx = 0
            if exit_idx >= need_count:
                exit_idx = need_count - 1
        need_count = len(df)

        dump_dir = G.get('kline_dump_dir')
        if not dump_dir:
            dump_dir = os.path.join(G.get('log_dir', '.'), 'trade_kline')
        try:
            os.makedirs(dump_dir, exist_ok=True)
        except Exception:
            pass
        file_name = f"{item.get('trade_id','')}_{contract_code}_{item.get('layer','')}_{item.get('direction','')}_{item.get('entry_date','')}_{item.get('exit_date','')}.csv"
        file_name = re.sub(r'[^0-9A-Za-z_.\-]+', '_', file_name)
        file_path = os.path.join(dump_dir, file_name)
        pos_volume = item.get('pos_volume')
        volume_multiple = item.get('volume_multiple')
        try:
            pos_volume_f = float(pos_volume) if pos_volume is not None else None
        except Exception:
            pos_volume_f = None
        try:
            volume_multiple_f = float(volume_multiple) if volume_multiple is not None else None
        except Exception:
            volume_multiple_f = None
        try:
            _ep = float(item.get('entry_price'))
            _xp = float(item.get('exit_price'))
            _dir = str(item.get('direction') or '').lower()
            if _dir == 'short':
                pnl_points = _ep - _xp
            else:
                pnl_points = _xp - _ep
            pnl_pct = (pnl_points / _ep) if abs(_ep) > 1e-12 else None
        except Exception:
            pnl_points = None
            pnl_pct = None
        if pnl_points is not None and pos_volume_f is not None and volume_multiple_f is not None:
            pnl_money = pnl_points * pos_volume_f * volume_multiple_f
        else:
            pnl_money = None

        rsi_series = None
        try:
            rsi_data = calculate_rsi(df['close'], period=6)
            if rsi_data and 'rsi_series' in rsi_data:
                rsi_series = rsi_data['rsi_series']
        except Exception:
            rsi_series = None
        try:
            import csv

            _layer_trace = item.get('layer_trailing_stop_trace') or {}
            _layer = str(item.get('layer') or 'overall')
            _trace = []
            if isinstance(_layer_trace, dict):
                if _layer in _layer_trace and isinstance(_layer_trace.get(_layer), list):
                    _trace.extend(_layer_trace.get(_layer) or [])
                elif _layer.startswith('overall_'):
                    # 主仓完整平仓导出需要先拿到初始止损，再叠加overall更新轨迹。
                    if isinstance(_layer_trace.get('initial'), list):
                        _trace.extend(_layer_trace.get('initial') or [])
                    if isinstance(_layer_trace.get('overall'), list):
                        _trace.extend(_layer_trace.get('overall') or [])
                else:
                    if isinstance(_layer_trace.get('overall'), list):
                        _trace.extend(_layer_trace.get('overall') or [])
                    if not _trace and isinstance(_layer_trace.get('initial'), list):
                        _trace.extend(_layer_trace.get('initial') or [])
            _trace_map = {}
            if isinstance(_trace, list):
                for ev in _trace:
                    try:
                        _d = str(ev.get('date') or '')
                        _d = re.sub(r'\D+', '', _d)[:8]
                        _p = float(ev.get('price'))
                        _r = str(ev.get('reason') or '')
                        if _d:
                            _trace_map[_d] = (_p, _r)
                    except Exception:
                        continue

            with open(file_path, 'w', newline='', encoding='utf-8') as f:
                w = csv.writer(f)
                w.writerow(['idx', 'date', 'open', 'high', 'low', 'close', 'volume', 'open_interest', 'mark', 'contract', 'layer', 'direction', 'trade_id', 'root_trade_id', 'entry_price', 'exit_price', 'sizing_stop_price', 'sizing_stop_source', 'entry_signal_source', 'pending_breakout_created_date', 'pending_breakout_wait_days', 'visual_snapshot_only', 'pos_volume', 'volume_multiple', 'pnl_points', 'pnl_pct', 'pnl_money', 'close_reason', 'rsi_6', 'ts', 'ts_reason'])
                for i in range(need_count):
                    row = df.iloc[i]
                    if 'date' in df.columns:
                        dt = row.get('date')
                    else:
                        dt = df.index[i]
                    mark = ''
                    if i == entry_idx:
                        mark = 'ENTRY'
                    if i == exit_idx:
                        mark = 'EXIT'

                    try:
                        _rsi_v = None
                        if rsi_series is not None:
                            _rsi_v = rsi_series.iloc[i]
                            try:
                                if hasattr(_rsi_v, 'item'):
                                    _rsi_v = _rsi_v.item()
                            except Exception:
                                pass
                            try:
                                _rsi_v = float(_rsi_v)
                            except Exception:
                                _rsi_v = None
                            if _rsi_v is not None and _rsi_v != _rsi_v:
                                _rsi_v = None
                    except Exception:
                        _rsi_v = None

                    _dt_key = re.sub(r'\D+', '', str(dt))[:8]
                    _ts_v = None
                    _ts_r = ''
                    if _dt_key and _dt_key in _trace_map:
                        _ts_v, _ts_r = _trace_map.get(_dt_key)
                    bar_contract = contract_code
                    if 'contract' in df.columns:
                        try:
                            bar_contract = str(row.get('contract') or contract_code)
                        except Exception:
                            bar_contract = contract_code
                    w.writerow([
                        i,
                        str(dt),
                        float(row.get('open', 0) or 0),
                        float(row.get('high', 0) or 0),
                        float(row.get('low', 0) or 0),
                        float(row.get('close', 0) or 0),
                        float(row.get('volume', 0) or 0),
                        float(row.get('openInterest', 0) or 0),
                        mark,
                        bar_contract,
                        item.get('layer'),
                        item.get('direction'),
                        item.get('trade_id'),
                        item.get('root_trade_id', item.get('trade_id')),
                        item.get('entry_price'),
                        item.get('exit_price'),
                        item.get('sizing_stop_price'),
                        item.get('sizing_stop_source'),
                        item.get('entry_signal_source'),
                        item.get('pending_breakout_created_date'),
                        item.get('pending_breakout_wait_days'),
                        1 if bool(item.get('visual_snapshot_only')) else 0,
                        pos_volume_f,
                        volume_multiple_f,
                        pnl_points,
                        pnl_pct,
                        pnl_money,
                        item.get('close_reason'),
                        _rsi_v,
                        _ts_v,
                        _ts_r,
                    ])
        except Exception as e:
            G['logger'].warning(f"K线导出失败: {e}")
            continue

        _log_structured('TRADE_KLINE_DUMP', {
            'trade_id': item.get('trade_id'),
            'contract': contract_code,
            'layer': item.get('layer'),
            'direction': item.get('direction'),
            'entry_date': item.get('entry_date'),
            'exit_date': item.get('exit_date'),
            'sizing_stop_price': item.get('sizing_stop_price'),
            'sizing_stop_source': item.get('sizing_stop_source'),
            'pre_days': pre_days,
            'post_days': post_days,
            'bars': need_count,
            'file_path': file_path,
            'entry_idx': entry_idx,
            'exit_idx': exit_idx,
            'close_reason': item.get('close_reason')
        })

    G['kline_dump_queue'] = remaining


def _dump_block_kline_if_ready(ContextInfo, current_date_str):
    queue = G.get('block_kline_dump_queue')
    if not queue:
        return
    if not getattr(ContextInfo, 'do_back_test', False):
        return
    post_days = int(G.get('block_kline_post_days', G.get('kline_post_days', 20)) or 20)
    cur_barpos = _get_barpos(ContextInfo)
    remaining = []
    for item in queue:
        try:
            trigger_barpos = int(item.get('trigger_barpos'))
        except Exception:
            remaining.append(item)
            continue
        if trigger_barpos < 0 or cur_barpos < trigger_barpos + post_days:
            remaining.append(item)
            continue
        pre_days = int(item.get('pre_days', G.get('block_kline_pre_days', G.get('kline_pre_days', 20))) or 20)
        need_count = int(pre_days + post_days + 1)
        if need_count < 5:
            need_count = 5

        contract_code = item.get('contract_code')
        if not contract_code:
            continue
        market_map = ContextInfo.get_market_data_ex(
            fields=['open', 'high', 'low', 'close', 'volume', 'openInterest'],
            stock_code=[contract_code],
            period=G['period'],
            end_time=current_date_str,
            count=need_count,
            dividend_type='front_ratio',
            subscribe=False
        )
        if contract_code not in market_map or market_map[contract_code].empty:
            continue
        df = market_map[contract_code]
        if len(df) < need_count:
            need_count = len(df)
        mark_idx = min(max(0, pre_days), need_count - 1)

        dump_dir = G.get('block_kline_dump_dir')
        if not dump_dir:
            dump_dir = os.path.join(G.get('log_dir', '.'), 'blocked_kline')
        try:
            os.makedirs(dump_dir, exist_ok=True)
        except Exception:
            pass

        try:
            G['blocked_id_seq'] = int(G.get('blocked_id_seq', 0) or 0) + 1
        except Exception:
            G['blocked_id_seq'] = 1
        blocked_id = int(G.get('blocked_id_seq', 1) or 1)

        file_name = f"blocked_{blocked_id}_{contract_code}_{item.get('tag','')}_{item.get('direction','')}_{item.get('date','')}.csv"
        file_name = re.sub(r'[^0-9A-Za-z_.\-]+', '_', file_name)
        file_path = os.path.join(dump_dir, file_name)

        rsi_series = None
        try:
            rsi_data = calculate_rsi(df['close'], period=6)
            if rsi_data and 'rsi_series' in rsi_data:
                rsi_series = rsi_data['rsi_series']
        except Exception:
            rsi_series = None

        try:
            import csv

            with open(file_path, 'w', newline='', encoding='utf-8') as f:
                w = csv.writer(f)
                w.writerow(['idx', 'date', 'open', 'high', 'low', 'close', 'volume', 'open_interest', 'mark', 'contract', 'layer', 'direction', 'entry_price', 'exit_price', 'pos_volume', 'volume_multiple', 'pnl_points', 'pnl_pct', 'pnl_money', 'close_reason', 'rsi_6'])
                for i in range(need_count):
                    row = df.iloc[-need_count + i]
                    dt = df.index[-need_count + i]
                    mark = 'BLOCK' if i == mark_idx else ''
                    try:
                        _rsi_v = None
                        if rsi_series is not None:
                            _rsi_v = rsi_series.iloc[-need_count + i]
                            try:
                                if hasattr(_rsi_v, 'item'):
                                    _rsi_v = _rsi_v.item()
                            except Exception:
                                pass
                            try:
                                _rsi_v = float(_rsi_v)
                            except Exception:
                                _rsi_v = None
                            if _rsi_v is not None and _rsi_v != _rsi_v:
                                _rsi_v = None
                    except Exception:
                        _rsi_v = None
                    w.writerow([
                        i,
                        str(dt),
                        float(row.get('open', 0) or 0),
                        float(row.get('high', 0) or 0),
                        float(row.get('low', 0) or 0),
                        float(row.get('close', 0) or 0),
                        float(row.get('volume', 0) or 0),
                        float(row.get('openInterest', 0) or 0),
                        mark,
                        contract_code,
                        item.get('tag'),
                        item.get('direction'),
                        None,
                        None,
                        None,
                        None,
                        None,
                        None,
                        None,
                        item.get('reason'),
                        _rsi_v,
                    ])
        except Exception as e:
            G['logger'].warning(f"过滤K线导出失败: {e}")
            continue

        _log_structured('BLOCK_KLINE_DUMP', {
            'blocked_id': blocked_id,
            'contract': contract_code,
            'tag': item.get('tag'),
            'direction': item.get('direction'),
            'date': item.get('date'),
            'pre_days': pre_days,
            'post_days': post_days,
            'bars': need_count,
            'file_path': file_path,
            'mark_idx': mark_idx,
            'reason': item.get('reason'),
        })

    G['block_kline_dump_queue'] = remaining


def send_startup_notification_email(ContextInfo):
    logger = G.get('logger')

    is_backtest = bool(getattr(ContextInfo, 'do_back_test', False))
    if is_backtest and G.get('startup_email_sent_backtest', False):
        return

    now_dt = get_context_datetime(ContextInfo)
    mode = 'backtest' if getattr(ContextInfo, 'do_back_test', False) else G.get('run_mode', 'live')
    subject = f"QMT策略启动 {mode} account={G.get('accountid', '')}"

    lines = []
    lines.append(f"时间: {now_dt.strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"账户: {G.get('accountid', '')}")
    lines.append(f"模式: {mode}")
    lines.append(f"日志: {G.get('log_file_path', '')}")
    lines.append(f"备份: {G.get('data_backup_file', '')}")
    lines.append(f"合约列表: {', '.join(G.get('contract_codes', []))}")

    valid_assets = False
    try:
        account_info = get_trade_detail_data(G['accountid'], 'FUTURE', 'ACCOUNT')
        if account_info:
            account = account_info[0]
            total_assets = getattr(account, 'm_dBalance', 0)
            available = getattr(account, 'm_dAvailable', 0)
            pos_profit = getattr(account, 'm_dPositionProfit', 0)
            total_assets_f = float(total_assets or 0)
            available_f = float(available or 0)
            pos_profit_f = float(pos_profit or 0)
            valid_assets = total_assets_f > 0
            if valid_assets:
                lines.append(f"总资产: {total_assets_f:.2f}")
                lines.append(f"可用资金: {available_f:.2f}")
                lines.append(f"持仓盈亏: {pos_profit_f:.2f}")
    except Exception:
        pass

    if not valid_assets:
        lines.append("资金信息: 未就绪/获取失败")

    if not is_backtest:
        if valid_assets:
            if G.get('startup_email_sent_assets', False):
                return
        else:
            if G.get('startup_email_sent_basic', False):
                return

    positions = G.get('open_positions', {})
    if positions:
        lines.append("持仓:")
        for contract, pos in positions.items():
            direction = pos.get('direction', '')
            total_volume = int(pos.get('total_volume', pos.get('volume', 0)) or 0)
            avg_price = float(pos.get('avg_price', pos.get('price', 0)) or 0)
            lines.append(f"- {contract} {direction} {total_volume} @ {avg_price:.2f}")
    else:
        lines.append("持仓: 无")

    body = "\n".join(lines)

    try:
        ok = send_email_via_smtp(subject, body, logger=logger)
        if ok:
            G['startup_email_sent_basic'] = True
            if valid_assets:
                G['startup_email_sent_assets'] = True
            if logger:
                logger.info('启动邮件已发送')
    except Exception as e:
        if logger:
            logger.warning(f"启动邮件发送失败: {e}")
    finally:
        if is_backtest:
            G['startup_email_sent_backtest'] = True


def send_trade_signal_email(ContextInfo, opType, orderType, accountid, orderCode, prType, price, volume, strategyName, quickTrade, userOrderId, mode_desc, reference_price=None):
    if getattr(ContextInfo, 'do_back_test', False):
        return

    logger = G.get('logger')
    now_dt = get_context_datetime(ContextInfo)
    day_key = now_dt.strftime('%Y%m%d')

    contract_type = _get_contract_type_label(orderCode)

    action_map = {
        0: '开多',
        3: '开空',
        6: '平多',
        8: '平空'
    }
    action = action_map.get(opType, f'opType={opType}')

    uniq_key = f"{day_key}|{opType}|{orderType}|{orderCode}|{int(volume)}|{strategyName}|{userOrderId}"
    ts_now = time.time()
    cache = G.setdefault('trade_signal_email_cache', {})
    last_ts = cache.get(uniq_key)
    if last_ts is not None and ts_now - float(last_ts) < 60:
        return
    cache[uniq_key] = ts_now
    try:
        for k, v in list(cache.items()):
            if ts_now - float(v) > 86400:
                cache.pop(k, None)
    except Exception:
        pass

    subject = f"QMT交易信号 {action} {orderCode} {int(volume)}手 [{contract_type}]"
    lines = []
    lines.append(f"时间: {now_dt.strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"账户: {accountid}")
    lines.append(f"模式: live")
    lines.append(f"动作: {action}")
    lines.append(f"合约: {orderCode}")
    lines.append(f"合约类型: {contract_type}")
    lines.append(f"手数: {int(volume)}")
    lines.append(f"orderType: {orderType}")
    lines.append(f"prType: {prType}")
    lines.append(f"price: {price}")
    if reference_price is not None:
        try:
            lines.append(f"参考价: {float(reference_price):.2f}")
        except Exception:
            lines.append(f"参考价: {reference_price}")

    if opType in (0, 3):
        direction = 'long' if opType == 0 else 'short'
        stop_key = f"smart_stop_loss_{orderCode}_{direction}"
        stop_loss = G.get(stop_key)
        if stop_loss is not None:
            try:
                lines.append(f"智能止损价({direction}): {float(stop_loss):.2f}")
            except Exception:
                lines.append(f"智能止损价({direction}): {stop_loss}")
        else:
            lines.append(f"智能止损价({direction}): 未设置")

        try:
            lines.append(f"基础止损比例: {float(G.get('stop_loss_pct', 0) or 0)*100:.2f}%")
        except Exception:
            pass

        if G.get('trailing_stop_enabled'):
            lines.append("移动止损: 启用")
        else:
            lines.append("移动止损: 禁用")

        if 'current_risk_per_trade' in G:
            try:
                lines.append(f"动态风险金额: {float(G.get('current_risk_per_trade', 0) or 0):.2f}")
            except Exception:
                pass
        if 'limited_available_balance' in G:
            try:
                lines.append(f"限制后可用资金: {float(G.get('limited_available_balance', 0) or 0):.2f}")
            except Exception:
                pass
        if 'total_assets' in G:
            try:
                lines.append(f"总资产: {float(G.get('total_assets', 0) or 0):.2f}")
            except Exception:
                pass
    lines.append(f"strategyName: {strategyName}")
    lines.append(f"userOrderId: {userOrderId}")
    lines.append(f"执行: {mode_desc}")
    body = "\n".join(lines)

    try:
        ok = send_email_via_smtp(subject, body, logger=logger)
        if ok and logger:
            logger.info(f"交易信号邮件已发送: {action} {orderCode} {int(volume)}手")
    except Exception as e:
        if logger:
            logger.warning(f"交易信号邮件发送失败: {e}")


def send_trade_candidate_blocked_email(ContextInfo, contract_code, direction, signal_type, reason, current_price, contract_info, account_info):
    if getattr(ContextInfo, 'do_back_test', False):
        return
    if not bool(G.get('enable_trade_blocked_email', True)):
        return

    logger = G.get('logger')
    now_dt = get_context_datetime(ContextInfo)
    day_key = now_dt.strftime('%Y%m%d')

    contract_type = _get_contract_type_label(contract_code)
    direction_cn = "多头" if str(direction).lower() == "long" else "空头"

    uniq_key = f"{day_key}|blocked|{contract_code}|{direction_cn}|{signal_type}|{reason}"
    ts_now = time.time()
    cache = G.setdefault('trade_blocked_email_cache', {})
    last_ts = cache.get(uniq_key)
    if last_ts is not None and ts_now - float(last_ts) < 300:
        return
    cache[uniq_key] = ts_now
    try:
        for k, v in list(cache.items()):
            if ts_now - float(v) > 86400:
                cache.pop(k, None)
    except Exception:
        pass

    account_obj = None
    if account_info:
        if isinstance(account_info, list):
            account_obj = account_info[0] if account_info else None
        else:
            account_obj = account_info

    try:
        available_balance = float(getattr(account_obj, 'm_dAvailable', 0) or 0)
    except Exception:
        available_balance = 0.0
    limited_available_balance = float(G.get('limited_available_balance', available_balance) or 0)

    try:
        volume_multiple = float(contract_info.get('VolumeMultiple', 10) or 10)
    except Exception:
        volume_multiple = 10.0
    if direction_cn == "多头":
        try:
            margin_ratio = float(contract_info.get('LongMarginRatio', 0.1) or 0.1)
        except Exception:
            margin_ratio = 0.1
    else:
        try:
            margin_ratio = float(contract_info.get('ShortMarginRatio', 0.1) or 0.1)
        except Exception:
            margin_ratio = 0.1
    try:
        single_contract_value = float(current_price) * float(volume_multiple)
    except Exception:
        single_contract_value = 0.0
    try:
        min_pos = int(G.get('min_position_size', 1) or 1)
    except Exception:
        min_pos = 1
    if min_pos <= 0:
        min_pos = 1
    required_margin_min = float(min_pos) * float(single_contract_value) * float(margin_ratio)

    subject = f"QMT候选信号未下单(保证金不足) {direction_cn} {contract_code} [{contract_type}]"
    lines = []
    lines.append(f"时间: {now_dt.strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"账户: {G.get('accountid', '')}")
    lines.append("模式: live")
    lines.append(f"合约: {contract_code}")
    lines.append(f"合约类型: {contract_type}")
    lines.append(f"方向: {direction_cn}")
    lines.append(f"信号: {signal_type}")
    lines.append(f"原因: {reason}")
    try:
        lines.append(f"价格: {float(current_price):.2f}")
    except Exception:
        lines.append(f"价格: {current_price}")
    lines.append(f"最小手数: {min_pos}")
    lines.append(f"单手价值: {single_contract_value:.2f}")
    lines.append(f"保证金率: {margin_ratio*100:.2f}%")
    lines.append(f"最小手数保证金需求: {required_margin_min:.2f}")
    lines.append(f"限制后可用资金: {limited_available_balance:.2f}")
    lines.append(f"原始可用资金: {available_balance:.2f}")
    if 'current_risk_per_trade' in G:
        try:
            lines.append(f"动态风险金额: {float(G.get('current_risk_per_trade', 0) or 0):.2f}")
        except Exception:
            pass
    if 'total_assets' in G:
        try:
            lines.append(f"总资产: {float(G.get('total_assets', 0) or 0):.2f}")
        except Exception:
            pass
    body = "\n".join(lines)

    try:
        ok = send_email_via_smtp(subject, body, logger=logger)
        if ok and logger:
            logger.info(f"候选信号保证金不足邮件已发送: {contract_code} {direction_cn} {signal_type}")
    except Exception as e:
        if logger:
            logger.warning(f"候选信号保证金不足邮件发送失败: {e}")


def get_context_datetime(ContextInfo):
    try:
        if ContextInfo and getattr(ContextInfo, 'do_back_test', False):
            timetag = ContextInfo.get_bar_timetag(ContextInfo.barpos)
            return datetime.datetime.fromtimestamp(timetag / 1000)
    except Exception:
        pass
    return datetime.datetime.now()


def parse_datetime_flexible(value):
    if isinstance(value, datetime.datetime):
        return value
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    fmts = (
        '%Y-%m-%d %H:%M:%S',
        '%Y%m%d %H:%M:%S',
        '%Y-%m-%d %H:%M',
        '%Y%m%d %H:%M',
        '%Y-%m-%d',
        '%Y%m%d',
    )
    for f in fmts:
        try:
            return datetime.datetime.strptime(s, f)
        except Exception:
            continue
    return None


def get_base_code(contract_code):
    """ 从完整合约代码中提取基础代码，例如 sm2409.ZF -> sm.ZF """
    # 使用正则表达式去除合约代码中的数字部分
    match = re.match(r"([a-zA-Z]+)\d*(\..+)", contract_code)
    if match:
        # 将匹配到的字母部分和交易所部分拼接成基础代码
        return match.group(1).lower() + match.group(2)
    
    # 如果没有匹配到（例如，合约代码不含数字），则尝试直接分割
    parts = contract_code.split('.')
    if len(parts) == 2:
        # 假设第一个部分是基础代码（去除数字）
        base_symbol = ''.join(filter(str.isalpha, parts[0]))
        if base_symbol:
            return base_symbol.lower() + '.' + parts[1]
    
    G['logger'].warning(f"无法从 {contract_code} 中提取基础代码")
    return None


def safe_get_attr(obj, names, default=None):
    for name in names:
        try:
            v = getattr(obj, name)
            if v is not None:
                return v
        except Exception:
            continue
    return default


def parse_layer_type_from_remark(remark):
    if not remark:
        return None
    m = re.findall(r'(donchian_add_\d+|add_\d+|initial)', remark)
    return m[-1] if m else None


def _dict_get_first(d, keys, default=None):
    if not isinstance(d, dict) or not keys:
        return default
    for k in keys:
        try:
            if k in d and d.get(k) is not None:
                return d.get(k)
        except Exception:
            continue
    return default


def rebuild_positions_from_deals(ContextInfo):
    try:
        deals = get_trade_detail_data(G['accountid'], 'FUTURE', 'DEAL')
    except Exception as e:
        G['logger'].warning(f"⚠️ 成交回报查询失败，无法重建分层持仓: {e}")
        return False

    if not deals:
        G['logger'].info("📁 未查询到成交回报，跳过分层持仓重建")
        return False

    max_n = int(G.get('deal_replay_max_records', 5000))
    deals = deals[-max_n:]

    def is_our_remark(r):
        return isinstance(r, str) and r.startswith('期货多空排布策略')

    filtered = []
    for dt in deals:
        remark = safe_get_attr(dt, ['m_strRemark'], '')
        if is_our_remark(remark):
            filtered.append(dt)

    if not filtered:
        G['logger'].info("📁 未发现本策略成交回报，跳过分层持仓重建")
        return False

    ledger = {}
    last_add_date = {}

    for dt in filtered:
        instrument_id = safe_get_attr(dt, ['m_strInstrumentID'], '')
        exchange_id = safe_get_attr(dt, ['m_strExchangeID'], '')
        if not instrument_id or not exchange_id:
            continue
        contract_code = f"{instrument_id}.{exchange_id}"

        remark = safe_get_attr(dt, ['m_strRemark'], '')
        price = float(safe_get_attr(dt, ['m_dPrice', 'm_dTradedPrice'], 0) or 0)
        volume = int(safe_get_attr(dt, ['m_nVolume', 'm_nVolumeTraded'], 0) or 0)
        if volume <= 0:
            continue

        t = safe_get_attr(dt, ['m_strTradeTime', 'm_strOrderTime', 'm_strTime'], '')
        if not t:
            t = get_context_datetime(ContextInfo).strftime('%Y-%m-%d %H:%M:%S')

        is_open_long = ('开多' in remark) or ('加多' in remark) or ('换月开多' in remark)
        is_open_short = ('开空' in remark) or ('加空' in remark) or ('换月开空' in remark)
        is_close_long = '平多' in remark
        is_close_short = '平空' in remark

        if is_open_long and is_open_short:
            continue
        if is_close_long and is_close_short:
            continue

        if is_open_long or is_open_short:
            direction = 'long' if is_open_long else 'short'
            pos = ledger.get(contract_code)
            if not pos:
                ledger[contract_code] = {
                    'direction': direction,
                    'price': price,
                    'initial_price': price,
                    'volume': volume,
                    'time': t,
                    'avg_price': price,
                    'total_volume': volume,
                    'add_positions': [],
                    'donchian_add_positions': [],
                    'add_count': 0,
                    'donchian_add_count': 0,
                    'sync_source': 'deal_replay'
                }
            else:
                if pos.get('direction') != direction:
                    ledger[contract_code] = {
                        'direction': direction,
                        'price': price,
                        'initial_price': price,
                        'volume': volume,
                        'time': t,
                        'avg_price': price,
                        'total_volume': volume,
                        'add_positions': [],
                        'donchian_add_positions': [],
                        'add_count': 0,
                        'donchian_add_count': 0,
                        'sync_source': 'deal_replay'
                    }
                else:
                    layer_type = parse_layer_type_from_remark(remark)
                    if layer_type and str(layer_type).startswith('donchian_add_'):
                        _get_donchian_add_positions(pos, create=True).append({
                            'price': price,
                            'volume': volume,
                            'time': t,
                            'type': layer_type,
                            'trailing_stop_price': None
                        })
                    else:
                        pos.setdefault('add_positions', [])
                        pos['add_positions'].append({
                            'price': price,
                            'volume': volume,
                            'time': t,
                            'type': 'replay_add'
                        })
                    pos['add_count'] = len(pos.get('add_positions', []))
                    pos['donchian_add_count'] = len(_get_donchian_add_positions(pos, create=True))
                    _recalculate_position_totals(pos)
                    dt_key = re.findall(r'(\d{8})', t)
                    if dt_key:
                        if layer_type and str(layer_type).startswith('donchian_add_'):
                            if 'last_donchian_add_date' not in G or not isinstance(G.get('last_donchian_add_date'), dict):
                                G['last_donchian_add_date'] = {}
                            G['last_donchian_add_date'][contract_code] = dt_key[0]
                        else:
                            last_add_date[contract_code] = dt_key[0]
            continue

        if is_close_long or is_close_short:
            direction = 'long' if is_close_long else 'short'
            pos = ledger.get(contract_code)
            if not pos or pos.get('direction') != direction:
                continue
            layer_type = parse_layer_type_from_remark(remark)

            def reduce_from_layer(pos_ref, lt, qty):
                if qty <= 0:
                    return 0
                if lt == 'initial':
                    base_vol = int(pos_ref.get('volume', 0))
                    take = base_vol if base_vol <= qty else qty
                    pos_ref['volume'] = base_vol - take
                    return take
                if lt and lt.startswith('add_'):
                    idx = int(lt.split('_')[1]) - 1
                    aps = pos_ref.get('add_positions', [])
                    if 0 <= idx < len(aps):
                        ap_vol = int(aps[idx].get('volume', 0))
                        take = ap_vol if ap_vol <= qty else qty
                        aps[idx]['volume'] = ap_vol - take
                        if int(aps[idx].get('volume', 0)) <= 0:
                            aps.pop(idx)
                        pos_ref['add_positions'] = aps
                        return take
                if lt and lt.startswith('donchian_add_'):
                    idx = int(lt.split('_')[-1]) - 1
                    aps = _get_donchian_add_positions(pos_ref, create=True)
                    if 0 <= idx < len(aps):
                        ap_vol = int(aps[idx].get('volume', 0))
                        take = ap_vol if ap_vol <= qty else qty
                        aps[idx]['volume'] = ap_vol - take
                        if int(aps[idx].get('volume', 0)) <= 0:
                            aps.pop(idx)
                        pos_ref['donchian_add_positions'] = aps
                        return take
                return 0

            remaining = volume
            used = 0
            if layer_type:
                took = reduce_from_layer(pos, layer_type, remaining)
                used += took
                remaining -= took

            while remaining > 0:
                aps = _get_donchian_add_positions(pos, create=True)
                if aps:
                    last_idx = len(aps) - 1
                    ap_vol = int(aps[last_idx].get('volume', 0))
                    take = ap_vol if ap_vol <= remaining else remaining
                    aps[last_idx]['volume'] = ap_vol - take
                    if int(aps[last_idx].get('volume', 0)) <= 0:
                        aps.pop(last_idx)
                    pos['donchian_add_positions'] = aps
                    used += take
                    remaining -= take
                    continue
                aps = pos.get('add_positions', [])
                if aps:
                    last_idx = len(aps) - 1
                    ap_vol = int(aps[last_idx].get('volume', 0))
                    take = ap_vol if ap_vol <= remaining else remaining
                    aps[last_idx]['volume'] = ap_vol - take
                    if int(aps[last_idx].get('volume', 0)) <= 0:
                        aps.pop(last_idx)
                    pos['add_positions'] = aps
                    used += take
                    remaining -= take
                    continue
                base_vol = int(pos.get('volume', 0))
                if base_vol <= 0:
                    break
                take = base_vol if base_vol <= remaining else remaining
                pos['volume'] = base_vol - take
                used += take
                remaining -= take

            pos['add_count'] = len(pos.get('add_positions', []))
            pos['donchian_add_count'] = len(_get_donchian_add_positions(pos, create=True))
            total, _ = _recalculate_position_totals(pos)
            if total > 0:
                pass
            else:
                ledger.pop(contract_code, None)

    if not ledger:
        G['logger'].info("📁 成交回放后无持仓，跳过分层持仓重建")
        return False

    G['open_positions'] = ledger
    if 'last_add_date' not in G or not isinstance(G.get('last_add_date'), dict):
        G['last_add_date'] = {}
    for k, v in last_add_date.items():
        G['last_add_date'][k] = v
    G['logger'].info(f"✅ 成交回放重建分层持仓完成: {len(G['open_positions'])}个")
    return True


def calculate_macd(close_prices, fast_period=12, slow_period=26, signal_period=9):
    """
    计算MACD指标
    
    参数:
    - close_prices: 收盘价序列
    - fast_period: 快线周期，默认12
    - slow_period: 慢线周期，默认26
    - signal_period: 信号线周期，默认9
    
    返回:
    - dict: 包含macd, signal, histogram的字典
    """
    if len(close_prices) < slow_period + signal_period:
        return None
    
    # 计算快速和慢速EMA
    ema_fast = close_prices.ewm(span=fast_period).mean()
    ema_slow = close_prices.ewm(span=slow_period).mean()
    
    # 计算MACD线 (DIF)
    macd_line = ema_fast - ema_slow
    
    # 计算信号线 (DEA)
    signal_line = macd_line.ewm(span=signal_period).mean()
    
    # 计算MACD柱状图 (MACD)
    macd_histogram = macd_line - signal_line
    
    return {
        'macd_line': macd_line,        # DIF线
        'signal_line': signal_line,    # DEA线  
        'histogram': macd_histogram,   # MACD柱状图
        'current_macd': macd_histogram.iloc[-1] if not macd_histogram.empty else 0,
        'current_dif': macd_line.iloc[-1] if not macd_line.empty else 0,
        'current_dea': signal_line.iloc[-1] if not signal_line.empty else 0
    }

def calculate_rsi(close_prices, period=6):
    """
    计算RSI指标（相对强弱指数）- 标准方法
    
    参数:
    - close_prices: 收盘价序列
    - period: RSI周期，默认6日
    
    返回:
    - dict: 包含RSI值和当前RSI的字典
    """
    if len(close_prices) < period + 1:
        return None
    
    # 计算价格变化
    price_changes = close_prices.diff()
    
    # 分离上涨和下跌
    gains = price_changes.where(price_changes > 0, 0)
    losses = -price_changes.where(price_changes < 0, 0)
    
    # 使用标准RSI计算方法（EMA平滑）
    # alpha = 1 / period，这是EMA的标准参数
    alpha = 1.0 / period
    
    # 计算EMA平均涨幅和跌幅
    avg_gains = gains.ewm(alpha=alpha, adjust=False).mean()
    avg_losses = losses.ewm(alpha=alpha, adjust=False).mean()
    
    # 计算相对强度 RS
    rs = avg_gains / avg_losses
    
    # 计算RSI
    rsi = 100 - (100 / (1 + rs))
    
    return {
        'rsi_series': rsi,
        'current_rsi': rsi.iloc[-1] if not rsi.empty else 50,
        'avg_gains': avg_gains.iloc[-1] if not avg_gains.empty else 0,
        'avg_losses': avg_losses.iloc[-1] if not avg_losses.empty else 0
    }

def calculate_multi_period_rsi(close_prices, periods=[6, 12, 24]):
    """
    计算多周期RSI指标
    
    参数:
    - close_prices: 收盘价序列
    - periods: RSI周期列表，默认[6, 12, 24]
    
    返回:
    - dict: 包含各周期RSI值的字典
    """
    results = {}
    
    for period in periods:
        rsi_data = calculate_rsi(close_prices, period)
        if rsi_data:
            results[f'rsi_{period}'] = rsi_data['current_rsi']
        else:
            results[f'rsi_{period}'] = 50  # 默认中性值
    
    # 计算RSI综合信号
    rsi_values = [v for v in results.values() if v != 50]
    if rsi_values:
        results['rsi_avg'] = sum(rsi_values) / len(rsi_values)
        results['rsi_trend'] = 'bullish' if results['rsi_avg'] < 40 else 'bearish' if results['rsi_avg'] > 60 else 'neutral'
    else:
        results['rsi_avg'] = 50
        results['rsi_trend'] = 'neutral'
    
    return results

def calculate_er(close_prices, period=20):
    try:
        n = int(period or 0)
    except Exception:
        n = 0
    if n <= 0:
        return None
    try:
        if len(close_prices) < n + 1:
            return None
    except Exception:
        return None
    try:
        end = float(close_prices.iloc[-1])
        start = float(close_prices.iloc[-(n + 1)])
        net = abs(end - start)
        diffs = close_prices.diff().abs()
        denom = float(diffs.iloc[-n:].sum())
        if denom <= 0:
            return 0.0
        return float(net / denom)
    except Exception:
        return None



def evaluate_er_open_filter(close_prices, thresholds=None):
    if thresholds is None:
        thresholds = {5: 0.2, 10: 0.2, 20: 0.2}
    result = {
        'er_5': calculate_er(close_prices, 5),
        'er_10': calculate_er(close_prices, 10),
        'er_20': calculate_er(close_prices, 20),
        'threshold_5': float(thresholds.get(5, 0.2)),
        'threshold_10': float(thresholds.get(10, 0.2)),
        'threshold_20': float(thresholds.get(20, 0.2)),
        'should_block': False,
        'failed_periods': [],
    }
    for period in (5, 10, 20):
        er_v = result.get(f'er_{period}')
        thr = result.get(f'threshold_{period}')
        if er_v is None:
            continue
        try:
            if float(er_v) < float(thr):
                result['failed_periods'].append(period)
        except Exception:
            continue
    result['should_block'] = len(result['failed_periods']) > 0
    return result

def smart_passorder(opType, orderType, accountid, orderCode, current_price, volume,
                   strategyName, quickTrade, userOrderId, ContextInfo, extra=None):
    """
    智能订单执行函数 - 根据回测/实盘模式自动选择最佳价格类型
    """
    if ContextInfo.do_back_test:
        prType = 11
        price = current_price
        mode_desc = f"回测模式-指定价({price:.2f})"
    else:
        prType = 14
        price = -1
        mode_desc = "实盘模式-对手价"

    G['logger'].info(f"📋 订单执行策略: {mode_desc}")

    try:
        now_dt = get_context_datetime(ContextInfo)
        bt_date = now_dt.strftime('%Y%m%d')
        ts = now_dt.strftime('%Y-%m-%d %H:%M:%S')
    except Exception:
        bt_date = None
        ts = None

    _log_structured('ORDER_EVENT', {
        'bt_date': bt_date,
        'ts': ts,
        'barpos': int(getattr(ContextInfo, 'barpos', -1)) if ContextInfo is not None else -1,
        'do_back_test': bool(getattr(ContextInfo, 'do_back_test', False)) if ContextInfo is not None else False,
        'accountid': accountid,
        'orderCode': orderCode,
        'opType': int(opType),
        'orderType': int(orderType),
        'prType': int(prType),
        'price': float(price) if price is not None else None,
        'reference_price': float(current_price) if current_price is not None else None,
        'volume': int(volume) if volume is not None else None,
        'strategyName': strategyName,
        'quickTrade': int(quickTrade),
        'userOrderId': userOrderId,
        'mode': mode_desc,
        'risk': _risk_snapshot(ContextInfo),
        'extra': extra
    })

    send_trade_signal_email(
        ContextInfo,
        opType,
        orderType,
        accountid,
        orderCode,
        prType,
        price,
        volume,
        strategyName,
        quickTrade,
        userOrderId,
        mode_desc,
        reference_price=current_price
    )

    order_id = passorder(
        opType,
        orderType,
        accountid,
        orderCode,
        prType,
        price,
        volume,
        strategyName,
        quickTrade,
        userOrderId,
        ContextInfo
    )

    if order_id in (None, 0):
        if ContextInfo.do_back_test:
            G['logger'].info("📋 回测模式passorder无返回/返回0，按提交成功处理")
            return 1
        G['logger'].warning("📋 实盘passorder无返回/返回0，无法据此判断成败，按已提交处理并等待回报/查询确认")
        return 1

    return order_id


def calculate_donchian_channel(market_data, period=20):
    """
    计算唐奇安通道（修正版）
    
    **关键修正：** 使用前N日（排除当日）的数据计算通道，用当日价格比较前N日通道
    这样才能正确检测突破！
    
    参数:
    - market_data: 包含high、low、close的DataFrame
    - period: 计算周期，默认20日
    
    返回:
    - dict: 包含upper、lower、middle的字典
    """
    if len(market_data) < period + 1:  # +1因为需要排除当日
        return None
    
    # 【关键修正】排除当日，使用前N日数据计算通道
    historical_data = market_data.iloc[:-1]  # 排除最后一日（当日）
    
    # 计算过去N日的最高价和最低价（不包括当日）
    high_prices = historical_data['high']
    low_prices = historical_data['low']
    
    # 唐奇安通道上轨：前N日最高价
    upper_channel = high_prices.rolling(window=period).max()
    
    # 唐奇安通道下轨：前N日最低价  
    lower_channel = low_prices.rolling(window=period).min()
    
    # 唐奇安通道中轨：(上轨+下轨)/2
    middle_channel = (upper_channel + lower_channel) / 2
    
    # 返回最新的通道值（基于前N日计算）
    return {
        'upper': upper_channel.iloc[-1] if not upper_channel.empty else None,
        'lower': lower_channel.iloc[-1] if not lower_channel.empty else None,
        'middle': middle_channel.iloc[-1] if not middle_channel.empty else None,
        'upper_series': upper_channel,
        'lower_series': lower_channel,
        'middle_series': middle_channel,
        'calculation_note': f'基于前{period}日数据（排除当日）计算'
    }

def check_donchian_breakout(current_price, donchian_channel, direction='both'):
    """
    检查是否突破唐奇安通道
    
    参数:
    - current_price: 当前价格
    - donchian_channel: 唐奇安通道数据
    - direction: 检查方向 'long'（向上突破）、'short'（向下突破）、'both'（双向）
    
    返回:
    - dict: {'breakout': bool, 'direction': str, 'details': str}
    """
    if not donchian_channel or donchian_channel['upper'] is None or donchian_channel['lower'] is None:
        return {'breakout': False, 'direction': 'none', 'details': '唐奇安通道数据不足'}
    
    upper = donchian_channel['upper']
    lower = donchian_channel['lower']
    middle = donchian_channel['middle']
    
    # 检查向上突破（做多信号）
    upward_breakout = current_price > upper
    
    # 检查向下突破（做空信号）
    downward_breakout = current_price < lower
    
    result = {
        'breakout': False,
        'direction': 'none',
        'details': f'价格{current_price:.2f}在前20日通道内[{lower:.2f}, {upper:.2f}]',
        'upper': upper,
        'lower': lower,
        'middle': middle
    }
    
    if direction in ['long', 'both'] and upward_breakout:
        result = {
            'breakout': True,
            'direction': 'long',
            'details': f'🚀 向上突破：当前价格{current_price:.2f} > 前20日最高价{upper:.2f}',
            'upper': upper,
            'lower': lower,
            'middle': middle
        }
    elif direction in ['short', 'both'] and downward_breakout:
        result = {
            'breakout': True,
            'direction': 'short', 
            'details': f'📉 向下突破：当前价格{current_price:.2f} < 前20日最低价{lower:.2f}',
            'upper': upper,
            'lower': lower,
            'middle': middle
        }
    
    return result

def get_target_contract_code(base_code, trade_date, ContextInfo=None):
    # 支持"提前切换主力合约"功能：将日期向前推进 G['roll_lead_days'] 天后再按原规则判定
    lead_days = G.get('roll_lead_days', 0)

    effective_date = trade_date
    if isinstance(trade_date, (datetime.datetime, datetime.date)) and lead_days > 0:
        effective_date = trade_date + datetime.timedelta(days=lead_days)

    month = effective_date.month
    year = effective_date.year
    
    # 螺纹钢：1、5、10月
    if base_code.startswith('rb.'):
        if 1 <= month <= 4:
            contract_month = '05'
            contract_year = year
        elif 5 <= month <= 8:
            contract_month = '10'
            contract_year = year
        else:
            contract_month = '01'
            contract_year = year + 1
    # 热卷：1、5、10月
    elif base_code.startswith('hc.'):
        if 1 <= month <= 4:
            contract_month = '05'
            contract_year = year
        elif 5 <= month <= 9:
            contract_month = '10'  # 修正为10月
            contract_year = year
        else:
            contract_month = '01'
            contract_year = year + 1
    else:
        # 其他品种使用标准的01、05、09月
        if 1 <= month <= 4:
            contract_month = '05'
            contract_year = year
        elif 5 <= month <= 8:
            contract_month = '09'
            contract_year = year
        else:  # 9, 10, 11, 12
            contract_month = '01'
            contract_year = year + 1
    
    # 构造完整的合约代码
    # 从基础代码中提取品种和交易所
    parts = base_code.split('.')
    if len(parts) == 2:
        symbol = parts[0].lower()
        exchange = parts[1].upper()
        if ContextInfo is not None and getattr(ContextInfo, 'do_back_test', False):
            if exchange == 'ZF':
                target_contract = f"{symbol.upper()}{contract_month}.{exchange}"
            else:
                target_contract = f"{symbol}{contract_month}.{exchange}"
        else:
            if exchange == 'ZF':
                y = str(int(contract_year) % 10)
                target_contract = f"{symbol.upper()}{y}{contract_month}.{exchange}"
            else:
                yy = str(int(contract_year) % 100).zfill(2)
                target_contract = f"{symbol}{yy}{contract_month}.{exchange}"
        return target_contract
    else:
        G['logger'].warning(f"无法解析基础代码: {base_code}")
        return None


def _normalize_trade_date(trade_date):
    if isinstance(trade_date, datetime.datetime):
        return trade_date.date()
    if isinstance(trade_date, datetime.date):
        return trade_date
    if isinstance(trade_date, str):
        try:
            return datetime.datetime.strptime(str(trade_date)[:8], '%Y%m%d').date()
        except Exception:
            return None
    return None


def parse_contract_delivery_year_month(contract_code, trade_date=None):
    try:
        left = str(contract_code or '').split('.')[0]
        digit_part = ''
        for ch in reversed(left):
            if ch.isdigit():
                digit_part = ch + digit_part
            else:
                break
        if len(digit_part) < 2:
            return None, None

        month = int(digit_part[-2:])
        if month < 1 or month > 12:
            return None, None

        trade_dt = _normalize_trade_date(trade_date)
        trade_year = trade_dt.year if trade_dt else datetime.datetime.now().year

        if len(digit_part) == 2:
            year = trade_year if month >= (trade_dt.month if trade_dt else 1) else trade_year + 1
        elif len(digit_part) == 3:
            decade_base = (trade_year // 10) * 10
            year = decade_base + int(digit_part[0])
            if year < trade_year - 5:
                year += 10
            elif year > trade_year + 5:
                year -= 10
        else:
            yy = int(digit_part[-4:-2])
            century_base = (trade_year // 100) * 100
            year = century_base + yy
            if year < trade_year - 50:
                year += 100
            elif year > trade_year + 50:
                year -= 100

        return int(year), int(month)
    except Exception:
        return None, None


def get_near_delivery_month_info(contract_code, trade_date):
    trade_dt = _normalize_trade_date(trade_date)
    if trade_dt is None:
        return {
            'is_near_month': False,
            'delivery_year': None,
            'delivery_month': None,
            'near_year': None,
            'near_month': None,
            'delivery_ym': None,
            'near_ym': None,
        }

    delivery_year, delivery_month = parse_contract_delivery_year_month(contract_code, trade_dt)
    if delivery_year is None or delivery_month is None:
        return {
            'is_near_month': False,
            'delivery_year': None,
            'delivery_month': None,
            'near_year': None,
            'near_month': None,
            'delivery_ym': None,
            'near_ym': None,
        }

    if delivery_month == 1:
        near_year = delivery_year - 1
        near_month = 12
    else:
        near_year = delivery_year
        near_month = delivery_month - 1

    is_near_month = (trade_dt.year == near_year and trade_dt.month == near_month)
    return {
        'is_near_month': bool(is_near_month),
        'delivery_year': int(delivery_year),
        'delivery_month': int(delivery_month),
        'near_year': int(near_year),
        'near_month': int(near_month),
        'delivery_ym': f"{int(delivery_year):04d}{int(delivery_month):02d}",
        'near_ym': f"{int(near_year):04d}{int(near_month):02d}",
    }


def evaluate_non_near_month_oi_filter(contract_code, market_data_df, trade_date, ContextInfo=None):
    try:
        base_code = get_base_code(contract_code)
    except Exception:
        base_code = None
    near_info = get_near_delivery_month_info(contract_code, trade_date)
    is_near_month = bool(near_info.get('is_near_month', False))

    oi_today = None
    oi_yesterday = None
    oi_declining = False
    if market_data_df is not None and len(market_data_df) >= 2 and 'openInterest' in getattr(market_data_df, 'columns', []):
        try:
            oi_today = float(pd.to_numeric(market_data_df['openInterest'], errors='coerce').iloc[-1])
        except Exception:
            oi_today = None
        try:
            oi_yesterday = float(pd.to_numeric(market_data_df['openInterest'], errors='coerce').iloc[-2])
        except Exception:
            oi_yesterday = None
        if oi_today is not None and oi_yesterday is not None:
            try:
                oi_declining = math.isfinite(oi_today) and math.isfinite(oi_yesterday) and oi_today < oi_yesterday
            except Exception:
                oi_declining = False

    should_block = (not is_near_month) and oi_declining
    return {
        'base_code': base_code,
        'near_contract': None,
        'is_near_month': bool(is_near_month),
        'delivery_ym': near_info.get('delivery_ym'),
        'near_ym': near_info.get('near_ym'),
        'oi_today': oi_today,
        'oi_yesterday': oi_yesterday,
        'oi_declining': bool(oi_declining),
        'should_block': bool(should_block),
    }


# 【新增】设置日志记录器
def setup_logger(log_to_file=True, log_file_path=None):
    """设置日志记录器，可选择是否输出到文件"""
    logger = logging.getLogger('strategy_logger')
    logger.setLevel(logging.INFO)

    # 防止重复添加handler
    if logger.hasHandlers():
        logger.handlers.clear()

    console_formatter = logging.Formatter('%(levelname)s - %(message)s')
    file_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

    # 控制台处理器 (始终添加)
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(console_formatter)
    logger.addHandler(ch)

    # 文件处理器 (根据参数可选添加)
    if log_to_file:
        if log_file_path:
            # 使用绝对路径
            log_filename = log_file_path
            
            # 确保日志目录存在
            log_dir = os.path.dirname(log_filename)
            if log_dir and not os.path.exists(log_dir):
                os.makedirs(log_dir, exist_ok=True)
                print(f"创建日志目录: {log_dir}")
        else:
            # 使用默认文件名（当前目录）
            log_filename = '期货多空排布_盈利加仓版2.log'
        
        fh = logging.FileHandler(log_filename, mode='a', encoding='utf-8')    
        fh.setLevel(logging.INFO)
        fh.setFormatter(file_formatter)
        logger.addHandler(fh)
        print(f"日志文件路径: {os.path.abspath(log_filename)}")

    return logger

def init(ContextInfo):
    """
    策略初始化函数 - 优化版本
    简化了数据获取逻辑，避免复杂的手动数据截取
    """
    # 【新增】日志记录器参数
    G['log_to_file'] = True  # 是否将日志写入文件
    # G['log_file_path'] = r'D:\quantPro\qmt\期货多空排布_优化版2.log'  # 日志文件绝对路径，请根据需要修改
    # G['log_file_path'] = r''  # 日志文件绝对路径，请根据需要修改
    G['log_dir'] = r'E:\Users\hermanna\qmtlog'
    G['run_tag'] = '142'
    G['log_file_path'] = f"{G['log_dir']}\\期货多空排布_盈利加仓版{G['run_tag']}.log"

    G['prefer_api_replay_recovery'] = True
    G['api_replay_lookback_days'] = 90
    G['api_replay_kline_count'] = 260
    G['enable_replay_kline_export'] = True
    G['replay_kline_export_dir'] = os.path.join(str(G.get('log_dir') or '.'), 'replay_kline')

    G['enable_data_persistence'] = bool(ContextInfo.do_back_test)
    G['data_backup_file'] = f"{G['log_dir']}\\strategy_data_backup{G['run_tag']}.pkl"

    G['startup_override'] = {
        'enabled': (not bool(ContextInfo.do_back_test)),
        'positions': {
            # 'a2605.DF': {
            #     'direction': 'long',1
            #     'time': '2026-02-24 14:55:00',
            #     'entry_date': '20260224',
            #     'base_position': {'price': 4633.0, 'volume': 11},
            #     'add_positions': [
            #         {'price': 4678.0, 'volume': 11, 'time': '2026-02-25 14:55:00', 'date': '20260225'},
            #     ]
            # },
            # 'hc2605.SF': {
            #     'direction': 'short',
            #     'time': '2026-02-24 14:55:00',
            #     'entry_date': '20260224',
            #     'base_position': {'price': 3195.1, 'volume': 9},
            # },
            # 'i2605.DF': {
            #     'direction': 'short',
            #     'time': '2026-02-24 14:55:00',
            #     'entry_date': '20260224',
            #     'base_position': {'price': 761.5, 'volume': 1},
            # },
            # 'jm2605.DF': {
            #     'direction': 'short',
            #     'time': '2026-02-24 14:55:00',
            #     'entry_date': '20260224',
            #     'base_position': {'price': 1102.0, 'volume': 4},
            #     'add_positions': [
            #         {'price': 1086.0, 'volume': 4, 'time': '2026-02-26 21:05:00', 'date': '20260226'},
            #     ]
            # },
            # 'sm2605.ZF': {
            #     'direction': 'short',
            #     'time': '2026-02-24 14:55:00',
            #     'entry_date': '20260224',
            #     'base_position': {'price': 5814.0, 'volume': 1},
            # },
        }
    }

    # 【新增】设置日志记录器
    G['logger'] = setup_logger(log_to_file=G['log_to_file'], log_file_path=G['log_file_path'])
    
    G['logger'].info('='*50)
    G['logger'].info('开始初始化期货均线交叉策略...')
    G['logger'].info(f'日志配置: 文件记录={G["log_to_file"]}, 路径={G["log_file_path"] if G["log_to_file"] else "无"}')
    
    # 基本参数设置
    # G['contract_codes'] = [
    #     'SM09.ZF',   # 锰硅
    #     'sa09.ZF',   # 纯碱
    #     'rb2509.SF',   # 螺纹钢期货
    #     'JM2509.DF',   # 焦煤期货
    #     'hc2510.SF',   # 热卷
    #     'j2509.DF',   # 焦炭期货
    #     'sp2509.SF',   # 纸浆期货
    #     'al2508.SF',   # 铝
    # ]  # 期货合约代码数组
    contract_codes_backtest = [
        'LC.GF',
        'sm.ZF',
        'sa.ZF',
        'rb.SF',
        'JM.DF',
        'a.DF',
        'hc.SF',
        'j.DF',
        'cf.ZF',
        'fg.ZF',
        'sh.ZF',
        'si.GF',
        'ru.SF',
        'lh.df',
        'sp.SF',
        'al.SF',
        # 'cu.SF',
        # 'ag.SF',
        # 'sn.SF',
        # 'y.DF'
    ]
    G['contract_codes_backtest'] = list(contract_codes_backtest)
    if ContextInfo.do_back_test:
        G['contract_codes'] = list(contract_codes_backtest)
    else:
        live_all = build_all_domestic_futures_base_codes()
        G['contract_codes_live_all'] = list(live_all)
        merged = []
        seen = set()
        for x in list(contract_codes_backtest) + list(live_all):
            k = str(x)
            if k in seen:
                continue
            seen.add(k)
            merged.append(k)
        G['contract_codes'] = merged
    G['period'] = '1d'  # K线周期，日线
    
    # 主力合约换月提前天数
    G['roll_lead_days'] = 5
    
    # 多合约交易参数
    G['max_concurrent_positions'] = 10  # 最大同时持仓合约数量
    # 移除：G['single_contract_risk_ratio'] - 不再使用，改为每笔交易固定20000元风险
    
    # 均线参数
    G['ma_short'] = 5   # 短期均线周期
    G['ma_mid'] = 10    # 中期均线周期
    G['ma_long'] = 20   # 长期均线周期
    G['ma_extra_long'] = 40  # 超长期均线周期

    
    # 风险控制参数
    G['stop_loss_pct'] = 0.02  # 止损比例 (2%)
    # G['stop_profit_pct'] = 0.9  # 固定止盈比例 - 已删除，不使用固定止盈
    # 【新增】动态风险控制参数
    G['risk_ratio_of_total_assets'] = 0.01
    G['risk_ratio_breakout'] = 0.01
    G['risk_ratio_ma_cross_breakout'] = 0.01
    G['min_risk_per_trade'] = 1000      # 最小单笔交易风险金额（元）- 防止总资产过小时风险过小
    G['max_risk_per_trade'] = 50000000     # 最大单笔交易风险金额（元）- 防止总资产过大时风险过大
    G['streak_risk_multipliers'] = [1.0, 1.0, 1.0, 0.1]
    G['enable_annual_withdrawal_cap'] = bool(G.get('enable_annual_withdrawal_cap', True))
    G['annual_withdrawal_enabled'] = bool(G.get('enable_annual_withdrawal_cap', False))
    G['annual_withdrawal_capital'] = float(G.get('annual_withdrawal_capital', 1000000.0) or 1000000.0)
    
    # 【新增】资金使用限制参数
    G['max_capital_usage_ratio'] = 0.9  # 最大资金使用比例
    
    # 【新增】唐奇安通道参数
    G['donchian_period'] = 20  # 唐奇安通道周期（20日）
    G['min_position_size'] = 1  # 最小交易手数
    G['max_position_size'] = 50000  # 最大交易手数
    
    # 账户和交易参数
    if ContextInfo.do_back_test:
        G['accountid'] = 'testS'
    else:
        G['accountid'] = account if 'account' in globals() else '809207951'  # 账户ID
    G['position_size'] = 1  # 每次开仓手数（将被动态计算覆盖）

    G['run_mode'] = 'backtest' if ContextInfo.do_back_test else 'live'
    G['resume_backtest'] = False
    G['enable_recovery_in_backtest'] = True
    backup_dir = G.get('log_dir', '.')
    G['data_backup_file'] = f"{backup_dir}\\strategy_data_backup_{G['accountid']}_{G['run_mode']}12.pkl"
    
    # 状态变量初始化
    G['positions'] = {}  # 记录持仓状态
    G['signals'] = {}    # 记录信号状态
    G['executed_days'] = set()  # 防止重复执行
    G['open_positions'] = {}  # 记录开仓信息
    G['rollover_opened_today'] = set()  # 换月当天已在新合约开过仓的合约集合（防止重复开仓）
    
    # 加仓策略参数
    G['enable_add_position'] = False  # 是否启用加仓策略
    G['max_add_layers'] = 1  # 最大加仓层数
    G['add_position_threshold'] = 0.01  # 首次加仓阈值（盈利1%）
    G['second_add_position_threshold'] = 0.01  # 第二次加仓阈值（盈利1%）
    G['add_position_min_profit'] = 0.001  # 加仓后移动止损的最小盈利比例（0.1%）
    G['last_add_date'] = {}
    G['enable_donchian_add_position'] = True  # 是否启用独立唐奇安加仓策略
    G['donchian_add_period'] = 20  # 唐奇安加仓使用的通道周期
    G['donchian_add_max_layers'] = 2  # 唐奇安加仓最多加仓次数
    G['donchian_add_volume_multipliers'] = [2.0, 1.0]  # 第一次加2倍原始仓位，第二次加1倍原始仓位
    G['last_donchian_add_date'] = {}
    G['deal_replay_max_records'] = 5000

    G['enable_trade_kline_dump'] = True
    G['use_kline_cache'] = bool(ContextInfo.do_back_test)
    try:
        _local_cache_dir = os.path.join(os.path.dirname(__file__), 'kline_cache')
    except Exception:
        _local_cache_dir = None
    if _local_cache_dir and os.path.isdir(_local_cache_dir):
        G['kline_cache_dir'] = _local_cache_dir
    else:
        G['kline_cache_dir'] = os.path.join(str(G.get('log_dir') or '.'), 'kline_cache')
    G['kline_pre_days'] = 60
    G['kline_pre_days_cache'] = 60
    G['enable_block_kline_dump'] = True
    G['block_kline_pre_days'] = 60
    G['enable_trade_blocked_email'] = True

    G['profit_3bar_stop_enabled'] = True
    G['profit_3bar_stop_pct'] = 0.005
    G['er_open_filter_enabled'] = False
    G['oi_decline_filter_enabled'] = False
    G['down_day_open_filter_enabled'] = False
    G['ma5_angle_reversal_filter_enabled'] = False
    G['ma5_angle_reversal_lookback_days'] = 10
    G['ma5_angle_reversal_angle_threshold_deg'] = 45.0

    G['wick_chop_filter_enabled'] = True
    G['wick_chop_filter_lookback'] = 10
    G['wick_chop_filter_max_days'] = 5
    G['short_entry_enabled'] = False  # 是否允许新开空仓（含换月续开空）

    G['rsi_overheat_reduce_enabled'] = True
    G['rsi_overheat_reduce_threshold'] = 95
    G['rsi_overheat_reduce_period'] = 6
    G['kline_post_days'] = 60
    G['kline_post_days_cache'] = 60
    G['block_kline_post_days'] = 60
    try:
        G['kline_dump_dir'] = os.path.join(G.get('log_dir', '.'), 'trade_kline')
    except Exception:
        G['kline_dump_dir'] = None
    try:
        G['block_kline_dump_dir'] = os.path.join(G.get('log_dir', '.'), 'blocked_kline')
    except Exception:
        G['block_kline_dump_dir'] = None
    G['kline_dump_queue'] = []
    G['block_kline_dump_queue'] = []
    G['trade_id_seq'] = 0
    G['blocked_id_seq'] = 0
    try:
        if G.get('logger'):
            G['logger'].info(f"trade_kline dump_dir={G.get('kline_dump_dir')} post_days={G.get('kline_post_days')}")
            G['logger'].info(f"blocked_kline dump_dir={G.get('block_kline_dump_dir')} post_days={G.get('block_kline_post_days')}")
    except Exception:
        pass
    
    # 移动止损参数
    G['trailing_stop_enabled'] = True  # 开启通用移动止损触发（最大盈利回撤）
    G['atr_2x_mid_stop_enabled'] = True  # 仅开启2ATR止损抬升到当日中间价
    G['max_profit_tracking'] = {}  # 追踪每个合约的最大盈利
    
    # 统计变量
    G['golden_cross_count'] = 0  # 金叉次数统计
    G['death_cross_count'] = 0   # 死叉次数统计
    G['trade_count'] = 0         # 交易次数统计
    G['stop_loss_count'] = 0     # 止损次数统计
    G['stop_profit_count'] = 0   # 止盈次数统计
    G['trailing_stop_count'] = 0 # 移动止损次数统计
    # 交易绩效统计
    G['total_realized_pnl'] = 0.0
    G['gross_profit'] = 0.0
    G['gross_loss_abs'] = 0.0
    G['num_winning_trades'] = 0
    G['num_losing_trades'] = 0
    G['best_trade_pnl'] = 0.0
    G['worst_trade_pnl'] = 0.0
    G['closed_trades'] = 0
    G['sum_holding_days'] = 0.0
    G['equity_curve'] = [0.0]  # 累计实盈亏曲线（仅已平仓）
    G['case_stats'] = {}  # 各开仓case统计

    G['risk_multiplier'] = float(G.get('risk_multiplier', 1.0) or 1.0)
    G['risk_tier'] = int(G.get('risk_tier', 0) or 0)
    G['loss_streak'] = int(G.get('loss_streak', 0) or 0)
    if 'recent_nonzero_results' not in G or not isinstance(G.get('recent_nonzero_results'), list):
        G['recent_nonzero_results'] = []

    G['ai_position_enabled'] = False
    if 'ai_position_log_enabled' not in G:
        G['ai_position_log_enabled'] = True
    if 'ai_position_min_multiplier' not in G:
        G['ai_position_min_multiplier'] = 0.3
    if 'ai_position_max_multiplier' not in G:
        G['ai_position_max_multiplier'] = 2.0
    if 'ai_position_mapping_mode' not in G:
        G['ai_position_mapping_mode'] = 'linear'
    if 'ai_position_linear_center_mult' not in G:
        G['ai_position_linear_center_mult'] = 1.0
    if 'ai_position_linear_target_q25' not in G:
        G['ai_position_linear_target_q25'] = 0.8
    if 'ai_position_linear_target_q75' not in G:
        G['ai_position_linear_target_q75'] = 1.2
    if 'ai_position_low_multiplier' not in G:
        G['ai_position_low_multiplier'] = 0.7
    if 'ai_position_mid_multiplier' not in G:
        G['ai_position_mid_multiplier'] = 1.0
    if 'ai_position_high_multiplier' not in G:
        G['ai_position_high_multiplier'] = 1.2
    if 'ai_position_fallback_multiplier' not in G:
        G['ai_position_fallback_multiplier'] = 1.0
    if 'ai_position_model_path' not in G:
        _env_model_path = os.getenv('QMT_AI_MODEL_PATH') or os.getenv('QMT_AI_POSITION_MODEL_PATH')
        if _env_model_path:
            G['ai_position_model_path'] = str(_env_model_path)
        else:
            _win_dir = r'E:\Users\hermanna\qmtml'
            _win_path = os.path.join(_win_dir, 'ai_position_model.json')
            if os.path.isfile(_win_path):
                G['ai_position_model_path'] = _win_path
            else:
                G['ai_position_model_path'] = os.path.join(_ai_get_base_dir(), 'ai_position_model.json')
    G['ai_position_model_cache'] = None
    
    G['logger'].info('策略参数设置完成:')
    G['logger'].info(f'期货合约: {len(G["contract_codes"])}个合约')
    for i, contract in enumerate(G["contract_codes"], 1):
        G['logger'].info(f'  {i}. {contract}')
    G['logger'].info(f'均线参数: {G["ma_short"]}/{G["ma_mid"]}/{G["ma_long"]}/{G["ma_extra_long"]}日')
    G['logger'].info(f'主力合约切换提前: {G["roll_lead_days"]}天')
    G['logger'].info(f'风险控制: 基础止损{G["stop_loss_pct"]*100}% (无固定止盈，主要依靠移动止损和20日均线止损)')
    G['logger'].info(f'【简化】动态风险控制: 单笔交易风险 = 总资产 × {G["risk_ratio_of_total_assets"]*100}% (基于实时总资产)')
    G['logger'].info(f'【简化】突破风险控制: 唐奇安通道突破时风险 = 总资产 × {G["risk_ratio_breakout"]*100}% (基于实时总资产)')
    G['logger'].info(f'【简化】均线穿越突破风险控制: 均线穿越期间+通道突破时风险 = 总资产 × {G["risk_ratio_ma_cross_breakout"]*100}% (基于实时总资产)')
    G['logger'].info(f'风险金额限制: 最小{G["min_risk_per_trade"]}元, 最大{G["max_risk_per_trade"]}元')
    G['logger'].info(f'【简化】期货资金管理: 基于总资产({G["max_capital_usage_ratio"]*100}%限制)，含浮盈浮亏的实时资产管理')
    G['logger'].info(f'【新增】唐奇安通道({G["donchian_period"]}日): 基于前{G["donchian_period"]}日数据计算通道，当日价格突破时使用高风险模式')
    G['logger'].info(f'  💡 关键修正: 使用前{G["donchian_period"]}日数据（排除当日）计算通道，确保能正确检测突破')
    G['logger'].info(f'多合约参数: 最大持仓数{G["max_concurrent_positions"]}个')
    G['logger'].info(f'允许开空仓: {"启用" if G["short_entry_enabled"] else "禁用"}')
    G['logger'].info(f'移动止损: {"启用" if G["trailing_stop_enabled"] else "禁用"} - 主要盈利保护机制')
    G['logger'].info(f'20日均线止损: 启用 - 多仓价格跌破20日均线平仓，空仓价格涨破20日均线平仓')
    G['logger'].info(f'智能固定止损: 启用 - 结合基础波动(±2%)和近3日价格极值的智能止损')
    G['logger'].info(f'  • 做多: 止损价 = max(基础波动止损价, 近3日最低价)')
    G['logger'].info(f'  • 做空: 止损价 = min(基础波动止损价, 近3日最高价)')
    G['logger'].info(f'【新增】盈利加仓策略: {"启用" if G["enable_add_position"] else "禁用"}')
    G['logger'].info(f'  • 最大加仓层数: {G["max_add_layers"]}层')
    G['logger'].info(f'  • 首次加仓条件: 盈利达到{G["add_position_threshold"]*100}%')
    if int(G.get('max_add_layers', 1) or 1) >= 2:
        G['logger'].info(f'  • 第二次加仓条件: 盈利达到{G["second_add_position_threshold"]*100}%')
    G['logger'].info(f'  • 加仓手数: 初始开仓手数的一半')
    G['logger'].info(f'  • 加仓后移动止损: 不低于加权平均成本价+{G["add_position_min_profit"]*100}%微利')
    G['logger'].info(f'【新增】智能订单执行策略:')
    G['logger'].info(f'  • 回测模式: 使用指定价(prType=11) + 当前收盘价，准确模拟成交')
    G['logger'].info(f'  • 实盘模式: 使用对手价(prType=14) + price=-1，保证成交并接受最小滑点')
    G['logger'].info(f'  • 自动根据ContextInfo.do_back_test状态切换，无需手动调整')
    G['logger'].info(f'【新增】重启数据恢复机制:')
    G['logger'].info(f'  • 自动检测: 策略启动时自动检测智能止损价格、移动止损追踪等关键数据')
    G['logger'].info(f'  • 智能恢复: 重启后自动重建智能止损价格(基于开仓价+当前市场数据)')
    G['logger'].info(f'  • 状态估算: 基于当前盈亏情况估算移动止损历史状态')
    G['logger'].info(f'  • 手动调用: 可通过manual_data_recovery(ContextInfo)手动触发数据恢复')
    G['logger'].info(f'  • 完整性验证: 自动验证恢复后的数据完整性，确保风控有效')
    G['logger'].info(f'  ⚠️ 重要: 重建的智能止损价格可能与原始值有差异，请密切监控')
    G['logger'].info(f'【清晰交易逻辑】:')
    G['logger'].info(f'  情况1: {G["ma_short"]}日穿{G["ma_mid"]}日 → 无突破用常规模式({G["risk_ratio_of_total_assets"]*100}%), 有突破用突破模式({G["risk_ratio_breakout"]*100}%)')
    G['logger'].info(f'  情况2: 10日穿20日或20日穿40日 → 只有突破时才开仓，用保守模式({G["risk_ratio_ma_cross_breakout"]*100}%)')
    G['logger'].info(f'【新增MACD过滤】:')
    G['logger'].info(f'  多头过滤: MACD > 0时允许开多仓，MACD <= 0禁止开多')
    G['logger'].info(f'  空头过滤: MACD < 0时允许开空仓，MACD >= 0禁止开空')
    G['logger'].info(f'【新增RSI过滤】:')
    G['logger'].info(f'  多周期RSI: 6日、12日、24日')
    G['logger'].info(f'  当前状态: 已关闭开仓过滤（仅记录/展示RSI，不限制开仓）')
    G['logger'].info(f'  等价阈值: 开多 RSI<=100；开空 RSI>=0')
    G['logger'].info(f'  趋势确认: 多周期RSI平均值辅助判断市场情绪')
    G['logger'].info(f'【数据持久化配置】:')
    G['logger'].info(f'  启用状态: {"开启" if G["enable_data_persistence"] else "关闭"}')
    if G['enable_data_persistence']:
        G['logger'].info(f'  备份文件: {G["data_backup_file"]}')
        G['logger'].info(f'  功能说明: 自动保存持仓/止损/统计数据，重启后可恢复')
    else:
        G['logger'].info(f'  功能说明: 已禁用文件读写，重启后将使用API同步恢复基础数据')
    G['logger'].info(f'期货资金管理策略: 基于总资产的{G["max_capital_usage_ratio"]*100:.0f}%限制，实时反映账户状态')
    G['logger'].info('期货多合约均线交叉策略初始化完成')
    G['logger'].info('='*50)
    
    if not ContextInfo.do_back_test:
        ContextInfo.run_time("daily_trade", "1nDay", "2019-01-01 14:45:10")
        G['logger'].info('实盘模式：设置定时交易任务成功，每天14:40:20执行')

    # 【新增】加载历史数据，恢复重启前状态
    G['logger'].info('\n' + '='*50)
    G['logger'].info('开始加载历史策略数据...')
    if (not ContextInfo.do_back_test) and bool(G.get('prefer_api_replay_recovery', False)):
        G['logger'].info('实盘模式：启用API回放恢复，跳过本地持久化/成交回报恢复流程')
    elif ContextInfo.do_back_test and not G.get('resume_backtest', False):
        G['logger'].info('回测模式：已关闭恢复（resume_backtest=False）')
    else:
        if load_strategy_data():
            G['logger'].info('✅ 策略数据恢复完成，可继续之前的交易状态')
        else:
            G['logger'].info('📁 无历史数据或加载失败，尝试通过成交回报重建分层持仓')
            if rebuild_positions_from_deals(ContextInfo):
                G['logger'].info('✅ 成交回报重建完成，可继续之前的交易状态')
            else:
                G['logger'].info('📁 成交回报重建失败，将通过API同步机制恢复基础数据')
    G['logger'].info('='*50)

    sync_positions_from_api(ContextInfo)
    if (not ContextInfo.do_back_test) and bool(G.get('prefer_api_replay_recovery', False)):
        replay_rebuild_state_from_api(ContextInfo)

    if not ContextInfo.do_back_test:
        send_startup_notification_email(ContextInfo)

def handlebar(ContextInfo):
    """
    K线处理函数，每根K线运行一次
    在回测中用于执行交易逻辑
    """
    if ContextInfo.do_back_test:
        # 获取当前K线时间
        current_timetag = ContextInfo.get_bar_timetag(ContextInfo.barpos)
        current_dt = datetime.datetime.fromtimestamp(current_timetag/1000)
        day_key = current_dt.strftime('%Y%m%d')
        
        # 每天只执行一次
        if day_key not in G['executed_days']:
            G['executed_days'].add(day_key)
            G['logger'].info(f'\n回测触发交易: {current_dt.strftime("%Y-%m-%d")}')
            daily_trade(ContextInfo)

def sync_positions_from_api(ContextInfo):
    """
    持仓同步机制 - 从QMT API获取真实持仓并同步到内存记录
    解决程序重启后持仓记录丢失导致止损失效的问题
    """
    G['logger'].info(f"\n========== 持仓同步检查 ==========")

    if ContextInfo.do_back_test and not G.get('enable_recovery_in_backtest', False):
        G['logger'].info("回测模式：跳过持仓API同步")
        return

    real_positions = get_trade_detail_data(G['accountid'], 'FUTURE', 'POSITION')
    override_positions = {}
    startup_override = G.get('startup_override')
    if isinstance(startup_override, dict) and bool(startup_override.get('enabled', False)):
        raw_positions = startup_override.get('positions')
        if isinstance(raw_positions, dict):
            for raw_contract, raw_meta in raw_positions.items():
                if not isinstance(raw_meta, dict):
                    continue
                contract_code = str(raw_contract).strip()
                if not contract_code:
                    continue
                direction = str(raw_meta.get('direction', '')).strip().lower()
                if direction not in ('long', 'short'):
                    continue
                base_position = raw_meta.get('base_position')
                if not isinstance(base_position, dict):
                    base_position = None
                raw_total_volume = raw_meta.get('total_volume', raw_meta.get('volume', None))
                try:
                    total_volume = int(raw_total_volume) if raw_total_volume is not None else 0
                except Exception:
                    total_volume = 0

                raw_avg_price = raw_meta.get('avg_price', raw_meta.get('price', raw_meta.get('open_price', None)))
                try:
                    avg_price = float(raw_avg_price) if raw_avg_price is not None else 0.0
                except Exception:
                    avg_price = 0.0

                if base_position is not None:
                    base_price_raw = base_position.get('price', base_position.get('avg_price', None))
                    try:
                        base_price = float(base_price_raw) if base_price_raw is not None else 0.0
                    except Exception:
                        base_price = 0.0
                else:
                    base_price = 0.0

                add_positions = raw_meta.get('add_positions', [])
                if not isinstance(add_positions, list):
                    add_positions = []
                normalized_add_positions = []
                add_total = 0
                add_cost = 0.0
                for ap in add_positions:
                    if not isinstance(ap, dict):
                        continue
                    try:
                        ap_vol = int(ap.get('volume', 0) or 0)
                    except Exception:
                        ap_vol = 0
                    if ap_vol <= 0:
                        continue
                    try:
                        ap_price = float(ap.get('price', avg_price if avg_price > 0 else base_price) or (avg_price if avg_price > 0 else base_price))
                    except Exception:
                        ap_price = avg_price if avg_price > 0 else base_price
                    ap_time = ap.get('time')
                    ap_date = ap.get('date', ap.get('entry_date', None))
                    ap_type = ap.get('type', 'manual')
                    normalized_add_positions.append({'price': ap_price, 'volume': ap_vol, 'time': ap_time, 'date': ap_date, 'type': ap_type})
                    add_total += ap_vol
                    if ap_price > 0:
                        add_cost += float(ap_price) * float(ap_vol)

                donchian_add_positions = raw_meta.get('donchian_add_positions', [])
                if not isinstance(donchian_add_positions, list):
                    donchian_add_positions = []
                normalized_donchian_add_positions = []
                donchian_add_total = 0
                donchian_add_cost = 0.0
                for ap in donchian_add_positions:
                    if not isinstance(ap, dict):
                        continue
                    try:
                        ap_vol = int(ap.get('volume', 0) or 0)
                    except Exception:
                        ap_vol = 0
                    if ap_vol <= 0:
                        continue
                    try:
                        ap_price = float(ap.get('price', avg_price if avg_price > 0 else base_price) or (avg_price if avg_price > 0 else base_price))
                    except Exception:
                        ap_price = avg_price if avg_price > 0 else base_price
                    normalized_donchian_add_positions.append({
                        'price': ap_price,
                        'volume': ap_vol,
                        'time': ap.get('time'),
                        'date': ap.get('date', ap.get('entry_date', None)),
                        'type': ap.get('type', 'donchian_add'),
                        'trailing_stop_price': ap.get('trailing_stop_price'),
                    })
                    donchian_add_total += ap_vol
                    if ap_price > 0:
                        donchian_add_cost += float(ap_price) * float(ap_vol)

                raw_base_volume = raw_meta.get('base_volume', None)
                if raw_base_volume is None and base_position is not None:
                    raw_base_volume = base_position.get('volume', base_position.get('base_volume', None))
                if raw_base_volume is None:
                    base_volume = total_volume - add_total - donchian_add_total if total_volume > 0 else 0
                else:
                    try:
                        base_volume = int(raw_base_volume or 0)
                    except Exception:
                        base_volume = total_volume - add_total - donchian_add_total if total_volume > 0 else 0
                if base_volume < 0:
                    base_volume = 0
                normalized_total_volume = base_volume + add_total + donchian_add_total
                if normalized_total_volume <= 0:
                    continue

                if total_volume <= 0:
                    total_volume = normalized_total_volume

                if avg_price <= 0:
                    if base_position is not None and base_price > 0 and total_volume > 0:
                        total_cost = float(base_price) * float(base_volume) + float(add_cost) + float(donchian_add_cost)
                        avg_price = float(total_cost) / float(total_volume)
                    elif base_price > 0:
                        avg_price = float(base_price)

                raw_initial_price = raw_meta.get('initial_price', None)
                if raw_initial_price is None and base_position is not None:
                    raw_initial_price = base_position.get('initial_price', base_position.get('price', None))
                if raw_initial_price is None:
                    raw_initial_price = avg_price if avg_price > 0 else base_price
                try:
                    initial_price = float(raw_initial_price or 0)
                except Exception:
                    initial_price = avg_price if avg_price > 0 else base_price
                if initial_price <= 0:
                    initial_price = avg_price if avg_price > 0 else base_price

                entry_date = raw_meta.get('entry_date', raw_meta.get('date', None))
                stop_loss_price = None
                raw_smart_stop = raw_meta.get('smart_stop_loss', raw_meta.get('stop_loss_price', None))
                if isinstance(raw_smart_stop, dict):
                    raw_smart_stop = raw_smart_stop.get(direction)
                if raw_smart_stop is not None:
                    try:
                        stop_loss_price = float(raw_smart_stop)
                    except Exception:
                        stop_loss_price = None
                if stop_loss_price is not None and stop_loss_price <= 0:
                    stop_loss_price = None

                max_profit_tracking = raw_meta.get('max_profit_tracking')
                if not isinstance(max_profit_tracking, dict):
                    max_profit_tracking = None

                override_positions[contract_code] = {
                    'direction': direction,
                    'total_volume': total_volume,
                    'avg_price': avg_price,
                    'initial_price': initial_price if initial_price > 0 else avg_price,
                    'base_volume': base_volume,
                    'add_positions': normalized_add_positions,
                    'donchian_add_positions': normalized_donchian_add_positions,
                    'stop_loss_price': stop_loss_price,
                    'max_profit_tracking': max_profit_tracking,
                    'time': raw_meta.get('time'),
                    'entry_date': entry_date,
                    'open_reason': raw_meta.get('open_reason'),
                    'risk_mode': raw_meta.get('risk_mode')
                }
        
    if not real_positions:
        if override_positions:
            G['logger'].warning("⚠️ 未查询到真实持仓返回，使用启动配置覆盖恢复持仓")
            real_positions = []
        else:
            if G.get('open_positions'):
                G['logger'].warning("⚠️ 未查询到真实持仓返回，但内存存在持仓，疑似查询异常，暂不清空")
                return
            G['logger'].info("✅ 无真实持仓，内存记录保持清空状态")
            G['open_positions'].clear()
            return
        
    aggregated_positions = {}
    aggregated_counts = {}

    for position in real_positions:
        try:
            volume = int(getattr(position, 'm_nVolume', 0) or 0)
        except Exception:
            volume = 0
        if volume <= 0:
            continue

        instrument_id = getattr(position, 'm_strInstrumentID', '')
        exchange_id = getattr(position, 'm_strExchangeID', '')
        if not instrument_id or not exchange_id:
            continue

        contract_code = f"{instrument_id}.{exchange_id}"
        direction = 'long' if getattr(position, 'm_nDirection', 0) == 48 else 'short'
        avg_price = float(getattr(position, 'm_dOpenPrice', 0) or 0)

        key = (contract_code, direction)
        aggregated_counts[key] = aggregated_counts.get(key, 0) + 1
        if key not in aggregated_positions:
            aggregated_positions[key] = {
                'volume': 0,
                'cost': 0.0,
                'has_price': False,
                'last_price': avg_price
            }

        aggregated_positions[key]['volume'] += volume
        if avg_price > 0:
            aggregated_positions[key]['cost'] += avg_price * volume
            aggregated_positions[key]['has_price'] = True
            aggregated_positions[key]['last_price'] = avg_price

    if override_positions:
        for contract_code, meta in override_positions.items():
            direction = meta.get('direction')
            if direction not in ('long', 'short'):
                continue
            for other_direction in ('long', 'short'):
                if other_direction != direction:
                    other_key = (contract_code, other_direction)
                    if other_key in aggregated_positions:
                        del aggregated_positions[other_key]
                    if other_key in aggregated_counts:
                        del aggregated_counts[other_key]

            total_volume = int(meta.get('total_volume', 0) or 0)
            if total_volume <= 0:
                continue
            avg_price = float(meta.get('avg_price', 0) or 0)
            key = (contract_code, direction)
            aggregated_counts[key] = 1
            aggregated_positions[key] = {
                'volume': total_volume,
                'cost': (avg_price * total_volume) if avg_price > 0 else 0.0,
                'has_price': bool(avg_price > 0),
                'last_price': avg_price
            }
            G['logger'].warning(f"🧩 启动配置覆盖持仓: {contract_code} {direction} {total_volume}手 @{avg_price:.2f}")

    real_position_contracts = set()

    for (contract_code, direction), agg in aggregated_positions.items():
        volume = int(agg.get('volume', 0))
        if volume <= 0:
            continue

        if agg.get('has_price', False) and float(agg.get('cost', 0.0)) > 0:
            avg_price = float(agg['cost']) / float(volume)
        else:
            avg_price = float(agg.get('last_price', 0) or 0)

        cnt = aggregated_counts.get((contract_code, direction), 1)
        if cnt > 1:
            G['logger'].info(f"真实持仓: {contract_code} {direction} {volume}手, 开仓价: {avg_price:.2f} (合并{cnt}条)")
        else:
            G['logger'].info(f"真实持仓: {contract_code} {direction} {volume}手, 开仓价: {avg_price:.2f}")

        real_position_contracts.add(contract_code)
        override_meta = override_positions.get(contract_code)

        if contract_code in G['open_positions']:
            memory_pos = G['open_positions'][contract_code]
            memory_direction = memory_pos['direction']
            memory_volume = int(memory_pos.get('total_volume', memory_pos.get('volume', 0)))
            memory_price = float(memory_pos.get('avg_price', memory_pos.get('price', 0)))
            memory_initial_price = memory_pos.get('initial_price', memory_price)

            if (direction == memory_direction and
                volume == memory_volume and
                abs(avg_price - memory_price) < 10):
                G['logger'].info(f"✅ {contract_code} 持仓信息一致，保持内存记录")
            else:
                G['logger'].warning(f"⚠️ {contract_code} 持仓信息不一致:")
                G['logger'].warning(f"   真实: {direction} {volume}手 @{avg_price:.2f}")
                G['logger'].warning(f"   内存: {memory_direction} {memory_volume}手 @{memory_price:.2f}")

                pos = memory_pos
                pos['direction'] = direction
                pos['price'] = avg_price
                pos['avg_price'] = avg_price
                if override_meta:
                    pos['initial_price'] = float(override_meta.get('initial_price', memory_initial_price) or avg_price)
                    pos['sync_source'] = 'startup_override'
                else:
                    pos['initial_price'] = memory_initial_price
                    pos['sync_source'] = 'api_recovery'

                if override_meta:
                    add_positions = override_meta.get('add_positions', [])
                    if not isinstance(add_positions, list):
                        add_positions = []
                    donchian_add_positions = override_meta.get('donchian_add_positions', [])
                    if not isinstance(donchian_add_positions, list):
                        donchian_add_positions = []
                    add_total = 0
                    for ap in add_positions:
                        try:
                            add_total += int(ap.get('volume', 0) or 0)
                        except Exception:
                            continue
                    for ap in donchian_add_positions:
                        try:
                            add_total += int(ap.get('volume', 0) or 0)
                        except Exception:
                            continue
                    try:
                        base_vol = int(override_meta.get('base_volume', 0) or 0)
                    except Exception:
                        base_vol = max(int(volume) - int(add_total), 0)
                    if base_vol <= 0:
                        base_vol = max(int(volume) - int(add_total), 0)
                    pos['volume'] = base_vol
                    pos['add_positions'] = add_positions
                    pos['donchian_add_positions'] = donchian_add_positions
                    new_total, _ = _recalculate_position_totals(pos)
                else:
                    mem_total = int(pos.get('total_volume', pos.get('volume', 0)) or 0)
                    diff = int(volume) - int(mem_total)

                    if diff < 0:
                        _reduce_position_volume(pos, -diff)
                    elif diff > 0:
                        add_positions = pos.get('add_positions', [])
                        if not isinstance(add_positions, list):
                            add_positions = []
                        add_positions.append({
                            'price': avg_price,
                            'volume': diff,
                            'time': get_context_datetime(ContextInfo).strftime('%Y-%m-%d %H:%M:%S'),
                            'type': 'sync_external'
                        })
                        pos['add_positions'] = add_positions
                    new_total, _ = _recalculate_position_totals(pos)

                if new_total <= 0:
                    del G['open_positions'][contract_code]
                    continue
                if (not ContextInfo.do_back_test) and bool(G.get('prefer_api_replay_recovery', False)):
                    if 'api_replay_pending_contracts' not in G or not isinstance(G.get('api_replay_pending_contracts'), set):
                        G['api_replay_pending_contracts'] = set()
                    G['api_replay_pending_contracts'].add(contract_code)
        else:
            G['logger'].warning(f"🔄 发现未记录的持仓: {contract_code} {direction} {volume}手")
            G['logger'].warning(f"   可能是程序重启导致记录丢失，正在恢复...")

            if override_meta:
                add_positions = override_meta.get('add_positions', [])
                if not isinstance(add_positions, list):
                    add_positions = []
                donchian_add_positions = override_meta.get('donchian_add_positions', [])
                if not isinstance(donchian_add_positions, list):
                    donchian_add_positions = []
                add_total = 0
                for ap in add_positions:
                    try:
                        add_total += int(ap.get('volume', 0) or 0)
                    except Exception:
                        continue
                for ap in donchian_add_positions:
                    try:
                        add_total += int(ap.get('volume', 0) or 0)
                    except Exception:
                        continue
                try:
                    base_vol = int(override_meta.get('base_volume', 0) or 0)
                except Exception:
                    base_vol = max(int(volume) - int(add_total), 0)
                if base_vol <= 0:
                    base_vol = max(int(volume) - int(add_total), 0)
                total_volume = base_vol + int(add_total)
                init_price = float(override_meta.get('initial_price', avg_price) or avg_price)
                pos_time = override_meta.get('time') or ''
                open_reason = override_meta.get('open_reason')
                risk_mode = override_meta.get('risk_mode')
                new_pos = {
                    'direction': direction,
                    'price': avg_price,
                    'initial_price': init_price,
                    'volume': base_vol,
                    'time': pos_time,
                    'sync_source': 'startup_override',
                    'add_positions': add_positions,
                    'donchian_add_positions': donchian_add_positions,
                    'total_volume': total_volume,
                    'avg_price': avg_price,
                    'add_count': len(add_positions),
                    'donchian_add_count': len(donchian_add_positions)
                }
                entry_date = override_meta.get('entry_date')
                if entry_date:
                    new_pos['entry_date'] = str(entry_date).replace('-', '')[:8]
                if open_reason is not None:
                    new_pos['open_reason'] = open_reason
                if risk_mode is not None:
                    new_pos['risk_mode'] = risk_mode
                G['open_positions'][contract_code] = new_pos
            else:
                G['open_positions'][contract_code] = {
                    'direction': direction,
                    'price': avg_price,
                    'initial_price': avg_price,
                    'volume': volume,
                    'time': get_context_datetime(ContextInfo).strftime('%Y-%m-%d %H:%M:%S'),
                    'sync_source': 'api_recovery',
                    'add_positions': [],
                    'donchian_add_positions': [],
                    'total_volume': volume,
                    'avg_price': avg_price,
                    'add_count': 0,
                    'donchian_add_count': 0
                }
            if (not ContextInfo.do_back_test) and bool(G.get('prefer_api_replay_recovery', False)):
                if 'api_replay_pending_contracts' not in G or not isinstance(G.get('api_replay_pending_contracts'), set):
                    G['api_replay_pending_contracts'] = set()
                G['api_replay_pending_contracts'].add(contract_code)

            current_price_data = ContextInfo.get_market_data_ex(
                fields=['close'],
                stock_code=[contract_code],
                period='1d',
                count=1,
                subscribe=not ContextInfo.do_back_test
            )

            if (not override_meta or override_meta.get('stop_loss_price') is None) and contract_code in current_price_data and not current_price_data[contract_code].empty:
                current_price = current_price_data[contract_code]['close'].iloc[-1]
                entry_price = float(avg_price)
                sl_pct = float(G['stop_loss_pct'])
                if direction == 'long':
                    entry_stop = entry_price * (1 - sl_pct)
                    current_stop = float(current_price) * (1 - sl_pct)
                    basic_stop_loss = max(entry_stop, current_stop)
                else:
                    entry_stop = entry_price * (1 + sl_pct)
                    current_stop = float(current_price) * (1 + sl_pct)
                    basic_stop_loss = min(entry_stop, current_stop)
                stop_loss_key = f'smart_stop_loss_{contract_code}_{direction}'
                G[stop_loss_key] = basic_stop_loss
                G['logger'].info(f"🎯 恢复智能止损价格: {basic_stop_loss:.2f} (基于当前价{current_price:.2f})")

        if override_meta and contract_code in G.get('open_positions', {}):
            pos = G['open_positions'][contract_code]
            pos['direction'] = direction
            pos['price'] = avg_price
            pos['avg_price'] = avg_price
            try:
                pos['initial_price'] = float(override_meta.get('initial_price', pos.get('initial_price', avg_price)) or avg_price)
            except Exception:
                pos['initial_price'] = float(pos.get('initial_price', avg_price) or avg_price)
            override_time = override_meta.get('time')
            if override_time:
                pos['time'] = override_time
            open_reason = override_meta.get('open_reason')
            if open_reason is not None:
                pos['open_reason'] = open_reason
            risk_mode = override_meta.get('risk_mode')
            if risk_mode is not None:
                pos['risk_mode'] = risk_mode
            add_positions = override_meta.get('add_positions', [])
            if not isinstance(add_positions, list):
                add_positions = []
            add_total = 0
            for ap in add_positions:
                try:
                    add_total += int(ap.get('volume', 0) or 0)
                except Exception:
                    continue
            try:
                base_vol = int(override_meta.get('base_volume', 0) or 0)
            except Exception:
                base_vol = 0
            if base_vol <= 0:
                base_vol = max(int(override_meta.get('total_volume', 0) or 0) - int(add_total), 0)
            pos['volume'] = base_vol
            pos['add_positions'] = add_positions
            pos['add_count'] = len(add_positions)
            pos['total_volume'] = base_vol + int(add_total)
            pos['sync_source'] = 'startup_override'
            entry_date = override_meta.get('entry_date')
            if entry_date:
                pos['entry_date'] = str(entry_date).replace('-', '')[:8]
            stop_loss_price = override_meta.get('stop_loss_price')
            if stop_loss_price is not None:
                stop_loss_key = f'smart_stop_loss_{contract_code}_{direction}'
                G[stop_loss_key] = float(stop_loss_price)
                G['logger'].info(f"🎯 启动配置覆盖智能止损价格: {float(stop_loss_price):.2f}")

            tracking = override_meta.get('max_profit_tracking')
            if isinstance(tracking, dict):
                if 'max_profit_tracking' not in G or not isinstance(G.get('max_profit_tracking'), dict):
                    G['max_profit_tracking'] = {}
                G['max_profit_tracking'][contract_code] = dict(tracking)
                G['logger'].info("📈 启动配置覆盖移动止损追踪状态")
        
    for contract_code in list(G['open_positions'].keys()):
        if contract_code not in real_position_contracts:
            G['logger'].warning(f"🗑️ 发现已平仓但未清理的记录: {contract_code}")
            G['logger'].warning(f"   清理内存记录...")
            del G['open_positions'][contract_code]

            for direction in ['long', 'short']:
                stop_loss_key = f'smart_stop_loss_{contract_code}_{direction}'
                if stop_loss_key in G:
                    del G[stop_loss_key]

            if contract_code in G['max_profit_tracking']:
                del G['max_profit_tracking'][contract_code]

    G['logger'].info(f"\n📊 持仓同步结果:")
    G['logger'].info(f"   真实持仓数: {len(real_position_contracts)}")
    G['logger'].info(f"   内存记录数: {len(G['open_positions'])}")

    if G['open_positions']:
        G['logger'].info(f"   当前持仓:")
        for contract, pos in G['open_positions'].items():
            source = pos.get('sync_source', 'normal')
            source_text = '(API恢复)' if source == 'api_recovery' else ''
            total_volume = int(pos.get('total_volume', pos.get('volume', 0)))
            G['logger'].info(f"     {contract}: {pos['direction']} {total_volume}手 @{pos['price']:.2f} {source_text}")
    else:
        G['logger'].info(f"   ✅ 无持仓")

def daily_trade(ContextInfo):
    """
    每日交易函数
    """
    # 【新增】持仓同步机制 - 解决程序重启后持仓记录丢失问题
    sync_positions_from_api(ContextInfo)
    
    G['logger'].info('\n' + '='*50)
    
    # 获取当前时间
    if ContextInfo.do_back_test:
        current_timetag = ContextInfo.get_bar_timetag(ContextInfo.barpos)
        current_dt = datetime.datetime.fromtimestamp(current_timetag/1000)
        current_time = current_dt.strftime("%Y-%m-%d %H:%M:%S")
        current_date_str = current_dt.strftime("%Y%m%d")
        G['logger'].info(f'回测模式 - 当前时间: {current_time}')
    else:
        current_dt = datetime.datetime.now()
        current_time = current_dt.strftime("%Y-%m-%d %H:%M:%S")
        current_date_str = current_dt.strftime("%Y%m%d")
        G['logger'].info(f'实盘模式 - 当前时间: {current_time}')

        if bool(G.get('prefer_api_replay_recovery', False)):
            pending = G.get('api_replay_pending_contracts')
            if isinstance(pending, set) and pending:
                pending_list = list(pending)
                pending.clear()
                replay_rebuild_state_from_api(ContextInfo, only_contracts=pending_list)
    
    # 清空换月当日已开仓集合，确保每日只记录当日数据
    G['rollover_opened_today'].clear()

    # 实盘模式防重复执行
    if not ContextInfo.do_back_test:
        if current_date_str in G['executed_days']:
            G['logger'].info(f"今日({current_date_str})已执行过交易，跳过")
            return
        G['executed_days'].add(current_date_str)
    
    # ========== 【新增】自动数据恢复检测 ==========
    G['logger'].info(f"\n========== 自动数据恢复检测 ==========")
    
    
    account_info, current_total_assets, available_balance, limited_available_balance, position_profit, effective_total_assets, _annual_offset = _refresh_account_and_risk_state(ContextInfo, current_dt=current_dt)
    max_usable_capital = float(effective_total_assets or 0) * float(G.get('max_capital_usage_ratio', 1.0) or 1.0)
    G['logger'].info("✅ 期货账户资金信息:")
    G['logger'].info(f"  【当前】总资产: {current_total_assets:.2f}元 (含浮盈浮亏)")
    if getattr(ContextInfo, 'do_back_test', False) and bool(G.get('annual_withdrawal_enabled', False)):
        G['logger'].info(f"  【年度】锁定交易总资产: {effective_total_assets:.2f}元 (offset={float(_annual_offset or 0):.2f}元)")
    G['logger'].info(f"  【限制】最大可用: {max_usable_capital:.2f}元 (总资产 × {G['max_capital_usage_ratio']*100}%)")
    G['logger'].info(f"  【实际】可用资金: {available_balance:.2f}元")
    G['logger'].info(f"  【最终】限制后资金: {limited_available_balance:.2f}元")
    G['logger'].info(f"  【持仓】盈亏: {position_profit:.2f}元 (实时持仓盈亏)")

    if limited_available_balance < available_balance:
        reduction_amount = available_balance - limited_available_balance
        G['logger'].info(f"  💡 资金管理生效: 限制使用资金 {reduction_amount:.2f}元，基于总资产管理")
    else:
        G['logger'].info("  💡 资金管理未触发: 可用资金在限制范围内")

    _ensure_streak_risk_state()
    try:
        _m = float(G.get('risk_multiplier', 1.0) or 1.0)
    except Exception:
        _m = 1.0
    if _m < 0:
        _m = 0.0
    if _m > 1:
        _m = 1.0

    dynamic_risk_per_trade = float(limited_available_balance) * float(G.get('risk_ratio_of_total_assets', 0.04) or 0.04)
    if dynamic_risk_per_trade < float(G.get('min_risk_per_trade', 0) or 0):
        dynamic_risk_per_trade = float(G.get('min_risk_per_trade', 0) or 0)
    elif dynamic_risk_per_trade > float(G.get('max_risk_per_trade', dynamic_risk_per_trade) or dynamic_risk_per_trade):
        dynamic_risk_per_trade = float(G.get('max_risk_per_trade', dynamic_risk_per_trade) or dynamic_risk_per_trade)

    G['logger'].info(f"  【基准】动态风险金额: {dynamic_risk_per_trade:.2f}元 (限制后资金 × {G['risk_ratio_of_total_assets']*100}%)")
    G['logger'].info(f"  【风控】风险乘数m: {_m:.2f} (loss_streak={int(G.get('loss_streak', 0) or 0)} tier={int(G.get('risk_tier', 0) or 0)})")
    dynamic_risk_per_trade = dynamic_risk_per_trade * _m
    G['logger'].info(f"  【最终】动态风险金额: {dynamic_risk_per_trade:.2f}元 (基准×m)")

    send_startup_notification_email(ContextInfo)

    G['current_risk_per_trade'] = float(dynamic_risk_per_trade)
    G['limited_available_balance'] = float(limited_available_balance)
    G['total_assets'] = float(current_total_assets)
    G['available_balance'] = float(available_balance)
    _update_nav_state(effective_total_assets)
    try:
        _now_dt = get_context_datetime(ContextInfo)
        _bt_date = _now_dt.strftime('%Y%m%d')
        _ts = _now_dt.strftime('%Y-%m-%d %H:%M:%S')
    except Exception:
        _bt_date = None
        _ts = None
    _log_structured('EQUITY_SNAPSHOT', {
        'bt_date': _bt_date,
        'ts': _ts,
        'barpos': int(getattr(ContextInfo, 'barpos', -1)) if ContextInfo is not None else -1,
        'do_back_test': bool(getattr(ContextInfo, 'do_back_test', False)) if ContextInfo is not None else False,
        'total_assets': float(current_total_assets),
        'total_assets_effective': float(effective_total_assets),
        'available_balance': float(available_balance),
        'limited_available_balance': float(limited_available_balance),
        'position_profit': float(position_profit),
        'positions_count': int(len(G.get('open_positions') or {})),
        'risk': _risk_snapshot(ContextInfo)
    })
        
    # ========== 【新增】同步持仓状态 ==========
    # sync_position_status(ContextInfo, current_date_str)
    
    # ========== 【新增】检查并处理非主力合约持仓 ==========
    G['logger'].info(f"\n========== 检查并处理非主力合约持仓 ==========")
    # 创建一个副本进行迭代，因为我们可能会在循环中修改 G['open_positions']
    for contract_code, pos_info in list(G['open_positions'].items()):
        base_code = get_base_code(contract_code)
        if not base_code:
            continue
            
        target_contract_code = get_target_contract_code(base_code, current_dt, ContextInfo=ContextInfo)
        
        if contract_code.upper() != target_contract_code.upper():
            G['logger'].info(f"持仓合约 {contract_code} 非当前主力合约 {target_contract_code}，准备平仓...")
            G['logger'].info(f"  比较结果: {contract_code.upper()} vs {target_contract_code.upper()}")
            
            if pos_info['direction'] == 'long':
                opType = 6  # 平多
                order_remark = '期货多空排布策略-换月平多'
            else:
                opType = 8  # 平空
                order_remark = '期货多空排布策略-换月平空'

            if getattr(ContextInfo, 'do_back_test', False):
                current_market_data = ContextInfo.get_market_data_ex(
                    fields=['close'],
                    stock_code=[contract_code],
                    period='1d',
                    end_time=current_date_str,
                    count=1,
                    dividend_type='front_ratio',
                    subscribe=False
                )
            else:
                current_market_data = ContextInfo.get_market_data_ex(
                    fields=['close'],
                    stock_code=[contract_code],
                    period='1d',
                    count=1,
                    dividend_type='front_ratio',
                    subscribe=True
                )
            current_close_price = current_market_data[contract_code]['close'].iloc[-1] if contract_code in current_market_data and not current_market_data[contract_code].empty else 0

            close_volume = int(pos_info.get('total_volume', pos_info.get('volume', 0)))

            order_id = smart_passorder(
                opType,
                1101,
                G['accountid'],
                contract_code,
                current_close_price,
                close_volume,
                order_remark,
                2,
                '非主力合约换月',
                ContextInfo,
                extra={
                    'action': 'close',
                    'contract': contract_code,
                    'direction': pos_info.get('direction'),
                    'layer': 'all',
                    'reason': '非主力合约换月',
                    'entry_price': float(pos_info.get('avg_price', pos_info.get('price', 0)) or 0),
                    'exit_price': float(current_close_price or 0),
                    'volume': int(close_volume or 0),
                    'case': pos_info.get('open_reason', 'unknown')
                }
            )
            G['logger'].info(f"✅ 平仓指令已发送: {pos_info['direction']} {close_volume}手 {contract_code}")

            if order_id > 0 and getattr(ContextInfo, 'do_back_test', False) and G.get('enable_trade_kline_dump', False):
                _exit_barpos = _get_barpos(ContextInfo)
                _use_cache = bool(G.get('use_kline_cache', False))
                _pre = int((G.get('kline_pre_days_cache') if _use_cache else G.get('kline_pre_days')) or 20)
                _post = int((G.get('kline_post_days_cache') if _use_cache else G.get('kline_post_days')) or 20)
                _base = _base_code_from_contract(contract_code)

                try:
                    _vm = float(get_contract_info(ContextInfo, contract_code).get('VolumeMultiple', 10) or 10)
                except Exception:
                    _vm = None

                _entry_barpos = pos_info.get('entry_barpos')
                try:
                    _entry_barpos_i = int(_entry_barpos)
                except Exception:
                    _entry_barpos_i = None
                if _entry_barpos_i is not None and _entry_barpos_i >= 0:
                    _schedule_trade_kline_dump({
                        'trade_id': pos_info.get('trade_id'),
                        'root_trade_id': pos_info.get('root_trade_id', pos_info.get('trade_id')),
                        'contract_code': contract_code,
                        'base_code': _base,
                        'layer': 'initial',
                        'direction': pos_info.get('direction'),
                        'entry_price': float(pos_info.get('initial_price', pos_info.get('price', 0)) or 0),
                        'exit_price': float(current_close_price or 0),
                        'pos_volume': int(pos_info.get('volume', close_volume) or 0),
                        'volume_multiple': _vm,
                        'close_reason': '非主力合约换月',
                        'sizing_stop_price': pos_info.get('sizing_stop_price'),
                        'sizing_stop_source': pos_info.get('sizing_stop_source'),
                        'entry_signal_source': pos_info.get('entry_signal_source'),
                        'pending_breakout_created_date': pos_info.get('pending_breakout_created_date'),
                        'pending_breakout_wait_days': pos_info.get('pending_breakout_wait_days'),
                        'entry_date': pos_info.get('entry_date'),
                        'exit_date': current_date_str,
                        'entry_barpos': _entry_barpos_i,
                        'exit_barpos': _exit_barpos,
                        'pre_days': _pre,
                        'post_days': _post,
                        'layer_trailing_stop_trace': pos_info.get('layer_trailing_stop_trace')
                    })

                _aps = pos_info.get('add_positions') or []
                if isinstance(_aps, list):
                    for _i, _ap in enumerate(_aps):
                        try:
                            _ap_entry_barpos = int(_ap.get('barpos'))
                        except Exception:
                            _ap_entry_barpos = None
                        if _ap_entry_barpos is None or _ap_entry_barpos < 0:
                            continue
                        _schedule_trade_kline_dump({
                            'trade_id': _ap.get('trade_id'),
                            'root_trade_id': pos_info.get('root_trade_id', pos_info.get('trade_id')),
                            'contract_code': contract_code,
                            'base_code': _base,
                            'layer': f"add_{_i+1}",
                            'direction': pos_info.get('direction'),
                            'entry_price': float(_ap.get('price', 0) or 0),
                            'exit_price': float(current_close_price or 0),
                            'pos_volume': int(_ap.get('volume', 0) or 0),
                            'volume_multiple': _vm,
                            'close_reason': '非主力合约换月',
                            'sizing_stop_price': _ap.get('sizing_stop_price', _ap.get('trailing_stop_price')),
                            'sizing_stop_source': _ap.get('sizing_stop_source') or 'add_layer_stop',
                            'entry_signal_source': pos_info.get('entry_signal_source'),
                            'pending_breakout_created_date': pos_info.get('pending_breakout_created_date'),
                            'pending_breakout_wait_days': pos_info.get('pending_breakout_wait_days'),
                            'entry_date': _ap.get('date'),
                            'exit_date': current_date_str,
                            'entry_barpos': _ap_entry_barpos,
                            'exit_barpos': _exit_barpos,
                            'pre_days': _pre,
                            'post_days': _post,
                            'layer_trailing_stop_trace': pos_info.get('layer_trailing_stop_trace')
                        })

                _don_aps = _get_donchian_add_positions(pos_info, create=False)
                if isinstance(_don_aps, list):
                    for _i, _ap in enumerate(_don_aps):
                        try:
                            _ap_entry_barpos = int(_ap.get('barpos'))
                        except Exception:
                            _ap_entry_barpos = None
                        if _ap_entry_barpos is None or _ap_entry_barpos < 0:
                            continue
                        _schedule_trade_kline_dump({
                            'trade_id': _ap.get('trade_id'),
                            'root_trade_id': pos_info.get('root_trade_id', pos_info.get('trade_id')),
                            'contract_code': contract_code,
                            'base_code': _base,
                            'layer': str(_ap.get('type') or f"donchian_add_{_i+1}"),
                            'direction': pos_info.get('direction'),
                            'entry_price': float(_ap.get('price', 0) or 0),
                            'exit_price': float(current_close_price or 0),
                            'pos_volume': int(_ap.get('volume', 0) or 0),
                            'volume_multiple': _vm,
                            'close_reason': '非主力合约换月',
                            'sizing_stop_price': _ap.get('trailing_stop_price'),
                            'sizing_stop_source': 'donchian_add_stop',
                            'entry_signal_source': pos_info.get('entry_signal_source'),
                            'pending_breakout_created_date': pos_info.get('pending_breakout_created_date'),
                            'pending_breakout_wait_days': pos_info.get('pending_breakout_wait_days'),
                            'entry_date': _ap.get('date'),
                            'exit_date': current_date_str,
                            'entry_barpos': _ap_entry_barpos,
                            'exit_barpos': _exit_barpos,
                            'pre_days': _pre,
                            'post_days': _post,
                            'layer_trailing_stop_trace': pos_info.get('layer_trailing_stop_trace')
                        })

            if contract_code in G['open_positions']:
                old_pos_snapshot = pos_info.copy()
                del G['open_positions'][contract_code]
            else:
                old_pos_snapshot = pos_info.copy()
            if contract_code in G['max_profit_tracking']:
                del G['max_profit_tracking'][contract_code]

            long_key = f'smart_stop_loss_{contract_code}_long'
            short_key = f'smart_stop_loss_{contract_code}_short'
            if long_key in G:
                del G[long_key]
            if short_key in G:
                del G[short_key]

            attempt_reopen_after_rollover(
                ContextInfo=ContextInfo,
                target_contract_code=target_contract_code,
                old_direction=old_pos_snapshot['direction'],
                old_risk_mode=old_pos_snapshot.get('risk_mode', 'normal'),
                old_root_trade_id=old_pos_snapshot.get('root_trade_id', old_pos_snapshot.get('trade_id')),
                old_entry_signal_source=old_pos_snapshot.get('entry_signal_source'),
                old_pending_breakout_created_date=old_pos_snapshot.get('pending_breakout_created_date'),
                old_pending_breakout_wait_days=old_pos_snapshot.get('pending_breakout_wait_days'),
                account_info=account_info,
                current_dt=current_dt,
                current_date_str=current_date_str
            )

    # 统计当前持仓数量
    current_positions_count = len(G['open_positions'])
    G['logger'].info(f"当前持仓合约数量: {current_positions_count}/{G['max_concurrent_positions']}")
    
    # ========== 遍历所有合约进行交易 ==========
    # G['contract_codes'] 现在是基础合约代码列表
    for base_contract_code in G['contract_codes']:
        # 根据当前日期动态生成目标合约代码
        target_contract_code = get_target_contract_code(base_contract_code, current_dt, ContextInfo=ContextInfo)
        
        G['logger'].info(f"\n{'='*60}")
        G['logger'].info(f"处理合约: {base_contract_code} -> 目标合约: {target_contract_code}")
        G['logger'].info(f"{'='*60}")
        
        # 处理单个合约（若换月续开当日已开过仓，则跳过以防重复）
        if target_contract_code in G.get('rollover_opened_today', set()):
            G['logger'].info(f"⏭️ 跳过当日已换月开仓的合约: {target_contract_code}")
        else:
            try:
                account_info, _, _, _, _, _, _ = _refresh_account_and_risk_state(ContextInfo, current_dt=current_dt)
            except Exception:
                pass
            process_single_contract(ContextInfo, target_contract_code, current_date_str, account_info)
    
    if G['open_positions']:
        G['logger'].info("\n========== 持仓风控保底巡检 ==========")
        for _cc, _pos in list(G['open_positions'].items()):
            if ContextInfo.do_back_test:
                _md = ContextInfo.get_market_data_ex(fields=['close'], stock_code=[_cc], period=G['period'], end_time=current_date_str, count=1, dividend_type='front_ratio', subscribe=False)
            else:
                _md = ContextInfo.get_market_data_ex(fields=['close'], stock_code=[_cc], period=G['period'], count=1, dividend_type='front_ratio', subscribe=True)
            if _cc in _md and not _md[_cc].empty:
                _last = _md[_cc]['close'].iloc[-1]
                check_stop_conditions(ContextInfo, _last, _cc)
    
    # ========== 多合约策略运行统计 ==========
    G['logger'].info(f"\n========== 多合约策略运行统计 ==========")
    G['logger'].info(f"交易合约列表: {G['contract_codes']}")
    G['logger'].info(f"最大同时持仓数: {G['max_concurrent_positions']}")
    G['logger'].info(f"当前持仓数: {len(G['open_positions'])}")
    G['logger'].info(f"当前总资产: {current_total_assets:.2f}元 (含浮盈浮亏)")
    G['logger'].info(f"总资产基础: {G['total_assets']:.2f}元 (总资产含浮盈浮亏)")
    G['logger'].info(f"实际可用资金: {available_balance:.2f}元")
    G['logger'].info(f"限制后资金: {G['limited_available_balance']:.2f}元 ({G['max_capital_usage_ratio']*100:.0f}%限制)")
    if G['total_assets'] > 0:
        G['logger'].info(f"资金利用率: {(G['limited_available_balance']/G['total_assets'])*100:.1f}% (目标{G['max_capital_usage_ratio']*100:.0f}%)")
    else:
        G['logger'].info(f"资金利用率: 无法计算 (总资产为0)")
    G['logger'].info(f"动态风险金额: {G['current_risk_per_trade']:.2f}元")
    G['logger'].info(f"信号统计:")
    G['logger'].info(f"  金叉信号次数: {G['golden_cross_count']}")
    G['logger'].info(f"  死叉信号次数: {G['death_cross_count']}")
    G['logger'].info(f"  总交易执行次数: {G['trade_count']}")
    G['logger'].info(f"风控统计:")
    G['logger'].info(f"  20日均线止损次数: {G.get('ma_stop_count', 0)}")
    G['logger'].info(f"  移动止损次数: {G['trailing_stop_count']}")
    G['logger'].info(f"  智能固定止损次数: {G.get('smart_stop_count', 0)}")
    G['logger'].info(f"  基础固定止损次数: {G['stop_loss_count']}")
    G['logger'].info(f"  固定止盈次数: {G['stop_profit_count']}")
    
    # 止损方式统计分析
    total_stops = G.get('ma_stop_count', 0) + G['trailing_stop_count'] + G.get('smart_stop_count', 0) + G['stop_loss_count'] + G['stop_profit_count']
    
    # 初始化统计变量
    ma_stop_rate = 0
    trailing_stop_rate = 0
    smart_stop_rate = 0
    fixed_stop_rate = 0
    fixed_profit_rate = 0
    
    if total_stops > 0:
        ma_stop_rate = (G.get('ma_stop_count', 0) / total_stops) * 100
        trailing_stop_rate = (G['trailing_stop_count'] / total_stops) * 100
        smart_stop_rate = (G.get('smart_stop_count', 0) / total_stops) * 100
        fixed_stop_rate = (G['stop_loss_count'] / total_stops) * 100
        fixed_profit_rate = (G['stop_profit_count'] / total_stops) * 100
        G['logger'].info(f"止损方式占比:")
        G['logger'].info(f"  20日均线止损: {ma_stop_rate:.1f}% (趋势跟踪)")
        G['logger'].info(f"  移动止损: {trailing_stop_rate:.1f}% (利润保护)")
        G['logger'].info(f"  智能固定止损: {smart_stop_rate:.1f}% (技术分析)")
        G['logger'].info(f"  基础固定止损: {fixed_stop_rate:.1f}% (风险控制)")
        G['logger'].info(f"  固定止盈: {fixed_profit_rate:.1f}% (极端保护)")
    
    # 多合约持仓状态显示
    if G['open_positions']:
        G['logger'].info(f"当前所有持仓状态:")
        for contract, pos_info in G['open_positions'].items():
            direction_cn = "多头" if pos_info['direction'] == 'long' else "空头"
            total_vol = pos_info.get('total_volume', pos_info.get('volume', 0))
            base_vol = pos_info.get('volume', 0)
            G['logger'].info(f"  {contract}: {direction_cn} volume={base_vol}手, total_volume={total_vol}手")
            G['logger'].info(f"    开仓价: {pos_info['price']:.2f}, 开仓时间: {pos_info['time']}")
            if 'open_reason' in pos_info:
                try:
                    _om = float(pos_info.get('open_macd') if pos_info.get('open_macd') is not None else 0.0)
                except Exception:
                    _om = 0.0
                try:
                    _or = float(pos_info.get('open_rsi') if pos_info.get('open_rsi') is not None else 0.0)
                except Exception:
                    _or = 0.0
                G['logger'].info(
                    f"    开仓原因: {pos_info.get('open_reason')} | 风险模式: {pos_info.get('risk_mode','')} | 开仓MACD: {_om:.4f} | 开仓RSI: {_or:.2f}"
                )
            
            if contract in G['max_profit_tracking']:
                tracking = G['max_profit_tracking'][contract]
                G['logger'].info(f"    最大盈利记录: {tracking.get('max_profit_pct', 0.0)*100:.2f}%")
                G['logger'].info(f"    移动止损价: {tracking.get('trailing_stop_price', 0.0):.2f}")
                G['logger'].info(f"    最后更新: {tracking.get('last_update_time', '')}")
    else:
        G['logger'].info(f"当前持仓状态: 无持仓")
    
    # 【简化】期货资金管理效果分析
    G['logger'].info(f"\n========== 期货资金管理分析 ==========")
    if G['total_assets'] > 0:
        capital_efficiency = (G['limited_available_balance'] / G['total_assets']) * 100
        preserved_capital = G['total_assets'] - G['limited_available_balance']
        preserved_percentage = (preserved_capital / G['total_assets']) * 100
        G['logger'].info(f"基于总资产的管理效果:")
        G['logger'].info(f"  总资产基础: {G['total_assets']:.2f}元 (含浮盈浮亏)")
        G['logger'].info(f"  资金利用率: {capital_efficiency:.1f}% (目标: {G['max_capital_usage_ratio']*100:.0f}%)")
        G['logger'].info(f"  保留缓冲资金: {preserved_capital:.2f}元 ({preserved_percentage:.1f}%)")
        G['logger'].info(f"  持仓盈亏: {position_profit:.2f}元 (实时持仓盈亏)")
    else:
        G['logger'].info(f"基于总资产的管理效果:")
        G['logger'].info(f"  资金利用率: 无法计算 (总资产为0)")
        G['logger'].info(f"  保留缓冲资金: 无法计算 (总资产为0)")
    
    G['logger'].info(f"  【最终】可交易资金: {G['limited_available_balance']:.2f}元")
    
    if G['total_assets'] > 0:
        if capital_efficiency <= G['max_capital_usage_ratio'] * 100:
            G['logger'].info(f"✅ 资金管理目标达成：基于总资产的保守管理")
        else:
            G['logger'].warning(f"⚠️  资金利用率超过目标，但已应用限制保护")
    else:
        G['logger'].warning(f"⚠️  无法评估资金管理目标（稳定资金基础为0）")
    
    G['logger'].info('='*50)

    G['logger'].info(f"📊 止损方式分析: 预计各止损方式占比")
    G['logger'].info(f"  20日均线止损: {ma_stop_rate:.1f}%")
    G['logger'].info(f"  移动止损: {trailing_stop_rate:.1f}%")
    G['logger'].info(f"  智能固定止损: {smart_stop_rate:.1f}%")
    G['logger'].info(f"  基础固定止损: {fixed_stop_rate:.1f}%")
    G['logger'].info(f"  固定止盈: {fixed_profit_rate:.1f}%")
    
    # 【新增】每日交易结束时保存策略数据
    G['logger'].info(f"\n========== 每日数据保存 ==========")
    if G.get('enable_data_persistence', False):
        if save_strategy_data():
            G['logger'].info(f"✅ 当日交易数据已保存，策略可安全重启")
        else:
            G['logger'].warning(f"⚠️ 数据保存失败，重启可能丢失部分数据，但不影响当前交易")
            G['logger'].info(f"💡 提示：可检查磁盘空间和文件权限，或手动备份重要数据")
    else:
        G['logger'].info(f"📁 数据持久化已禁用，未保存策略数据")
        G['logger'].info(f"💡 提示：如需启用，请设置 G['enable_data_persistence'] = True")

    closed_trades = G.get('closed_trades', 0)
    num_wins = G.get('num_winning_trades', 0)
    num_losses = G.get('num_losing_trades', 0)
    total_pnl = G.get('total_realized_pnl', 0.0)
    gross_profit = G.get('gross_profit', 0.0)
    gross_loss_abs = G.get('gross_loss_abs', 0.0)
    win_rate = (num_wins / closed_trades * 100) if closed_trades > 0 else 0.0
    if gross_loss_abs > 0:
        profit_factor = gross_profit / gross_loss_abs
    else:
        profit_factor = float('inf') if gross_profit > 0 else 0.0
    avg_trade = (total_pnl / closed_trades) if closed_trades > 0 else 0.0
    avg_holding_days = (G.get('sum_holding_days', 0.0) / closed_trades) if closed_trades > 0 else 0.0
    best_trade = G.get('best_trade_pnl', 0.0)
    worst_trade = G.get('worst_trade_pnl', 0.0)

    G['logger'].info("\n========== 策略总体统计（阶段性） ==========")
    G['logger'].info(f"累计平仓笔数: {closed_trades}")
    G['logger'].info(f"胜/负笔数: {num_wins}/{num_losses} | 胜率: {win_rate:.1f}%")
    G['logger'].info(f"累计收益(实盈亏): {total_pnl:.2f} | 盈亏比(ProfitFactor): {profit_factor:.2f}")
    G['logger'].info(f"平均每笔: {avg_trade:.2f} | 最佳/最差: {best_trade:.2f}/{worst_trade:.2f}")
    G['logger'].info(f"平均持有天数: {avg_holding_days:.1f}d | 曲线最后净值(累计PnL): {G['equity_curve'][-1] if G.get('equity_curve') else 0.0:.2f}")

    if G.get('case_stats'):
        G['logger'].info("分Case表现：")
        for case_key, cs in G['case_stats'].items():
            wins = cs['wins']
            trades = cs['trades']
            losses = cs['losses']
            wr = (wins / trades * 100) if trades > 0 else 0.0
            pf = (cs['gross_profit'] / cs['gross_loss_abs']) if cs['gross_loss_abs'] > 0 else float('inf')
            G['logger'].info(f"  {case_key}: 次数={trades}, 胜率={wr:.1f}%, PF={pf:.2f}, 盈利={cs['gross_profit']:.2f}, 亏损={cs['gross_loss_abs']:.2f}")

    if ContextInfo.do_back_test and G.get('enable_trade_kline_dump', False):
        _dump_trade_kline_if_ready(ContextInfo, current_date_str)
    if ContextInfo.do_back_test and G.get('enable_block_kline_dump', False):
        _dump_block_kline_if_ready(ContextInfo, current_date_str)

def process_single_contract(ContextInfo, contract_code, current_date, account_info):
    """
    处理单个合约的交易逻辑
    """
    G['logger'].info(f"开始处理合约: {contract_code}")
    try:
        _dt_now = get_context_datetime(ContextInfo)
    except Exception:
        _dt_now = None
    try:
        account_info, _, _, _, _, _, _ = _refresh_account_and_risk_state(ContextInfo, current_dt=_dt_now)
    except Exception:
        pass
    
    G['logger'].info("========== 获取期货行情数据 ==========")

    required_count = G['ma_extra_long'] + 10

    if ContextInfo.do_back_test:
        market_data = ContextInfo.get_market_data_ex(
            fields=['close', 'open', 'high', 'low', 'volume', 'openInterest'],
            stock_code=[contract_code],
            period=G['period'],
            end_time=current_date,
            count=required_count,
            dividend_type='front_ratio',
            subscribe=False
        )
        G['logger'].info(f"回测模式：获取到{current_date}截止的数据")
    else:
        market_data = ContextInfo.get_market_data_ex(
            fields=['close', 'open', 'high', 'low', 'volume', 'openInterest'],
            stock_code=[contract_code],
            period=G['period'],
            count=required_count,
            dividend_type='front_ratio',
            subscribe=True
        )
        G['logger'].info("实盘模式：获取最新数据")

    if contract_code not in market_data or market_data[contract_code].empty:
        G['logger'].warning(f"❌ 未获取到{contract_code}的有效数据，跳过此合约")
        return

    data = market_data[contract_code]
    close_prices = data['close']

    G['logger'].info("✅ 数据获取成功！")
    G['logger'].info(f"数据长度: {len(data)}")
    G['logger'].info(f"时间范围: {data.index[0]} 到 {data.index[-1]}")
    G['logger'].info(f"需要最小数据量: {required_count}, 实际数据量: {len(data)}")

    if len(data) < required_count:
        G['logger'].warning(f"❌ 数据量不足：需要{required_count}条，实际{len(data)}条，跳过此合约")
        return
    
    current_price = close_prices.iloc[-1]
    G['logger'].info(f"当前价格: {current_price:.2f}")

    # ========== 获取合约信息和计算交易手数（移动到ma_cross_filter定义之后） ==========
    
    # ========== 检查止损止盈条件 ==========
    G['logger'].info(f"========== 检查止损止盈条件 ==========")
    _pre_pos = G.get('open_positions', {}).get(contract_code) if isinstance(G.get('open_positions'), dict) else None
    if _pre_pos:
        try:
            _pre_total_vol = int(_pre_pos.get('total_volume', _pre_pos.get('volume', 0)) or 0)
        except Exception:
            _pre_total_vol = 0
    else:
        _pre_total_vol = 0
    check_stop_conditions(ContextInfo, current_price, contract_code)
    _post_pos = G.get('open_positions', {}).get(contract_code) if isinstance(G.get('open_positions'), dict) else None
    if _post_pos:
        try:
            _post_total_vol = int(_post_pos.get('total_volume', _post_pos.get('volume', 0)) or 0)
        except Exception:
            _post_total_vol = 0
    else:
        _post_total_vol = 0
    if _pre_total_vol > 0 and (_post_pos is None or _post_total_vol < _pre_total_vol):
        try:
            account_info, _, _, _, _, _, _ = _refresh_account_and_risk_state(ContextInfo, current_dt=_dt_now)
        except Exception:
            pass
    
    # ========== 计算均线 ==========
    ma_short = close_prices.rolling(window=G['ma_short']).mean()
    ma_mid = close_prices.rolling(window=G['ma_mid']).mean()
    ma_long = close_prices.rolling(window=G['ma_long']).mean()
    ma_extra_long = close_prices.rolling(window=G['ma_extra_long']).mean()
    
    # ========== 计算MACD指标（用于过滤） ==========
    G['logger'].info(f"\n========== MACD指标分析 [{current_date}|{contract_code}] ==========")
    macd_data = calculate_macd(close_prices)

    if macd_data:
        current_macd = macd_data['current_macd']
        current_dif = macd_data['current_dif']
        current_dea = macd_data['current_dea']

        G['logger'].info(f"[{current_date}|{contract_code}] MACD指标:")
        G['logger'].info(f"[{current_date}|{contract_code}]   DIF线: {current_dif:.4f}")
        G['logger'].info(f"[{current_date}|{contract_code}]   DEA线: {current_dea:.4f}")
        G['logger'].info(f"[{current_date}|{contract_code}]   MACD柱状图: {current_macd:.4f}")
        G['logger'].info(f"[{current_date}|{contract_code}]   MACD过滤状态: {'看多(>0)' if current_macd > 0 else '看空(<0)' if current_macd < 0 else '中性(=0)'}")

        dif_series = macd_data['macd_line']
        dea_series = macd_data['signal_line']
        if len(dif_series) >= 2 and len(dea_series) >= 2:
            y_dif, t_dif = dif_series.iloc[-2], dif_series.iloc[-1]
            y_dea, t_dea = dea_series.iloc[-2], dea_series.iloc[-1]
            macd_golden_cross = (y_dif < y_dea) and (t_dif > t_dea)
            macd_death_cross = (y_dif > y_dea) and (t_dif < t_dea)
        else:
            macd_golden_cross = False
            macd_death_cross = False

        G['logger'].info(f"[{current_date}|{contract_code}]   MACD交叉: 金叉={macd_golden_cross}, 死叉={macd_death_cross}")
    else:
        G['logger'].warning(f"[{current_date}|{contract_code}] ❌ 数据不足，无法计算MACD指标，跳过MACD过滤")
        current_macd = 0
        macd_golden_cross = False
        macd_death_cross = False
    
    # ========== 计算RSI指标 ==========
    G['logger'].info(f"\n========== RSI指标分析 [{current_date}|{contract_code}] ==========")
    rsi_results = calculate_multi_period_rsi(close_prices, periods=[6, 12, 24])
    
    if rsi_results:
        G['logger'].info(f"[{current_date}|{contract_code}] 多周期RSI指标:")
        G['logger'].info(f"[{current_date}|{contract_code}]   RSI(6): {rsi_results['rsi_6']:.2f}")
        G['logger'].info(f"[{current_date}|{contract_code}]   RSI(12): {rsi_results['rsi_12']:.2f}")
        G['logger'].info(f"[{current_date}|{contract_code}]   RSI(24): {rsi_results['rsi_24']:.2f}")
        G['logger'].info(f"[{current_date}|{contract_code}]   RSI平均: {rsi_results['rsi_avg']:.2f}")
        G['logger'].info(f"[{current_date}|{contract_code}]   RSI趋势: {rsi_results['rsi_trend']}")
        
        # 使用6日RSI作为主要过滤指标（短期信号）
        current_rsi = rsi_results['rsi_6']
        rsi_12 = rsi_results['rsi_12']
        rsi_24 = rsi_results['rsi_24']
        
        # RSI过滤逻辑（基于6日RSI）
        if current_rsi > 80:
            G['logger'].info(f"[{current_date}|{contract_code}]   📈 RSI(6) > 80 (超买)，禁止开多仓")
        elif current_rsi < 10:
            G['logger'].info(f"[{current_date}|{contract_code}]   📉 RSI(6) < 10 (超卖)，禁止开空仓")
        elif current_rsi > 70:
            G['logger'].info(f"[{current_date}|{contract_code}]   ⚠️  RSI(6) > 70 (偏高)，开多仓需谨慎")
        elif current_rsi < 30:
            G['logger'].info(f"[{current_date}|{contract_code}]   ⚠️  RSI(6) < 30 (偏低)，开空仓需谨慎")
        else:
            G['logger'].info(f"[{current_date}|{contract_code}]   ✅ RSI(6)在正常范围内 (10-80)")
            
        # 多周期RSI一致性检查
        if rsi_results['rsi_trend'] == 'bullish':
            G['logger'].info(f"[{current_date}|{contract_code}]   📈 多周期RSI趋势: 偏多（平均RSI < 40）")
        elif rsi_results['rsi_trend'] == 'bearish':
            G['logger'].info(f"[{current_date}|{contract_code}]   📉 多周期RSI趋势: 偏空（平均RSI > 60）")
        else:
            G['logger'].info(f"[{current_date}|{contract_code}]   ⚖️ 多周期RSI趋势: 中性")
    else:
        G['logger'].warning(f"[{current_date}|{contract_code}] ❌ 数据不足，无法计算RSI指标，跳过RSI过滤")
        current_rsi = 50  # 默认中性值
    
    # 获取昨日和今日的均线值
    if len(ma_short) < 2:
        G['logger'].warning("数据不足，无法获取昨日数据进行对比，跳过此合约")
        return
    
    yesterday_short = ma_short.iloc[-2]
    yesterday_mid = ma_mid.iloc[-2]
    yesterday_long = ma_long.iloc[-2]
    yesterday_extra_long = ma_extra_long.iloc[-2]
    
    today_short = ma_short.iloc[-1]
    today_mid = ma_mid.iloc[-1]
    today_long = ma_long.iloc[-1]
    today_extra_long = ma_extra_long.iloc[-1]
    
    # ========== 打印均线状态 ==========
    G['logger'].info(f"\n========== 均线状态 ==========")
    G['logger'].info(f"当前价格: {current_price:.2f}")
    G['logger'].info(f"昨日均线: {G['ma_short']}日={yesterday_short:.2f}, {G['ma_mid']}日={yesterday_mid:.2f}, {G['ma_long']}日={yesterday_long:.2f}, {G['ma_extra_long']}日={yesterday_extra_long:.2f}")
    G['logger'].info(f"今日均线: {G['ma_short']}日={today_short:.2f}, {G['ma_mid']}日={today_mid:.2f}, {G['ma_long']}日={today_long:.2f}, {G['ma_extra_long']}日={today_extra_long:.2f}")
    
    # ========== 检查交叉信号 ==========
    G['logger'].info(f"\n========== 交叉信号检测 ==========")
    
    # 金叉条件
    golden_cross_5_10 = yesterday_short < yesterday_mid and today_short > today_mid
    golden_cross_10_20 = yesterday_mid < yesterday_long and today_mid > today_long
    golden_cross_20_40 = yesterday_long < yesterday_extra_long and today_long > today_extra_long
    
    G['logger'].info(f"{G['ma_short']}日上穿{G['ma_mid']}日: {golden_cross_5_10}")
    G['logger'].info(f"10日上穿20日: {golden_cross_10_20}")
    G['logger'].info(f"20日上穿40日: {golden_cross_20_40}")
    
    # 死叉条件
    death_cross_5_10 = yesterday_short > yesterday_mid and today_short < today_mid
    death_cross_10_20 = yesterday_mid > yesterday_long and today_mid < today_long
    death_cross_20_40 = yesterday_long > yesterday_extra_long and today_long < today_extra_long
    
    G['logger'].info(f"{G['ma_short']}日下穿{G['ma_mid']}日: {death_cross_5_10}")
    G['logger'].info(f"10日下穿20日: {death_cross_10_20}")
    G['logger'].info(f"20日下穿40日: {death_cross_20_40}")
    
    # ========== 增加均线排布确认条件 ==========
    G['logger'].info(f"\n========== 均线排布检测 ==========")
    
    # 多头排布：短>{G['ma_mid']}> {G['ma_long']}> {G['ma_extra_long']}（由短到长递减排列）
    is_bullish_alignment = (today_short > today_mid > today_long > today_extra_long)
    
    # 空头排布：短<{G['ma_mid']}< {G['ma_long']}< {G['ma_extra_long']}（由短到长递增排列）
    is_bearish_alignment = (today_short < today_mid < today_long < today_extra_long)
    
    G['logger'].info(f"多头排布 ({G['ma_short']}>{G['ma_mid']}>{G['ma_long']}>{G['ma_extra_long']}): {is_bullish_alignment}")
    G['logger'].info(f"空头排布 ({G['ma_short']}<{G['ma_mid']}<{G['ma_long']}<{G['ma_extra_long']}): {is_bearish_alignment}")
    G['logger'].info(f"当前排列: {today_short:.2f} - {today_mid:.2f} - {today_long:.2f} - {today_extra_long:.2f}")
    
    # ========== 【关键】计算均线穿越过滤器（在交叉信号检测之后） ==========
    G['logger'].info(f"\n========== 均线穿越过滤器计算 ==========")
    
    # 检查交叉信号
    has_golden_cross = golden_cross_5_10 or golden_cross_10_20 or golden_cross_20_40
    has_death_cross = death_cross_5_10 or death_cross_10_20 or death_cross_20_40
    
    # 10日均线穿过20日均线和20日均线穿过40日均线的过滤条件
    ma_10_20_cross_filter = golden_cross_10_20 or death_cross_10_20
    ma_20_40_cross_filter = golden_cross_20_40 or death_cross_20_40
    
    # 综合过滤条件：10日穿20日 或 20日穿40日 时都不开仓
    ma_cross_filter = ma_10_20_cross_filter or ma_20_40_cross_filter
    
    G['logger'].info(f"基础金叉信号: {has_golden_cross}")
    G['logger'].info(f"基础死叉信号: {has_death_cross}")
    G['logger'].info(f"10日穿20日均线过滤器: {ma_10_20_cross_filter}")
    G['logger'].info(f"20日穿40日均线过滤器: {ma_20_40_cross_filter}")
    G['logger'].info(f"综合均线穿越过滤器: {ma_cross_filter}")
    
    contract_info = get_contract_info(ContextInfo, contract_code)
    if not contract_info:
        G['logger'].warning(f"⚠️ 合约 {contract_code} 无有效合约信息，跳过交易处理")
        return
    dynamic_position_size = calculate_position_size(current_price, contract_info, account_info, data, None, set_stop_loss=False)
    contract_position_size = dynamic_position_size
    G['logger'].info(f"动态计算交易手数: {contract_position_size}手")

    
    # ========== 执行交易逻辑 ==========
    execute_trading_logic(ContextInfo, current_price, contract_code, contract_position_size,
                          golden_cross_5_10, golden_cross_10_20, golden_cross_20_40,
                          death_cross_5_10, death_cross_10_20, death_cross_20_40,
                          is_bullish_alignment, is_bearish_alignment,
                          has_golden_cross, has_death_cross, ma_cross_filter,
                          ma_10_20_cross_filter, ma_20_40_cross_filter, macd_golden_cross, macd_death_cross, current_macd, current_rsi, current_date,
                          data)

def execute_trading_logic(ContextInfo, current_price, contract_code, position_size,
                         golden_cross_5_10, golden_cross_10_20, golden_cross_20_40,
                         death_cross_5_10, death_cross_10_20, death_cross_20_40,
                         is_bullish_alignment, is_bearish_alignment,
                         has_golden_cross, has_death_cross, ma_cross_filter,
                         ma_10_20_cross_filter, ma_20_40_cross_filter, macd_golden_cross, macd_death_cross, current_macd, current_rsi, current_date,
                         market_data_df):
    """执行交易逻辑 - 多合约优化版：使用每日检查止损止盈方式"""
    
    # ========== 获取当前持仓 ==========
    # 【优化】不再需要重复API查询，直接使用G中已同步好的持仓状态
    G['logger'].info(f"\n========== 持仓检查 ==========")
    has_current_contract_position = contract_code in G['open_positions']
    
    if has_current_contract_position:
        pos_info = G['open_positions'][contract_code]
        direction_cn = "多头" if pos_info['direction'] == 'long' else "空头"
        total_volume = int(pos_info.get('total_volume', pos_info.get('volume', 0)))
        G['logger'].info(f"合约 {contract_code} 当前有 {direction_cn} 持仓 {total_volume}手")
    else:
        G['logger'].info(f"合约 {contract_code} 当前无持仓")

    # ========== 多合约持仓数量检查 ==========
    current_positions_count = len(G['open_positions'])
    can_open_new_position = current_positions_count < G['max_concurrent_positions']
    
    G['logger'].info(f"\n========== 多合约风险控制 ==========")
    G['logger'].info(f"当前持仓合约数: {current_positions_count}")
    G['logger'].info(f"最大允许持仓数: {G['max_concurrent_positions']}")
    G['logger'].info(f"可以开新仓: {can_open_new_position}")
    G['logger'].info(f"当前合约 {contract_code} 是否有持仓: {has_current_contract_position}")
    
    # ========== 【重构】清晰的交易信号判断逻辑 ==========
    G['logger'].info(f"\n========== 交易信号分析（重构版） ==========")
    
    # 基础条件：多空排布
    G['logger'].info(f"多头排布: {is_bullish_alignment}")
    G['logger'].info(f"空头排布: {is_bearish_alignment}")
    
    has_breakout = False
    
    # 均线穿越情况
    G['logger'].info(f"{G['ma_short']}日穿{G['ma_mid']}日: 金叉={golden_cross_5_10}, 死叉={death_cross_5_10}")
    G['logger'].info(f"10日穿20日: 金叉={golden_cross_10_20}, 死叉={death_cross_10_20}")
    G['logger'].info(f"20日穿40日: 金叉={golden_cross_20_40}, 死叉={death_cross_20_40}")
    
    # MACD过滤条件
    G['logger'].info(f"[{current_date}|{contract_code}] MACD柱状图: {current_macd:.4f}")
    macd_allow_long = current_macd > 0
    macd_allow_short = current_macd < 0
    G['logger'].info(f"[{current_date}|{contract_code}] MACD允许开多: {macd_allow_long} (MACD>0)")
    G['logger'].info(f"[{current_date}|{contract_code}] MACD允许开空: {macd_allow_short} (MACD<0)")

    # RSI过滤条件
    G['logger'].info(f"[{current_date}|{contract_code}] RSI: {current_rsi:.2f}")
    rsi_allow_long = current_rsi <= 100  # RSI开仓过滤当前关闭：占位条件（恒为True）
    rsi_allow_short = current_rsi >= 0  # RSI开仓过滤当前关闭：占位条件（恒为True）
    G['logger'].info(f"[{current_date}|{contract_code}] RSI允许开多仓: {rsi_allow_long} (RSI过滤已关闭)")
    G['logger'].info(f"[{current_date}|{contract_code}] RSI允许开空仓: {rsi_allow_short} (RSI过滤已关闭)")
    
    # ========== 【重构】按照清晰逻辑重新判断交易信号 ==========
    trading_signal = None  # 交易信号：'long_case1a', 'long_case1b', 'long_case2', 'short_case1a', 'short_case1b', 'short_case2', None
    risk_mode = None       # 风险模式：'normal', 'breakout', 'ma_cross_breakout'

    G['logger'].info(f"📊 风险模式：统一常规模式 ({G['risk_ratio_of_total_assets']*100:.0f}%)")
    
    G['logger'].info(f"\n========== 清晰交易逻辑判断 [{current_date}|{contract_code}] ==========")
    
    # 【情况1：短期均线穿过中期均线】
    if (golden_cross_5_10 or death_cross_5_10) and not (golden_cross_10_20 or death_cross_10_20 or golden_cross_20_40 or death_cross_20_40):
        G['logger'].info(f"[{current_date}|{contract_code}] >>> 情况1：{G['ma_short']}日穿过{G['ma_mid']}日（无其他均线穿越）")
        
        # 做多方向：短期上穿中期 + 多头排布 + MACD过滤 + RSI过滤（不再受通道方向限制）
        if golden_cross_5_10 and is_bullish_alignment:
            if not macd_allow_long:
                G['logger'].info(f"[{current_date}|{contract_code}]   ❌ {G['ma_short']}日上穿{G['ma_mid']}日 + 多头排布，但MACD <= 0，禁止开多仓")
            elif not rsi_allow_long:
                G['logger'].info(f"[{current_date}|{contract_code}]   ❌ {G['ma_short']}日上穿{G['ma_mid']}日 + 多头排布，但RSI > 80 ({current_rsi:.2f})，避免超买，禁止开多仓")
            else:
                trading_signal = 'long_case1a'
                risk_mode = 'normal'
                G['logger'].info(f"[{current_date}|{contract_code}]   ✅ {G['ma_short']}日上穿{G['ma_mid']}日 + 多头排布 + RSI允许 → 开多仓")
        
        # 做空方向：短期下穿中期 + 空头排布 + MACD过滤 + RSI过滤（不再受通道方向限制）
        elif death_cross_5_10 and is_bearish_alignment:
            if not macd_allow_short:
                G['logger'].info(f"[{current_date}|{contract_code}]   ❌ {G['ma_short']}日下穿{G['ma_mid']}日 + 空头排布，但MACD >= 0，禁止开空仓")
            elif not rsi_allow_short:
                G['logger'].info(f"[{current_date}|{contract_code}]   ❌ {G['ma_short']}日下穿{G['ma_mid']}日 + 空头排布，但RSI < 10 ({current_rsi:.2f})，避免超卖，禁止开空仓")
            else:
                trading_signal = 'short_case1a'
                risk_mode = 'normal'
                G['logger'].info(f"[{current_date}|{contract_code}]   ✅ {G['ma_short']}日下穿{G['ma_mid']}日 + 空头排布 + RSI允许 → 开空仓")
        else:
            G['logger'].info(f"  ❌ {G['ma_short']}日穿{G['ma_mid']}日但无对应的多空排布，不开仓")
    
    # 【情况2：10日穿过20日 或 20日穿过40日】
    elif golden_cross_10_20 or death_cross_10_20 or golden_cross_20_40 or death_cross_20_40:
        G['logger'].info(f"[{current_date}|{contract_code}] >>> 情况2：10日穿过20日 或 20日穿过40日")
        
        # 做多方向：(10日上穿20日 或 20日上穿40日) + 多头排布 + MACD过滤 + RSI过滤（不再要求通道突破）
        if (golden_cross_10_20 or golden_cross_20_40) and is_bullish_alignment:
            if not macd_allow_long:
                G['logger'].info(f"[{current_date}|{contract_code}]   ❌ 长期均线上穿 + 多头排布，但MACD <= 0，禁止开多仓")
            elif not rsi_allow_long:
                G['logger'].info(f"[{current_date}|{contract_code}]   ❌ 长期均线上穿 + 多头排布，但RSI > 80 ({current_rsi:.2f})，避免超买，禁止开多仓")
            else:
                trading_signal = 'long_case2'
                risk_mode = 'normal'
                G['logger'].info(f"[{current_date}|{contract_code}]   ✅ 长期均线上穿 + 多头排布 + MACD/RSI允许 → 开多仓")
        
        # 做空方向：(10日下穿20日 或 20日下穿40日) + 空头排布 + MACD过滤 + RSI过滤（不再要求通道突破）
        elif (death_cross_10_20 or death_cross_20_40) and is_bearish_alignment:
            if not macd_allow_short:
                G['logger'].info(f"  ❌ 长期均线下穿 + 空头排布，但MACD >= 0，禁止开空仓")
            elif not rsi_allow_short:
                G['logger'].info(f"  ❌ 长期均线下穿 + 空头排布，但RSI < 10 ({current_rsi:.2f})，避免超卖，禁止开空仓")
            else:
                trading_signal = 'short_case2'
                risk_mode = 'normal'
                G['logger'].info(f"  ✅ 长期均线下穿 + 空头排布 + MACD/RSI允许 → 开空仓")
        else:
            G['logger'].info("  ❌ 长期均线穿越但无对应的多空排布，不开仓")
    
    else:
        G['logger'].info(">>> 无明确的均线穿越信号，继续评估MACD交叉+排布的机会")

        # 情况3：MACD金叉/死叉 + 排布（附带MACD与RSI过滤）
        if macd_golden_cross and is_bullish_alignment:
            if not (current_macd > 0):
                G['logger'].info(f"[{current_date}|{contract_code}]   ❌ MACD金叉 + 多头排布，但MACD <= 0（不满足开多过滤）")
            elif not rsi_allow_long:
                G['logger'].info(f"[{current_date}|{contract_code}]   ❌ MACD金叉 + 多头排布，但RSI > 80 ({current_rsi:.2f})，避免超买，禁止开多仓")
            else:
                trading_signal = 'long_case3'
                risk_mode = 'normal'
                G['logger'].info(f"[{current_date}|{contract_code}]   ✅ 情况3：MACD金叉 + 多头排布 + MACD>0 + RSI允许 → 开多候选")
        elif macd_death_cross and is_bearish_alignment:
            if not (current_macd < 0):
                G['logger'].info(f"[{current_date}|{contract_code}]   ❌ MACD死叉 + 空头排布，但MACD >= 0（不满足开空过滤）")
            elif not rsi_allow_short:
                G['logger'].info(f"[{current_date}|{contract_code}]   ❌ MACD死叉 + 空头排布，但RSI < 10 ({current_rsi:.2f})，避免超卖，禁止开空仓")
            else:
                trading_signal = 'short_case3'
                risk_mode = 'normal'
                G['logger'].info(f"[{current_date}|{contract_code}]   ✅ 情况3：MACD死叉 + 空头排布 + MACD<0 + RSI允许 → 开空候选")
        else:
            G['logger'].info(">>> MACD交叉+排布未满足，保持观望")
    
    
    
    if trading_signal and bool(G.get('er_open_filter_enabled', False)):
        _er_filter = evaluate_er_open_filter(market_data_df['close'])
        G['logger'].info(
            f"[{current_date}|{contract_code}] ER开仓过滤: "
            f"ER5={_er_filter.get('er_5')} ER10={_er_filter.get('er_10')} ER20={_er_filter.get('er_20')} "
            f"threshold=0.2 failed={_er_filter.get('failed_periods')}"
        )
        if _er_filter.get('should_block'):
            _dir_txt = 'long' if str(trading_signal).startswith('long') else 'short'
            G['logger'].info(f"[{current_date}|{contract_code}]   ❌ 开仓过滤：ER5/10/20 其中之一小于0.2，禁止开仓")
            try:
                if getattr(ContextInfo, 'do_back_test', False) and G.get('enable_block_kline_dump', False):
                    _schedule_block_kline_dump({
                        'contract_code': contract_code,
                        'direction': _dir_txt,
                        'tag': 'blocked_er_low',
                        'reason': (
                            f"er_low failed={_er_filter.get('failed_periods')} "
                            f"er5={_er_filter.get('er_5')} er10={_er_filter.get('er_10')} er20={_er_filter.get('er_20')}"
                        ),
                        'date': str(current_date),
                        'trigger_barpos': _get_barpos(ContextInfo),
                        'pre_days': int(G.get('block_kline_pre_days', G.get('kline_pre_days', 20)) or 20),
                        'post_days': int(G.get('block_kline_post_days', G.get('kline_post_days', 20)) or 20),
                    })
            except Exception:
                pass
            trading_signal = None

    if trading_signal and bool(G.get('oi_decline_filter_enabled', False)):
        _oi_filter = evaluate_non_near_month_oi_filter(contract_code, market_data_df, current_date, ContextInfo)
        G['logger'].info(
            f"[{current_date}|{contract_code}] 近月/持仓量过滤: near={_oi_filter.get('is_near_month')} "
            f"delivery_ym={_oi_filter.get('delivery_ym')} near_ym={_oi_filter.get('near_ym')} oi_today={_oi_filter.get('oi_today')} "
            f"oi_yesterday={_oi_filter.get('oi_yesterday')} oi_declining={_oi_filter.get('oi_declining')}"
        )
        if _oi_filter.get('should_block'):
            _dir_txt = 'long' if str(trading_signal).startswith('long') else 'short'
            G['logger'].info(f"[{current_date}|{contract_code}]   ❌ 开仓过滤：当前不是近月合约，且当日持仓量较昨日下降，禁止开仓")
            try:
                if getattr(ContextInfo, 'do_back_test', False) and G.get('enable_block_kline_dump', False):
                    _schedule_block_kline_dump({
                        'contract_code': contract_code,
                        'direction': _dir_txt,
                        'tag': 'blocked_non_near_oi_down',
                        'reason': f"non_near_oi_down delivery_ym={_oi_filter.get('delivery_ym')} near_ym={_oi_filter.get('near_ym')} oi_today={_oi_filter.get('oi_today')} oi_yesterday={_oi_filter.get('oi_yesterday')}",
                        'date': str(current_date),
                        'trigger_barpos': _get_barpos(ContextInfo),
                        'pre_days': int(G.get('block_kline_pre_days', G.get('kline_pre_days', 20)) or 20),
                        'post_days': int(G.get('block_kline_post_days', G.get('kline_post_days', 20)) or 20),
                    })
            except Exception:
                pass
            trading_signal = None

    if trading_signal and trading_signal.startswith('long') and bool(G.get('down_day_open_filter_enabled', False)):
        try:
            today_open = float(market_data_df['open'].iloc[-1])
            today_close = float(market_data_df['close'].iloc[-1])
            if today_close < today_open:
                G['logger'].info(f"[{current_date}|{contract_code}]   ❌ 多头开仓过滤：当日下跌(close {today_close:.2f} < open {today_open:.2f})，禁止开多")
                if getattr(ContextInfo, 'do_back_test', False) and G.get('enable_block_kline_dump', False):
                    _schedule_block_kline_dump({
                        'contract_code': contract_code,
                        'direction': 'long',
                        'tag': 'blocked_down_day',
                        'reason': f"down_day close<open ({today_close:.2f}<{today_open:.2f})",
                        'date': str(current_date),
                        'trigger_barpos': _get_barpos(ContextInfo),
                        'pre_days': int(G.get('block_kline_pre_days', G.get('kline_pre_days', 20)) or 20),
                        'post_days': int(G.get('block_kline_post_days', G.get('kline_post_days', 20)) or 20),
                    })
                trading_signal = None
        except Exception:
            pass

    if trading_signal and trading_signal.startswith('long'):
        try:
            ma5_is_max, ma5_latest, ma5_recent = is_latest_ma_extreme(
                market_data_df,
                period=G.get('ma_short', 5),
                compare_days=3,
                mode='max'
            )
        except Exception:
            ma5_is_max, ma5_latest, ma5_recent = False, None, []
        G['logger'].info(f"[{current_date}|{contract_code}] 多头MA5两日回落过滤: latest={ma5_latest} recent={ma5_recent} pass={ma5_is_max}")
        if not ma5_is_max:
            G['logger'].info(f"[{current_date}|{contract_code}]   ❌ 多头开仓过滤：MA5连续两天下降，禁止开多")
            try:
                if getattr(ContextInfo, 'do_back_test', False) and G.get('enable_block_kline_dump', False):
                    _latest_txt = f"{float(ma5_latest):.6f}" if ma5_latest is not None else "None"
                    _recent_txt = ",".join([f"{float(x):.6f}" for x in ma5_recent]) if ma5_recent else "None"
                    _schedule_block_kline_dump({
                        'contract_code': contract_code,
                        'direction': 'long',
                        'tag': 'blocked_ma5_not_3day_max',
                        'reason': f"ma5_not_3day_max latest={_latest_txt} recent3={_recent_txt}",
                        'date': str(current_date),
                        'trigger_barpos': _get_barpos(ContextInfo),
                        'pre_days': int(G.get('block_kline_pre_days', G.get('kline_pre_days', 20)) or 20),
                        'post_days': int(G.get('block_kline_post_days', G.get('kline_post_days', 20)) or 20),
                    })
            except Exception:
                pass
            trading_signal = None

    if trading_signal and bool(G.get('ma5_angle_reversal_filter_enabled', True)):
        try:
            _ma5_angle_filter = evaluate_ma5_angle_reversal_filter(
                market_data_df,
                period=G.get('ma_short', 5),
                lookback_days=G.get('ma5_angle_reversal_lookback_days', 10),
                angle_threshold_deg=G.get('ma5_angle_reversal_angle_threshold_deg', 30.0)
            )
        except Exception:
            _ma5_angle_filter = {'should_block': False, 'recent_angles': [], 'matched_prev_angle': None, 'matched_curr_angle': None}
        G['logger'].info(
            f"[{current_date}|{contract_code}] MA5角度反转过滤: recent_angles={_ma5_angle_filter.get('recent_angles')} "
            f"matched=({_ma5_angle_filter.get('matched_prev_angle')},{_ma5_angle_filter.get('matched_curr_angle')}) "
            f"threshold={G.get('ma5_angle_reversal_angle_threshold_deg', 30.0)} block={_ma5_angle_filter.get('should_block')}"
        )
        if _ma5_angle_filter.get('should_block'):
            _dir_txt = 'long' if str(trading_signal).startswith('long') else 'short'
            G['logger'].info(f"[{current_date}|{contract_code}]   ❌ 开仓过滤：最近10天出现MA5角度急跌后急拉，禁止开仓")
            try:
                if getattr(ContextInfo, 'do_back_test', False) and G.get('enable_block_kline_dump', False):
                    _angles_txt = ",".join([f"{float(x):.3f}" for x in (_ma5_angle_filter.get('recent_angles') or [])]) or "None"
                    _schedule_block_kline_dump({
                        'contract_code': contract_code,
                        'direction': _dir_txt,
                        'tag': 'blocked_ma5_angle_reversal',
                        'reason': (
                            f"ma5_angle_reversal prev={_ma5_angle_filter.get('matched_prev_angle')} "
                            f"curr={_ma5_angle_filter.get('matched_curr_angle')} recent_angles={_angles_txt}"
                        ),
                        'date': str(current_date),
                        'trigger_barpos': _get_barpos(ContextInfo),
                        'pre_days': int(G.get('block_kline_pre_days', G.get('kline_pre_days', 20)) or 20),
                        'post_days': int(G.get('block_kline_post_days', G.get('kline_post_days', 20)) or 20),
                    })
            except Exception:
                pass
            trading_signal = None

    if trading_signal and trading_signal.startswith('short') and not bool(G.get('short_entry_enabled', True)):
        G['logger'].info(f"[{current_date}|{contract_code}]   ❌ 空头开仓总开关关闭，禁止开空")
        try:
            if getattr(ContextInfo, 'do_back_test', False) and G.get('enable_block_kline_dump', False):
                _schedule_block_kline_dump({
                    'contract_code': contract_code,
                    'direction': 'short',
                    'tag': 'blocked_short_disabled',
                    'reason': 'short_entry_disabled',
                    'date': str(current_date),
                    'trigger_barpos': _get_barpos(ContextInfo),
                    'pre_days': int(G.get('block_kline_pre_days', G.get('kline_pre_days', 20)) or 20),
                    'post_days': int(G.get('block_kline_post_days', G.get('kline_post_days', 20)) or 20),
                })
        except Exception:
            pass
        trading_signal = None

    if trading_signal and trading_signal.startswith('short'):
        try:
            ma5_is_min, ma5_latest, ma5_recent = is_latest_ma_extreme(
                market_data_df,
                period=G.get('ma_short', 5),
                compare_days=3,
                mode='min'
            )
        except Exception:
            ma5_is_min, ma5_latest, ma5_recent = False, None, []
        G['logger'].info(f"[{current_date}|{contract_code}] 空头MA5两日反弹过滤: latest={ma5_latest} recent={ma5_recent} pass={ma5_is_min}")
        if not ma5_is_min:
            G['logger'].info(f"[{current_date}|{contract_code}]   ❌ 空头开仓过滤：MA5连续两天上升，禁止开空")
            try:
                if getattr(ContextInfo, 'do_back_test', False) and G.get('enable_block_kline_dump', False):
                    _latest_txt = f"{float(ma5_latest):.6f}" if ma5_latest is not None else "None"
                    _recent_txt = ",".join([f"{float(x):.6f}" for x in ma5_recent]) if ma5_recent else "None"
                    _schedule_block_kline_dump({
                        'contract_code': contract_code,
                        'direction': 'short',
                        'tag': 'blocked_ma5_not_3day_min',
                        'reason': f"ma5_not_3day_min latest={_latest_txt} recent3={_recent_txt}",
                        'date': str(current_date),
                        'trigger_barpos': _get_barpos(ContextInfo),
                        'pre_days': int(G.get('block_kline_pre_days', G.get('kline_pre_days', 20)) or 20),
                        'post_days': int(G.get('block_kline_post_days', G.get('kline_post_days', 20)) or 20),
                    })
            except Exception:
                pass
            trading_signal = None

    if trading_signal and trading_signal.startswith('short'):
        try:
            ma5_slope = get_ma_slope_direction(market_data_df, period=G.get('ma_short', 5))
        except Exception:
            ma5_slope = 0.0
        G['logger'].info(f"[{current_date}|{contract_code}] 5日均线斜率: {ma5_slope:.6f}")
        if ma5_slope > 0:
            G['logger'].info(f"[{current_date}|{contract_code}]   ❌ 空头开仓过滤：5日均线斜率朝上 ({ma5_slope:.6f} > 0)，禁止开空")
            try:
                if getattr(ContextInfo, 'do_back_test', False) and G.get('enable_block_kline_dump', False):
                    _schedule_block_kline_dump({
                        'contract_code': contract_code,
                        'direction': 'short',
                        'tag': 'blocked_ma5_slope_up',
                        'reason': f"ma5_slope_up slope={ma5_slope:.6f}",
                        'date': str(current_date),
                        'trigger_barpos': _get_barpos(ContextInfo),
                        'pre_days': int(G.get('block_kline_pre_days', G.get('kline_pre_days', 20)) or 20),
                        'post_days': int(G.get('block_kline_post_days', G.get('kline_post_days', 20)) or 20),
                    })
            except Exception:
                pass
            trading_signal = None

    if trading_signal and bool(G.get('wick_chop_filter_enabled', False)):
        _dir = 'long' if str(trading_signal).startswith('long') else 'short'
        if is_simple_ma_trend(market_data_df, _dir, G.get('ma_short', 5), G.get('ma_mid', 10), G.get('ma_long', 20), G.get('ma_extra_long', 40), 3):
            G['logger'].info(f"[{current_date}|{contract_code}]   ✅ 影线过滤豁免：均线趋势成立 ({_dir})")
        else:
            ok, cnt, n = wick_chop_filter_ok(
                market_data_df,
                lookback=G.get('wick_chop_filter_lookback', 10),
                max_days=G.get('wick_chop_filter_max_days', 4)
            )
            if not ok:
                try:
                    lookback_i = int(G.get('wick_chop_filter_lookback', 10) or 10)
                except Exception:
                    lookback_i = 10
                try:
                    max_days_i = int(G.get('wick_chop_filter_max_days', 4) or 4)
                except Exception:
                    max_days_i = 4
                G['logger'].info(f"[{current_date}|{contract_code}]   ❌ 影线震荡过滤：近{n}根(目标{lookback_i})K线中影线>实体天数={cnt} > {max_days_i}，禁止开仓")
                try:
                    if getattr(ContextInfo, 'do_back_test', False) and G.get('enable_block_kline_dump', False):
                        _direction = 'long' if str(trading_signal).startswith('long') else 'short'
                        _schedule_block_kline_dump({
                            'contract_code': contract_code,
                            'direction': _direction,
                            'tag': 'blocked_wick_chop',
                            'reason': f"wick_chop count={int(cnt)} > {int(max_days_i)} lookback={int(lookback_i)}",
                            'date': str(current_date),
                            'trigger_barpos': _get_barpos(ContextInfo),
                            'pre_days': int(G.get('block_kline_pre_days', G.get('kline_pre_days', 20)) or 20),
                            'post_days': int(G.get('block_kline_post_days', G.get('kline_post_days', 20)) or 20),
                        })
                except Exception:
                    pass
                trading_signal = None

    if trading_signal and trading_signal.startswith('long'):
            signal_type = {
                'long_case1a': f"🔥 {G['ma_short']}日穿{G['ma_mid']}日做多（常规）",
                'long_case2': "⚡ 长期均线穿越做多（突破）",
                'long_case3': "✨ MACD金叉做多（排布确认）"
            }.get(trading_signal, "未知做多信号")
            
            if has_current_contract_position:
                G['logger'].info(f"🚫 {signal_type}触发，但当前合约 {contract_code} 已有持仓，跳过开仓")
            elif not can_open_new_position:
                G['logger'].warning(f"🚫 {signal_type}触发，但已达到最大持仓数限制 ({current_positions_count}/{G['max_concurrent_positions']})，跳过开仓")
            else:
                contract_info = get_contract_info(ContextInfo, contract_code)
                if not contract_info:
                    G['logger'].warning(f"⚠️ 合约 {contract_code} 无有效合约信息，跳过开仓")
                    return
                try:
                    _dt_now = get_context_datetime(ContextInfo)
                except Exception:
                    _dt_now = None
                try:
                    account_info, _, _, _, _, _, _ = _refresh_account_and_risk_state(ContextInfo, current_dt=_dt_now)
                except Exception:
                    account_info = get_trade_detail_data(G['accountid'], 'FUTURE', 'ACCOUNT')

                ai_mult = ai_predict_position_multiplier('long', market_data_df, current_macd, current_rsi, is_bullish_alignment, is_bearish_alignment)
                final_position_size = calculate_position_size(
                    current_price,
                    contract_info,
                    account_info,
                    market_data_df,
                    {'entry_direction': 'long', 'ai_multiplier': ai_mult},
                    set_stop_loss=True
                )
                G['logger'].info(f"📈 重新计算仓位: {final_position_size}手")
                
                if final_position_size > 0:
                    G['logger'].info(f"{signal_type}触发且满足开仓条件，执行开多仓 {final_position_size}手")
                    G['logger'].info(f"开仓标记: case={trading_signal}, risk_mode={risk_mode}, 排布=多头, 突破={has_breakout}, MACD={current_macd:.4f}, RSI={current_rsi:.2f}")
                    
                    # 开多仓
                    order_remark = f'期货多空排布策略-开多-{contract_code}'
                    order_note = f'{signal_type}-{contract_code}'
                    
                    order_id = smart_passorder(
                        0,  # opType: 开多
                        1101,  # orderType: 限价单
                        G['accountid'],
                        contract_code,
                        current_price,  # 当前价格
                        final_position_size,
                        order_remark,
                        2,  # quickTrade: 快速下单
                        order_note,
                        ContextInfo
                    )
                    
                    G['logger'].info(f"✅ 开多仓订单提交成功，订单号: {order_id}")
                    
                    # 更新统计和持仓记录
                    G['golden_cross_count'] += 1
                    G['trade_count'] += 1

                    _entry_dt = get_context_datetime(ContextInfo)
                    _entry_date = _entry_dt.strftime('%Y%m%d')
                    _entry_barpos = _get_barpos(ContextInfo)
                    try:
                        G['trade_id_seq'] = int(G.get('trade_id_seq', 0) or 0) + 1
                    except Exception:
                        G['trade_id_seq'] = 1
                    _trade_id = int(G.get('trade_id_seq', 1) or 1)
                    _entry_stop = None
                    try:
                        _entry_stop = float(market_data_df['low'].iloc[-1])
                    except Exception:
                        _entry_stop = None
                    if _entry_stop is None:
                        try:
                            _entry_stop = float(current_price) * (1 - float(G.get('stop_loss_pct', 0.02) or 0.02))
                        except Exception:
                            _entry_stop = None

                    G['open_positions'][contract_code] = {
                        'trade_id': _trade_id,
                        'root_trade_id': _trade_id,
                        'entry_date': _entry_date,
                        'entry_barpos': _entry_barpos,
                        'direction': 'long',
                        'price': current_price,
                        'initial_price': current_price,
                        'volume': final_position_size,
                        'time': get_context_datetime(ContextInfo).strftime('%Y-%m-%d %H:%M:%S'),
                        'open_reason': trading_signal,
                        'risk_mode': risk_mode,
                        'open_macd': current_macd,
                        'open_rsi': current_rsi,
                        'add_positions': [],
                        'donchian_add_positions': [],
                        'total_volume': final_position_size,
                        'avg_price': current_price,
                        'add_count': 0,
                        'donchian_add_count': 0,
                        'initial_layer_max_profit_pct': 0.0,
                        'initial_layer_trailing_stop_price': _entry_stop,
                        'sizing_stop_price': _entry_stop,
                        'sizing_stop_source': 'entry_day_low',
                        'entry_signal_source': 'fresh_signal',
                        'pending_breakout_created_date': None,
                        'pending_breakout_wait_days': 0
                    }
                    if _entry_stop is not None:
                        try:
                            G['open_positions'][contract_code]['overall_trailing_stop_price'] = float(_entry_stop)
                        except Exception:
                            pass
                        _append_trailing_stop_trace(G['open_positions'][contract_code], 'initial', _entry_date, _entry_barpos, float(_entry_stop), "开仓初始化 当日最低价止损")
                    
                    # 初始化移动止损追踪（仅在启用移动止损时）
                    if G['trailing_stop_enabled']:
                        G['max_profit_tracking'][contract_code] = {
                            'max_profit_pct': 0.0,  # 最大盈利百分比
                            'trailing_stop_price': _entry_stop,
                            'last_update_time': get_context_datetime(ContextInfo).strftime('%Y-%m-%d %H:%M:%S')
                        }
                    
                    G['logger'].info(f"📈 更新持仓记录: 当前持仓数 = {len(G['open_positions'])}/{G['max_concurrent_positions']}")
                    
                    # 【新增】保存策略数据
                    save_strategy_data()

                else:
                    G['logger'].warning(f"⚠️ {signal_type}触发但计算出的仓位为0，跳过开仓")
                    try:
                        account_obj = None
                        if account_info:
                            if isinstance(account_info, list):
                                account_obj = account_info[0] if account_info else None
                            else:
                                account_obj = account_info
                        try:
                            available_balance = float(getattr(account_obj, 'm_dAvailable', 0) or 0)
                        except Exception:
                            available_balance = 0.0
                        limited_available_balance = float(G.get('limited_available_balance', available_balance) or 0)
                        try:
                            vm = float(contract_info.get('VolumeMultiple', 10) or 10)
                        except Exception:
                            vm = 10.0
                        try:
                            mr = float(contract_info.get('LongMarginRatio', 0.1) or 0.1)
                        except Exception:
                            mr = 0.1
                        try:
                            min_pos = int(G.get('min_position_size', 1) or 1)
                        except Exception:
                            min_pos = 1
                        if min_pos <= 0:
                            min_pos = 1
                        required_margin_min = float(min_pos) * float(current_price) * float(vm) * float(mr)
                        if required_margin_min > limited_available_balance:
                            try:
                                if getattr(ContextInfo, 'do_back_test', False) and G.get('enable_block_kline_dump', False):
                                    _schedule_block_kline_dump({
                                        'contract_code': contract_code,
                                        'direction': 'long',
                                        'tag': 'blocked_funds',
                                        'reason': f"保证金不足，最小手数需求{required_margin_min:.2f} > 限制后可用{limited_available_balance:.2f}",
                                        'date': str(current_date),
                                        'trigger_barpos': _get_barpos(ContextInfo),
                                        'pre_days': int(G.get('block_kline_pre_days', G.get('kline_pre_days', 20)) or 20),
                                        'post_days': int(G.get('block_kline_post_days', G.get('kline_post_days', 20)) or 20),
                                    })
                            except Exception:
                                pass
                            send_trade_candidate_blocked_email(
                                ContextInfo,
                                contract_code,
                                'long',
                                signal_type,
                                f"保证金不足，最小手数需求{required_margin_min:.2f} > 限制后可用{limited_available_balance:.2f}",
                                current_price,
                                contract_info,
                                account_info
                            )
                    except Exception:
                        pass

    elif trading_signal and trading_signal.startswith('short'):
            signal_type = {
                'short_case1a': f"📉 {G['ma_short']}日穿{G['ma_mid']}日做空（常规）",
                'short_case2': "⚡ 长期均线穿越做空（突破）",
                'short_case3': "✨ MACD死叉做空（排布确认）"
            }.get(trading_signal, "未知做空信号")
            
            if has_current_contract_position:
                G['logger'].info(f"🚫 {signal_type}触发，但当前合约 {contract_code} 已有持仓，跳过开仓")
            elif not can_open_new_position:
                G['logger'].warning(f"🚫 {signal_type}触发，但已达到最大持仓数限制 ({current_positions_count}/{G['max_concurrent_positions']})，跳过开仓")
            else:
                contract_info = get_contract_info(ContextInfo, contract_code)
                if not contract_info:
                    G['logger'].warning(f"⚠️ 合约 {contract_code} 无有效合约信息，跳过开仓")
                    return
                try:
                    _dt_now = get_context_datetime(ContextInfo)
                except Exception:
                    _dt_now = None
                try:
                    account_info, _, _, _, _, _, _ = _refresh_account_and_risk_state(ContextInfo, current_dt=_dt_now)
                except Exception:
                    account_info = get_trade_detail_data(G['accountid'], 'FUTURE', 'ACCOUNT')

                ai_mult = ai_predict_position_multiplier('short', market_data_df, current_macd, current_rsi, is_bullish_alignment, is_bearish_alignment)
                final_position_size = calculate_position_size(
                    current_price,
                    contract_info,
                    account_info,
                    market_data_df,
                    {'entry_direction': 'short', 'ai_multiplier': ai_mult},
                    set_stop_loss=True
                )
                G['logger'].info(f"📉 重新计算仓位: {final_position_size}手")
                
                if final_position_size > 0:
                    G['logger'].info(f"{signal_type}触发且满足开仓条件，执行开空仓 {final_position_size}手")
                    G['logger'].info(f"开仓标记: case={trading_signal}, risk_mode={risk_mode}, 排布=空头, 突破={has_breakout}, MACD={current_macd:.4f}, RSI={current_rsi:.2f}")
                    
                    # 开空仓
                    order_remark = f'期货多空排布策略-开空-{contract_code}'
                    order_note = f'{signal_type}-{contract_code}'
                    
                    order_id = smart_passorder(
                        3,  # opType: 开空
                        1101,  # orderType: 限价单
                        G['accountid'],
                        contract_code,
                        current_price,  # 当前价格
                        final_position_size,
                        order_remark,
                        2,  # quickTrade: 快速下单
                        order_note,
                        ContextInfo
                    )
                
                    G['logger'].info(f"✅ 开空仓订单提交成功，订单号: {order_id}")
                    
                    # 更新统计和持仓记录
                    G['death_cross_count'] += 1
                    G['trade_count'] += 1

                    _entry_dt = get_context_datetime(ContextInfo)
                    _entry_date = _entry_dt.strftime('%Y%m%d')
                    _entry_barpos = _get_barpos(ContextInfo)
                    try:
                        G['trade_id_seq'] = int(G.get('trade_id_seq', 0) or 0) + 1
                    except Exception:
                        G['trade_id_seq'] = 1
                    _trade_id = int(G.get('trade_id_seq', 1) or 1)
                    try:
                        _entry_stop = float(market_data_df['high'].iloc[-1])
                    except Exception:
                        _entry_stop = None
                    if _entry_stop is None:
                        try:
                            _entry_stop = float(current_price) * (1 + float(G.get('stop_loss_pct', 0.02) or 0.02))
                        except Exception:
                            _entry_stop = None

                    G['open_positions'][contract_code] = {
                        'trade_id': _trade_id,
                        'root_trade_id': _trade_id,
                        'entry_date': _entry_date,
                        'entry_barpos': _entry_barpos,
                        'direction': 'short',
                        'price': current_price,
                        'initial_price': current_price,
                        'volume': final_position_size,
                        'time': get_context_datetime(ContextInfo).strftime('%Y-%m-%d %H:%M:%S'),
                        'open_reason': trading_signal,
                        'risk_mode': risk_mode,
                        'open_macd': current_macd,
                        'open_rsi': current_rsi,
                        'add_positions': [],
                        'donchian_add_positions': [],
                        'total_volume': final_position_size,
                        'avg_price': current_price,
                        'add_count': 0,
                        'donchian_add_count': 0,
                        'initial_layer_max_profit_pct': 0.0,
                        'initial_layer_trailing_stop_price': _entry_stop,
                        'sizing_stop_price': _entry_stop,
                        'sizing_stop_source': 'entry_day_high',
                        'entry_signal_source': 'fresh_signal',
                        'pending_breakout_created_date': None,
                        'pending_breakout_wait_days': 0
                    }
                    _init_ts = _entry_stop
                    if _init_ts is not None:
                        try:
                            G['open_positions'][contract_code]['overall_trailing_stop_price'] = float(_init_ts)
                        except Exception:
                            pass
                        _append_trailing_stop_trace(G['open_positions'][contract_code], 'initial', _entry_date, _entry_barpos, _init_ts, f"开仓初始化 入场价*{1+float(G.get('stop_loss_pct', 0.02) or 0.02):.3f}")
                    
                    # 初始化移动止损追踪（仅在启用移动止损时）
                    if G['trailing_stop_enabled']:
                        G['max_profit_tracking'][contract_code] = {
                            'max_profit_pct': 0.0,  # 最大盈利百分比
                            'trailing_stop_price': current_price * (1 + G['stop_loss_pct']),  # 移动止损价格
                            'last_update_time': get_context_datetime(ContextInfo).strftime('%Y-%m-%d %H:%M:%S')
                        }
                    
                    G['logger'].info(f"📈 更新持仓记录: 当前持仓数 = {len(G['open_positions'])}/{G['max_concurrent_positions']}")
                    
                    # 【新增】保存策略数据
                    save_strategy_data()
                else:
                    G['logger'].warning(f"⚠️ {signal_type}触发但计算出的仓位为0，跳过开仓")
                    try:
                        account_obj = None
                        if account_info:
                            if isinstance(account_info, list):
                                account_obj = account_info[0] if account_info else None
                            else:
                                account_obj = account_info
                        try:
                            available_balance = float(getattr(account_obj, 'm_dAvailable', 0) or 0)
                        except Exception:
                            available_balance = 0.0
                        limited_available_balance = float(G.get('limited_available_balance', available_balance) or 0)
                        try:
                            vm = float(contract_info.get('VolumeMultiple', 10) or 10)
                        except Exception:
                            vm = 10.0
                        try:
                            mr = float(contract_info.get('ShortMarginRatio', 0.1) or 0.1)
                        except Exception:
                            mr = 0.1
                        try:
                            min_pos = int(G.get('min_position_size', 1) or 1)
                        except Exception:
                            min_pos = 1
                        if min_pos <= 0:
                            min_pos = 1
                        required_margin_min = float(min_pos) * float(current_price) * float(vm) * float(mr)
                        if required_margin_min > limited_available_balance:
                            try:
                                if getattr(ContextInfo, 'do_back_test', False) and G.get('enable_block_kline_dump', False):
                                    _schedule_block_kline_dump({
                                        'contract_code': contract_code,
                                        'direction': 'short',
                                        'tag': 'blocked_funds',
                                        'reason': f"保证金不足，最小手数需求{required_margin_min:.2f} > 限制后可用{limited_available_balance:.2f}",
                                        'date': str(current_date),
                                        'trigger_barpos': _get_barpos(ContextInfo),
                                        'pre_days': int(G.get('block_kline_pre_days', G.get('kline_pre_days', 20)) or 20),
                                        'post_days': int(G.get('block_kline_post_days', G.get('kline_post_days', 20)) or 20),
                                    })
                            except Exception:
                                pass
                            send_trade_candidate_blocked_email(
                                ContextInfo,
                                contract_code,
                                'short',
                                signal_type,
                                f"保证金不足，最小手数需求{required_margin_min:.2f} > 限制后可用{limited_available_balance:.2f}",
                                current_price,
                                contract_info,
                                account_info
                            )
                    except Exception:
                        pass
        
    else:
        G['logger'].info(f"⏸️  合约 {contract_code} 保持观望，等待更好的交易机会")

def check_donchian_add_position_conditions(ContextInfo, current_price, contract_code, market_data_df=None):
    if not G.get('enable_donchian_add_position', False):
        return False, None, None
    if contract_code not in G.get('open_positions', {}):
        return False, None, None

    position = G['open_positions'][contract_code]
    today_key = get_context_datetime(ContextInfo).strftime('%Y%m%d')
    if position.get('pending_close_day') == today_key:
        return False, None, None
    if G.get('last_donchian_add_date', {}).get(contract_code) == today_key:
        return False, None, None

    direction = str(position.get('direction', '') or '').strip().lower()
    if direction not in ('long', 'short'):
        return False, None, None

    donchian_layers = _get_donchian_add_positions(position, create=True)
    try:
        add_count = int(position.get('donchian_add_count', len(donchian_layers)) or 0)
    except Exception:
        add_count = len(donchian_layers)
    try:
        max_layers = int(G.get('donchian_add_max_layers', 2) or 2)
    except Exception:
        max_layers = 2
    if add_count >= max_layers:
        return False, None, None

    try:
        period = int(G.get('donchian_add_period', G.get('donchian_period', 20)) or 20)
    except Exception:
        period = 20
    period = max(period, 1)

    if market_data_df is None or market_data_df.empty or len(market_data_df) < period + 1:
        return False, None, None

    donchian_channel = calculate_donchian_channel(market_data_df[['high', 'low', 'close']], period=period)
    breakout_info = check_donchian_breakout(float(current_price), donchian_channel, direction=direction)
    if not breakout_info.get('breakout'):
        return False, None, breakout_info
    if breakout_info.get('direction') != direction:
        return False, None, breakout_info

    add_type = f"donchian_add_{add_count + 1}"
    G['logger'].info(
        f"[DON-ADD] {contract_code} 触发独立唐奇安加仓: dir={direction}, add_type={add_type}, "
        f"close={float(current_price):.2f}, upper={float(breakout_info.get('upper', 0) or 0):.2f}, "
        f"lower={float(breakout_info.get('lower', 0) or 0):.2f}"
    )
    return True, add_type, breakout_info


def execute_donchian_add_position(ContextInfo, current_price, contract_code, add_type, market_data_df=None, breakout_info=None):
    if contract_code not in G.get('open_positions', {}):
        return False

    position = G['open_positions'][contract_code]
    direction = str(position.get('direction', '') or '').strip().lower()
    if direction not in ('long', 'short'):
        return False

    try:
        original_volume = int(position.get('volume', 0) or 0)
    except Exception:
        original_volume = 0
    if original_volume <= 0:
        G['logger'].warning(f"[DON-ADD] {contract_code} 初始仓位异常，取消唐奇安加仓")
        return False

    try:
        current_add_idx = max(int(str(add_type).split('_')[-1]) - 1, 0)
    except Exception:
        current_add_idx = 0
    raw_multipliers = G.get('donchian_add_volume_multipliers', [2.0, 1.0])
    if not isinstance(raw_multipliers, (list, tuple)):
        raw_multipliers = [raw_multipliers]
    try:
        parsed_multipliers = [float(x) for x in raw_multipliers if float(x) > 0]
    except Exception:
        parsed_multipliers = []
    if not parsed_multipliers:
        parsed_multipliers = [2.0, 1.0]
    vol_mult = parsed_multipliers[current_add_idx] if current_add_idx < len(parsed_multipliers) else parsed_multipliers[-1]
    if vol_mult <= 0:
        return False
    add_volume = max(1, int(round(float(original_volume) * vol_mult)))

    contract_info = get_contract_info(ContextInfo, contract_code)
    if not contract_info:
        return False

    try:
        margin_ratio = float(contract_info.get('LongMarginRatio', 0.1) if direction == 'long' else contract_info.get('ShortMarginRatio', 0.1) or 0.1)
    except Exception:
        margin_ratio = 0.1
    try:
        volume_multiple = float(contract_info.get('VolumeMultiple', 10) or 10)
    except Exception:
        volume_multiple = 10.0

    required_margin = float(add_volume) * float(current_price) * float(volume_multiple) * float(margin_ratio)
    limited_available_balance = float(G.get('limited_available_balance', 0) or 0)
    if required_margin > limited_available_balance:
        G['logger'].warning(
            f"[DON-ADD] {contract_code} 保证金不足，取消唐奇安加仓: required={required_margin:.2f}, "
            f"limited_available={limited_available_balance:.2f}"
        )
        return False

    _entry_stop = None
    if market_data_df is not None and not market_data_df.empty:
        try:
            _entry_stop = float(market_data_df['low'].iloc[-1]) if direction == 'long' else float(market_data_df['high'].iloc[-1])
        except Exception:
            _entry_stop = None
    if _entry_stop is None:
        try:
            _sl_pct = float(G.get('stop_loss_pct', 0.02) or 0.02)
        except Exception:
            _sl_pct = 0.02
        _entry_stop = float(current_price) * (1 - _sl_pct) if direction == 'long' else float(current_price) * (1 + _sl_pct)

    if direction == 'long':
        op_type = 0
        order_remark = f'期货多空排布策略-唐加多-{add_type}-{contract_code}'
    else:
        op_type = 3
        order_remark = f'期货多空排布策略-唐加空-{add_type}-{contract_code}'
    order_note = f'{add_type}-{contract_code}'

    order_id = smart_passorder(
        op_type,
        1101,
        G['accountid'],
        contract_code,
        current_price,
        add_volume,
        order_remark,
        2,
        order_note,
        ContextInfo
    )
    if order_id <= 0:
        G['logger'].error(f"[DON-ADD] ❌ {contract_code} 唐奇安加仓下单失败: add_type={add_type}, order_id={order_id}")
        return False

    try:
        G['trade_id_seq'] = int(G.get('trade_id_seq', 0) or 0) + 1
    except Exception:
        G['trade_id_seq'] = 1
    trade_id = int(G.get('trade_id_seq', 1) or 1)
    layer_date = get_context_datetime(ContextInfo).strftime('%Y%m%d')
    layer_barpos = _get_barpos(ContextInfo)
    add_record = {
        'trade_id': trade_id,
        'price': float(current_price),
        'volume': int(add_volume),
        'time': get_context_datetime(ContextInfo).strftime('%Y-%m-%d %H:%M:%S'),
        'date': layer_date,
        'barpos': layer_barpos,
        'type': add_type,
        'source': 'donchian_breakout',
        'max_profit_pct': 0.0,
        'trailing_stop_price': float(_entry_stop),
        'trigger_upper': breakout_info.get('upper') if isinstance(breakout_info, dict) else None,
        'trigger_lower': breakout_info.get('lower') if isinstance(breakout_info, dict) else None,
    }
    _get_donchian_add_positions(position, create=True).append(add_record)
    _append_trailing_stop_trace(position, add_type, layer_date, layer_barpos, float(_entry_stop), "唐奇安加仓初始化止损")
    new_total_volume, new_avg_price = _recalculate_position_totals(position)

    G['logger'].info(
        f"[DON-ADD] ✅ {contract_code} 唐奇安加仓成功: add_type={add_type}, add_mult={vol_mult:.2f}, add_vol={add_volume}, "
        f"new_total={new_total_volume}, new_avg={new_avg_price:.2f}, stop={float(_entry_stop):.2f}"
    )
    if 'last_donchian_add_date' not in G or not isinstance(G.get('last_donchian_add_date'), dict):
        G['last_donchian_add_date'] = {}
    G['last_donchian_add_date'][contract_code] = layer_date
    save_strategy_data()
    return True


def _close_donchian_add_layer(ContextInfo, current_price, contract_code, layer_idx, close_reason):
    position = G.get('open_positions', {}).get(contract_code)
    if not isinstance(position, dict):
        return False
    layers = _get_donchian_add_positions(position, create=True)
    if layer_idx < 0 or layer_idx >= len(layers):
        return False

    layer = layers[layer_idx]
    try:
        close_volume = int(layer.get('volume', 0) or 0)
    except Exception:
        close_volume = 0
    if close_volume <= 0:
        return False

    direction = str(position.get('direction', '') or '').strip().lower()
    entry_price = float(layer.get('price', 0) or 0)
    layer_name = str(layer.get('type') or f'donchian_add_{layer_idx + 1}')
    op_type = 6 if direction == 'long' else 8
    remark = f"期货多空排布策略-平{'多' if direction == 'long' else '空'}-{layer_name}"

    contract_info = get_contract_info(ContextInfo, contract_code)
    try:
        volume_multiple = float(contract_info.get('VolumeMultiple', 10) or 10) if contract_info else 10.0
    except Exception:
        volume_multiple = 10.0

    if direction == 'long':
        pnl_pct = (float(current_price) - entry_price) / entry_price if entry_price else 0.0
    else:
        pnl_pct = (entry_price - float(current_price)) / entry_price if entry_price else 0.0

    order_id = smart_passorder(
        op_type,
        1101,
        G['accountid'],
        contract_code,
        current_price,
        close_volume,
        remark,
        2,
        close_reason,
        ContextInfo,
        extra={
            'action': 'close',
            'contract': contract_code,
            'direction': direction,
            'layer': layer_name,
            'reason': close_reason,
            'entry_price': float(entry_price),
            'exit_price': float(current_price),
            'volume': int(close_volume),
            'pnl_pct': float(pnl_pct),
            'case': position.get('open_reason', 'unknown'),
        }
    )
    if order_id <= 0:
        G['logger'].error(f"[DON-ADD] ❌ {contract_code} 独立加仓层平仓失败: layer={layer_name}, order_id={order_id}")
        return False

    today_key = get_context_datetime(ContextInfo).strftime('%Y%m%d')
    if getattr(ContextInfo, 'do_back_test', False) and G.get('enable_trade_kline_dump', False):
        try:
            entry_barpos = int(layer.get('barpos'))
        except Exception:
            entry_barpos = None
        if entry_barpos is not None and entry_barpos >= 0:
            _schedule_trade_kline_dump({
                'trade_id': layer.get('trade_id'),
                'root_trade_id': position.get('root_trade_id', position.get('trade_id')),
                'contract_code': contract_code,
                'base_code': _base_code_from_contract(contract_code),
                'layer': layer_name,
                'direction': direction,
                'entry_price': float(entry_price),
                'exit_price': float(current_price),
                'pos_volume': int(close_volume),
                'volume_multiple': float(volume_multiple),
                'close_reason': close_reason,
                'sizing_stop_price': layer.get('trailing_stop_price'),
                'sizing_stop_source': 'donchian_add_stop',
                'entry_signal_source': position.get('entry_signal_source'),
                'pending_breakout_created_date': position.get('pending_breakout_created_date'),
                'pending_breakout_wait_days': position.get('pending_breakout_wait_days'),
                'entry_date': layer.get('date'),
                'exit_date': today_key,
                'entry_barpos': entry_barpos,
                'exit_barpos': _get_barpos(ContextInfo),
                'pre_days': int((G.get('kline_pre_days_cache') if bool(G.get('use_kline_cache', False)) else G.get('kline_pre_days')) or 20),
                'post_days': int((G.get('kline_post_days_cache') if bool(G.get('use_kline_cache', False)) else G.get('kline_post_days')) or 20),
                'layer_trailing_stop_trace': position.get('layer_trailing_stop_trace')
            })

    if not ContextInfo.do_back_test:
        position['pending_close_day'] = today_key
        position['pending_close_reason'] = close_reason
        save_strategy_data()
        return True

    realized_pnl = (float(current_price) - entry_price) * int(close_volume) * float(volume_multiple) if direction == 'long' else (entry_price - float(current_price)) * int(close_volume) * float(volume_multiple)
    if realized_pnl >= 0:
        G['num_winning_trades'] += 1
        G['gross_profit'] += realized_pnl
        G['best_trade_pnl'] = max(G['best_trade_pnl'], realized_pnl)
    else:
        G['num_losing_trades'] += 1
        G['gross_loss_abs'] += -realized_pnl
        G['worst_trade_pnl'] = min(G['worst_trade_pnl'], realized_pnl)
    G['total_realized_pnl'] += realized_pnl
    G['closed_trades'] += 1
    _update_streak_risk_state_on_close(realized_pnl)

    case_key = position.get('open_reason', 'unknown')
    if case_key not in G['case_stats']:
        G['case_stats'][case_key] = {'trades': 0, 'wins': 0, 'losses': 0, 'gross_profit': 0.0, 'gross_loss_abs': 0.0}
    cs = G['case_stats'][case_key]
    cs['trades'] += 1
    if realized_pnl >= 0:
        cs['wins'] += 1
        cs['gross_profit'] += realized_pnl
    else:
        cs['losses'] += 1
        cs['gross_loss_abs'] += -realized_pnl

    del layers[layer_idx]
    position['donchian_add_positions'] = layers
    remaining_total, _ = _recalculate_position_totals(position)
    G['logger'].info(
        f"[DON-ADD] ✅ {contract_code} 独立加仓层已平仓: layer={layer_name}, volume={close_volume}, "
        f"realized_pnl={realized_pnl:+.2f}, remain_total={remaining_total}"
    )
    if remaining_total <= 0:
        if contract_code in G.get('open_positions', {}):
            del G['open_positions'][contract_code]
        if contract_code in G.get('max_profit_tracking', {}):
            del G['max_profit_tracking'][contract_code]
    save_strategy_data()
    return True


def check_donchian_add_stop_conditions(ContextInfo, current_price, contract_code, market_data_df=None):
    if not G.get('enable_donchian_add_position', False):
        return False
    position = G.get('open_positions', {}).get(contract_code)
    if not isinstance(position, dict):
        return False
    layers = _get_donchian_add_positions(position, create=True)
    if not layers:
        return False
    if market_data_df is None or market_data_df.empty:
        return False

    direction = str(position.get('direction', '') or '').strip().lower()
    if direction not in ('long', 'short'):
        return False
    try:
        day_stop_ref = float(market_data_df['low'].iloc[-1]) if direction == 'long' else float(market_data_df['high'].iloc[-1])
    except Exception:
        return False
    try:
        _sl_pct = float(G.get('stop_loss_pct', 0.02) or 0.02)
    except Exception:
        _sl_pct = 0.02

    today_key = get_context_datetime(ContextInfo).strftime('%Y%m%d')
    barpos = _get_barpos(ContextInfo)
    trigger_indices = []
    for idx, layer in enumerate(layers):
        if not isinstance(layer, dict):
            continue
        layer_name = str(layer.get('type') or f'donchian_add_{idx + 1}')
        try:
            entry_price = float(layer.get('price', 0) or 0)
        except Exception:
            entry_price = 0.0
        if entry_price <= 0:
            continue
        stop_price = layer.get('trailing_stop_price')
        if stop_price is None:
            stop_price = entry_price * (1 - _sl_pct) if direction == 'long' else entry_price * (1 + _sl_pct)
        try:
            stop_price = float(stop_price)
        except Exception:
            stop_price = entry_price * (1 - _sl_pct) if direction == 'long' else entry_price * (1 + _sl_pct)

        new_stop = max(stop_price, day_stop_ref) if direction == 'long' else min(stop_price, day_stop_ref)
        if abs(float(new_stop) - float(stop_price)) > 1e-9:
            layer['trailing_stop_price'] = float(new_stop)
            _append_trailing_stop_trace(position, layer_name, today_key, barpos, float(new_stop), "按当日极值抬升独立止损")
        else:
            layer['trailing_stop_price'] = float(stop_price)

        if direction == 'long' and float(current_price) <= float(layer['trailing_stop_price']):
            trigger_indices.append(idx)
        elif direction == 'short' and float(current_price) >= float(layer['trailing_stop_price']):
            trigger_indices.append(idx)

    if not trigger_indices:
        return False

    handled = False
    for idx in sorted(trigger_indices, reverse=True):
        cur_layers = _get_donchian_add_positions(position, create=True)
        if idx >= len(cur_layers):
            continue
        layer = cur_layers[idx]
        layer_name = str(layer.get('type') or f'donchian_add_{idx + 1}')
        stop_price = float(layer.get('trailing_stop_price', day_stop_ref) or day_stop_ref)
        if direction == 'long':
            close_reason = f"合约 {contract_code} 唐奇安加仓层止损平仓 ({layer_name}: 收盘价{float(current_price):.2f} <= 独立止损价{stop_price:.2f})"
        else:
            close_reason = f"合约 {contract_code} 唐奇安加仓层止损平仓 ({layer_name}: 收盘价{float(current_price):.2f} >= 独立止损价{stop_price:.2f})"
        handled = _close_donchian_add_layer(ContextInfo, current_price, contract_code, idx, close_reason) or handled
        if handled and not getattr(ContextInfo, 'do_back_test', False):
            break
    return handled


def check_add_position_conditions(ContextInfo, current_price, contract_code):
    """
    检查是否满足加仓条件（盈利加仓逻辑）
    1. 基础条件：持仓盈利必须大于阈值（首次/二次阈值可配）
    2. 加仓次数限制：最多加仓2次（首次和第二次）
    3. 时间间隔限制：开仓后至少间隔一定天数才能加仓
    4. 可选影线震荡过滤：避免震荡环境加仓
    """
    # 检查是否启用了加仓策略
    if not G.get('enable_add_position', False):
        G['logger'].info(f"[ADD] {contract_code} 加仓未启用，跳过")
        return False, None
    
    # 检查是否存在持仓
    if contract_code not in G['open_positions']:
        G['logger'].info(f"[ADD] {contract_code} 无持仓记录，跳过")
        return False, None
    
    position = G['open_positions'][contract_code]

    today_key = get_context_datetime(ContextInfo).strftime('%Y%m%d')
    if position.get('pending_close_day') == today_key:
        G['logger'].warning(f"⚠️ 合约 {contract_code} 当日已提交过平仓指令，等待回报/同步确认")
        return False, None
    
    # 确保必要的字段存在，如果不存在则提供默认值
    direction = position.get('direction', '')
    entry_price = position.get('avg_price', position.get('price', 0))
    add_count = position.get('add_count', 0)
    profit_threshold = float(G.get('add_position_threshold', 0.01)) if add_count == 0 else float(G.get('second_add_position_threshold', 0.01))
    max_add_layers = G.get('max_add_layers', 2)
    G['logger'].info(
        f"[ADD] {contract_code} 加仓判断开始: dir={direction}, current={current_price:.2f}, avg_cost={entry_price:.2f}, "
        f"add_count={add_count}/{max_add_layers}, threshold={profit_threshold*100:.2f}%"
    )
    
    # 如果缺少avg_price字段，使用price字段作为后备
    if 'avg_price' not in position:
        position['avg_price'] = entry_price
        G['logger'].warning(f"⚠️ 持仓记录缺少'avg_price'字段，使用'price'字段作为后备: {entry_price:.2f}")
    
    # 如果缺少add_count字段，添加默认值
    if 'add_count' not in position:
        position['add_count'] = 0
        G['logger'].warning("⚠️ 持仓记录缺少'add_count'字段，添加默认值0")
    
    # 添加额外的安全检查，确保方向字段有效
    if direction not in ['long', 'short']:
        G['logger'].warning(f"[ADD] {contract_code} 持仓方向无效: {direction}")
        return False, None

    open_time_str = position.get('time', '')
    if open_time_str:
        open_time = parse_datetime_flexible(open_time_str)
        if not open_time:
            G['logger'].warning(f"[ADD] {contract_code} 开仓时间解析失败: {open_time_str}")
            return False, None
        current_time = get_context_datetime(ContextInfo)

        time_diff = current_time - open_time
        days_since_open = time_diff.days
        min_interval_days = 1

        if days_since_open < min_interval_days:
            G['logger'].info(f"[ADD] {contract_code} 时间条件不满足: days_since_open={days_since_open} < {min_interval_days}")
            return False, None
        else:
            G['logger'].info(f"[ADD] {contract_code} 时间条件满足: days_since_open={days_since_open} >= {min_interval_days}")
    else:
        G['logger'].warning(f"[ADD] {contract_code} 缺少开仓时间，跳过时间检查")

    if entry_price <= 0:
        G['logger'].warning(f"[ADD] {contract_code} 持仓成本价异常: {entry_price}")
        return False, None

    if direction == 'long':
        profit_pct = (current_price - entry_price) / entry_price
    else:
        profit_pct = (entry_price - current_price) / entry_price

    G['logger'].info(f"[ADD] {contract_code} 盈利比例: {profit_pct*100:.2f}% (avg_cost={entry_price:.2f}, threshold={profit_threshold*100:.2f}%)")
    if profit_pct < profit_threshold:
        G['logger'].info(f"[ADD] {contract_code} 盈利条件不满足，拒绝加仓")
        return False, None

    required_count = 2
    if ContextInfo.do_back_test:
        current_timetag = ContextInfo.get_bar_timetag(ContextInfo.barpos)
        current_date = datetime.datetime.fromtimestamp(current_timetag/1000).strftime("%Y%m%d")
        market_data = ContextInfo.get_market_data_ex(
            fields=['open', 'close'],
            stock_code=[contract_code],
            period=G['period'],
            end_time=current_date,
            count=required_count,
            dividend_type='front_ratio',
            subscribe=False
        )
    else:
        market_data = ContextInfo.get_market_data_ex(
            fields=['open', 'close'],
            stock_code=[contract_code],
            period=G['period'],
            count=required_count,
            dividend_type='front_ratio',
            subscribe=True
        )

    if contract_code not in market_data or market_data[contract_code].empty or len(market_data[contract_code]) < required_count:
        G['logger'].warning(f"[ADD] {contract_code} K线数据不足(需要{required_count}根)，无法做反转确认")
        return False, None

    market_data_df = market_data[contract_code]
    yesterday_open = float(market_data_df['open'].iloc[-2])
    yesterday_close = float(market_data_df['close'].iloc[-2])
    today_open = float(market_data_df['open'].iloc[-1])
    today_close = float(market_data_df['close'].iloc[-1])
    if direction == 'long':
        reversal_ok = (yesterday_close < yesterday_open) and (today_close > today_open)
    else:
        reversal_ok = (yesterday_close > yesterday_open) and (today_close < today_open)
    G['logger'].info(
        f"[ADD] {contract_code} 反转确认: "
        f"y(o={yesterday_open:.2f},c={yesterday_close:.2f}) "
        f"t(o={today_open:.2f},c={today_close:.2f}) ok={reversal_ok}"
    )
    if not reversal_ok:
        G['logger'].info(f"[ADD] {contract_code} 反转确认不满足，拒绝加仓")
        return False, None

    if bool(G.get('wick_chop_filter_enabled', False)):
        try:
            lookback_i = int(G.get('wick_chop_filter_lookback', 10) or 10)
        except Exception:
            lookback_i = 10
        try:
            max_days_i = int(G.get('wick_chop_filter_max_days', 4) or 4)
        except Exception:
            max_days_i = 4
        if lookback_i < 1:
            lookback_i = 1
        required_count = lookback_i

        if ContextInfo.do_back_test:
            current_timetag = ContextInfo.get_bar_timetag(ContextInfo.barpos)
            current_date = datetime.datetime.fromtimestamp(current_timetag/1000).strftime("%Y%m%d")
            market_data = ContextInfo.get_market_data_ex(
                fields=['open', 'high', 'low', 'close'],
                stock_code=[contract_code],
                period=G['period'],
                end_time=current_date,
                count=required_count,
                dividend_type='front_ratio',
                subscribe=False
            )
        else:
            market_data = ContextInfo.get_market_data_ex(
                fields=['open', 'high', 'low', 'close'],
                stock_code=[contract_code],
                period=G['period'],
                count=required_count,
                dividend_type='front_ratio',
                subscribe=True
            )

        if contract_code not in market_data or market_data[contract_code].empty or len(market_data[contract_code]) < required_count:
            G['logger'].warning(f"[ADD] {contract_code} K线数据不足(需要{required_count}根)，无法做影线震荡过滤")
            return False, None

        market_data_df = market_data[contract_code]
        ok, cnt, n = wick_chop_filter_ok(market_data_df, lookback=lookback_i, max_days=max_days_i)
        if not ok:
            G['logger'].info(f"[ADD] {contract_code} 影线震荡过滤：近{n}根(目标{lookback_i})K线中影线>实体天数={cnt} > {max_days_i}，禁止加仓")
            return False, None

    if add_count < max_add_layers:
        add_type = 'first_add' if add_count == 0 else 'second_add'
        G['logger'].info(
            f"[ADD] {contract_code} 加仓条件通过: add_type={add_type}, profit={profit_pct*100:.2f}%, add_count={add_count}/{max_add_layers}"
        )
        return True, add_type

    G['logger'].info(f"[ADD] {contract_code} 已达最大加仓次数: {add_count}/{max_add_layers}")
    return False, None

def execute_add_position(ContextInfo, current_price, contract_code, add_type):
    """
    执行加仓操作 - 支持分层仓位独立管理
    """
    if contract_code not in G['open_positions']:
        G['logger'].warning(f"[ADD] {contract_code} 无持仓记录，无法加仓")
        return False
    
    position = G['open_positions'][contract_code]

    if add_type != 'first_add':
        G['logger'].info(f"[ADD] {contract_code} 已限制仅允许首次加仓，跳过: add_type={add_type}")
        return False
    
    # 确保必要的字段存在，如果不存在则提供默认值
    direction = position.get('direction', '')
    entry_price = position.get('avg_price', position.get('price', 0))
    current_volume = position.get('total_volume', position.get('volume', 0))
    add_count = position.get('add_count', 0)
    
    # 如果缺少avg_price字段，使用price字段作为后备
    if 'avg_price' not in position:
        position['avg_price'] = entry_price
        G['logger'].warning(f"⚠️ 持仓记录缺少'avg_price'字段，使用'price'字段作为后备: {entry_price:.2f}")
    
    # 如果缺少total_volume字段，使用volume字段作为后备
    if 'total_volume' not in position:
        position['total_volume'] = current_volume
        G['logger'].warning(f"⚠️ 持仓记录缺少'total_volume'字段，使用'volume'字段作为后备: {current_volume}")
    
    # 如果缺少add_count字段，添加默认值
    if 'add_count' not in position:
        position['add_count'] = 0
        G['logger'].warning("⚠️ 持仓记录缺少'add_count'字段，添加默认值0")
    
    # 计算加仓手数（加仓手数等于初始开仓手数）
    original_volume = position['volume']  # 初始开仓手数
    add_volume = max(1, original_volume)
    _ensure_streak_risk_state()
    try:
        _m = float(G.get('risk_multiplier', 1.0) or 1.0)
    except Exception:
        _m = 1.0
    if _m < 0:
        _m = 0.0
    if _m > 1:
        _m = 1.0
    scaled_add_volume = int(add_volume * _m)
    if scaled_add_volume <= 0:
        G['logger'].info(f"[ADD] {contract_code} 风险乘数m={_m:.2f}导致加仓手数<=0，跳过加仓")
        return False
    add_volume = scaled_add_volume
    
    G['logger'].info(
        f"[ADD] {contract_code} 执行加仓准备: add_type={add_type}, direction={direction}, "
        f"initial_vol={original_volume}, total_vol={current_volume}, add_vol={add_volume}, current={current_price:.2f}, avg_cost={entry_price:.2f}"
    )

    _add_entry_stop = None
    _add_entry_stop_reason = ""
    if direction == 'long':
        try:
            _today_key = get_context_datetime(ContextInfo).strftime('%Y%m%d')
            if ContextInfo.do_back_test:
                _md = ContextInfo.get_market_data_ex(
                    fields=['open', 'close', 'low'],
                    stock_code=[contract_code],
                    period=G['period'],
                    end_time=_today_key,
                    count=1,
                    dividend_type='front_ratio',
                    subscribe=False
                )
            else:
                _md = ContextInfo.get_market_data_ex(
                    fields=['open', 'close', 'low'],
                    stock_code=[contract_code],
                    period=G['period'],
                    count=1,
                    dividend_type='front_ratio',
                    subscribe=True
                )
            if _md is not None and contract_code in _md and not _md[contract_code].empty:
                _o = float(_md[contract_code]['open'].iloc[-1])
                _c = float(_md[contract_code]['close'].iloc[-1])
                try:
                    _l = float(_md[contract_code]['low'].iloc[-1])
                except Exception:
                    _l = None
                if _l is not None:
                    try:
                        if not math.isfinite(_l):
                            _l = None
                    except Exception:
                        _l = None
                if _c < _o:
                    G['logger'].info(f"[ADD] {contract_code} 多头加仓过滤：当日下跌(close {_c:.2f} < open {_o:.2f})，禁止加仓")
                    if getattr(ContextInfo, 'do_back_test', False) and G.get('enable_block_kline_dump', False):
                        _schedule_block_kline_dump({
                            'contract_code': contract_code,
                            'direction': 'long',
                            'tag': 'add_blocked_down_day',
                            'reason': f"down_day close<open ({_c:.2f}<{_o:.2f})",
                            'date': str(_today_key),
                            'trigger_barpos': _get_barpos(ContextInfo),
                            'pre_days': int(G.get('block_kline_pre_days', G.get('kline_pre_days', 20)) or 20),
                            'post_days': int(G.get('block_kline_post_days', G.get('kline_post_days', 20)) or 20),
                        })
                    return False
                if _l is not None:
                    _add_entry_stop = _l
                    _add_entry_stop_reason = "加仓初始化 当日最低价止损"
        except Exception:
            pass
    
    contract_info = get_contract_info(ContextInfo, contract_code)
    if not contract_info:
        G['logger'].warning(f"[ADD] {contract_code} 无有效合约信息，取消加仓")
        return False
    try:
        _dt_now = get_context_datetime(ContextInfo)
    except Exception:
        _dt_now = None
    try:
        account_info, _, _, _, _, _, _ = _refresh_account_and_risk_state(ContextInfo, current_dt=_dt_now)
    except Exception:
        account_info = get_trade_detail_data(G['accountid'], 'FUTURE', 'ACCOUNT')
        
    volume_multiple = contract_info.get('VolumeMultiple', 10)
    margin_ratio = contract_info.get('LongMarginRatio', 0.1) if direction == 'long' else contract_info.get('ShortMarginRatio', 0.1)
    single_contract_value = current_price * volume_multiple
    required_margin = add_volume * single_contract_value * margin_ratio
        
    limited_available_balance = G.get('limited_available_balance', 0)

    G['logger'].info(
        f"[ADD] {contract_code} 保证金评估: required_margin={required_margin:.2f}, limited_available={limited_available_balance:.2f}, "
        f"margin_ratio={margin_ratio:.4f}, vm={volume_multiple}"
    )
        
    if required_margin > limited_available_balance:
        G['logger'].warning(f"[ADD] {contract_code} 加仓保证金不足，取消下单")
        return False
        
    if direction == 'long':
        opType = 0
        order_remark = f'期货多空排布策略-加多-{contract_code}'
        order_note = f'加多仓-{add_type}-{contract_code}'
    else:
        opType = 3
        order_remark = f'期货多空排布策略-加空-{contract_code}'
        order_note = f'加空仓-{add_type}-{contract_code}'
        
    G['logger'].info(
        f"[ADD] {contract_code} 加仓下单调用: opType={opType}, orderType=1101, prType={'11' if ContextInfo.do_back_test else '14'}, "
        f"price={current_price:.2f}, volume={add_volume}, remark={order_remark}, note={order_note}"
    )

    order_id = smart_passorder(
        opType,
        1101,
        G['accountid'],
        contract_code,
        current_price,
        add_volume,
        order_remark,
        2,
        order_note,
        ContextInfo
    )
        
    if order_id > 0:
        new_total_volume = current_volume + add_volume
        new_avg_price = (entry_price * current_volume + current_price * add_volume) / new_total_volume

        try:
            G['trade_id_seq'] = int(G.get('trade_id_seq', 0) or 0) + 1
        except Exception:
            G['trade_id_seq'] = 1
        _trade_id = int(G.get('trade_id_seq', 1) or 1)

        if direction == 'long':
            if _add_entry_stop is None:
                try:
                    _add_entry_stop = float(current_price) * (1 - float(G.get('stop_loss_pct', 0.02) or 0.02))
                except Exception:
                    _add_entry_stop = None
            if not _add_entry_stop_reason:
                if _add_entry_stop is not None:
                    try:
                        _p = float(G.get('stop_loss_pct', 0.02) or 0.02)
                    except Exception:
                        _p = 0.02
                    _add_entry_stop_reason = f"加仓初始化 入场价*{(1 - _p):.3f}"

        add_record = {
            'trade_id': _trade_id,
            'price': current_price,
            'volume': add_volume,
            'time': get_context_datetime(ContextInfo).strftime('%Y-%m-%d %H:%M:%S'),
            'date': get_context_datetime(ContextInfo).strftime('%Y%m%d'),
            'barpos': _get_barpos(ContextInfo),
            'type': add_type,
            'max_profit_pct': 0.0,
            'trailing_stop_price': _add_entry_stop if direction == 'long' else current_price * (1 + G['stop_loss_pct']),
            'sizing_stop_price': _add_entry_stop if direction == 'long' else current_price * (1 + G['stop_loss_pct']),
            'sizing_stop_source': 'add_layer_stop'
        }
        position['add_positions'].append(add_record)
        try:
            _add_layer_key = f"add_{int(add_count or 0) + 1}"
        except Exception:
            _add_layer_key = "add_1"
        _append_trailing_stop_trace(position, _add_layer_key, add_record.get('date'), add_record.get('barpos'), add_record.get('trailing_stop_price'), _add_entry_stop_reason or "加仓初始化")
        position['total_volume'] = new_total_volume
        position['avg_price'] = new_avg_price
        position['add_count'] = add_count + 1
            
        G['logger'].info(f"[ADD] ✅ {contract_code} {add_type}加仓下单成功: add_vol={add_volume}, order_id={order_id}")
        G['logger'].info(f"   新的总持仓: {new_total_volume}手")
        G['logger'].info(f"   新的加权平均成本价: {new_avg_price:.2f}")
        G['logger'].info(f"   加仓详情: 第{add_count+1}次加仓 @ {current_price:.2f}")
            
        update_trailing_stop_after_add_position(contract_code, new_avg_price, direction)
        save_strategy_data()
        return True
    else:
        G['logger'].error(f"[ADD] ❌ {contract_code} {add_type}加仓下单失败: order_id={order_id}")
        return False

def update_trailing_stop_after_add_position(contract_code, avg_price, direction):
    """
    加仓后更新移动止损价格，确保不低于加权平均成本价+微利
    支持分层仓位独立管理
    """
    if not G['trailing_stop_enabled']:
        return

    if contract_code not in G.get('open_positions', {}):
        return

    position = G['open_positions'][contract_code]
    if bool(G.get('add_layers_independent', True)):
        return
    
    min_profit_pct = float(G.get('add_position_min_profit', 0.001) or 0.001)
    if direction == 'long':
        min_stop_price = avg_price * (1 + min_profit_pct)
    else:
        min_stop_price = avg_price * (1 - min_profit_pct)

    def get_layer_ts_values():
        ts_vals = []
        init_ts = position.get('initial_layer_trailing_stop_price')
        init_price = float(position.get('initial_price', position.get('price', avg_price)) or avg_price)
        if init_ts is None:
            init_ts = init_price * (1 - G['stop_loss_pct']) if direction == 'long' else init_price * (1 + G['stop_loss_pct'])
        ts_vals.append(float(init_ts))
        for ap in position.get('add_positions', []) or []:
            ap_price = float(ap.get('price', avg_price) or avg_price)
            ap_ts = ap.get('trailing_stop_price')
            if ap_ts is None:
                ap_ts = ap_price * (1 - G['stop_loss_pct']) if direction == 'long' else ap_price * (1 + G['stop_loss_pct'])
            ts_vals.append(float(ap_ts))
        return ts_vals

    before_vals = get_layer_ts_values()
    before_overall = max(before_vals) if direction == 'long' else min(before_vals)

    init_ts = position.get('initial_layer_trailing_stop_price')
    init_price = float(position.get('initial_price', position.get('price', avg_price)) or avg_price)
    if init_ts is None:
        init_ts = init_price * (1 - G['stop_loss_pct']) if direction == 'long' else init_price * (1 + G['stop_loss_pct'])
    init_ts = float(init_ts)
    if direction == 'long':
        init_ts = max(init_ts, min_stop_price)
    else:
        init_ts = min(init_ts, min_stop_price)
    position['initial_layer_trailing_stop_price'] = init_ts

    for ap in position.get('add_positions', []) or []:
        ap_price = float(ap.get('price', avg_price) or avg_price)
        ap_ts = ap.get('trailing_stop_price')
        if ap_ts is None:
            ap_ts = ap_price * (1 - G['stop_loss_pct']) if direction == 'long' else ap_price * (1 + G['stop_loss_pct'])
        ap_ts = float(ap_ts)
        if direction == 'long':
            ap_ts = max(ap_ts, min_stop_price)
        else:
            ap_ts = min(ap_ts, min_stop_price)
        ap['trailing_stop_price'] = ap_ts
        if 'max_profit_pct' not in ap:
            ap['max_profit_pct'] = 0.0

    after_vals = get_layer_ts_values()
    after_overall = max(after_vals) if direction == 'long' else min(after_vals)

    if abs(after_overall - before_overall) > 1e-9:
        G['logger'].info(f"🔄 加仓后调整移动止损价格: {before_overall:.2f} → {after_overall:.2f}")
        G['logger'].info(f"   基于加权平均成本价{avg_price:.2f}和最小盈利比例{min_profit_pct*100:.1f}%")

        _last_ap = None
        try:
            _aps = position.get('add_positions') or []
            if isinstance(_aps, list) and _aps:
                _last_ap = _aps[-1]
        except Exception:
            _last_ap = None
        _d = None
        _bp = None
        if _last_ap is not None:
            _d = _last_ap.get('date')
            _bp = _last_ap.get('barpos')
        if not _d:
            _d = position.get('entry_date')
        if _bp is None:
            _bp = position.get('entry_barpos')
        _append_trailing_stop_trace(position, 'overall', _d, _bp, float(after_overall), f"加仓后锁定微利 avg={float(avg_price):.2f} min_profit={min_profit_pct*100:.2f}%")

    if 'max_profit_tracking' not in G:
        G['max_profit_tracking'] = {}
    old = G['max_profit_tracking'].get(contract_code, {})
    G['max_profit_tracking'][contract_code] = {
        'max_profit_pct': float(old.get('max_profit_pct', 0.0) or 0.0),
        'trailing_stop_price': float(after_overall),
        'last_update_time': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }

def check_stop_conditions(ContextInfo, current_price, contract_code):
    """
    检查止损止盈条件 - 主要止损止盈方式（含移动止损 + 20日均线止损）
    每日检查当前持仓的止损止盈情况，符合条件时执行平仓
    
    【重要逻辑说明】：
    1. 更新最大盈利记录：当天盈利 > 历史最大盈利时，更新记录但不平仓
    2. 计算移动止损价格：基于历史最大盈利动态调整止损价格
    3. 【新增】20日均线止损：多仓价格跌破20日均线平仓，空仓价格涨破20日均线平仓
    4. 检查平仓条件：触发任一止损/止盈条件时平仓
    5. 主要依靠移动止损保护利润，固定止盈设置得很高(50%)作为极端保护
    6. 【新增】支持分层退出逻辑：当有加仓时，每个仓位层独立计算和退出
    """
    G['logger'].info(f"\n========== 止损止盈检查 (含移动止损 + 20日均线止损) ==========")
    G['logger'].info(f"💡 逻辑：盈利创新高→更新记录→调整移动止损→检查20日均线→检查平仓条件")
    
    # 检查是否有持仓记录
    if contract_code not in G['open_positions']:
        G['logger'].warning(f"⚠️ 合约 {contract_code} 无持仓记录，可能是持仓同步异常")
        G['logger'].warning(f"当前所有持仓记录: {list(G['open_positions'].keys())}")
        G['logger'].warning(f"建议检查API状态或手动验证持仓")
        return
    
    position = G['open_positions'][contract_code]

    today_key = get_context_datetime(ContextInfo).strftime('%Y%m%d')
    if position.get('pending_close_day') == today_key:
        G['logger'].warning(f"⚠️ 合约 {contract_code} 当日已提交过平仓指令，等待回报/同步确认")
        return
    
    # 确保必要的字段存在，如果不存在则提供默认值
    avg_price = position.get('avg_price', position.get('price', 0))
    initial_price = position.get('initial_price', position.get('price', avg_price))
    direction = position.get('direction', '')
    total_volume = position.get('total_volume') or position.get('volume') or 0
    original_volume = position.get('volume') or total_volume
    add_positions = position.get('add_positions') or []
    if not isinstance(add_positions, list):
        add_positions = []
        position['add_positions'] = add_positions
    donchian_add_positions = _get_donchian_add_positions(position, create=True)
    add_count = position.get('add_count')
    if add_count is None:
        add_count = len(add_positions)
    donchian_add_count = position.get('donchian_add_count')
    if donchian_add_count is None:
        donchian_add_count = len(donchian_add_positions)
    
    # 如果缺少avg_price字段，使用price字段作为后备
    if 'avg_price' not in position:
        position['avg_price'] = avg_price
        G['logger'].warning(f"⚠️ 持仓记录缺少'avg_price'字段，使用'price'字段作为后备: {avg_price:.2f}")

    # 如果缺少initial_price字段，使用price字段作为后备
    if 'initial_price' not in position:
        position['initial_price'] = initial_price
        G['logger'].warning(f"⚠️ 持仓记录缺少'initial_price'字段，使用'price'字段作为后备: {initial_price:.2f}")
    
    # 如果缺少total_volume字段，使用volume字段作为后备
    if 'total_volume' not in position:
        position['total_volume'] = total_volume
        G['logger'].warning(f"⚠️ 持仓记录缺少'total_volume'字段，使用'volume'字段作为后备: {total_volume}")
    
    # 如果缺少add_positions字段，添加默认值
    if 'add_positions' not in position:
        position['add_positions'] = []
        G['logger'].warning("⚠️ 持仓记录缺少'add_positions'字段，添加默认空列表")
    
    # 如果缺少add_count字段，添加默认值
    if 'add_count' not in position:
        position['add_count'] = 0
        G['logger'].warning("⚠️ 持仓记录缺少'add_count'字段，添加默认值0")
    if 'donchian_add_count' not in position:
        position['donchian_add_count'] = len(donchian_add_positions)
    total_volume, avg_price = _recalculate_position_totals(position)
    add_positions = position.get('add_positions') or []
    donchian_add_positions = _get_donchian_add_positions(position, create=True)
    original_volume = int(position.get('volume') or 0)
    
    G['logger'].info(f"合约 {contract_code} 持仓方向: {direction}, 初始成本价: {initial_price:.2f}, 加权平均成本价: {avg_price:.2f}, 当前价: {current_price:.2f}")
    G['logger'].info(
        f"总持仓手数: {total_volume}手 (初始:{original_volume}手, 旧加仓:{len(add_positions)}次, 唐奇安加仓:{len(donchian_add_positions)}次)"
    )
    
    # ========== 检查是否满足加仓条件 ==========
    if G.get('enable_add_position', False):
        today_key = get_context_datetime(ContextInfo).strftime('%Y%m%d')
        last_add_key = G.get('last_add_date', {}).get(contract_code)
        if last_add_key == today_key:
            G['logger'].info(f"[ADD] {contract_code} 已在{today_key}加仓过，跳过当日重复加仓")
        else:
            can_add, add_type = check_add_position_conditions(ContextInfo, current_price, contract_code)
            if can_add:
                G['logger'].info(f"🎉 满足{add_type}加仓条件，执行加仓操作")
                add_ok = execute_add_position(ContextInfo, current_price, contract_code, add_type)
                G['logger'].info(f"[ADD] {contract_code} 加仓执行结果: ok={add_ok}")
                if add_ok:
                    if 'last_add_date' not in G or not isinstance(G.get('last_add_date'), dict):
                        G['last_add_date'] = {}
                    G['last_add_date'][contract_code] = today_key
                # 更新position变量以获取最新的持仓信息
                position = G['open_positions'][contract_code]
                total_volume = position['total_volume']
                add_count = position['add_count']
            else:
                G['logger'].info(f"[ADD] {contract_code} 当日不满足加仓条件")
    
    required_count = G['ma_long'] + 5

    if ContextInfo.do_back_test:
        current_timetag = ContextInfo.get_bar_timetag(ContextInfo.barpos)
        current_date = datetime.datetime.fromtimestamp(current_timetag/1000).strftime("%Y%m%d")
        market_data = ContextInfo.get_market_data_ex(
            fields=['close', 'high', 'low'],
            stock_code=[contract_code],
            period=G['period'],
            end_time=current_date,
            count=required_count,
            dividend_type='front_ratio',
            subscribe=False
        )
    else:
        market_data = ContextInfo.get_market_data_ex(
            fields=['close', 'high', 'low'],
            stock_code=[contract_code],
            period=G['period'],
            count=required_count,
            dividend_type='front_ratio',
            subscribe=True
        )

    if contract_code in market_data and not market_data[contract_code].empty:
        close_prices = market_data[contract_code]['close']
        ma_20 = close_prices.rolling(window=G['ma_long']).mean().iloc[-1]
        G['logger'].info(f"合约 {contract_code} 当前20日均线: {ma_20:.2f}")
    else:
        G['logger'].warning(f"❌ 无法获取{contract_code}的20日均线数据，跳过均线止损检查")
        ma_20 = None
        market_data = None

    if market_data is not None and contract_code in market_data and not market_data[contract_code].empty:
        if G.get('enable_donchian_add_position', False):
            can_don_add, don_add_type, don_breakout = check_donchian_add_position_conditions(
                ContextInfo,
                current_price,
                contract_code,
                market_data_df=market_data[contract_code]
            )
            if can_don_add:
                add_ok = execute_donchian_add_position(
                    ContextInfo,
                    current_price,
                    contract_code,
                    don_add_type,
                    market_data_df=market_data[contract_code],
                    breakout_info=don_breakout
                )
                G['logger'].info(f"[DON-ADD] {contract_code} 唐奇安加仓执行结果: ok={add_ok}")
                if add_ok and contract_code in G.get('open_positions', {}):
                    position = G['open_positions'][contract_code]
                    total_volume, avg_price = _recalculate_position_totals(position)
                    add_positions = position.get('add_positions') or []
                    donchian_add_positions = _get_donchian_add_positions(position, create=True)
    
    tracking_info = G['max_profit_tracking'].get(contract_code)

    atr_mid_stop = None
    try:
        if G.get('atr_2x_mid_stop_enabled', False) and market_data is not None and contract_code in market_data and not market_data[contract_code].empty:
            _md = market_data[contract_code]
            if ('high' in _md.columns) and ('low' in _md.columns) and ('close' in _md.columns) and len(_md) >= 15:
                _h = pd.to_numeric(_md['high'], errors='coerce')
                _l = pd.to_numeric(_md['low'], errors='coerce')
                _c = pd.to_numeric(_md['close'], errors='coerce')
                _pc = _c.shift(1)
                _tr = pd.concat([(_h - _l).abs(), (_h - _pc).abs(), (_l - _pc).abs()], axis=1).max(axis=1)
                _atr = _tr.rolling(14).mean()
                _atr_last = float(_atr.iloc[-1]) if _atr is not None and len(_atr) > 0 else None
                _c_last = float(_c.iloc[-1])
                _c_prev = float(_c.iloc[-2])
                _h_last = float(_h.iloc[-1])
                _l_last = float(_l.iloc[-1])
                if (
                    _atr_last is not None
                    and math.isfinite(_atr_last)
                    and _atr_last > 0
                    and math.isfinite(_c_last)
                    and math.isfinite(_c_prev)
                    and math.isfinite(_h_last)
                    and math.isfinite(_l_last)
                ):
                    _move = abs(_c_last - _c_prev)
                    if _move >= 2.0 * _atr_last:
                        atr_mid_stop = 0.5 * (_h_last + _l_last)
                        if math.isfinite(float(atr_mid_stop)):
                            G['logger'].info(f"📌 2ATR触发：|Δclose|={_move:.2f} >= 2*ATR14={2.0*_atr_last:.2f}，移动止损移至当日中间价={atr_mid_stop:.2f}")
    except Exception:
        atr_mid_stop = None

    if atr_mid_stop is not None and G.get('atr_2x_mid_stop_enabled', False):
        try:
            _bp = _get_barpos(ContextInfo)
        except Exception:
            _bp = -1

        try:
            _sl_pct = float(G.get('stop_loss_pct', 0.02) or 0.02)
        except Exception:
            _sl_pct = 0.02

        init_ts = position.get('initial_layer_trailing_stop_price')
        if init_ts is None:
            init_ts = float(initial_price) * (1 - _sl_pct) if direction == 'long' else float(initial_price) * (1 + _sl_pct)
        try:
            init_ts = float(init_ts)
        except Exception:
            init_ts = float(initial_price) * (1 - _sl_pct) if direction == 'long' else float(initial_price) * (1 + _sl_pct)

        new_init_ts = max(init_ts, float(atr_mid_stop)) if direction == 'long' else min(init_ts, float(atr_mid_stop))
        if abs(float(new_init_ts) - float(init_ts)) > 1e-9:
            position['initial_layer_trailing_stop_price'] = float(new_init_ts)
            _append_trailing_stop_trace(position, 'initial', today_key, _bp, float(new_init_ts), f"2ATR触发 止损移至中间价 {float(atr_mid_stop):.2f}")

        try:
            _aps = position.get('add_positions') or []
        except Exception:
            _aps = []
        if isinstance(_aps, list) and _aps:
            for _i, _ap in enumerate(_aps):
                try:
                    _ap_price = float(_ap.get('price', 0) or 0)
                except Exception:
                    _ap_price = 0.0
                ap_ts = _ap.get('trailing_stop_price')
                if ap_ts is None:
                    ap_ts = _ap_price * (1 - _sl_pct) if direction == 'long' else _ap_price * (1 + _sl_pct)
                try:
                    ap_ts = float(ap_ts)
                except Exception:
                    ap_ts = _ap_price * (1 - _sl_pct) if direction == 'long' else _ap_price * (1 + _sl_pct)

                new_ap_ts = max(ap_ts, float(atr_mid_stop)) if direction == 'long' else min(ap_ts, float(atr_mid_stop))
                if abs(float(new_ap_ts) - float(ap_ts)) > 1e-9:
                    _ap['trailing_stop_price'] = float(new_ap_ts)
                    _append_trailing_stop_trace(position, f"add_{_i+1}", today_key, _bp, float(new_ap_ts), f"2ATR触发 止损移至中间价 {float(atr_mid_stop):.2f}")

        _vals = []
        try:
            _vals.append(float(position.get('initial_layer_trailing_stop_price')))
        except Exception:
            pass
        for _ap in (position.get('add_positions') or []):
            try:
                _vals.append(float(_ap.get('trailing_stop_price')))
            except Exception:
                pass
        if _vals:
            overall_ts = max(_vals) if direction == 'long' else min(_vals)
            prev_overall = position.get('overall_trailing_stop_price')
            try:
                prev_overall_f = float(prev_overall) if prev_overall is not None else None
            except Exception:
                prev_overall_f = None
            position['overall_trailing_stop_price'] = float(overall_ts)
            if prev_overall_f is None or abs(float(overall_ts) - float(prev_overall_f)) > 1e-9:
                _append_trailing_stop_trace(position, 'overall', today_key, _bp, float(overall_ts), f"2ATR触发 止损移至中间价 {float(atr_mid_stop):.2f}")
            if 'max_profit_tracking' not in G:
                G['max_profit_tracking'] = {}
            old_track = G['max_profit_tracking'].get(contract_code, {})
            G['max_profit_tracking'][contract_code] = {
                'max_profit_pct': float(old_track.get('max_profit_pct', 0.0) or 0.0),
                'trailing_stop_price': float(overall_ts),
                'last_update_time': get_context_datetime(ContextInfo).strftime('%Y-%m-%d %H:%M:%S')
            }
    
    # 存储每个仓位层的盈亏信息
    layer_pnl_info = []
    
    # 计算初始仓位的盈亏（使用初始开仓价，而非加权均价）
    if direction == 'long':
        initial_pnl_pct = (current_price - initial_price) / initial_price
    else:  # short
        initial_pnl_pct = (initial_price - current_price) / initial_price
    
    layer_pnl_info.append({
        'type': 'initial',
        'price': initial_price,
        'volume': original_volume,
        'pnl_pct': initial_pnl_pct
    })
    
    # 计算加仓仓位的盈亏
    for i, add_pos in enumerate(add_positions):
        add_price = add_pos['price']
        add_volume = add_pos['volume']
        if direction == 'long':
            add_pnl_pct = (current_price - add_price) / add_price
        else:  # short
            add_pnl_pct = (add_price - current_price) / add_price
        
        layer_pnl_info.append({
            'type': f'add_{i+1}',
            'price': add_price,
            'volume': add_volume,
            'pnl_pct': add_pnl_pct
        })
    
    for layer_info in layer_pnl_info:
        layer_type = layer_info['type']
        layer_pnl_pct = float(layer_info.get('pnl_pct', 0) or 0)
        stored_max = 0.0
        if layer_type == 'initial':
            try:
                stored_max = float(position.get('initial_layer_max_profit_pct', 0.0) or 0.0)
            except Exception:
                stored_max = 0.0
            if layer_pnl_pct > stored_max:
                stored_max = layer_pnl_pct
                position['initial_layer_max_profit_pct'] = stored_max
        elif layer_type.startswith('add_'):
            try:
                layer_idx = int(layer_type.split('_')[1]) - 1
            except Exception:
                layer_idx = -1
            if 0 <= layer_idx < len(add_positions):
                ap_ref = add_positions[layer_idx]
                try:
                    stored_max = float(ap_ref.get('max_profit_pct', 0.0) or 0.0)
                except Exception:
                    stored_max = 0.0
                if layer_pnl_pct > stored_max:
                    stored_max = layer_pnl_pct
                    ap_ref['max_profit_pct'] = stored_max
        drawdown_from_peak = stored_max - layer_pnl_pct
        if drawdown_from_peak < 0:
            drawdown_from_peak = 0.0
        layer_info['max_profit_pct'] = float(stored_max)
        layer_info['drawdown_from_peak_pct'] = float(drawdown_from_peak)

    try:
        _now_dt = get_context_datetime(ContextInfo)
        _bt_date = _now_dt.strftime('%Y%m%d')
        _ts = _now_dt.strftime('%Y-%m-%d %H:%M:%S')
    except Exception:
        _bt_date = None
        _ts = None
    _log_structured('POSITION_LAYER', {
        'bt_date': _bt_date,
        'ts': _ts,
        'barpos': int(getattr(ContextInfo, 'barpos', -1)) if ContextInfo is not None else -1,
        'do_back_test': bool(getattr(ContextInfo, 'do_back_test', False)) if ContextInfo is not None else False,
        'contract': contract_code,
        'direction': direction,
        'cur': float(current_price),
        'avg_price': float(avg_price),
        'initial_price': float(initial_price),
        'ma20': float(ma_20) if ma_20 is not None else None,
        'layers': [
            {
                'type': x.get('type'),
                'price': float(x.get('price', 0) or 0),
                'volume': int(x.get('volume', 0) or 0),
                'pnl_pct': float(x.get('pnl_pct', 0) or 0),
                'max_profit_pct': float(x.get('max_profit_pct', 0) or 0),
                'drawdown_from_peak_pct': float(x.get('drawdown_from_peak_pct', 0) or 0)
            }
            for x in (layer_pnl_info or [])
        ],
        'risk': _risk_snapshot(ContextInfo)
    })

    for layer_info in layer_pnl_info:
        G['logger'].info(
            f"合约 {contract_code} {layer_info['type']}层仓位: 成本价{float(layer_info['price']):.2f}, "
            f"手数{int(layer_info['volume'])}手, 盈亏{float(layer_info['pnl_pct'])*100:.2f}%"
        )

    if direction == 'long':
        position_pnl_pct = (current_price - avg_price) / avg_price if avg_price else 0.0
    else:
        position_pnl_pct = (avg_price - current_price) / avg_price if avg_price else 0.0

    close_reason = ""
    close_mode = None
    close_type = None
    close_volume = 0
    entry_day_stop_price = None
    try:
        md_df = market_data.get(contract_code) if market_data else None
    except Exception:
        md_df = None
    entry_day_stop_price = calculate_entry_day_stop_price(md_df, position.get('entry_date'), direction)
    current_rsi_stop = None
    try:
        _rsi_period = int(G.get('rsi_overheat_reduce_period', 6) or 6)
    except Exception:
        _rsi_period = 6
    if md_df is not None and len(md_df) >= max(_rsi_period, 2):
        try:
            _rsi_res = calculate_multi_period_rsi(md_df['close'], periods=[_rsi_period])
            if _rsi_res:
                current_rsi_stop = float(_rsi_res.get(f'rsi_{_rsi_period}', 50))
        except Exception:
            current_rsi_stop = None

    if close_mode is None and bool(G.get('profit_3bar_stop_enabled', False)):
        stop_price = calculate_prev2day_stop_price(
            market_data.get(contract_code) if market_data else None,
            position.get('entry_date'),
            direction
        )
        if stop_price is not None:
            prev_stop = position.get('overall_prev2day_stop_price')
            try:
                prev_stop_f = float(prev_stop) if prev_stop is not None else None
            except Exception:
                prev_stop_f = None
            stop_price_f = float(stop_price)
            if direction == 'long':
                final_stop = stop_price_f if prev_stop_f is None else max(prev_stop_f, stop_price_f)
                if float(current_price) <= float(final_stop):
                    close_mode = 'full'
                    close_type = 'p3'
                    close_volume = int(total_volume)
                    close_reason = f"合约 {contract_code} 多头前两日止损全平 (收盘价{current_price:.2f} <= 前两日最低价{final_stop:.2f})"
            else:
                final_stop = stop_price_f if prev_stop_f is None else min(prev_stop_f, stop_price_f)
                if float(current_price) >= float(final_stop):
                    close_mode = 'full'
                    close_type = 'p3'
                    close_volume = int(total_volume)
                    close_reason = f"合约 {contract_code} 空头前两日止损全平 (收盘价{current_price:.2f} >= 前两日最高价{final_stop:.2f})"
            position['overall_prev2day_stop_price'] = float(final_stop)

    if close_mode is None and entry_day_stop_price is not None:
        if direction == 'long' and float(current_price) <= float(entry_day_stop_price):
            close_mode = 'full'
            close_type = 'base_stop'
            close_volume = int(total_volume)
            close_reason = f"合约 {contract_code} 多头开仓日低点止损全平 (当前价{current_price:.2f} <= 开仓日最低价{entry_day_stop_price:.2f})"
        elif direction == 'short' and float(current_price) >= float(entry_day_stop_price):
            close_mode = 'full'
            close_type = 'base_stop'
            close_volume = int(total_volume)
            close_reason = f"合约 {contract_code} 空头开仓日高点止损全平 (当前价{current_price:.2f} >= 开仓日最高价{entry_day_stop_price:.2f})"

    if close_mode is None and direction == 'long' and bool(G.get('rsi_overheat_reduce_enabled', False)):
        try:
            _rsi_threshold = float(G.get('rsi_overheat_reduce_threshold', 95) or 95)
        except Exception:
            _rsi_threshold = 95.0
        _reduced_today = str(position.get('rsi_overheat_reduce_day') or '')
        if current_rsi_stop is not None and current_rsi_stop > _rsi_threshold and str(_bt_date or '') != _reduced_today:
            close_mode = 'half'
            close_type = 'rsi_overheat'
            close_volume = max(1, (int(total_volume) + 1) // 2)
            close_reason = f"合约 {contract_code} 多头RSI超热减仓一半 (RSI({_rsi_period})={current_rsi_stop:.2f} > {_rsi_threshold:.2f})"
            if _bt_date:
                position['rsi_overheat_reduce_day'] = str(_bt_date)

    if close_mode is None and bool(G.get('trailing_stop_enabled', False)):
        overall_ts = position.get('overall_trailing_stop_price')
        try:
            overall_ts_f = float(overall_ts) if overall_ts is not None else None
        except Exception:
            overall_ts_f = None
        if overall_ts_f is not None:
            if direction == 'long' and float(current_price) <= float(overall_ts_f):
                close_mode = 'full'
                close_type = 'trailing'
                close_volume = int(total_volume)
                close_reason = f"合约 {contract_code} 多头移动止损全平 (当前价{current_price:.2f} <= 移动止损价{overall_ts_f:.2f})"
            elif direction == 'short' and float(current_price) >= float(overall_ts_f):
                close_mode = 'full'
                close_type = 'trailing'
                close_volume = int(total_volume)
                close_reason = f"合约 {contract_code} 空头移动止损全平 (当前价{current_price:.2f} >= 移动止损价{overall_ts_f:.2f})"

    if close_mode is None and ma_20 is not None:
        if direction == 'long' and current_price < ma_20:
            close_mode = 'full'
            close_type = 'ma20'
            close_volume = int(total_volume)
            close_reason = f"合约 {contract_code} 多头20日均线止损全平 (当前价{current_price:.2f} < 20日均线{ma_20:.2f})"
        elif direction == 'short' and current_price > ma_20:
            close_mode = 'full'
            close_type = 'ma20'
            close_volume = int(total_volume)
            close_reason = f"合约 {contract_code} 空头20日均线止损全平 (当前价{current_price:.2f} > 20日均线{ma_20:.2f})"

    if close_mode is None:
        md_df_for_don = market_data.get(contract_code) if market_data else None
        if check_donchian_add_stop_conditions(ContextInfo, current_price, contract_code, market_data_df=md_df_for_don):
            return

    if close_mode is not None and close_volume > 0:
        G['logger'].info(f"🚨 触发平仓条件: {close_reason}")
        contract_info = get_contract_info(ContextInfo, contract_code)
        volume_multiple = contract_info.get('VolumeMultiple', 10)
        case_key = position.get('open_reason', 'unknown')
        realized_entry_price = float(avg_price)
        op_type = 6 if direction == 'long' else 8
        layer_tag = 'full' if close_mode == 'full' else 'half'
        remark = f"期货多空排布策略-平{'多' if direction == 'long' else '空'}-{layer_tag}"

        order_id = smart_passorder(
            op_type,
            1101,
            G['accountid'],
            contract_code,
            current_price,
            int(close_volume),
            remark,
            2,
            close_reason,
            ContextInfo,
            extra={
                'action': 'close',
                'contract': contract_code,
                'direction': direction,
                'layer': layer_tag,
                'reason': close_reason,
                'entry_price': float(realized_entry_price),
                'exit_price': float(current_price),
                'volume': int(close_volume),
                'pnl_pct': float(position_pnl_pct),
                'case': case_key,
            }
        )
        if order_id <= 0:
            G['logger'].error(f"❌ 平仓订单提交失败: mode={close_mode}, order_id={order_id}")
            return

        G['logger'].info(f"✅ 平仓订单提交成功: mode={close_mode}, order_id={order_id}, volume={close_volume}")

        if getattr(ContextInfo, 'do_back_test', False) and G.get('enable_trade_kline_dump', False):
            _exit_barpos = _get_barpos(ContextInfo)
            _use_cache = bool(G.get('use_kline_cache', False))
            try:
                _entry_barpos_i = int(position.get('entry_barpos')) if position.get('entry_barpos') is not None else None
            except Exception:
                _entry_barpos_i = None
            if _entry_barpos_i is not None and _entry_barpos_i >= 0:
                _schedule_trade_kline_dump({
                    'trade_id': position.get('trade_id'),
                    'root_trade_id': position.get('root_trade_id', position.get('trade_id')),
                    'contract_code': contract_code,
                    'base_code': _base_code_from_contract(contract_code),
                    'layer': f"overall_{close_mode}",
                    'direction': direction,
                    'entry_price': float(realized_entry_price),
                    'exit_price': float(current_price),
                    'pos_volume': int(close_volume),
                    'volume_multiple': float(volume_multiple),
                    'close_reason': close_reason,
                    'sizing_stop_price': position.get('sizing_stop_price'),
                    'sizing_stop_source': position.get('sizing_stop_source'),
                    'entry_signal_source': position.get('entry_signal_source'),
                    'pending_breakout_created_date': position.get('pending_breakout_created_date'),
                    'pending_breakout_wait_days': position.get('pending_breakout_wait_days'),
                    'entry_date': position.get('entry_date'),
                    'exit_date': today_key,
                    'entry_barpos': _entry_barpos_i,
                    'exit_barpos': _exit_barpos,
                    'pre_days': int((G.get('kline_pre_days_cache') if _use_cache else G.get('kline_pre_days')) or 20),
                    'post_days': int((G.get('kline_post_days_cache') if _use_cache else G.get('kline_post_days')) or 20),
                    'layer_trailing_stop_trace': position.get('layer_trailing_stop_trace'),
                    'visual_snapshot_only': True,
                })

                # 无论是全平还是减半，都把当前的 initial 和 add_x 状态导出，防止减仓导致加仓记录丢失
                _schedule_trade_kline_dump({
                    'trade_id': position.get('trade_id'),
                    'root_trade_id': position.get('root_trade_id', position.get('trade_id')),
                    'contract_code': contract_code,
                    'base_code': _base_code_from_contract(contract_code),
                    'layer': 'initial',
                    'direction': direction,
                    'entry_price': float(position.get('initial_price', position.get('price', 0)) or 0),
                    'exit_price': float(current_price),
                    'pos_volume': int(position.get('volume', close_volume) or 0),
                    'volume_multiple': float(volume_multiple),
                    'close_reason': close_reason,
                    'sizing_stop_price': position.get('sizing_stop_price'),
                    'sizing_stop_source': position.get('sizing_stop_source'),
                    'entry_signal_source': position.get('entry_signal_source'),
                    'pending_breakout_created_date': position.get('pending_breakout_created_date'),
                    'pending_breakout_wait_days': position.get('pending_breakout_wait_days'),
                    'entry_date': position.get('entry_date'),
                    'exit_date': today_key,
                    'entry_barpos': _entry_barpos_i,
                    'exit_barpos': _exit_barpos,
                    'pre_days': int((G.get('kline_pre_days_cache') if _use_cache else G.get('kline_pre_days')) or 20),
                    'post_days': int((G.get('kline_post_days_cache') if _use_cache else G.get('kline_post_days')) or 20),
                    'layer_trailing_stop_trace': position.get('layer_trailing_stop_trace'),
                    'visual_snapshot_only': True,
                })
                
                _aps = position.get('add_positions') or []
                if isinstance(_aps, list):
                    for _i, _ap in enumerate(_aps):
                        try:
                            _ap_entry_barpos = int(_ap.get('barpos'))
                        except Exception:
                            _ap_entry_barpos = None
                        if _ap_entry_barpos is None or _ap_entry_barpos < 0:
                            continue
                        _schedule_trade_kline_dump({
                            'trade_id': _ap.get('trade_id'),
                            'root_trade_id': position.get('root_trade_id', position.get('trade_id')),
                            'contract_code': contract_code,
                            'base_code': _base_code_from_contract(contract_code),
                            'layer': f"add_{_i+1}",
                            'direction': direction,
                            'entry_price': float(_ap.get('price', 0) or 0),
                            'exit_price': float(current_price),
                            'pos_volume': int(_ap.get('volume', 0) or 0),
                            'volume_multiple': float(volume_multiple),
                            'close_reason': close_reason,
                            'sizing_stop_price': _ap.get('sizing_stop_price', _ap.get('trailing_stop_price')),
                            'sizing_stop_source': _ap.get('sizing_stop_source') or 'add_layer_stop',
                            'entry_signal_source': position.get('entry_signal_source'),
                            'pending_breakout_created_date': position.get('pending_breakout_created_date'),
                            'pending_breakout_wait_days': position.get('pending_breakout_wait_days'),
                            'entry_date': _ap.get('date'),
                            'exit_date': today_key,
                            'entry_barpos': _ap_entry_barpos,
                            'exit_barpos': _exit_barpos,
                            'pre_days': int((G.get('kline_pre_days_cache') if _use_cache else G.get('kline_pre_days')) or 20),
                            'post_days': int((G.get('kline_post_days_cache') if _use_cache else G.get('kline_post_days')) or 20),
                            'layer_trailing_stop_trace': position.get('layer_trailing_stop_trace'),
                            'visual_snapshot_only': True,
                        })

                _don_aps = _get_donchian_add_positions(position, create=False)
                if isinstance(_don_aps, list):
                    for _i, _ap in enumerate(_don_aps):
                        try:
                            _ap_entry_barpos = int(_ap.get('barpos'))
                        except Exception:
                            _ap_entry_barpos = None
                        if _ap_entry_barpos is None or _ap_entry_barpos < 0:
                            continue
                        _schedule_trade_kline_dump({
                            'trade_id': _ap.get('trade_id'),
                            'root_trade_id': position.get('root_trade_id', position.get('trade_id')),
                            'contract_code': contract_code,
                            'base_code': _base_code_from_contract(contract_code),
                            'layer': str(_ap.get('type') or f"donchian_add_{_i+1}"),
                            'direction': direction,
                            'entry_price': float(_ap.get('price', 0) or 0),
                            'exit_price': float(current_price),
                            'pos_volume': int(_ap.get('volume', 0) or 0),
                            'volume_multiple': float(volume_multiple),
                            'close_reason': close_reason,
                            'sizing_stop_price': _ap.get('trailing_stop_price'),
                            'sizing_stop_source': 'donchian_add_stop',
                            'entry_signal_source': position.get('entry_signal_source'),
                            'pending_breakout_created_date': position.get('pending_breakout_created_date'),
                            'pending_breakout_wait_days': position.get('pending_breakout_wait_days'),
                            'entry_date': _ap.get('date'),
                            'exit_date': today_key,
                            'entry_barpos': _ap_entry_barpos,
                            'exit_barpos': _exit_barpos,
                            'pre_days': int((G.get('kline_pre_days_cache') if _use_cache else G.get('kline_pre_days')) or 20),
                            'post_days': int((G.get('kline_post_days_cache') if _use_cache else G.get('kline_post_days')) or 20),
                            'layer_trailing_stop_trace': position.get('layer_trailing_stop_trace'),
                            'visual_snapshot_only': True,
                        })

        if close_type == 'ma20':
            G['ma_stop_count'] = G.get('ma_stop_count', 0) + 1
        elif close_type == 'trailing':
            G['trailing_stop_count'] = G.get('trailing_stop_count', 0) + 1
        elif close_type == 'base_stop':
            G['stop_loss_count'] = G.get('stop_loss_count', 0) + 1

        if not ContextInfo.do_back_test:
            position['pending_close_day'] = today_key
            position['pending_close_reason'] = close_reason
            save_strategy_data()
            return

        if direction == 'long':
            realized_pnl = (current_price - realized_entry_price) * int(close_volume) * volume_multiple
        else:
            realized_pnl = (realized_entry_price - current_price) * int(close_volume) * volume_multiple

        if close_type == 'p3':
            G['stop_profit_count'] += 1

        if realized_pnl >= 0:
            G['num_winning_trades'] += 1
            G['gross_profit'] += realized_pnl
            G['best_trade_pnl'] = max(G['best_trade_pnl'], realized_pnl)
        else:
            G['num_losing_trades'] += 1
            G['gross_loss_abs'] += -realized_pnl
            G['worst_trade_pnl'] = min(G['worst_trade_pnl'], realized_pnl)

        G['total_realized_pnl'] += realized_pnl
        G['closed_trades'] += 1
        _update_streak_risk_state_on_close(realized_pnl)
        G['logger'].info(f"📈 本次平仓盈亏({close_mode}): {realized_pnl:+.2f}元")
        G['logger'].info(f"📊 累计平仓盈亏: {G['total_realized_pnl']:+.2f}元")

        last_equity = G['equity_curve'][-1] if G.get('equity_curve') else 0.0
        G['equity_curve'].append(last_equity + realized_pnl)

        if case_key not in G['case_stats']:
            G['case_stats'][case_key] = {
                'trades': 0,
                'wins': 0,
                'losses': 0,
                'gross_profit': 0.0,
                'gross_loss_abs': 0.0
            }
        cs = G['case_stats'][case_key]
        cs['trades'] += 1
        if realized_pnl >= 0:
            cs['wins'] += 1
            cs['gross_profit'] += realized_pnl
        else:
            cs['losses'] += 1
            cs['gross_loss_abs'] += -realized_pnl

        if contract_code not in G['open_positions']:
            return
        position = G['open_positions'][contract_code]

        reduced_volume = _reduce_position_volume(position, int(close_volume))
        remaining_total = int(position.get('total_volume', 0) or 0)
        if remaining_total > 0:
            G['logger'].info(
                f"📈 更新持仓记录: volume={position.get('volume', 0)}手, "
                f"total_volume={position.get('total_volume', 0)}手, add_count={position.get('add_count', 0)}, "
                f"donchian_add_count={position.get('donchian_add_count', 0)}, reduced={reduced_volume}"
            )
        else:
            del G['open_positions'][contract_code]
            if contract_code in G['max_profit_tracking']:
                del G['max_profit_tracking'][contract_code]
            G['logger'].info(f"🗑️  清除持仓记录和追踪记录: {contract_code}")
        save_strategy_data()
        return
    else:
        G['logger'].info(f"✅ 未触发止损止盈条件，继续持仓")
        if ma_20 is not None:
            if direction == 'long':
                ma_status = "安全" if current_price >= ma_20 else "警告"
                G['logger'].info(f"   20日均线状态: {ma_status} (当前价{current_price:.2f} vs 20日均线{ma_20:.2f})")
            else:
                ma_status = "安全" if current_price <= ma_20 else "警告"
                G['logger'].info(f"   20日均线状态: {ma_status} (当前价{current_price:.2f} vs 20日均线{ma_20:.2f})")
        if not G['trailing_stop_enabled']:
            G['logger'].info(f"   移动止损: 已禁用")

        if direction == 'long':
            pnl_pct = (current_price - avg_price) / avg_price
        else:
            pnl_pct = (avg_price - current_price) / avg_price
        G['logger'].info(f"合约 {contract_code} 持仓盈亏: {pnl_pct*100:.2f}% ({'多头' if direction == 'long' else '空头'})")

        if G['trailing_stop_enabled']:
            agg_max = 0.0
            agg_ts = None
            agg_updates = []
            for layer_info in layer_pnl_info:
                layer_type = layer_info['type']
                layer_price = layer_info['price']
                layer_pnl = layer_info['pnl_pct']
                if layer_type == 'initial':
                    layer_max = position.get('initial_layer_max_profit_pct', 0.0)
                    layer_ts = position.get('initial_layer_trailing_stop_price', layer_price * (1 - G['stop_loss_pct']) if direction == 'long' else layer_price * (1 + G['stop_loss_pct']))
                else:
                    layer_idx = int(layer_type.split('_')[1]) - 1
                    layer_max = 0.0
                    layer_ts = layer_price * (1 - G['stop_loss_pct']) if direction == 'long' else layer_price * (1 + G['stop_loss_pct'])
                    if layer_idx < len(add_positions):
                        ap_ref = add_positions[layer_idx]
                        layer_max = ap_ref.get('max_profit_pct', 0.0)
                        layer_ts = ap_ref.get('trailing_stop_price', layer_ts)

                if layer_pnl > layer_max:
                    layer_max = layer_pnl
                    _ts_reason = ""
                    if direction == 'long':
                        new_ts = layer_ts
                        if layer_max >= 0.30:
                            new_ts = max(new_ts, layer_price * 1.20)
                            agg_updates.append(f"{layer_type} max_profit>={30}% 锁定20%")
                            _ts_reason = "max_profit>=30% 锁定20%"
                        elif layer_max >= 0.20:
                            new_ts = max(new_ts, layer_price * 1.15)
                            agg_updates.append(f"{layer_type} max_profit>={20}% 锁定15%")
                            _ts_reason = "max_profit>=20% 锁定15%"
                        elif layer_max >= 0.10:
                            new_ts = max(new_ts, layer_price * 1.08)
                            agg_updates.append(f"{layer_type} max_profit>={10}% 锁定8%")
                            _ts_reason = "max_profit>=10% 锁定8%"
                        elif layer_max >= 0.05:
                            new_ts = max(new_ts, layer_price * 1.03)
                            agg_updates.append(f"{layer_type} max_profit>={5}% 锁定3%")
                            _ts_reason = "max_profit>=5% 锁定3%"
                        elif layer_max >= 0.03:
                            new_ts = max(new_ts, layer_price * 1.01)
                            agg_updates.append(f"{layer_type} max_profit>={3}% 锁定1%")
                            _ts_reason = "max_profit>=3% 锁定1%"
                        elif layer_max >= 0.02:
                            new_ts = max(new_ts, layer_price * 1.001)
                            agg_updates.append(f"{layer_type} max_profit>={2}% 锁定0.1%")
                            _ts_reason = "max_profit>=2% 锁定0.1%"
                    else:
                        new_ts = layer_ts
                        if layer_max >= 0.30:
                            new_ts = min(new_ts, layer_price * 0.80)
                            agg_updates.append(f"{layer_type} max_profit>={30}% 锁定20%")
                            _ts_reason = "max_profit>=30% 锁定20%"
                        elif layer_max >= 0.20:
                            new_ts = min(new_ts, layer_price * 0.85)
                            agg_updates.append(f"{layer_type} max_profit>={20}% 锁定15%")
                            _ts_reason = "max_profit>=20% 锁定15%"
                        elif layer_max >= 0.10:
                            new_ts = min(new_ts, layer_price * 0.92)
                            agg_updates.append(f"{layer_type} max_profit>={10}% 锁定8%")
                            _ts_reason = "max_profit>=10% 锁定8%"
                        elif layer_max >= 0.05:
                            new_ts = min(new_ts, layer_price * 0.97)
                            agg_updates.append(f"{layer_type} max_profit>={5}% 锁定3%")
                            _ts_reason = "max_profit>=5% 锁定3%"
                        elif layer_max >= 0.03:
                            new_ts = min(new_ts, layer_price * 0.99)
                            agg_updates.append(f"{layer_type} max_profit>={3}% 锁定1%")
                            _ts_reason = "max_profit>=3% 锁定1%"
                        elif layer_max >= 0.02:
                            new_ts = min(new_ts, layer_price * 0.999)
                            agg_updates.append(f"{layer_type} max_profit>={2}% 锁定0.1%")
                            _ts_reason = "max_profit>=2% 锁定0.1%"

                    try:
                        if abs(float(new_ts) - float(layer_ts)) > 1e-9 and _ts_reason:
                            _append_trailing_stop_trace(position, layer_type, today_key, _get_barpos(ContextInfo), float(new_ts), _ts_reason)
                    except Exception:
                        pass

                    if layer_type == 'initial':
                        position['initial_layer_max_profit_pct'] = layer_max
                        position['initial_layer_trailing_stop_price'] = new_ts
                    else:
                        if layer_idx < len(add_positions):
                            ap_ref = add_positions[layer_idx]
                            ap_ref['max_profit_pct'] = layer_max
                            ap_ref['trailing_stop_price'] = new_ts
                    layer_ts = new_ts

                agg_max = max(agg_max, layer_max)
                if direction == 'long':
                    if agg_ts is None or layer_ts > agg_ts:
                        agg_ts = layer_ts
                else:
                    if agg_ts is None or layer_ts < agg_ts:
                        agg_ts = layer_ts

            if agg_ts is not None:
                _prev_agg = None
                try:
                    _prev_agg = float(position.get('overall_trailing_stop_price')) if position.get('overall_trailing_stop_price') is not None else None
                except Exception:
                    _prev_agg = None
                try:
                    position['overall_trailing_stop_price'] = float(agg_ts)
                except Exception:
                    pass
                if _prev_agg is None or abs(float(agg_ts) - float(_prev_agg)) > 1e-9:
                    _append_trailing_stop_trace(position, 'overall', today_key, _get_barpos(ContextInfo), float(agg_ts), ' ; '.join(agg_updates) if agg_updates else '移动止损更新')
                if 'max_profit_tracking' not in G:
                    G['max_profit_tracking'] = {}
                G['max_profit_tracking'][contract_code] = {
                    'max_profit_pct': agg_max,
                    'trailing_stop_price': agg_ts,
                    'last_update_time': get_context_datetime(ContextInfo).strftime('%Y-%m-%d %H:%M:%S')
                }
                G['logger'].info(f"合约 {contract_code} 历史最大盈利: {agg_max*100:.2f}%")
                G['logger'].info(f"合约 {contract_code} 当前移动止损价: {agg_ts:.2f}")
                save_strategy_data()
        


def get_contract_info(ContextInfo, contract_code):
    """获取合约信息 - 简化版本，直接使用QMT API获取"""
    contract_info = None
    try:
        contract_info = ContextInfo.get_instrumentdetail(contract_code)
    except Exception as e:
        G['logger'].warning(f"⚠️ 获取合约信息异常，跳过: {contract_code} ({e})")
        return None

    if contract_info:
        G['logger'].info("✅ 成功获取合约信息:")

        volume_multiple = _dict_get_first(contract_info, ['VolumeMultiple', 'volumemultiple', 'volume_multiple'], 10)
        price_tick = _dict_get_first(contract_info, ['PriceTick', 'pricetick', 'price_tick'], 1)
        instrument_name = _dict_get_first(contract_info, ['InstrumentName', 'instrumentname', 'Instrumentname', 'name'], contract_code)
        long_margin_ratio = _dict_get_first(contract_info, ['LongMarginRatio', 'longmarginratio', 'LongMargin', 'long_margin_ratio'], 0.1)
        short_margin_ratio = _dict_get_first(contract_info, ['ShortMarginRatio', 'shortmarginratio', 'ShortMargin', 'short_margin_ratio'], 0.1)

        try:
            volume_multiple = float(volume_multiple) if volume_multiple is not None else 10.0
        except Exception:
            volume_multiple = 10.0
        try:
            price_tick = float(price_tick) if price_tick is not None else 1.0
        except Exception:
            price_tick = 1.0
        instrument_name = instrument_name if instrument_name else contract_code
        try:
            long_margin_ratio = float(long_margin_ratio) if long_margin_ratio is not None else 0.1
        except Exception:
            long_margin_ratio = 0.1
        try:
            short_margin_ratio = float(short_margin_ratio) if short_margin_ratio is not None else 0.1
        except Exception:
            short_margin_ratio = 0.1

        G['logger'].info(f"  合约名称: {instrument_name}")
        G['logger'].info(f"  合约乘数: {volume_multiple}")
        G['logger'].info(f"  最小价格变动: {price_tick}")
        G['logger'].info(f"  多头保证金率: {long_margin_ratio*100:.2f}%")
        G['logger'].info(f"  空头保证金率: {short_margin_ratio*100:.2f}%")

        return {
            'VolumeMultiple': volume_multiple,
            'PriceTick': price_tick,
            'InstrumentName': instrument_name,
            'LongMarginRatio': long_margin_ratio,
            'ShortMarginRatio': short_margin_ratio,
            'contract_code': contract_code
        }
    else:
        G['logger'].warning(f"⚠️ 未获取到合约信息，跳过: {contract_code}")
        return None

def calculate_3day_low_stop_price(market_data, current_price, direction):
    """
    计算最近3天最低价-1%或多头最近3天最高价+1%的止损价格
    
    参数:
    - market_data: 市场数据
    - current_price: 当前价格
    - direction: 持仓方向 ('long' 或 'short')
    
    返回:
    - float: 止损价格
    """
    if market_data is not None and len(market_data) >= 4:
        recent_3_days = market_data.iloc[:-1].tail(3)

        if direction == 'long':
            min_low_3days = recent_3_days['low'].min()
            stop_price = min_low_3days * 0.99
            return stop_price
        elif direction == 'short':
            max_high_3days = recent_3_days['high'].max()
            stop_price = max_high_3days * 1.01
            return stop_price

    return None


def wick_chop_filter_ok(market_data_df, lookback=10, max_days=4):
    try:
        if market_data_df is None:
            return True, 0, 0
        try:
            lookback_i = int(lookback or 10)
        except Exception:
            lookback_i = 10
        try:
            max_days_i = int(max_days or 4)
        except Exception:
            max_days_i = 4
        if lookback_i < 1:
            lookback_i = 1
        df = market_data_df[['open', 'high', 'low', 'close']].tail(lookback_i)
        try:
            df = df.dropna()
        except Exception:
            pass
        n = len(df)
        if n < lookback_i:
            return True, 0, n
        count = 0
        for _, r in df.iterrows():
            o = float(r['open'])
            h = float(r['high'])
            l = float(r['low'])
            c = float(r['close'])
            body = abs(c - o)
            upper = h - max(o, c)
            lower = min(o, c) - l
            if upper > body or lower > body:
                count += 1
        return count <= max_days_i, int(count), n
    except Exception:
        return True, 0, 0


def calculate_prev2day_stop_price(market_data, entry_date, direction):
    try:
        if market_data is None or len(market_data) < 3:
            return None
        entry_key = str(entry_date or '').replace('-', '')[:8]
        if not entry_key or len(entry_key) != 8:
            return None
        idx = market_data.index
        dates = []
        for x in idx:
            try:
                if hasattr(x, 'strftime'):
                    dates.append(x.strftime('%Y%m%d'))
                else:
                    s = str(x)
                    s = s.replace('-', '')
                    dates.append(s[:8])
            except Exception:
                dates.append('')
        use_rows = [i for i, d in enumerate(dates) if d and d >= entry_key]
        if len(use_rows) < 3:
            return None
        recent = market_data.iloc[use_rows[-3:-1]]
        if direction == 'long':
            return float(recent['low'].min())
        if direction == 'short':
            return float(recent['high'].max())
        return None
    except Exception:
        return None


def calculate_entry_day_stop_price(market_data, entry_date, direction):
    try:
        if market_data is None or len(market_data) < 1:
            return None
        entry_key = str(entry_date or '').replace('-', '')[:8]
        if not entry_key or len(entry_key) != 8:
            return None
        idx = market_data.index
        target_rows = []
        for i, x in enumerate(idx):
            try:
                if hasattr(x, 'strftime'):
                    d = x.strftime('%Y%m%d')
                else:
                    s = str(x).replace('-', '')
                    d = s[:8]
            except Exception:
                d = ''
            if d == entry_key:
                target_rows.append(i)
        if not target_rows:
            return None
        day_df = market_data.iloc[target_rows]
        if direction == 'long':
            return float(day_df['low'].min())
        if direction == 'short':
            return float(day_df['high'].max())
        return None
    except Exception:
        return None


def is_simple_ma_trend(market_data_df, direction, ma_short=5, ma_mid=10, ma_long=20, ma_extra_long=40, slope_lookback=3):
    try:
        if market_data_df is None:
            return False
        need = int(ma_extra_long) + int(slope_lookback) + 2
        if len(market_data_df) < need:
            return False
        c = market_data_df['close']
        close_last = float(c.iloc[-1])

        ma_s = float(c.rolling(int(ma_short)).mean().iloc[-1])
        ma_m = float(c.rolling(int(ma_mid)).mean().iloc[-1])
        ma_l = float(c.rolling(int(ma_long)).mean().iloc[-1])
        ma_x = float(c.rolling(int(ma_extra_long)).mean().iloc[-1])

        ma_l_prev = float(c.rolling(int(ma_long)).mean().iloc[-1 - int(slope_lookback)])

        if direction == 'long':
            if not (ma_s > ma_m > ma_l > ma_x):
                return False
            if not (ma_l > ma_l_prev):
                return False
            if not (close_last > ma_l):
                return False
            return True

        if direction == 'short':
            if not (ma_s < ma_m < ma_l < ma_x):
                return False
            if not (ma_l < ma_l_prev):
                return False
            if not (close_last < ma_l):
                return False
            return True

        return False
    except Exception:
        return False


def get_ma_slope_direction(market_data_df, period=5):
    try:
        if market_data_df is None or len(market_data_df) < max(int(period or 5), 2) + 1:
            return 0.0
        close = market_data_df['close'].astype(float)
        ma = close.rolling(window=int(period or 5)).mean()
        if len(ma) < 2 or pd.isna(ma.iloc[-1]) or pd.isna(ma.iloc[-2]):
            return 0.0
        return float(ma.iloc[-1] - ma.iloc[-2])
    except Exception:
        return 0.0


def evaluate_ma5_angle_reversal_filter(market_data_df, period=5, lookback_days=10, angle_threshold_deg=30.0):
    result = {
        'should_block': False,
        'recent_angles': [],
        'matched_prev_angle': None,
        'matched_curr_angle': None,
        'threshold_deg': float(angle_threshold_deg or 30.0),
    }
    try:
        period_i = max(int(period or 5), 1)
        lookback_i = max(int(lookback_days or 10), 2)
        threshold_f = float(angle_threshold_deg or 30.0)
        if market_data_df is None or len(market_data_df) < period_i + 2:
            return result
        close = pd.to_numeric(market_data_df['close'], errors='coerce')
        ma = close.rolling(window=period_i).mean().dropna()
        if len(ma) < 3:
            return result
        angles = []
        for i in range(1, len(ma)):
            prev_v = ma.iloc[i - 1]
            curr_v = ma.iloc[i]
            if pd.isna(prev_v) or pd.isna(curr_v):
                continue
            delta = float(curr_v) - float(prev_v)
            angle_deg = float(math.degrees(math.atan(delta)))
            angles.append(angle_deg)
        if len(angles) < 2:
            return result
        recent_angles = [float(x) for x in angles[-lookback_i:]]
        result['recent_angles'] = recent_angles
        for i in range(1, len(recent_angles)):
            prev_angle = float(recent_angles[i - 1])
            curr_angle = float(recent_angles[i])
            if prev_angle < -threshold_f and curr_angle > threshold_f:
                result['should_block'] = True
                result['matched_prev_angle'] = prev_angle
                result['matched_curr_angle'] = curr_angle
                break
        return result
    except Exception:
        return result


def is_latest_ma_extreme(market_data_df, period=5, compare_days=3, mode='max'):
    try:
        period_i = max(int(period or 5), 1)
        compare_i = max(int(compare_days or 3), 1)
        if market_data_df is None or len(market_data_df) < period_i + compare_i - 1:
            return False, None, []
        close = pd.to_numeric(market_data_df['close'], errors='coerce')
        ma = close.rolling(window=period_i).mean().dropna()
        if len(ma) < compare_i:
            return False, None, []
        recent_vals = [float(x) for x in ma.iloc[-compare_i:].tolist() if pd.notna(x)]
        if len(recent_vals) < compare_i:
            return False, None, recent_vals
        latest_val = float(recent_vals[-1])
        if compare_i >= 3:
            prev1_val = float(recent_vals[-2])
            prev2_val = float(recent_vals[-3])
            if mode == 'min':
                # 空头仅在MA5连续两天上升时拦截，避免过早过滤趋势下行中的正常波动。
                should_block = (prev1_val < latest_val) and (prev2_val < prev1_val)
                return (not should_block), latest_val, recent_vals
            # 多头仅在MA5连续两天下降时拦截，放宽原来的“必须是近3天最大”限制。
            should_block = (prev1_val > latest_val) and (prev2_val > prev1_val)
            return (not should_block), latest_val, recent_vals
        if mode == 'min':
            return latest_val <= min(recent_vals), latest_val, recent_vals
        return latest_val >= max(recent_vals), latest_val, recent_vals
    except Exception:
        return False, None, []


def calculate_position_size(current_price, contract_info, account_info, market_data=None, trading_mode_info=None, set_stop_loss=False):
    """
    动态计算交易手数 - 智能止损价格版本（支持多种交易模式）
    基于交易模式、动态风险金额和智能止损价格精确计算交易手数
    
    【重要说明】：
    - 支持三种风险模式：
      * 常规模式：4% 风险（正常均线信号）
      * 突破模式：6% 风险（唐奇安通道突破）
      * 均线穿越突破模式：2% 风险（均线穿越期间+通道突破）
    - 智能止损价格计算：
      * 做多：止损价 = max(基础波动止损价, min(当天/昨天/前天最低价))
      * 做空：止损价 = min(基础波动止损价, max(当天/昨天/前天最高价))
    - 根据智能止损价格和合约乘数计算每手风险
    - 倒推计算最大可交易手数
    
    参数：
    set_stop_loss: 是否设置智能止损价格，只有确认开仓时才设置为True
    
    计算逻辑：
    1. 根据交易模式确定风险比例（2%/4%/6%）
    2. 动态单笔风险金额 = 当前总资产 × 风险比例
    3. 基础波动止损 = 当前价格 ± 2%
    4. 技术止损 = 近3日价格极值
    5. 智能止损价格 = 结合基础波动和技术止损
    6. 每手风险 = |当前价格 - 智能止损价格| × 合约乘数
    7. 最大交易手数 = 动态单笔风险金额 / 每手风险
    8. 根据可用保证金调整手数，确保资金充足
    """
    volume_multiple = contract_info.get('VolumeMultiple', 10)
    price_tick = contract_info.get('PriceTick', 1)
    instrument_name = contract_info.get('InstrumentName', '期货合约')

    G['logger'].info(f"\n========== 智能止损仓位计算 (含保证金检查) ==========")
    G['logger'].info(f"合约信息: {instrument_name}")
    G['logger'].info(f"当前价格: {current_price:.2f} 元")
    G['logger'].info(f"合约乘数: {volume_multiple}")
    G['logger'].info(f"最小价格变动: {price_tick}")

    if True:
        
        # 【修改】获取限制后的可用资金
        # 统一处理account_info，无论传入的是列表还是单个对象
        if account_info:
            if isinstance(account_info, list):
                account_obj = account_info[0] if account_info else None
            else:
                account_obj = account_info
            
            original_available_balance = account_obj.m_dAvailable if account_obj else 0
        else:
            original_available_balance = 0
            
        limited_available_balance = G.get('limited_available_balance', original_available_balance)  # 使用60%限制后的资金
        
        G['logger'].info(f"原始可用资金: {original_available_balance:.2f} 元")
        G['logger'].info(f"限制后可用资金: {limited_available_balance:.2f} 元 (60%限制)")
        
        if limited_available_balance < original_available_balance:
            G['logger'].info(f"💡 应用80%资金限制，实际可用资金减少 {original_available_balance - limited_available_balance:.2f} 元")
        
        # 计算每手合约价值
        single_contract_value = current_price * volume_multiple
        G['logger'].info(f"单手合约价值: {single_contract_value:.2f} 元")
        
        # 【修改】根据交易模式调整风险比例
        breakout_info = trading_mode_info.get('breakout_info') if trading_mode_info else None
        has_ma_cross_filter = trading_mode_info.get('has_ma_cross_filter', False) if trading_mode_info else False
        is_breakout = breakout_info and breakout_info.get('breakout', False) if breakout_info else False
        risk_ratio_override = trading_mode_info.get('risk_ratio_override') if trading_mode_info else None
        mode_description_override = trading_mode_info.get('mode_description_override') if trading_mode_info else None
        
        # 【修复】确定交易模式和对应的风险比例 - 统一基于60%限制后的资金
        # 获取60%限制后的可用资金作为风险计算基础
        effective_capital_for_risk = limited_available_balance
        
        if risk_ratio_override is not None:
            try:
                risk_ratio = float(risk_ratio_override)
            except Exception:
                risk_ratio = G['risk_ratio_of_total_assets']
            mode_description = mode_description_override or "📐 均线斜率风险模式"
            dynamic_risk_amount = effective_capital_for_risk * risk_ratio
        elif has_ma_cross_filter and is_breakout:
            # 均线穿越期间 + 通道突破：使用低风险模式
            risk_ratio = G['risk_ratio_ma_cross_breakout']  # 2%
            mode_description = "⚡ 均线穿越+通道突破模式"
            dynamic_risk_amount = effective_capital_for_risk * risk_ratio  # 🔧 修复：基于60%限制资金
        elif is_breakout and not has_ma_cross_filter:
            # 常规通道突破：使用高风险模式
            risk_ratio = G['risk_ratio_breakout']  # 6%
            mode_description = "🚀 唐奇安通道突破模式"
            dynamic_risk_amount = effective_capital_for_risk * risk_ratio  # 🔧 修复：基于60%限制资金
        else:
            # 常规模式：使用标准风险
            risk_ratio = G['risk_ratio_of_total_assets']  # 4%
            mode_description = "📊 常规风险模式"
            dynamic_risk_amount = G['current_risk_per_trade']  # 使用预计算的值（已修复）
        
        # 应用风险金额限制（仅对新计算的风险金额）
        if risk_ratio_override is not None or has_ma_cross_filter or (is_breakout and not has_ma_cross_filter):
            if dynamic_risk_amount < G['min_risk_per_trade']:
                dynamic_risk_amount = G['min_risk_per_trade']
            elif dynamic_risk_amount > G['max_risk_per_trade']:
                dynamic_risk_amount = G['max_risk_per_trade']

            _ensure_streak_risk_state()
            try:
                _m = float(G.get('risk_multiplier', 1.0) or 1.0)
            except Exception:
                _m = 1.0
            if _m < 0:
                _m = 0.0
            if _m > 1:
                _m = 1.0
            dynamic_risk_amount = dynamic_risk_amount * _m
        
        # 输出风险模式信息
        G['logger'].info(f"{mode_description}:")
        G['logger'].info(f"  风险比例: {risk_ratio*100:.1f}%")
        G['logger'].info(f"  风险金额: {dynamic_risk_amount:.2f} 元")
        
        if is_breakout:
            G['logger'].info(f"  突破方向: {breakout_info['direction']}")
        if has_ma_cross_filter:
            G['logger'].info(f"  均线穿越: 是")
            
        fixed_single_trade_risk = dynamic_risk_amount

        ai_mult = 1.0
        if trading_mode_info and isinstance(trading_mode_info, dict) and ('ai_multiplier' in trading_mode_info):
            try:
                ai_mult = float(trading_mode_info.get('ai_multiplier', 1.0) or 1.0)
            except Exception:
                ai_mult = 1.0
        try:
            ai_min = float(G.get('ai_position_min_multiplier', 0.3) or 0.3)
        except Exception:
            ai_min = 0.3
        try:
            ai_max = float(G.get('ai_position_max_multiplier', 1.5) or 1.5)
        except Exception:
            ai_max = 1.5
        if ai_min < 0:
            ai_min = 0.0
        if ai_max < ai_min:
            ai_max = ai_min
        if ai_mult < ai_min:
            ai_mult = ai_min
        if ai_mult > ai_max:
            ai_mult = ai_max
        if ai_mult != 1.0:
            G['logger'].info(f"AI动态仓位倍率: {ai_mult:.3f} | 风险金额: {fixed_single_trade_risk:.2f} -> {fixed_single_trade_risk * ai_mult:.2f}")
        fixed_single_trade_risk = fixed_single_trade_risk * ai_mult
        
        # ========== 【新增】智能止损价格计算 ==========
        # 1. 计算基础波动止损价格
        basic_stop_loss_long = current_price * (1 - G['stop_loss_pct'])  # 多头基础止损价
        basic_stop_loss_short = current_price * (1 + G['stop_loss_pct'])  # 空头基础止损价
        
        G['logger'].info(f"\n--- 基础波动止损 (±{G['stop_loss_pct']*100:.1f}%) ---")
        G['logger'].info(f"多头基础止损价: {basic_stop_loss_long:.2f} 元")
        G['logger'].info(f"空头基础止损价: {basic_stop_loss_short:.2f} 元")
        
        # 2. 获取近3日价格极值（如果有市场数据）
        technical_stop_loss_long = basic_stop_loss_long  # 默认值
        technical_stop_loss_short = basic_stop_loss_short  # 默认值
        today_low = None
        today_high = None
        
        if market_data is not None and len(market_data) >= 3:
            # 获取最近3日的高低价数据
            recent_3_days = market_data.tail(3)
            
            # 计算近3日最低价和最高价
            min_low_3days = recent_3_days['low'].min()
            max_high_3days = recent_3_days['high'].max()
            
            G['logger'].info(f"\n--- 近3日价格极值分析 ---")
            G['logger'].info(f"近3日最低价: {min_low_3days:.2f} 元")
            G['logger'].info(f"近3日最高价: {max_high_3days:.2f} 元")
            
            # 技术止损价格
            technical_stop_loss_long = min_low_3days  # 多头技术止损：近3日最低价
            technical_stop_loss_short = max_high_3days  # 空头技术止损：近3日最高价
            
            G['logger'].info(f"多头技术止损价: {technical_stop_loss_long:.2f} 元")
            G['logger'].info(f"空头技术止损价: {technical_stop_loss_short:.2f} 元")
        else:
            G['logger'].info(f"\n--- 无足够历史数据，使用基础波动止损 ---")
        
        # 3. 计算智能止损价格（结合基础波动和技术分析）
        #做多：选择更接近开仓价的止损位，降低每手风险，增加仓位
        smart_stop_loss_long = max(basic_stop_loss_long, technical_stop_loss_long)
        
        #做空：选择更接近开仓价的止损位，降低每手风险，增加仓位
        smart_stop_loss_short = min(basic_stop_loss_short, technical_stop_loss_short)

        entry_direction = (trading_mode_info or {}).get('entry_direction') if trading_mode_info else None
        if market_data is not None and len(market_data) >= 1:
            try:
                today_low = float(market_data['low'].iloc[-1])
            except Exception:
                today_low = None
            try:
                today_high = float(market_data['high'].iloc[-1])
            except Exception:
                today_high = None
        if entry_direction == 'long' and today_low is not None:
            smart_stop_loss_long = today_low
        elif entry_direction == 'short' and today_high is not None:
            smart_stop_loss_short = today_high

        G['logger'].info(f"\n--- 开仓手数使用的止损价格 ---")
        G['logger'].info(f"多头智能止损价: {smart_stop_loss_long:.2f} 元")
        G['logger'].info(f"空头智能止损价: {smart_stop_loss_short:.2f} 元")
        if entry_direction == 'long' and today_low is not None:
            G['logger'].info(f"多头初始止损取当日最低价: {today_low:.2f} 元")
        if entry_direction == 'short' and today_high is not None:
            G['logger'].info(f"空头初始止损取当日最高价: {today_high:.2f} 元")
        
        # 4. 计算基于智能止损的每手风险
        risk_per_contract_long = (current_price - smart_stop_loss_long) * volume_multiple
        risk_per_contract_short = (smart_stop_loss_short - current_price) * volume_multiple
        try:
            _min_risk = float(price_tick or 0) * float(volume_multiple or 0)
        except Exception:
            _min_risk = 0.0
        if _min_risk > 0:
            if abs(float(risk_per_contract_long)) < _min_risk:
                risk_per_contract_long = _min_risk
            if abs(float(risk_per_contract_short)) < _min_risk:
                risk_per_contract_short = _min_risk
        
        G['logger'].info(f"\n--- 基于智能止损的风险计算 ---")
        G['logger'].info(f"每手多头风险: {risk_per_contract_long:.2f} 元")
        G['logger'].info(f"每手空头风险: {risk_per_contract_short:.2f} 元")
        
        if entry_direction == 'long':
            avg_risk_per_contract = risk_per_contract_long
        elif entry_direction == 'short':
            avg_risk_per_contract = risk_per_contract_short
        else:
            avg_risk_per_contract = (risk_per_contract_long + risk_per_contract_short) / 2
        
        # 【关键】基于动态风险金额计算最大可交易手数
        if avg_risk_per_contract <= 0:
            G['logger'].warning("❌ 每手风险计算结果为0或负数，无法计算手数，设为0")
            max_contracts_by_risk = 0
        else:
            max_contracts_by_risk = fixed_single_trade_risk / avg_risk_per_contract
        
        G['logger'].info(f"平均每手风险: {avg_risk_per_contract:.2f} 元")
        G['logger'].info(f"风险计算手数: {max_contracts_by_risk:.2f} 手")
        
        # 确保手数为整数且在合理范围内
        position_size = max(0, min(G['max_position_size'], int(max_contracts_by_risk)))
        
        G['logger'].info(f"\n--- 保证金检查与调整 ---")
        G['logger'].info(f"基于风险计算的初始手数: {position_size} 手")
        
        # 【核心逻辑】保证金不足时直接按可用保证金上限裁剪手数（避免逐手递减导致日志刷屏）
        if position_size > 0:
            try:
                margin_ratio = float(contract_info.get('LongMarginRatio', 0.1) or 0.0)
            except Exception:
                margin_ratio = 0.0
            if margin_ratio <= 0:
                margin_ratio = 0.1
            denom = float(single_contract_value) * float(margin_ratio)
            if denom <= 0:
                position_size = 0
            else:
                max_by_margin = int(float(limited_available_balance) // denom)
                if max_by_margin < 0:
                    max_by_margin = 0
                if max_by_margin < position_size:
                    required_margin_old = float(position_size) * denom
                    required_margin_new = float(max_by_margin) * denom
                    G['logger'].warning(
                        f"⚠️  保证金不足，手数按保证金上限裁剪: {position_size} → {max_by_margin} "
                        f"(需求: {required_margin_old:.2f} > 限制后可用: {float(limited_available_balance):.2f})"
                    )
                    if max_by_margin > 0:
                        G['logger'].info(
                            f"✅ 裁剪后满足保证金: 需求 {required_margin_new:.2f} <= 限制后可用 {float(limited_available_balance):.2f}"
                        )
                    position_size = max_by_margin
            if position_size == 0:
                G['logger'].error("❌ 即使是最小手数，在60%资金限制下保证金也不足，无法开仓。")
        
        # 最终手数不能小于最小交易手数
        if 0 < position_size < G['min_position_size']:
             G['logger'].warning(f"调整后手数({position_size})小于最小手数({G['min_position_size']})，无法开仓")
             position_size = 0
        
        position_size = max(0, position_size)

        # 计算实际风险金额
        actual_risk = position_size * avg_risk_per_contract
        
        # 计算保证金需求（估算）
        margin_ratio = contract_info.get('LongMarginRatio', 0.1)
        required_margin = position_size * single_contract_value * margin_ratio
        
        G['logger'].info(f"\n--- 最终交易参数 ---")
        G['logger'].info(f"最终交易手数: {position_size} 手")
        G['logger'].info(f"实际风险金额: {actual_risk:.2f} 元")
        G['logger'].info(f"预估保证金需求: {required_margin:.2f} 元")
        if fixed_single_trade_risk > 0:
            G['logger'].info(f"风险利用率: {(actual_risk/fixed_single_trade_risk)*100:.1f}%")
        
        # 智能止损优势分析
        basic_avg_risk = ((current_price - basic_stop_loss_long) + (basic_stop_loss_short - current_price)) / 2 * volume_multiple
        if basic_avg_risk > 0:
            basic_position_size = int(fixed_single_trade_risk / basic_avg_risk)
            
            G['logger'].info(f"\n--- 智能止损优势分析 ---")
            G['logger'].info(f"基础波动止损手数: {basic_position_size} 手")
            G['logger'].info(f"智能止损手数: {position_size} 手")
            
            if position_size > basic_position_size:
                G['logger'].info(f"✅ 智能止损允许更大仓位 (+{position_size - basic_position_size}手)")
            elif position_size < basic_position_size:
                G['logger'].warning(f"⚠️  智能止损要求更小仓位 (-{basic_position_size - position_size}手，更安全)")
            else:
                G['logger'].info(f"➡️  智能止损与基础止损结果一致")
        
        # 风险提示
        if actual_risk > fixed_single_trade_risk * 1.1:
            G['logger'].warning("⚠️  警告：实际风险超过动态单笔风险金额10%")
        elif actual_risk < fixed_single_trade_risk * 0.5 and position_size > 0:
            G['logger'].info("💡 提示：实际风险较小，可考虑增加仓位")
        
        # 多合约风险统计
        current_positions_count = len(G['open_positions'])
        if current_positions_count >= 0:
            # 这里的风险统计仅为估算，实际总风险需要累加所有持仓的实际风险
            G['logger'].info(f"\n--- 多合约风险管理 (估算) ---")
            G['logger'].info(f"当前持仓数: {current_positions_count}, 开仓后: {current_positions_count + 1 if position_size > 0 else current_positions_count}")
            
            # 风险控制提示
            if current_positions_count >= G['max_concurrent_positions']:
                G['logger'].warning("⚠️  已达到最大持仓数限制")
        
        G['logger'].info("=" * 50)
        
        # 【修复】只有在确认开仓时才设置智能止损价格
        if set_stop_loss:
            long_key = f'smart_stop_loss_{contract_info["contract_code"]}_long'
            short_key = f'smart_stop_loss_{contract_info["contract_code"]}_short'
            
            # 【修改】每次开仓都重新计算和设置智能止损价格，确保基于最新价格
            G[long_key] = smart_stop_loss_long
            G[short_key] = smart_stop_loss_short
            G['logger'].info(f"🎯 开仓时设置智能止损价格 - 多头: {smart_stop_loss_long:.2f}")
            G['logger'].info(f"🎯 开仓时设置智能止损价格 - 空头: {smart_stop_loss_short:.2f}")
        else:
            G['logger'].info(f"ℹ️  仅计算仓位大小，未设置智能止损价格")
        
        return position_size

def print_strategy_statistics():
    """打印多合约策略统计信息"""
    G['logger'].info("\n========== 多合约策略运行统计 ==========")
    G['logger'].info(f"交易合约数量: {len(G['contract_codes'])}个")
    G['logger'].info(f"合约列表: {G['contract_codes']}")
    G['logger'].info(f"最大同时持仓数: {G['max_concurrent_positions']}")
    G['logger'].info(f"当前持仓数: {len(G['open_positions'])}")
    G['logger'].info(f"金叉信号次数: {G['golden_cross_count']}次")
    G['logger'].info(f"死叉信号次数: {G['death_cross_count']}次")
    G['logger'].info(f"总交易执行次数: {G['trade_count']}次")
    G['logger'].info(f"20日均线止损次数: {G.get('ma_stop_count', 0)}次 (趋势跟踪)")
    G['logger'].info(f"移动止损次数: {G['trailing_stop_count']}次 (利润保护)")
    G['logger'].info(f"智能固定止损次数: {G.get('smart_stop_count', 0)}")
    G['logger'].info(f"基础固定止损次数: {G['stop_loss_count']}")
    G['logger'].info(f"固定止盈次数: {G['stop_profit_count']}")
    
    total_closes = G.get('ma_stop_count', 0) + G['trailing_stop_count'] + G.get('smart_stop_count', 0) + G['stop_loss_count'] + G['stop_profit_count']
    if total_closes > 0:
        ma_stop_rate = (G.get('ma_stop_count', 0) / total_closes) * 100
        trailing_stop_rate = (G['trailing_stop_count'] / total_closes) * 100
        smart_stop_rate = (G.get('smart_stop_count', 0) / total_closes) * 100
        fixed_stop_rate = (G['stop_loss_count'] / total_closes) * 100
        fixed_profit_rate = (G['stop_profit_count'] / total_closes) * 100
        G['logger'].info(f"止损方式占比:")
        G['logger'].info(f"  20日均线止损: {ma_stop_rate:.1f}% (趋势跟踪)")
        G['logger'].info(f"  移动止损: {trailing_stop_rate:.1f}% (利润保护)")
        G['logger'].info(f"  智能固定止损: {smart_stop_rate:.1f}% (技术分析)")
        G['logger'].info(f"  基础固定止损: {fixed_stop_rate:.1f}% (风险控制)")
        G['logger'].info(f"  固定止盈: {fixed_profit_rate:.1f}% (极端保护)")
    
    # 显示各合约的交易情况
    if G['open_positions']:
        G['logger'].info(f"\n当前各合约持仓情况:")
        for contract, pos_info in G['open_positions'].items():
            direction_cn = "多头" if pos_info['direction'] == 'long' else "空头"
            total_vol = pos_info.get('total_volume', pos_info.get('volume', 0))
            base_vol = pos_info.get('volume', 0)
            G['logger'].info(f"  {contract}: {direction_cn} volume={base_vol}手, total_volume={total_vol}手")
    
    G['logger'].info("=" * 50) 

def calculate_trailing_stop_price(contract_code, open_price, max_profit_pct):
    """
    计算移动止损价格
    
    参数:
    - contract_code (str): 合约代码
    - open_price (float): 开仓价格（这里使用加权平均成本价）
    - max_profit_pct (float): 最大盈利百分比
    
    返回:
    - float: 移动止损价格
    """
    # 移动止损触发和回撤比例
    trailing_start_profit_pct = 0.05  # 盈利达到5%时开始移动止损
    trailing_stop_drawdown_pct = 0.3  # 从最高点回撤30%止损

    if max_profit_pct < trailing_start_profit_pct:
        # 未达到移动止损启动条件，返回0或一个标记值
        return 0

    pos_info = G['open_positions'].get(contract_code)
    if not pos_info:
        return 0

    # 使用加权平均成本价而不是初始开仓价
    avg_price = pos_info.get('avg_price', pos_info.get('price', open_price))
    
    # 确保必要的字段存在，如果不存在则提供默认值
    if 'avg_price' not in pos_info:
        pos_info['avg_price'] = avg_price
        G['logger'].warning(f"⚠️ 持仓记录缺少'avg_price'字段，使用'price'字段作为后备: {avg_price:.2f}")
    
    if pos_info['direction'] == 'long':
        # 计算盈利期间的最高价格（基于加权平均成本价）
        highest_price = avg_price * (1 + max_profit_pct)
        # 计算止损价格
        stop_price = highest_price * (1 - trailing_stop_drawdown_pct)
        # 止损价不能低于加权平均成本价
        return max(stop_price, avg_price)
    elif pos_info['direction'] == 'short':
        # 计算盈利期间的最低价格（基于加权平均成本价）
        lowest_price = avg_price * (1 - max_profit_pct)
        # 计算止损价格
        stop_price = lowest_price * (1 + trailing_stop_drawdown_pct)
        # 止损价不能高于加权平均成本价
        return min(stop_price, avg_price)
    
    return 0

def save_strategy_data():
    """
    保存策略关键数据到文件，防止重启丢失
    """
    # 检查是否启用数据持久化
    if not G.get('enable_data_persistence', False):
        return False

    strategy_data = {
            'open_positions': G['open_positions'],
            'max_profit_tracking': G['max_profit_tracking'],
            'smart_stop_losses': {k: v for k, v in G.items() if k.startswith('smart_stop_loss_')},
            'last_add_date': G.get('last_add_date', {}),
            'last_donchian_add_date': G.get('last_donchian_add_date', {}),
            'executed_days': G.get('executed_days', set()),
            'streak_risk': {
                'risk_multiplier': float(G.get('risk_multiplier', 1.0) or 1.0),
                'risk_tier': int(G.get('risk_tier', 0) or 0),
                'loss_streak': int(G.get('loss_streak', 0) or 0),
                'recent_nonzero_results': list(G.get('recent_nonzero_results') or []),
                'streak_risk_multipliers': list(G.get('streak_risk_multipliers') or []),
            },
            'annual_withdrawal': {
                'enabled': bool(G.get('annual_withdrawal_enabled', False)),
                'capital': float(G.get('annual_withdrawal_capital', 1000000.0) or 1000000.0),
                'year': int(G.get('annual_withdrawal_year', 0) or 0),
                'offset': float(G.get('annual_withdrawal_offset', 0) or 0),
                'trading_capital': float(G.get('annual_trading_capital', 0) or 0),
                'withdrawn_by_year': dict(G.get('annual_withdrawn_by_year') or {}),
            },
            'performance': {
                'total_realized_pnl': G.get('total_realized_pnl', 0.0),
                'gross_profit': G.get('gross_profit', 0.0),
                'gross_loss_abs': G.get('gross_loss_abs', 0.0),
                'num_winning_trades': G.get('num_winning_trades', 0),
                'num_losing_trades': G.get('num_losing_trades', 0),
                'best_trade_pnl': G.get('best_trade_pnl', 0.0),
                'worst_trade_pnl': G.get('worst_trade_pnl', 0.0),
                'closed_trades': G.get('closed_trades', 0),
                'sum_holding_days': G.get('sum_holding_days', 0),
                'equity_curve': G.get('equity_curve', []),
                'case_stats': G.get('case_stats', {})
            },
            'statistics': {
                'golden_cross_count': G['golden_cross_count'],
                'death_cross_count': G['death_cross_count'],
                'trade_count': G['trade_count'],
                'stop_loss_count': G['stop_loss_count'],
                'stop_profit_count': G['stop_profit_count'],
                'trailing_stop_count': G['trailing_stop_count'],
                'ma_stop_count': G.get('ma_stop_count', 0),
                'smart_stop_count': G.get('smart_stop_count', 0)
            },
            'save_time': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
    backup_file = G.get('data_backup_file', 'strategy_data_backup.pkl')

    backup_dir = os.path.dirname(os.path.abspath(backup_file))
    if not os.path.exists(backup_dir):
        os.makedirs(backup_dir, exist_ok=True)

    with open(backup_file, 'wb') as f:
        pickle.dump(strategy_data, f)

    G['logger'].info(f"✅ 策略数据已保存到 {backup_file}")
    return True

def load_strategy_data():
    """
    从文件加载策略数据，恢复重启前状态
    """
    # 检查是否启用数据持久化
    if not G.get('enable_data_persistence', False):
        G['logger'].info("📁 数据持久化已禁用，使用默认初始化")
        return False

    backup_file = G.get('data_backup_file', 'strategy_data_backup.pkl')
    if not os.path.exists(backup_file):
        G['logger'].info("📁 未找到备份文件，使用默认初始化")
        return False

    with open(backup_file, 'rb') as f:
        strategy_data = pickle.load(f)

        # 恢复持仓记录
        G['open_positions'] = strategy_data.get('open_positions', {})
        
        # 恢复移动止损追踪
        G['max_profit_tracking'] = strategy_data.get('max_profit_tracking', {})
        
        # 恢复智能止损价格
        smart_stops = strategy_data.get('smart_stop_losses', {})
        for key, value in smart_stops.items():
            G[key] = value

        G['last_add_date'] = strategy_data.get('last_add_date', {})
        G['last_donchian_add_date'] = strategy_data.get('last_donchian_add_date', {})
        G['executed_days'] = strategy_data.get('executed_days', set())
        for _contract_code, _pos in (G.get('open_positions') or {}).items():
            if not isinstance(_pos, dict):
                continue
            _get_donchian_add_positions(_pos, create=True)
            _recalculate_position_totals(_pos)

        sr = strategy_data.get('streak_risk', {}) or {}
        G['risk_multiplier'] = float(sr.get('risk_multiplier', G.get('risk_multiplier', 1.0)) or 1.0)
        G['risk_tier'] = int(sr.get('risk_tier', G.get('risk_tier', 0)) or 0)
        G['loss_streak'] = int(sr.get('loss_streak', G.get('loss_streak', 0)) or 0)
        rr = sr.get('recent_nonzero_results')
        if isinstance(rr, list):
            G['recent_nonzero_results'] = rr
        rm = sr.get('streak_risk_multipliers')
        if isinstance(rm, list):
            G['streak_risk_multipliers'] = rm

        aw = strategy_data.get('annual_withdrawal', {}) or {}
        if isinstance(aw, dict):
            if 'enable_annual_withdrawal_cap' not in G:
                G['annual_withdrawal_enabled'] = bool(aw.get('enabled', G.get('annual_withdrawal_enabled', False)))
            try:
                G['annual_withdrawal_capital'] = float(aw.get('capital', G.get('annual_withdrawal_capital', 1000000.0)) or 1000000.0)
            except Exception:
                pass
            try:
                G['annual_withdrawal_year'] = int(aw.get('year', G.get('annual_withdrawal_year', 0)) or 0)
            except Exception:
                pass
            try:
                G['annual_withdrawal_offset'] = float(aw.get('offset', G.get('annual_withdrawal_offset', 0.0)) or 0.0)
            except Exception:
                pass
            try:
                G['annual_trading_capital'] = float(aw.get('trading_capital', G.get('annual_trading_capital', 0.0)) or 0.0)
            except Exception:
                pass
            wby = aw.get('withdrawn_by_year')
            if isinstance(wby, dict):
                G['annual_withdrawn_by_year'] = wby

        if 'enable_annual_withdrawal_cap' in G:
            G['annual_withdrawal_enabled'] = bool(G.get('enable_annual_withdrawal_cap', False))

        perf = strategy_data.get('performance', {})
        G['total_realized_pnl'] = float(perf.get('total_realized_pnl', 0.0))
        G['gross_profit'] = float(perf.get('gross_profit', 0.0))
        G['gross_loss_abs'] = float(perf.get('gross_loss_abs', 0.0))
        G['num_winning_trades'] = int(perf.get('num_winning_trades', 0))
        G['num_losing_trades'] = int(perf.get('num_losing_trades', 0))
        G['best_trade_pnl'] = float(perf.get('best_trade_pnl', 0.0))
        G['worst_trade_pnl'] = float(perf.get('worst_trade_pnl', 0.0))
        G['closed_trades'] = int(perf.get('closed_trades', 0))
        G['sum_holding_days'] = int(perf.get('sum_holding_days', 0))
        G['equity_curve'] = perf.get('equity_curve', [])
        G['case_stats'] = perf.get('case_stats', {})
        
        # 恢复统计数据
        stats = strategy_data.get('statistics', {})
        G['golden_cross_count'] = stats.get('golden_cross_count', 0)
        G['death_cross_count'] = stats.get('death_cross_count', 0) 
        G['trade_count'] = stats.get('trade_count', 0)
        G['stop_loss_count'] = stats.get('stop_loss_count', 0)
        G['stop_profit_count'] = stats.get('stop_profit_count', 0)
        G['trailing_stop_count'] = stats.get('trailing_stop_count', 0)
        G['ma_stop_count'] = stats.get('ma_stop_count', 0)
        G['smart_stop_count'] = stats.get('smart_stop_count', 0)
        
    save_time = strategy_data.get('save_time', '未知')
    G['logger'].info(f"✅ 成功加载策略数据 (保存时间: {save_time})")
    G['logger'].info(f"   恢复持仓: {len(G['open_positions'])}个")
    G['logger'].info(f"   恢复移动止损追踪: {len(G['max_profit_tracking'])}个")
    G['logger'].info(f"   恢复智能止损: {len(smart_stops)}个")
    G['logger'].info(f"   恢复交易统计: 总交易{G['trade_count']}次")

    return True

def auto_save_strategy_data(reason=""):
    """
    自动保存策略数据的辅助函数
    在启用数据持久化时保存，关闭时静默跳过
    """
    if G.get('enable_data_persistence', False):
        result = save_strategy_data()
        if not result and reason:
            G['logger'].debug(f"数据保存失败: {reason}")
        return result
    return False

# 新增：换月后按相同风控策略判断并在新合约上开仓
def attempt_reopen_after_rollover(ContextInfo, target_contract_code, old_direction, old_risk_mode, old_root_trade_id=None, old_entry_signal_source=None, old_pending_breakout_created_date=None, old_pending_breakout_wait_days=None, account_info=None, current_dt=None, current_date_str=None):
    G['logger'].info(f"\n🔁 换月后尝试在新合约开仓: {target_contract_code} | 旧方向: {old_direction} | 风控: {old_risk_mode}")

    required_count = max(G['ma_extra_long'] + 10, 26 + 9 + 5)

    if ContextInfo.do_back_test:
        market_map = ContextInfo.get_market_data_ex(
            fields=['close', 'open', 'high', 'low', 'volume', 'openInterest'],
            stock_code=[target_contract_code],
            period=G['period'],
            end_time=current_date_str,
            count=required_count,
            dividend_type='front_ratio',
            subscribe=False
        )
    else:
        market_map = ContextInfo.get_market_data_ex(
            fields=['close', 'open', 'high', 'low', 'volume', 'openInterest'],
            stock_code=[target_contract_code],
            period=G['period'],
            count=required_count,
            dividend_type='front_ratio',
            subscribe=True
        )

    if target_contract_code not in market_map or market_map[target_contract_code].empty:
        G['logger'].warning(f"❌ 新合约无有效数据，放弃换月开仓: {target_contract_code}")
        return

    data = market_map[target_contract_code]
    close_prices = data['close']

    if bool(G.get('er_open_filter_enabled', False)):
        _er_filter = evaluate_er_open_filter(close_prices)
        G['logger'].info(
            f"换月开仓ER过滤: ER5={_er_filter.get('er_5')} ER10={_er_filter.get('er_10')} "
            f"ER20={_er_filter.get('er_20')} threshold=0.2 failed={_er_filter.get('failed_periods')}"
        )
        if _er_filter.get('should_block'):
            G['logger'].info("换月开仓过滤：ER5/10/20 其中之一小于0.2，跳过换月开仓")
            return

    if bool(G.get('oi_decline_filter_enabled', False)):
        _oi_filter = evaluate_non_near_month_oi_filter(target_contract_code, data, current_date_str, ContextInfo)
        G['logger'].info(
            f"换月开仓近月/持仓量过滤: near={_oi_filter.get('is_near_month')} "
            f"delivery_ym={_oi_filter.get('delivery_ym')} near_ym={_oi_filter.get('near_ym')} oi_today={_oi_filter.get('oi_today')} "
            f"oi_yesterday={_oi_filter.get('oi_yesterday')} oi_declining={_oi_filter.get('oi_declining')}"
        )
        if _oi_filter.get('should_block'):
            G['logger'].info("换月开仓过滤：当前不是近月合约，且当日持仓量较昨日下降，跳过换月开仓")
            return

    ma_short = close_prices.rolling(window=G['ma_short']).mean()
    ma_mid = close_prices.rolling(window=G['ma_mid']).mean()
    ma_long = close_prices.rolling(window=G['ma_long']).mean()
    ma_extra_long = close_prices.rolling(window=G['ma_extra_long']).mean()

    if len(ma_short) < 1 or len(ma_extra_long) < 1:
        G['logger'].warning("❌ 新合约均线数据不足，放弃换月开仓")
        return

    today_short = ma_short.iloc[-1]
    today_mid = ma_mid.iloc[-1]
    today_long = ma_long.iloc[-1]
    today_extra_long = ma_extra_long.iloc[-1]

    is_bullish_alignment = (today_short > today_mid > today_long > today_extra_long)
    is_bearish_alignment = (today_short < today_mid < today_long < today_extra_long)

    macd = calculate_macd(close_prices)
    current_macd = macd['current_macd'] if macd else 0

    current_price = close_prices.iloc[-1]

    if old_direction == 'long' and bool(G.get('down_day_open_filter_enabled', False)):
        try:
            _o = float(data['open'].iloc[-1])
            _c = float(data['close'].iloc[-1])
            if _c < _o:
                G['logger'].info(f"换月开多过滤：当日下跌(close {_c:.2f} < open {_o:.2f})，跳过换月开多")
                if getattr(ContextInfo, 'do_back_test', False) and G.get('enable_block_kline_dump', False):
                    _schedule_block_kline_dump({
                        'contract_code': target_contract_code,
                        'direction': 'long',
                        'tag': 'rollover_blocked_down_day',
                        'reason': f"down_day close<open ({_c:.2f}<{_o:.2f})",
                        'date': str(current_date_str),
                        'trigger_barpos': _get_barpos(ContextInfo),
                        'pre_days': int(G.get('block_kline_pre_days', G.get('kline_pre_days', 20)) or 20),
                        'post_days': int(G.get('block_kline_post_days', G.get('kline_post_days', 20)) or 20),
                    })
                return
            if bool(G.get('wick_chop_filter_enabled', False)):
                if is_simple_ma_trend(data, 'long', G.get('ma_short', 5), G.get('ma_mid', 10), G.get('ma_long', 20), G.get('ma_extra_long', 40), 3):
                    G['logger'].info("换月开多过滤豁免：均线趋势成立 (long)")
                else:
                    ok, cnt, n = wick_chop_filter_ok(
                        data,
                        lookback=G.get('wick_chop_filter_lookback', 10),
                        max_days=G.get('wick_chop_filter_max_days', 4)
                    )
                    if not ok:
                        try:
                            lookback_i = int(G.get('wick_chop_filter_lookback', 10) or 10)
                        except Exception:
                            lookback_i = 10
                        try:
                            max_days_i = int(G.get('wick_chop_filter_max_days', 4) or 4)
                        except Exception:
                            max_days_i = 4
                        G['logger'].info(f"换月开多过滤：近{n}根(目标{lookback_i})K线影线>实体天数={cnt} > {max_days_i}，跳过换月开多")
                        return
        except Exception:
            pass
        try:
            ma5_is_max, ma5_latest, ma5_recent = is_latest_ma_extreme(
                data,
                period=G.get('ma_short', 5),
                compare_days=3,
                mode='max'
            )
        except Exception:
            ma5_is_max, ma5_latest, ma5_recent = False, None, []
        G['logger'].info(f"换月开多过滤：MA5两日回落过滤 latest={ma5_latest} recent={ma5_recent} pass={ma5_is_max}")
        if not ma5_is_max:
            G['logger'].info("换月开多过滤：MA5连续两天下降，跳过换月开多")
            return

    if bool(G.get('ma5_angle_reversal_filter_enabled', True)):
        try:
            _ma5_angle_filter = evaluate_ma5_angle_reversal_filter(
                data,
                period=G.get('ma_short', 5),
                lookback_days=G.get('ma5_angle_reversal_lookback_days', 10),
                angle_threshold_deg=G.get('ma5_angle_reversal_angle_threshold_deg', 30.0)
            )
        except Exception:
            _ma5_angle_filter = {'should_block': False, 'recent_angles': [], 'matched_prev_angle': None, 'matched_curr_angle': None}
        G['logger'].info(
            f"换月开仓MA5角度反转过滤: recent_angles={_ma5_angle_filter.get('recent_angles')} "
            f"matched=({_ma5_angle_filter.get('matched_prev_angle')},{_ma5_angle_filter.get('matched_curr_angle')}) "
            f"threshold={G.get('ma5_angle_reversal_angle_threshold_deg', 30.0)} block={_ma5_angle_filter.get('should_block')}"
        )
        if _ma5_angle_filter.get('should_block'):
            G['logger'].info("换月开仓过滤：最近10天出现MA5角度急跌后急拉，跳过换月开仓")
            try:
                if getattr(ContextInfo, 'do_back_test', False) and G.get('enable_block_kline_dump', False):
                    _angles_txt = ",".join([f"{float(x):.3f}" for x in (_ma5_angle_filter.get('recent_angles') or [])]) or "None"
                    _schedule_block_kline_dump({
                        'contract_code': target_contract_code,
                        'direction': old_direction,
                        'tag': 'rollover_blocked_ma5_angle_reversal',
                        'reason': (
                            f"ma5_angle_reversal prev={_ma5_angle_filter.get('matched_prev_angle')} "
                            f"curr={_ma5_angle_filter.get('matched_curr_angle')} recent_angles={_angles_txt}"
                        ),
                        'date': str(current_date_str),
                        'trigger_barpos': _get_barpos(ContextInfo),
                        'pre_days': int(G.get('block_kline_pre_days', G.get('kline_pre_days', 20)) or 20),
                        'post_days': int(G.get('block_kline_post_days', G.get('kline_post_days', 20)) or 20),
                    })
            except Exception:
                pass
            return

    if old_direction == 'short' and not bool(G.get('short_entry_enabled', True)):
        G['logger'].info("换月开空总开关关闭，跳过换月开空")
        return

    if old_direction == 'short' and bool(G.get('wick_chop_filter_enabled', False)):
        if is_simple_ma_trend(data, 'short', G.get('ma_short', 5), G.get('ma_mid', 10), G.get('ma_long', 20), G.get('ma_extra_long', 40), 3):
            G['logger'].info("换月开空过滤豁免：均线趋势成立 (short)")
        else:
            ok, cnt, n = wick_chop_filter_ok(
                data,
                lookback=G.get('wick_chop_filter_lookback', 10),
                max_days=G.get('wick_chop_filter_max_days', 4)
            )
            if not ok:
                try:
                    lookback_i = int(G.get('wick_chop_filter_lookback', 10) or 10)
                except Exception:
                    lookback_i = 10
                try:
                    max_days_i = int(G.get('wick_chop_filter_max_days', 4) or 4)
                except Exception:
                    max_days_i = 4
                G['logger'].info(f"换月开空过滤：近{n}根(目标{lookback_i})K线影线>实体天数={cnt} > {max_days_i}，跳过换月开空")
                return

    if old_direction == 'short':
        try:
            ma5_is_min, ma5_latest, ma5_recent = is_latest_ma_extreme(
                data,
                period=G.get('ma_short', 5),
                compare_days=3,
                mode='min'
            )
        except Exception:
            ma5_is_min, ma5_latest, ma5_recent = False, None, []
        G['logger'].info(f"换月开空过滤：MA5两日反弹过滤 latest={ma5_latest} recent={ma5_recent} pass={ma5_is_min}")
        if not ma5_is_min:
            G['logger'].info("换月开空过滤：MA5连续两天上升，跳过换月开空")
            return

        try:
            ma5_slope = get_ma_slope_direction(data, period=G.get('ma_short', 5))
        except Exception:
            ma5_slope = 0.0
        G['logger'].info(f"换月开空过滤：5日均线斜率={ma5_slope:.6f}")
        if ma5_slope > 0:
            G['logger'].info(f"换月开空过滤：5日均线斜率朝上 ({ma5_slope:.6f} > 0)，跳过换月开空")
            return

    allow_long = is_bullish_alignment and (current_macd > 0)
    allow_short = is_bearish_alignment and (current_macd < 0)

    G['logger'].info(f"换月新合约信号: 多头排布={is_bullish_alignment}, 空头排布={is_bearish_alignment}, MACD={current_macd:.4f}")

    if (old_direction == 'long' and not allow_long) or (old_direction == 'short' and not allow_short):
        G['logger'].info("条件未满足（多头需 排布+MACD>0 / 空头需 排布+MACD<0），不在新合约开仓")
        return

    if len(G['open_positions']) >= G['max_concurrent_positions']:
        G['logger'].warning("已达最大持仓限制，跳过换月开仓")
        return

    contract_info = get_contract_info(ContextInfo, target_contract_code)
    if not contract_info:
        G['logger'].warning(f"⚠️ 换月开仓失败：新合约无有效合约信息 {target_contract_code}")
        return
    risk_mode = old_risk_mode or 'normal'

    _ai_rsi = 50.0
    try:
        _r = calculate_multi_period_rsi(data['close'], periods=[6, 12, 24])
        if _r and 'rsi_6' in _r:
            _ai_rsi = float(_r['rsi_6'])
    except Exception:
        _ai_rsi = 50.0
    ai_mult = ai_predict_position_multiplier(old_direction, data, current_macd, _ai_rsi, is_bullish_alignment, is_bearish_alignment)
    final_position_size = calculate_position_size(
        current_price,
        contract_info,
        account_info,
        data,
        {'entry_direction': old_direction, 'ai_multiplier': ai_mult},
        set_stop_loss=True
    )

    if final_position_size <= 0:
        G['logger'].warning("换月开仓手数计算为0，放弃")
        return

    if old_direction == 'long':
        opType = 0
        order_remark = f'期货多空排布策略-换月开多-{target_contract_code}'
    else:
        opType = 3
        order_remark = f'期货多空排布策略-换月开空-{target_contract_code}'

    order_note = f'rollover_reopen-{risk_mode}-{target_contract_code}'
    order_id = smart_passorder(
        opType,
        1101,
        G['accountid'],
        target_contract_code,
        current_price,
        final_position_size,
        order_remark,
        2,
        order_note,
        ContextInfo
    )

    if order_id > 0:
        G['logger'].info(f"✅ 换月新合约开仓成功: 方向={old_direction}, 手数={final_position_size}, 订单号={order_id}")

        _entry_dt = get_context_datetime(ContextInfo)
        _entry_date = _entry_dt.strftime('%Y%m%d')
        _entry_barpos = _get_barpos(ContextInfo)
        try:
            G['trade_id_seq'] = int(G.get('trade_id_seq', 0) or 0) + 1
        except Exception:
            G['trade_id_seq'] = 1
        _trade_id = int(G.get('trade_id_seq', 1) or 1)
        G['open_positions'][target_contract_code] = {
            'trade_id': _trade_id,
            'root_trade_id': int(old_root_trade_id or _trade_id),
            'entry_date': _entry_date,
            'entry_barpos': _entry_barpos,
            'direction': 'long' if opType == 0 else 'short',
            'price': current_price,
            'initial_price': current_price,
            'volume': final_position_size,
            'time': get_context_datetime(ContextInfo).strftime('%Y-%m-%d %H:%M:%S'),
            'open_reason': 'rollover_reopen',
            'risk_mode': risk_mode,
            'open_macd': float(current_macd),
            'open_rsi': None,
            'add_positions': [],
            'donchian_add_positions': [],
            'total_volume': final_position_size,
            'avg_price': current_price,
            'add_count': 0,
            'donchian_add_count': 0,
            'entry_signal_source': old_entry_signal_source,
            'pending_breakout_created_date': old_pending_breakout_created_date,
            'pending_breakout_wait_days': int(old_pending_breakout_wait_days or 0)
        }
        try:
            if old_direction == 'long':
                _entry_stop = float(data['low'].iloc[-1])
                _entry_stop_source = 'entry_day_low'
                _entry_stop_reason = "换月续开初始化 当日最低价止损"
            else:
                _entry_stop = float(data['high'].iloc[-1])
                _entry_stop_source = 'entry_day_high'
                _entry_stop_reason = "换月续开初始化 当日最高价止损"
        except Exception:
            _entry_stop = None
            _entry_stop_source = ''
            _entry_stop_reason = "换月续开初始化 固定比例止损"
        if _entry_stop is None:
            try:
                if old_direction == 'long':
                    _entry_stop = float(current_price) * (1 - float(G.get('stop_loss_pct', 0.02) or 0.02))
                    _entry_stop_source = 'entry_day_low'
                else:
                    _entry_stop = float(current_price) * (1 + float(G.get('stop_loss_pct', 0.02) or 0.02))
                    _entry_stop_source = 'entry_day_high'
            except Exception:
                _entry_stop = None
        G['open_positions'][target_contract_code]['initial_layer_max_profit_pct'] = 0.0
        G['open_positions'][target_contract_code]['initial_layer_trailing_stop_price'] = _entry_stop
        G['open_positions'][target_contract_code]['sizing_stop_price'] = _entry_stop
        G['open_positions'][target_contract_code]['sizing_stop_source'] = _entry_stop_source
        if _entry_stop is not None:
            try:
                G['open_positions'][target_contract_code]['overall_trailing_stop_price'] = float(_entry_stop)
            except Exception:
                pass
            _append_trailing_stop_trace(G['open_positions'][target_contract_code], 'initial', _entry_date, _entry_barpos, float(_entry_stop), _entry_stop_reason)
        if G['trailing_stop_enabled']:
            G['max_profit_tracking'][target_contract_code] = {
                'max_profit_pct': 0.0,
                'trailing_stop_price': _entry_stop,
                'last_update_time': get_context_datetime(ContextInfo).strftime('%Y-%m-%d %H:%M:%S')
            }
        G['rollover_opened_today'].add(target_contract_code)
        save_strategy_data()
    else:
        G['logger'].error("❌ 换月新合约开仓下单失败")


def orderError_callback(ContextInfo, orderArgs, errMsg):
    try:
        G['logger'].error(f"orderError_callback: {errMsg}")
        if orderArgs is not None:
            payload = {}
            for k in dir(orderArgs):
                if not k.startswith('m_'):
                    continue
                try:
                    payload[k] = getattr(orderArgs, k)
                except Exception:
                    continue
            if payload:
                G['logger'].error(f"orderError_args: {payload}")
    except Exception:
        pass
