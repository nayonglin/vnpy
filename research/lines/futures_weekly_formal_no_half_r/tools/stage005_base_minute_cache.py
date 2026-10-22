"""Stage005原分钟CSV无损数据缓存；无策略/账户/订单/回测调用。

bars.parquet保存pd.read_csv读出的完整raw DataFrame，不做符号过滤或规范化，
从而任意请求均保留原loader“先过滤、后转换”的类型推断语义。读取时按请求
symbols过滤后精确沿用Stage901转换步骤。完整readback及实际请求输出均严格
assert_frame_equal。source/cache/代码每次重新SHA校验，不以stat代替内容证明。
"""
from __future__ import annotations
from pathlib import Path
from datetime import datetime
import argparse, hashlib, inspect, json, os, sys, tempfile, time
import pandas as pd

ROOT=Path(__file__).resolve().parents[4]
LINE=ROOT/'research/lines/futures_weekly_formal_no_half_r'
DEFAULT_CACHE=LINE/'outputs/stage005_base_minute_cache'
SCHEMA='stage005_lossless_base_minute_csv_cache_v1'


def sha(path):
    result=hashlib.sha256()
    with Path(path).open('rb') as handle:
        for chunk in iter(lambda:handle.read(1024*1024),b''):result.update(chunk)
    return result.hexdigest()


def dataframe_schema(frame):
    return dict(columns=list(frame.columns),dtypes={str(k):str(v) for k,v in frame.dtypes.items()},
        rows=len(frame),index_type=type(frame.index).__name__,index_name=frame.index.name,
        columns_type=type(frame.columns).__name__,columns_name=frame.columns.name)


def normalize_like_stage901(data,vt_symbols):
    """与冻结Stage901 loader在read_csv之后的代码相同；先过滤，后转换。"""
    data=data[data['vt_symbol'].astype(str).isin(vt_symbols)].copy()
    data['bar_datetime']=pd.to_datetime(data['bar_datetime'],errors='coerce')
    if 'bar_date' not in data.columns:data['bar_date']=data['bar_datetime'].dt.normalize()
    else:data['bar_date']=pd.to_datetime(data['bar_date'],errors='coerce').dt.normalize()
    for column in ['open','high','low','close','volume','open_oi','close_oi']:
        if column in data.columns:data[column]=pd.to_numeric(data[column],errors='coerce')
    return data.dropna(subset=['vt_symbol','bar_datetime','open','high','low','close']).reset_index(drop=True)


def assert_exact(left,right):
    pd.testing.assert_frame_equal(left,right,check_dtype=True,check_exact=True,check_index_type=True,
        check_column_type=True,check_categorical=True,check_freq=True,check_flags=True)


def verified_manifest(cache_dir,source_path=None):
    cache_dir=Path(cache_dir);path=cache_dir/'manifest.json'
    if not path.is_file() or not (cache_dir/'bars.parquet').is_file():raise ValueError('minute_cache_incomplete_or_unrecognized')
    manifest=json.loads(path.read_text())
    if manifest.get('schema')!=SCHEMA:raise ValueError('minute_cache_schema_changed')
    source=Path(manifest['source_csv']).resolve()
    if source_path is not None and source!=Path(source_path).resolve():raise ValueError('minute_cache_source_path_changed')
    if sha(source)!=manifest['source_sha256']:raise ValueError('minute_cache_source_sha_changed')
    parquet=cache_dir/'bars.parquet'
    if sha(parquet)!=manifest['cached_sha256']:raise ValueError('minute_cache_parquet_sha_changed')
    for file,digest in manifest['code_files'].items():
        if sha(file)!=digest:raise ValueError('minute_cache_code_sha_changed:'+file)
    return manifest


def load_cached_minute_bars(vt_symbols,*,source_path=None,cache_dir=DEFAULT_CACHE):
    """提供原loader相同签名的symbols参数；调用者仍须冻结manifest/cache身份。"""
    cache_dir=Path(cache_dir);manifest=verified_manifest(cache_dir,source_path)
    raw=pd.read_parquet(cache_dir/'bars.parquet')
    if dataframe_schema(raw)!=manifest['raw_dataframe_schema']:raise ValueError('minute_cache_dataframe_schema_changed')
    result=normalize_like_stage901(raw,set(vt_symbols))
    # 同次读取结束仍检查内容；不接受校验后被改动的源或parquet。
    if sha(manifest['source_csv'])!=manifest['source_sha256']:raise ValueError('minute_cache_source_changed_during_read')
    if sha(cache_dir/'bars.parquet')!=manifest['cached_sha256']:raise ValueError('minute_cache_parquet_changed_during_read')
    return result


