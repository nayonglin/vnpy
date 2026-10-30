"""Verify published offline images/HTML bind the independently accepted tables."""
from pathlib import Path
from html.parser import HTMLParser
import argparse,base64,hashlib,json
from PIL import Image
import numpy as np
ROOT=Path(__file__).resolve().parents[4];LINE=ROOT/'research/lines/futures_weekly_short_ma_slope_gate';STAGES=LINE/'stages'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p):return json.loads(Path(p).read_text())
class Document(HTMLParser):
 def __init__(self):super().__init__();self.images=[];self.rows=[];self.options=[];self.external_active=[]
 def handle_starttag(self,tag,attrs):
  a=dict(attrs)
  if tag=='img':self.images.append(a)
  if tag=='tr' and 'data-start' in a:self.rows.append(a['data-start'])
  if tag=='option':self.options.append(a.get('value'))
  if tag in ['iframe','script','video','audio','source','link'] and any(k in a for k in ['src','href']):self.external_active.append((tag,a))
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--report',type=Path,default=LINE/'artifacts/stage011_uniform_risk_comparison');ap.add_argument('--numeric-review',type=Path,default=STAGES/'stage011_independent_numeric_review.json');ap.add_argument('--output',type=Path,default=STAGES/'stage011_independent_delivery_review.json');args=ap.parse_args()
 if args.output.exists():raise ValueError('immutable_independent_delivery_review_exists')
 numeric=load(args.numeric_review);receipt=load(args.report/'delivery_receipt.json');assert numeric['status']=='PASS_WITH_LIMITATIONS' and not numeric['failures'];assert receipt['status']=='PASS_WITH_LIMITATIONS' and receipt['independent_review_sha256']==sha(args.numeric_review) and receipt['data_files_sha256']==numeric['data_files_sha256'];assert receipt['browser_interaction_verified'] is False and receipt['promotion_decision']=='NO_PROMOTION'
 for p,h in {**numeric['data_files_sha256'],**numeric['audited_code_sha256'],**receipt['figure_files_sha256'],**receipt['report_files_sha256']}.items():assert sha(p)==h,p
 html=next(Path(p) for p in receipt['report_files_sha256'] if p.endswith('.html'));text=html.read_text();doc=Document();doc.feed(text);starts=load(STAGES/'stage011_freeze.json')['starts'];assert len(doc.images)==5 and len(doc.rows)==92 and all(doc.rows.count(s)==4 for s in starts);assert doc.options==['all']+starts and not doc.external_active;assert 'NO_PROMOTION' in text and 'E/150000' in text and 'W=E+R' in text and '2026-10-29' in text;assert 'fetch(' not in text and 'XMLHttpRequest' not in text
 figures={};paths=list(receipt['figure_files_sha256'])
 for img,p in zip(doc.images,paths):
  assert img['src'].startswith('data:image/png;base64,') and hashlib.sha256(base64.b64decode(img['src'].split(',',1)[1],validate=True)).hexdigest()==sha(p),'embedded_image_does_not_match_published_png'
  with Image.open(p) as im:
   im.verify()
  with Image.open(p) as im:
   pixels=np.asarray(im.convert('RGB'));w,h=im.size;nonwhite=float((pixels.min(axis=2)<230).mean());assert w>=1500 and h>=900 and .01<nonwhite<.9;figures[p]={'width':w,'height':h,'nonwhite_fraction':nonwhite,'sha256':sha(p)}
 result=dict(schema='stage011_independent_delivery_review_v1',status='PASS_WITH_LIMITATIONS',accepted=True,P0=0,P1=0,P2=0,failures=0,numeric_review_sha256=sha(args.numeric_review),delivery_receipt_sha256=sha(args.report/'delivery_receipt.json'),data_files_sha256=numeric['data_files_sha256'],report_files_sha256=receipt['report_files_sha256'],figures=figures,offline_html={'embedded_images':5,'exact_published_image_bytes':True,'table_rows':92,'unique_starts':23,'rows_per_start':4,'options':24,'active_external_resources':0,'filter_script_present':'startFilter' in text,'browser_interaction_verified':False,'reason':'Known automatic file URL browser safety restriction; no HTTP or bypass attempted'},visual_inspection='Independent model inspection of all five local PNGs recorded separately; this tool verifies byte and structural delivery binding.',financial_replays=0,market_downloads=0,production_accesses=0,promotion_decision='NO_PROMOTION',auditor_source_sha256=sha(__file__))
 args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'status':result['status'],'path':str(args.output),'sha256':sha(args.output),'figures':figures},ensure_ascii=False))
if __name__=='__main__':main()
