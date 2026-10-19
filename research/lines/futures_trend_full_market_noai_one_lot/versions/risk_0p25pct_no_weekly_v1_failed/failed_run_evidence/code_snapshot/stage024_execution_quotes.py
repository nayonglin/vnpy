"""Append hash-bound price-consensus quotes for existing-position execution only."""
from pathlib import Path
import hashlib,json
import numpy as np
import pandas as pd


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_quantity_execution_overlay(market,contracts,csv,receipt):
    csv,receipt=Path(csv),Path(receipt)
    evidence=json.loads(receipt.read_text())
    if sha(csv)!=evidence['output']['sha256']:raise ValueError('quantity_quote_hash_mismatch')
    overlay=pd.read_csv(csv)
    if len(overlay)!=evidence['rows']:raise ValueError('quantity_quote_row_count')
    required={'vt_symbol','contract_epoch_id','date','open','high','low','close','volume',
              'execution_only','allow_new_open','quantity_certified','quote_class','evidence_id'}
    if not required.issubset(overlay.columns):raise ValueError('quantity_quote_columns')
    if not overlay.execution_only.eq(True).all() or not overlay.allow_new_open.eq(False).all() or not overlay.quantity_certified.eq(False).all():
        raise ValueError('quantity_quote_authority_violation')
    if not overlay.quote_class.eq('quantity_conflict_price_consensus_execution_only').all():raise ValueError('unknown_quantity_quote_policy')
    if overlay.evidence_id.isna().any() or overlay.evidence_id.duplicated().any():raise ValueError('invalid_quantity_quote_evidence')
    values=overlay[['open','high','low','close','volume']].to_numpy(dtype=float)
    if not np.isfinite(values).all() or (values[:,:4]<=0).any() or (values[:,4]<1).any():raise ValueError('invalid_quantity_quote_values')
    if (overlay.low>overlay[['open','close']].min(axis=1)).any() or (overlay.high<overlay[['open','close']].max(axis=1)).any():raise ValueError('invalid_quantity_quote_geometry')
    meta=contracts.set_index('vt_symbol')
    if not overlay.vt_symbol.isin(meta.index).all():raise ValueError('unknown_quantity_quote_contract')
    if not overlay.contract_epoch_id.eq(overlay.vt_symbol.map(meta.contract_epoch_id)).all():raise ValueError('quantity_quote_epoch_mismatch')
    dates=pd.to_datetime(overlay.date,errors='raise').dt.strftime('%Y-%m-%d')
    if dates.gt(overlay.vt_symbol.map(meta.maturity_date)).any():raise ValueError('post_maturity_quantity_quote')
    if not dates.between('2014-01-01','2026-10-16').all():raise ValueError('quantity_quote_outside_research_interval')
    overlay['date']=dates
    combined=pd.concat([market,overlay],ignore_index=True,sort=False)
    if combined.duplicated(['vt_symbol','date']).any():raise ValueError('quantity_quote_overlaps_existing_market')
    combined=combined.sort_values(['vt_symbol','date']).reset_index(drop=True)
    return combined,dict(csv_sha256=sha(csv),manifest_sha256=sha(receipt),bound_rows=len(overlay),
        policy='price_consensus_quantity_uncertified_existing_position_execution_and_valuation_only')
