"""Finite saved native cases only; independent Wilder and first-hit interpretation."""
import gzip,json
import numpy as np
from stage102_cash_adapter import compare,bound

def review_native(binding,kind):
    payload=json.loads(gzip.decompress(bound(binding)))
    assert payload['schema']=='stage070_finite_first_native_cases_v1' and payload['raw_ohlc'] is True
    assert payload['native_source_queries']==0
    result=[]
    for case in payload['cases']:
        e=case['event'];s=case['selection'];bars=case['bars'];u=int(e['u_index']);k=float(case['policy_k'])
        assert k==(2. if s['policy']=='WIDE' else .25)
        assert [b['source_index'] for b in bars]==list(range(u-int(e['history_run'])+1,bars[-1]['source_index']+1))
        local={b['source_index']:b for b in bars};nd={};lows={};run=0;N=None;previous=None;trlist=[];lowlist=[]
        for b in bars:
            ix=b['source_index']
            if b['native_missing'] or not b.get('valid',False):
                run=0;N=None;previous=None;trlist=[];lowlist=[];continue
            tr=b['high']-b['low'] if previous is None else max(b['high']-b['low'],abs(b['high']-previous),abs(b['low']-previous))
            run+=1;trlist.append(tr);lowlist.append(b['low'])
            if run==20:N=sum(trlist)/20
            elif run>20:N=(19*N+tr)/20
            if run>=20:nd[ix]=N;lows[ix]=min(lowlist[-20:])
            previous=b['close']
        compare([nd[u],lows[u],local[u]['close']],[e['N_u'],e['low20_u'],e['u_close']],'native_Wilder_low20_C',atol=1e-9)
        D=u+1;first=local.get(D);exit_result=None
        if first is None or first['native_missing'] or not first.get('valid'):
            exit_result=('entry_execution_unknown',D,None,None)
        else:
            F=first['open'];SL=F-k*nd[u];B=max(SL,lows[u]);force=None
            compare(e['entry_reference'],F,'native_label_entry_reference')
            if e.get('SL0') is not None:compare(e['SL0'],SL,'native_initial_stop')
            schedule={r['u_date']:r.get('reference_epoch') for r in case['reference_schedule']}
            for ix in range(D,bars[-1]['source_index']+1):
                b=local[ix]
                if b['native_missing'] or not b.get('valid'):
                    exit_result=('path_or_execution_unknown',ix,None,None);break
                if force:ref=b['open'];reason=force
                elif b['open']<=B:ref=b['open'];reason='gap_stop'
                elif b['low']<=B:ref=B;reason='stop_boundary'
                else:ref=None;reason=None
                if ref is not None:
                    exit_result=('closed_complete_bar_model',ix,ref,reason);break
                B=max(SL,lows[ix])
                current=schedule.get(b['date'])
                force=('lifecycle_exit' if ix+1>=int(e['lifecycle_index']) else
                       'observation_exit_requested' if not current else 'liquidity_reference_changed' if current!=e['reference_epoch'] else None)
        if kind=='labels':
            assert exit_result is not None and exit_result[0]==e['label_state']
            state,ix,ref,reason=exit_result
            if state=='closed_complete_bar_model':
                assert ix==int(e['exit_index']) and reason==e['exit_reason']
                compare(e['exit_reference'],ref,'native_label_first_exit')
                assert e['label_known_date']==e['exit_date']==local[ix]['date']
            else:assert ix==int(e['unknown_index'])
        else:
            decision=bars[-1];assert decision['date']==s['date']
            if 'fill' in s:
                fill=s['fill'];assert not decision['native_missing'] and decision['valid']
                if fill['reason']=='stop_boundary':
                    assert exit_result is not None and exit_result[0]=='closed_complete_bar_model'
                    assert exit_result[1]==decision['source_index'];compare(fill['reference_price'],exit_result[2],'native_cash_stop')
                else:compare(fill['reference_price'],decision['open'],'native_cash_open_exit')
            if 'position' in s:
                assert decision['native_missing'] or not decision.get('valid');assert s['position']['mark_state']=='stale'
        outcome=None if exit_result is None else {'state':exit_result[0],'source_index':exit_result[1],'reason':exit_result[3]}
        result.append(dict(policy=s['policy'],kind=s['kind'],event_id=s['event_id'],bars=len(bars),warmup=int(e['history_run']),model_first_exit=outcome))
    return result
