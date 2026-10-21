"""Frozen 230-URL original PMI source batch; no daily join, model or financial run."""
import argparse, hashlib, json, re, threading, time, unicodedata
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
import urllib.error, urllib.parse, urllib.request
from stage545_pmi_source_pilot import TextAndTables, NoRedirect

def now(): return datetime.now(timezone.utc).isoformat()
def digest(data): return hashlib.sha256(data).hexdigest()
def binding(path):
    data = path.read_bytes(); return {'path': str(path.resolve()), 'bytes': len(data), 'sha256': digest(data)}
def dump(path, obj):
    with path.open('x') as f: json.dump(obj, f, ensure_ascii=False, indent=2, allow_nan=False); f.write('\n')
def compact(s): return re.sub(r'\s+', '', unicodedata.normalize('NFKC', s))
def ym(s):
    m = re.fullmatch(r'(20\d{2})年(1[0-2]|0?[1-9])月(?:份)?', compact(s))
    return f'{int(m[1]):04d}-{int(m[2]):02d}' if m else None

class Page(TextAndTables):
    def __init__(self):
        super().__init__(); self.headings = []; self.capture = None; self.first_table_offset = None; self.header_end_offset = 0
    def handle_starttag(self, tag, attrs):
        if tag == 'table' and self.first_table_offset is None: self.first_table_offset = len(''.join(self.text))
        if tag in ('title','h1','h2'): self.capture = [tag, []]
        super().handle_starttag(tag, attrs)
    def handle_data(self, data):
        if self.capture is not None: self.capture[1].append(data)
        super().handle_data(data)
    def handle_endtag(self, tag):
        if self.capture is not None and tag == self.capture[0]:
            self.headings.append(compact(''.join(self.capture[1]))); self.capture = None
            if self.first_table_offset is None: self.header_end_offset = len(''.join(self.text))
        super().handle_endtag(tag)

