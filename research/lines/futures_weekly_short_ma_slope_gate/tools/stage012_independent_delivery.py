"""Offline PNG/HTML and publication-state binding for Stage012; no browser."""
from pathlib import Path
from html.parser import HTMLParser
import argparse,base64,hashlib,json,re
import numpy as np
from PIL import Image
ROOT=Path(__file__).resolve().parents[4];LINE=ROOT/'research/lines/futures_weekly_short_ma_slope_gate';STAGES=LINE/'stages'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p):return json.loads(Path(p).read_text())
class Document(HTMLParser):
 def __init__(self):super().__init__();self.images=[];self.rows=[];self.options=[];self.external=[]
 def handle_starttag(self,tag,attrs):
  a=dict(attrs)
  if tag=='img':self.images.append(a)
  if tag=='tr' and 'data-start' in a:self.rows.append(a['data-start'])
  if tag=='option':self.options.append(a.get('value'))
  if tag in ['script','iframe','video','audio','source','link'] and any(k in a for k in ['src','href']):self.external.append((tag,a))
def normalized_html(t):return re.sub(r'data:image/png;base64,[A-Za-z0-9+/=]+','<EXACT_PUBLISHED_PNG>',t.replace('独立复核中','独立复核通过（有局限）'))
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--report',type=Path,default=LINE/'artifacts/stage012_reserve50k_comparison');ap.add_argument('--pending',action='store_true');ap.add_argument('--output',type=Path);ap.add_argument('--numeric-review',type=Path,default=STAGES/'stage012_independent_numeric_review_v2.json');a=ap.parse_args();folder=a.report/'review_pending' if a.pending else a.report;output=a.output or STAGES/('stage012_independent_pending_delivery_review.json' if a.pending else 'stage012_independent_delivery_review.json')
 if output.exists():raise ValueError('immutable_stage012_delivery_review_exists')
 r=load(folder/'delivery_receipt.json');data=load(a.report/'data_manifest.json')['files_sha256'];expected='INDEPENDENT_REVIEW_PENDING' if a.pending else 'PASS_WITH_LIMITATIONS';assert r['status']==expected and r['data_files_sha256']==data and r['browser_interaction_verified'] is False and r['promotion_decision']=='NO_PROMOTION'
 if a.pending:assert r['independent_review_sha256'] is None
 else:
  numeric=load(a.numeric_review);assert numeric['status']=='PASS_WITH_LIMITATIONS' and not numeric['failures'] and numeric['data_files_sha256']==data and r['independent_review_sha256']==sha(a.numeric_review)
  for q,h in numeric['audited_code_sha256'].items():assert sha(q)==h,q
 for q,h in {**data,**r['figure_files_sha256'],**r['report_files_sha256']}.items():assert sha(q)==h,q
 html=next(Path(q) for q in r['report_files_sha256'] if q.endswith('.html'));text=html.read_text();doc=Document();doc.feed(text);starts=load(STAGES/'stage012_freeze.json')['starts'];assert len(doc.images)==5 and len(doc.rows)==46 and all(doc.rows.count(s)==2 for s in starts) and doc.options==['all']+starts and not doc.external;assert '9' in text and '14' in text and 'proven_nonbinding_reuse' in text and 'fresh_engine' in text and 'NO_PROMOTION' in text;assert 'fetch(' not in text and 'XMLHttpRequest' not in text
 figures={};pixels={}
 for image,q in zip(doc.images,r['figure_files_sha256']):
  assert image['src'].startswith('data:image/png;base64,') and hashlib.sha256(base64.b64decode(image['src'].split(',',1)[1],validate=True)).hexdigest()==sha(q),'embedded_png_exact_published_bytes'
  with Image.open(q) as im:im.verify()
  with Image.open(q) as im:
   imagearray=np.asarray(im.convert('RGBA'));rgb=imagearray[:,:,:3];nonwhite=float((rgb.min(axis=2)<230).mean());assert im.width>=1500 and im.height>=900 and .01<nonwhite<.9;figures[q]={'sha256':sha(q),'width':im.width,'height':im.height,'nonwhite_fraction':nonwhite}
  if not a.pending:
   old=np.asarray(Image.open(a.report/'review_pending'/Path(q).name).convert('RGBA'));assert old.shape==imagearray.shape;ys,xs=np.where(np.any(old!=imagearray,axis=2));assert len(ys)>0 and int(ys.max())<80,'only_status_title_pixels_may_change';pixels[Path(q).name]={'changed_pixels':len(ys),'changed_bbox':[int(xs.min()),int(ys.min()),int(xs.max()),int(ys.max())],'all_chart_body_pixels_exact':True}
 if not a.pending:
  assert normalized_html(text)==normalized_html((a.report/'review_pending'/html.name).read_text()),'HTML_only_status_and_verified_PNG_payload_changes';assert (folder/'report.md').read_text()==(a.report/'review_pending/report.md').read_text().replace('独立复核中','独立复核通过（有局限）'),'Markdown_only_status_changed'
 records={};found=set()
 for q in (STAGES/'stage012_windows').glob('*.md'):
  match=re.search(r'_stage012_C_(\d{8})\.md$',q.name);assert match;v=match.group(1);start=v[:4]+'-'+v[4:6]+'-'+v[6:];assert start not in found;found.add(start);t=q.read_text();assert all(k in t for k in ['NO_PROMOTION','proven_nonbinding_reuse','fresh_engine','期末交易权益','真实交易净盈亏','累计入金','账户回撤','账户Sharpe','胜率','平均盈利','平均亏损','盈亏比','PF','过拟合','后续','2026-10-29']);records[str(q)]=sha(q)
 assert len(records)==23 and found==set(starts)
 result=dict(schema='stage012_independent_offline_delivery_v1',status='PASS_PENDING_OFFLINE_LAYOUT_BINDING' if a.pending else 'PASS_WITH_LIMITATIONS',accepted=True,P0=0,P1=0,P2=0,failures=[],data_files_sha256=data,figure_files=figures,report_files_sha256=r['report_files_sha256'],delivery_receipt_sha256=sha(folder/'delivery_receipt.json'),publication_status_only_pixel_proof=pixels,html_rows=46,starts=23,rows_per_start=2,options=24,embedded_images=5,active_external_resources=0,chinese_window_records_sha256=records,browser_interaction_verified=False,browser_limitation='Known automatic file URL safety restriction; noHTTP/bypass attempted',financial_replays=0,market_downloads=0,production_accesses=0,promotion_decision='NO_PROMOTION',auditor_source_sha256=sha(__file__))
 output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'path':str(output),'sha256':sha(output),'status':result['status'],'figures':figures},ensure_ascii=False))
if __name__=='__main__':main()