def prepare_cache(source_path,vt_symbols,original_loader,cache_dir,*,minimum_loader_seconds=0.5):
    """计时一次真实loader；足够慢才创建缓存，已存在只核验、不覆盖。"""
    source_path=Path(source_path).resolve();cache_dir=Path(cache_dir).resolve()
    if cache_dir.exists():
        manifest=verified_manifest(cache_dir,source_path)
        raw=pd.read_parquet(cache_dir/'bars.parquet')
        if dataframe_schema(raw)!=manifest['raw_dataframe_schema']:raise ValueError('minute_cache_existing_dataframe_changed')
        return dict(status='verified_existing_cache_no_overwrite',manifest=manifest)
    before=sha(source_path);timings={}
    started=time.perf_counter();expected=original_loader(set(vt_symbols));timings['original_loader_seconds']=time.perf_counter()-started
    if sha(source_path)!=before:raise ValueError('minute_csv_changed_during_original_loader')
    if timings['original_loader_seconds']<minimum_loader_seconds:
        return dict(status='loader_fast_enough_no_cache',source_csv=str(source_path),source_sha256=before,
                    source_bytes=source_path.stat().st_size,requested_symbols=len(vt_symbols),requested_rows=len(expected),timings=timings)
    started=time.perf_counter();raw=pd.read_csv(source_path,encoding='utf-8-sig');timings['full_raw_csv_read_seconds']=time.perf_counter()-started
    # 直接比较完整内存源的同一转换与实际原loader，排除语义漂移。
    assert_exact(normalize_like_stage901(raw,set(vt_symbols)),expected)
    stage=cache_dir.parent/'stage005_base_minute_cache_builds';stage.mkdir(parents=True,exist_ok=True)
    temporary=Path(tempfile.mkdtemp(prefix='cache_',dir=stage))
    parquet=temporary/'bars.parquet'
    started=time.perf_counter();raw.to_parquet(parquet,index=None,compression='zstd');timings['parquet_write_seconds']=time.perf_counter()-started
    started=time.perf_counter();readback=pd.read_parquet(parquet);timings['parquet_read_seconds']=time.perf_counter()-started
    assert_exact(readback,raw)
    started=time.perf_counter();actual=normalize_like_stage901(readback,set(vt_symbols));timings['cached_filter_and_normalize_seconds']=time.perf_counter()-started
    assert_exact(actual,expected)
    if sha(source_path)!=before:raise ValueError('minute_csv_changed_during_cache_build')
    loader_file=Path(inspect.getsourcefile(original_loader)).resolve()
    manifest=dict(schema=SCHEMA,created_at=datetime.now().astimezone().isoformat(),
        representation='entire_original_pd_read_csv_dataframe_before_symbol_filter_or_normalization',
        source_csv=str(source_path),source_sha256=before,source_sha256_after=before,source_unchanged=True,
        source_bytes=source_path.stat().st_size,cached_file='bars.parquet',cached_sha256=sha(parquet),cached_bytes=parquet.stat().st_size,
        raw_dataframe_schema=dataframe_schema(raw),raw_symbol_count=int(raw.vt_symbol.astype(str).nunique()),
        requested_symbols=len(vt_symbols),requested_symbol_set_sha256=hashlib.sha256(json.dumps(sorted(vt_symbols)).encode()).hexdigest(),
        requested_output_schema=dataframe_schema(expected),strict_full_raw_readback_equal=True,strict_requested_output_equal=True,
        parser='pandas.read_csv(encoding=utf-8-sig)',pandas_version=pd.__version__,
        original_loader_function=original_loader.__qualname__,
        original_loader_function_source_sha256=hashlib.sha256(inspect.getsource(original_loader).encode()).hexdigest(),
        code_files={str(Path(__file__).resolve()):sha(__file__),str(loader_file):sha(loader_file)},
        timings=timings,financial_replays=0,order_api_calls=0,network_calls=0)
    (temporary/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    if cache_dir.exists():raise ValueError('minute_cache_destination_created_concurrently')
    os.rename(temporary,cache_dir)
    started=time.perf_counter();validated=load_cached_minute_bars(vt_symbols,source_path=source_path,cache_dir=cache_dir);validated_seconds=time.perf_counter()-started
    assert_exact(validated,expected)
    # 新建补充计时文件；不改已固定manifest。
    with (cache_dir/'validated_read_timing.json').open('x') as handle:json.dump(dict(verified_cached_load_seconds=validated_seconds,
        original_loader_seconds=timings['original_loader_seconds'],strict_output_equal=True),handle,indent=2)
    return dict(status='created_and_strictly_verified',cache_dir=str(cache_dir),manifest=manifest,verified_cached_load_seconds=validated_seconds)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--self-test',action='store_true');parser.add_argument('--minimum-loader-seconds',type=float,default=0.5);args=parser.parse_args()
    if args.self_test:return self_test()
    vendor='/Users/mac/Documents/Codex/fian-handoff-20261014/vnpy_handoff_20261014/vendor'
    sys.path[:0]=[str(ROOT),vendor,str(ROOT/'examples/portfolio_backtesting')]
    os.environ.setdefault('MPLCONFIGDIR','/private/tmp/weekly-research-mpl')
    from vnpy.trader.setting import SETTINGS
    SETTINGS.update({'log.file':False,'log.console':False,'log.active':False})
    import contract_metadata as cm
    cm.ALL_FUTURES_CONTRACT_METADATA_PATH=LINE/'outputs/stage005_data/metadata.csv'
    import main_contract_mapping as mm
    import analyze_qmt_roll_stage901_stage847_c9_2026_ytd_live_shadow as s901
    products=mm.load_product_universe_symbols(LINE/'outputs/stage005_data/universe.csv')
    metadata=mm.build_contract_metadata(mapping_path=LINE/'outputs/stage005_data/mapping.csv',supported_symbols=products)
    result=prepare_cache(s901.s861.FULL_MINUTE_BARS_PATH,set(metadata['vt_symbols']),s901._load_stage861_full_minute_bars,DEFAULT_CACHE,minimum_loader_seconds=args.minimum_loader_seconds)
    print(json.dumps({k:v for k,v in result.items() if k!='manifest'},ensure_ascii=False),flush=True)
    if 'manifest' in result:
        m=result['manifest'];print(json.dumps(dict(source_mib=m['source_bytes']/1024**2,cached_mib=m['cached_bytes']/1024**2,
            raw_rows=m['raw_dataframe_schema']['rows'],raw_symbols=m['raw_symbol_count'],requested_symbols=m['requested_symbols'],
            requested_rows=m['requested_output_schema']['rows'],timings=m['timings'],strict_raw_and_requested_equal=True),ensure_ascii=False),flush=True)


def self_test():
    import unittest
    class Tests(unittest.TestCase):
        def test_full_lossless_and_subset_type_semantics_and_change_guards(self):
            with tempfile.TemporaryDirectory() as temporary:
                root=Path(temporary);source=root/'source.csv';destination=root/'cache'
                source.write_text('vt_symbol,bar_datetime,bar_date,open,high,low,close,volume,open_oi,close_oi\nA.X,2020-01-01 09:00,2020-01-01,1,2,1,2,3,4,5\nB.X,2020-01-01 09:00,2020-01-01,bad,2,1,2,3,4,5\n')
                def original(symbols):return normalize_like_stage901(pd.read_csv(source,encoding='utf-8-sig'),symbols)
                result=prepare_cache(source,{'A.X'},original,destination,minimum_loader_seconds=0)
                self.assertEqual(result['manifest']['raw_dataframe_schema']['rows'],2)
                for symbols in [{'A.X'},{'B.X'},{'A.X','B.X'},set()]:assert_exact(load_cached_minute_bars(symbols,cache_dir=destination),original(symbols))
                self.assertEqual(prepare_cache(source,{'A.X'},original,destination)['status'],'verified_existing_cache_no_overwrite')
                with source.open('a') as handle:handle.write('\n')
                with self.assertRaisesRegex(ValueError,'source_sha'):load_cached_minute_bars({'A.X'},cache_dir=destination)
        def test_incomplete_existing_folder_rejected(self):
            with tempfile.TemporaryDirectory() as temporary:
                with self.assertRaisesRegex(ValueError,'incomplete'):verified_manifest(Path(temporary))
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
    if not result.wasSuccessful():raise SystemExit(1)

if __name__=='__main__':main()