def extract(body):
    hint = body[:4096].decode('ascii', errors='ignore')
    m = re.search(r'charset\s*=\s*[\"\']?([\w-]+)', hint, re.I); enc = m[1].lower() if m else 'utf-8'
    if enc in ('gbk','gb2312'): enc = 'gb18030'
    p = Page(); p.feed(body.decode(enc, errors='strict')); rawtext = ''.join(p.text); text = compact(rawtext)
    before = compact(rawtext[:p.first_table_offset]) if p.first_table_offset is not None else text
    titles = list(dict.fromkeys(p.headings)); titletext = '|'.join(titles)
    titlemonths = sorted({f'{int(y):04d}-{int(m):02d}' for y,m in re.findall(r'(20\d{2})年(1[0-2]|0?[1-9])月', titletext)})
    header_end = len(compact(rawtext[:p.header_end_offset])); leadtext = before[header_end:]
    lead = re.search(r'(20\d{2})年(1[0-2]|0?[1-9])月(?:份)?[，,]*(?:中国|全国)?制造业(?:采购经理指数|PMI)', leadtext)
    leadmonth = f'{int(lead[1]):04d}-{int(lead[2]):02d}' if lead else None
    bad = bool(re.search(r'解读|统计师|什么是|指标解释|调查制度|含义|编制方法|基础数据|如何', titletext))
    choices = set(titlemonths + ([leadmonth] if leadmonth else []))
    month = next(iter(choices)) if len(choices) == 1 and not bad else None
    state = 'monthly_report' if month else ('nonmonthly_or_out_of_scope' if bad else 'identity_unknown_or_conflict')
    result = {'titles': titles, 'report_month': month, 'identity_state': state,
              'identity_evidence': {'title_months': titlemonths, 'lead_month': leadmonth, 'lead': lead.group() if lead else None},
              'decode_encoding': enc, 'availability_qualified': False, 'first_vintage_qualified': False}
    prefix = before[:header_end+lead.start()] if lead else before[:header_end]
    clock = re.search(r'(20\d{2})[/\-](\d{1,2})[/\-](\d{1,2})[ T]?(\d{1,2}):(\d{2})', prefix)
    date = re.search(r'(?:发布时间|发布日期)[：:]?(20\d{2})[年/\-](\d{1,2})[月/\-](\d{1,2})日?', prefix)
    proxy = re.search(r'成文日期[：:]?(20\d{2})年(\d{1,2})月(\d{1,2})日', prefix)
    match = clock or date or proxy
    stamp = f'{int(match[1]):04d}-{int(match[2]):02d}-{int(match[3]):02d}' if match else None
    if clock: stamp += f'T{int(clock[4]):02d}:{int(clock[5]):02d}:00+08:00'
    result['clock'] = {'claimed_at': stamp, 'kind': 'publication_minute' if clock else 'publication_date' if date else 'document_date_proxy' if proxy else 'unknown',
                       'evidence': match.group() if match else None, 'timezone_basis': 'publisher_China_context_not_printed_suffix', 'availability_qualified': False}
    evidence = {'headline_pmi': [], 'new_orders': [], 'finished_goods': []}
    def add(key, value, source, **extra):
        try: value = float(value)
        except ValueError: return
        if 0 <= value <= 100: evidence[key].append(dict(value=value, source=source, **extra))
    if month:
        for ti, table in enumerate(p.tables):
            cells = [[compact(c) for c in row] for row in table]; flat = '|'.join(c for row in cells for c in row)
            main = all(k in flat for k in ['生产','新订单','原材料库存','从业人员','供应商配送']) and '商务活动' not in flat
            aux = all(k in flat for k in ['新出口订单','采购量','产成品库存']) and not any(k in flat for k in ['商务活动','投入品价格'])
            if not (main or aux): continue
            # Early vertical tables: reference months are columns, index names are rows.
            for ri, row in enumerate(cells):
                cols = [j for j,c in enumerate(row) if ym(c) == month]
                if not cols or ri > 3: continue
                for later in cells[ri+1:]:
                    key = {'PMI':'headline_pmi','新订单':'new_orders','产成品库存':'finished_goods'}.get(later[0] if later else '')
                    if key:
                        for j in cols:
                            if j < len(later): add(key, later[j], 'vertical_table', table=ti, column=j, label=later[0])
            # Later horizontal tables: preserve combined rowspan headers, exact current row only.
            headers = []; headerlabels = ['PMI','生产','新订单','原材料库存','主要原材料库存','从业人员','供应商配送时间','供应商配送',
                '新出口订单','进口','采购量','主要原材料购进价格','出厂价格','产成品库存','在手订单','生产经营活动预期']
            for row in cells:
                if row and ym(row[0]): break
                for c in row:
                    if c in headerlabels and c not in headers: headers.append(c)
            for ri, row in enumerate(cells):
                if not row or ym(row[0]) != month or len(row)-1 != len(headers): continue
                for label, key in [('PMI','headline_pmi'),('新订单','new_orders'),('产成品库存','finished_goods')]:
                    if label in headers: add(key, row[1+headers.index(label)], 'horizontal_table', table=ti, row=ri, label=label)
        # Narrative cannot cross into nonmanufacturing; no question-list or direction-only fill.
        scope = before[header_end+lead.start():] if lead else before[header_end:]
        scope = re.split(r'二[、.．](?:中国)?非制造业', scope)[0]
        for label,key in [('新订单','new_orders'),('产成品库存','finished_goods')]:
            for m in re.finditer(r'(?<![新出外])'+label+r'指数(?:为|是)(\d+(?:\.\d+)?)%', scope):
                add(key, m[1], 'manufacturing_narrative', text=m.group())
        for m in re.finditer(r'(?<!非)制造业(?:采购经理指数(?:\(PMI\))?|PMI)(?:为|是)(\d+(?:\.\d+)?)%', scope):
            add('headline_pmi', m[1], 'manufacturing_narrative', text=m.group())
    result['fields'] = {}
    for key, items in evidence.items():
        items = list({json.dumps(e, sort_keys=True, ensure_ascii=False): e for e in items}.values()); values = sorted({e['value'] for e in items})
        result['fields'][key] = {'value': values[0] if len(values) == 1 else None,
            'state': 'agrees' if len(values) == 1 else 'conflict' if values else 'unparsed_or_not_reported', 'evidence': items}
    methods = text.split('调查范围',1)[-1] if '调查范围' in text else ''
    gb = sorted(set(re.findall(r'GB/T4754[-—](?:19|20)\d{2}', methods)))
    samples = re.findall(r'(?<!非)制造业(?:的)?\d+个行业大类[，,](\d+)家调查样本', methods)
    expanded = re.findall(r'调查样本从原来的\d+家(?:扩充|扩大)(?:到|至)(\d+)家', methods)
    if expanded: samples += expanded
    elif not samples: samples += re.findall(r'从全国(?:制造业企业中)?抽取(\d+)家样本企业', methods)
    values = sorted(set(map(int, samples))); industry = sorted(set(map(int,re.findall(r'(?<!非)制造业(?:的)?(\d+)个行业大类', methods))))
    result['methodology'] = {'gb_candidates': gb, 'manufacturing_sample_candidates': values,
        'manufacturing_sample': values[0] if len(values)==1 else None, 'manufacturing_industry_count_candidates': industry}
    result['pair_complete'] = month is not None and all(result['fields'][k]['value'] is not None for k in ['new_orders','finished_goods'])
    return result

