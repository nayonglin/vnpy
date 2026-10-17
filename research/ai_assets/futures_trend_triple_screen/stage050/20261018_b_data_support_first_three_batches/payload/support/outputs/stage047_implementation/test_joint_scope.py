"""One fixture: wanted identities, old/new filtering and actual Stage021 parser.

Synthetic price values test parser identity only. No actual data is qualified,
no resolver main is executed, and this fixture receipt is never an engine input.
"""
from pathlib import Path
from copy import deepcopy
import json
import sys

LINE=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(LINE/'tools'))
import stage047_multi_exact_request_resolver as resolver


def main():
    dest=Path(__file__).parent/'fixture_only';dest.mkdir(exist_ok=False)
    actual=resolver.frozen.read_json(LINE/'outputs/stage036_b_ts_account/B_TS/data_wait/request_e57199da875c3f6f91f6d282066dbc73c6a6c2d897f5461f4750ca9ebca49ce9/request.json')
    assert len(actual['active_orders'])==3 and len(actual['requirements'])==2
    request=deepcopy(actual);request['requirements'][0]['existing_source_timestamps']=request['requirements'][0]['required_timestamps']
    request['request_sha256']=resolver.gate.request_sha256(request)
    old,new=resolver.request_key_scope(request)
    assert len(old)==len(new)==1
    frames={}
    for target in request['requirements']:
        identity=tuple(target[k]for k in ['vt_symbol','execution_trade_date','requirement_kind'])
        frames[identity]=resolver.pd.DataFrame([dict(vt_symbol=identity[0],bar_datetime=resolver.pd.Timestamp(stamp),
            open=10.,high=11.,low=9.,close=10.,volume=1.,open_oi=3.,close_oi=3.)for stamp in target['required_timestamps']])
    data,accepted=resolver.assemble_delivery(request,frames)
    assert len(data)==len(accepted)==2 and all(r['vt_symbol']!='rb2005.SHFE'for r in accepted)
    added=data.loc[[((str(row.vt_symbol),resolver.pd.Timestamp(row.bar_datetime))in new)for row in data.itertuples(index=False)]]
    assert len(added)==1 and set(added.vt_symbol)=={'hc2005.SHFE'}
    data_path=(dest/'fixture_data.csv').resolve();data.to_csv(data_path,index=False);data_sha=resolver.old.sha256(data_path)
    receipt_path=(dest/'fixture_only_receipt.json').resolve()
    resolver.frozen.write(receipt_path,dict(schema=resolver.gate.RECEIPT_SCHEMA,independent_review=True,
        reviewer='fixture_only_not_actual_data_qualification',qualified_research_data=True,p0_findings=0,p1_findings=0,
        request_sha256=request['request_sha256'],accepted_requirements=accepted,data_path=str(data_path),data_sha256=data_sha,
        source_fingerprints={str(data_path):data_sha},fixture_scope=True,signed_for_engine=False))
    parsed,full,anchors,info=resolver.gate._read_delivery(request,resolver.gate.QualifiedDelivery(receipt_path,resolver.old.sha256(receipt_path)))
    assert len(parsed)==2 and not full and len(anchors)==2 and info['accepted_keys']==2
    calendar=resolver.pd.DatetimeIndex(resolver.pd.to_datetime(sorted(resolver.pd.read_csv(resolver.old.MAPPING,usecols=['date']).date.unique())))
    probe=deepcopy(actual);first=probe['requirements'][0]
    grid=resolver.old.session_grid(first['vt_symbol'],first['execution_trade_date'],calendar)
    first['requirement_kind']='full_session';first['required_timestamps']=[s.isoformat()for s in grid]
    first['existing_source_timestamps']=first['required_timestamps'][:-1]
    first['missing_or_unqualified_timestamps']=first['required_timestamps'][-1:]
    old_probe,new_probe=resolver.request_key_scope(probe)
    assert len(old_probe)==len(grid)-1 and len(new_probe)==2
    result=dict(status='joint_scope_fixture_passed',actual_request_qualified=False,fixture_only=True,actual_main_runs=0,
        wanted_requirements=2,active_orders=3,delivered_rows=2,full_keys=0,anchor_keys=2,old_keys=1,new_keys=1,
        A0_candidate_new_rows=1,nonrequired_rb_excluded=True,partial_missing_full_grid_minutes=len(grid),
        partial_missing_old_keys=len(old_probe),partial_missing_new_keys=len(new_probe),
        actual_stage021_parser_passed=True,source_sha256=resolver.old.sha256(resolver.__file__),
        fixture_sha256=resolver.old.sha256(__file__),financial_replays=0,network_connections=0,orders=0,response_written=False)
    resolver.frozen.write(Path(__file__).parent/'joint_scope_result.json',result)
    print(json.dumps(result,ensure_ascii=False))


if __name__=='__main__':main()
