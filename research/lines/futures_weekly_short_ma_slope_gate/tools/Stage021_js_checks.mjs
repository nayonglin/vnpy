// Static parsing and synthetic DOM checks only; never launch a browser.
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import {run as originalChecks} from './Stage020_js_checks.mjs';

export function run(output) {
 const original = originalChecks(output);
 const source = fs.readFileSync(path.join(output, 'index.html'), 'utf8');
 const scripts = [...source.matchAll(/<script[^>]*>([\s\S]*?)<\/script>/g)].map(m=>m[1]);
 let checks=0, capture;
 function assert(value,label){if(!value)throw Error(label);checks++;}
 assert(scripts.length===3,'three self-contained scripts');
 for(let i=0;i<3;i++){
  new vm.Script(scripts[i]);
  assert(scripts[i]===fs.readFileSync(path.join(output,`embedded_script_${i}.js`),'utf8'),'embedded script matches tested file');
 }
 assert(!/<script[^>]+src\s*=/i.test(source),'no external JS dependency');
 assert(source.includes('id="exitReasonPanel"')&&source.includes('aria-live="polite"'),'dedicated exit card is present and live');
 assert(source.indexOf('id="exitReasonPanel"')<source.indexOf('id="metrics"'),'card immediately precedes metrics/chart');
 assert(source.includes('全部18轮平仓原因对照表'),'full static reason table available');
 const elements={};
 const el=id=>elements[id]??=({innerHTML:'',value:({result:'all',sort:'extreme',year:'',product:'',trade:'0'})[id]??'',style:{},classList:{toggle(){}},addEventListener(){}});
 const inputs=['day30','day10','monthly','weekly','daily','intraday'].map(p=>({dataset:{period:p},checked:['day30','daily'].includes(p),addEventListener(){}}));
 const context=vm.createContext({document:{getElementById:el,querySelectorAll(){return inputs},querySelector(){return el('minute-chip')}},
  Plotly:{react(target,traces,layout,config){capture={target,traces,layout,config}},purge(){}},console});
 for(const script of scripts.slice(1))new vm.Script(script).runInContext(context,{timeout:30000});
 const get=code=>vm.runInContext(code,context,{timeout:30000});
 let technical=0;
 for(let i=0;i<18;i++){
  get(`active=${i};refreshSelect();render()`);
  const m=get('filtered[active].meta'), x=m.exit_explanation, text=elements.exitReasonPanel.innerHTML;
  assert(text.includes(x.label),'current reason label visible');
  assert(text.includes(x.raw_code)&&text.includes(x.fill_id),'raw reason and fill identity visible');
  assert(text.includes(x.description)&&text.includes(x.evidence),'specific rule and original evidence visible');
  assert(text.includes(x.signal_date)&&text.includes(x.trading_date)&&text.includes(x.execution_datetime),'signal day/trading day/natural execution clock distinct');
  assert(text.includes(Number(x.execution_price).toLocaleString('zh-CN',{maximumFractionDigits:4})),'actual execution price visible');
  const marker=capture.traces.find(t=>t.name==='同源成交价格');
  assert(marker.text[1].includes(x.label)&&marker.text[1].includes(x.evidence)&&marker.text[1].includes(x.raw_code),'exit hover contains reason and evidence');
  assert(marker.hovertemplate==='%{text}<extra></extra>','Plotly hover uses explanation');
  assert(capture.layout.annotations.some(a=>a.text==='平仓：'+x.label),'exit annotation labels the reason');
  assert(marker.x[1]===m.exit_x&&marker.y[1]===m.exit_price,'frozen exit coordinate/price unchanged');
  assert(elements.tradeFacts.innerHTML.includes(m.entry_execution_datetime),'existing execution facts retained');
  if(x.kind==='technical_stop'){
   technical++;
   assert(text.includes(Number(x.stop_price).toLocaleString('zh-CN',{maximumFractionDigits:4})),'recorded weekly stop visible');
   assert(text.includes(Number(x.trigger_close).toLocaleString('zh-CN',{maximumFractionDigits:4})),'recorded weekly trigger close visible');
  }
 }
 assert(technical===9,'nine real technical trigger comparisons');
 get("resultEl.value='flat';apply()");
 assert(get('filtered.length')===0,'empty filter exercised');
 assert(elements.exitReasonPanel.innerHTML==='没有符合筛选条件的交易','no stale reason after empty filter');
 assert(elements.tradeFacts.innerHTML==='','no stale execution facts after empty filter');
 get("resultEl.value='all';apply();active=records.findIndex(r=>!r.meta.draw_intraday);selectedPeriods.clear();selectedPeriods.add('intraday');render()");
 assert(elements.exitReasonPanel.innerHTML.includes(get('filtered[active].meta.exit_explanation.raw_code')),'reason retained even if no selected panel is drawable');
 get("selectedPeriods.clear();selectedPeriods.add('daily');render();sortEl.value='price_desc';apply()");
 const before=get('filtered[active].meta.exit_explanation.fill_id');
 elements.next.onclick();
 assert(elements.exitReasonPanel.innerHTML.includes(get('filtered[active].meta.exit_explanation.fill_id')),'reason changes with next navigation after sorting');
 assert(get('filtered[active].meta.exit_explanation.fill_id')!==before,'different transaction exercised');
 get("resultEl.value='profit';apply()");
 assert(get('filtered.length')===8&&elements.exitReasonPanel.innerHTML.includes(get('filtered[active].meta.exit_explanation.fill_id')),'profit filter changes reason to matching fill');
 get("resultEl.value='loss';apply()");
 assert(get('filtered.length')===10&&elements.exitReasonPanel.innerHTML.includes(get('filtered[active].meta.exit_explanation.fill_id')),'loss filter changes reason to matching fill');
 return {...original,stage021_checks:checks,total_static_checks:checks+original.checks,
  exit_explanations:18,technical_price_comparisons:technical,actual_plotly_rendering:false,actual_pointer_zoom:false};
}