def main(protocol_path, output, check):
    protocol = json.loads(protocol_path.read_text()); net = protocol['network']; cb = protocol['candidate_binding']; cp = Path(cb['path'])
    assert binding(cp) == cb and protocol['schema'] == 'stage560_frozen_pmi_original_article_batch_v1'
    candidates = json.loads(cp.read_text()); assert len(candidates) == 230 and len({c['url'] for c in candidates}) == 230
    cache = protocol['cache_exact_URL']; assert sum(c['url'] not in cache for c in candidates) <= 228
    assert (net['concurrency'],net['timeout_seconds'],net['maximum_body_bytes'],net['minimum_start_gap_seconds']) == (2,12,2097152,0.3)
    assert not net['automatic_retry'] and not net['follow_redirects'] and not net['fallback']
    for c in candidates:
        u = urllib.parse.urlsplit(c['url']); assert u.hostname == 'www.stats.gov.cn' and u.scheme in ('http','https')
    output.mkdir(parents=True,exist_ok=False)
    if check:
        records = []
        for suffix, expected in [('nbs_201008',(2010,8,53.1,None,'publication_minute')),('nbs_201901',(2019,1,49.6,47.1,'publication_minute')),('nbs_202001',(2020,1,51.4,46.0,'document_date_proxy'))]:
            item = next(v for v in cache.values() if v['source_id']==suffix); path = Path(item['raw']['path']); assert binding(path)==item['raw']
            result = extract(path.read_bytes()); y,m,no,fg,clock = expected
            assert (result['report_month'],result['fields']['new_orders']['value'],result['fields']['finished_goods']['value'],result['clock']['kind']) == (f'{y:04d}-{m:02d}',no,fg,clock), result
            records.append({'source_id':suffix,'extract':result})
        ready = {'source_ready':True,'actual_started':False,'source':binding(Path(__file__)),'shared_parser':binding(Path(__file__).with_name('stage545_pmi_source_pilot.py')),
                 'protocol':binding(protocol_path),'checks':records,'GET':0,'fit':0,'cash':0,'SQL':0}
        dump(output/'source_ready.json',ready); print(json.dumps({k:v for k,v in ready.items() if k!='checks'})); return
    started = time.monotonic(); lock = threading.Lock(); last_start = [0.0]
    dump(output/'started.json',{'started_at':now(),'protocol':binding(protocol_path),'source':binding(Path(__file__))})
    def fetch(pair):
        index,item = pair; url = item['url']; stem=f'url_{index:03d}'; response=None; body=b''
        receipt={'id':stem,'url':url,'started_at':now(),'request_count':int(url not in cache),'retry':False,'redirect_followed':False,'candidate':item}
        try:
            if url in cache:
                previous=cache[url]; path=Path(previous['raw']['path']); body=path.read_bytes()
                assert (len(body),digest(body))==(previous['raw']['bytes'],previous['raw']['sha256'])
                receipt.update(cached_source=previous,http_status=200,headers=json.loads(Path(previous['receipt']).read_text()).get('headers',{}))
            else:
                with lock:
                    time.sleep(max(0,0.3-(time.monotonic()-last_start[0]))); last_start[0]=time.monotonic(); receipt['request_started_at']=now()
                req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0','Accept-Encoding':'identity'})
                try: response=urllib.request.build_opener(NoRedirect()).open(req,timeout=12)
                except urllib.error.HTTPError as e: response=e
                receipt.update(http_status=response.status,response_url=response.geturl(),headers=dict(response.headers)); body=response.read(2097153)
            receipt['body_over_limit']=len(body)>2097152
            normalized=extract(body) if receipt['http_status']==200 and not receipt['body_over_limit'] else {'identity_state':'transport_unavailable','report_month':None,'pair_complete':False}
        except Exception as e:
            receipt.update(error_type=type(e).__name__,error=str(e)); normalized={'identity_state':'transport_or_parser_error','report_month':None,'pair_complete':False}
        finally:
            if response is not None: response.close()
        raw=output/(stem+'.body'); raw.write_bytes(body); receipt['raw']=binding(raw); receipt['completed_at']=now()
        normalized.update(id=stem,url=url,raw=receipt['raw']); dump(output/(stem+'_receipt.json'),receipt); dump(output/(stem+'_extract.json'),normalized)
        print(json.dumps({'id':stem,'status':receipt.get('http_status'),'month':normalized['report_month'],'pair':normalized['pair_complete']}),flush=True)
        return receipt,normalized
    with ThreadPoolExecutor(max_workers=2) as pool: results=list(pool.map(fetch,enumerate(candidates)))
    normalized=[v for _,v in results]; dump(output/'article_extracts.json',normalized); grid=[]
    for y in range(2010,2027):
        for m in range(1,13):
            if (y,m)>(2026,9): continue
            month=f'{y:04d}-{m:02d}'; versions=[r for r in normalized if r['report_month']==month]
            fields={k:sorted({r['fields'][k]['value'] for r in versions if r.get('fields',{}).get(k,{}).get('value') is not None}) for k in ['new_orders','finished_goods']}
            grid.append({'report_month':month,'version_ids':[r['id'] for r in versions],'version_count':len(versions),'pair_complete_versions':sum(r['pair_complete'] for r in versions),
                'field_values':fields,'cross_version_conflict':any(len(v)>1 for v in fields.values()),'within_version_conflict':any(any(f['state']=='conflict' for f in r.get('fields',{}).values()) for r in versions),
                'clock_kinds':sorted({r['clock']['kind'] for r in versions if 'clock' in r}),'methodology':[r['methodology'] for r in versions if 'methodology' in r],
                'availability_qualified':False,'first_vintage_qualified':False})
    dump(output/'coverage_201_months.json',{'months':grid,'unresolved_articles':[r['id'] for r in normalized if not r['report_month']]})
    terminal={'status':'completed','exit_code':0,'new_GET_attempts':sum(r['request_count'] for r,_ in results),'cached_URLs':sum('cached_source' in r for r,_ in results),
        'URL_count':len(results),'http200':sum(r.get('http_status')==200 for r,_ in results),'transport_or_parser_errors':sum('error_type' in r for r,_ in results),
        'original_months_confirmed':sum(bool(r['version_count']) for r in grid),'pair_complete_months':sum(bool(r['pair_complete_versions']) for r in grid),
        'pair_complete_URL_versions':sum(r['pair_complete'] for r in normalized),'cross_version_conflict_months':sum(r['cross_version_conflict'] for r in grid),
        'unresolved_URLs':sum(not r['report_month'] for r in normalized),'fit':0,'cash':0,'SQL':0,'elapsed_seconds':time.monotonic()-started,'full_history_qualified':False,'goal_complete':False}
    dump(output/'manifest.json',{'protocol':binding(protocol_path),'source':binding(Path(__file__)),'shared_parser':binding(Path(__file__).with_name('stage545_pmi_source_pilot.py')),'records':[r for r,_ in results],'terminal':terminal})
    dump(output/'terminal.json',terminal); print(json.dumps(terminal),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('--protocol',type=Path,required=True); p.add_argument('--output',type=Path,required=True); p.add_argument('--check-cache',action='store_true')
    a=p.parse_args(); main(a.protocol,a.output,a.check_cache)
