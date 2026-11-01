// Static JS compilation and synthetic-DOM logic only. This is NOT a browser.
import fs from 'node:fs';
import vm from 'node:vm';
import path from 'node:path';

export function run(output) {
 const files=[0,1,2].map(i=>path.join(output,`embedded_script_${i}.js`));
 for(const file of files)new vm.Script(fs.readFileSync(file,'utf8'),{filename:file});
 const ids={};
 function el(id){return ids[id]??=( {innerHTML:'',value:({result:'all',sort:'extreme',year:'',product:'',trade:'0'})[id]??'',style:{},classList:{toggle(){}},addEventListener(){}} );}
 const inputs=['day30','day10','monthly','weekly','daily','intraday'].map(p=>({dataset:{period:p},checked:['day30','daily'].includes(p),addEventListener(){}}));
 let capture;
 const context=vm.createContext({document:{getElementById:el,querySelectorAll(){return inputs},querySelector(){return el('minute-chip');}},
  Plotly:{react(target,traces,layout,config){capture={target,traces,layout,config};},purge(){}},console});
 // Parse library, but deliberately do not execute it in a fake browser.
 for(const file of files.slice(1))new vm.Script(fs.readFileSync(file,'utf8'),{filename:file}).runInContext(context,{timeout:30000});
 const get=code=>vm.runInContext(code,context,{timeout:30000});let checks=0;
 const assert=(value,label)=>{if(!value)throw Error(label);checks++;};
 assert(get('records.length')===18&&get('filtered.length')===18,'18 initial closed episodes');
 assert(JSON.stringify(get('[...selectedPeriods]'))===JSON.stringify(['day30','daily']),'default periods 30-day plus daily');
 let minuteEpisodes=0;
 for(let i=0;i<18;i++){
  get(`active=${i};refreshSelect();render()`);const m=get('filtered[active].meta');
  const marker=capture.traces.find(t=>t.name==='同源成交价格');
  assert(marker&&marker.x[0]===m.entry_x&&marker.x[1]===m.exit_x,'real entry and exit coordinates');
  assert(marker.y[0]===m.entry_price&&marker.y[1]===m.exit_price,'frozen fill prices');
  assert(capture.layout.shapes.some(s=>s.type==='rect'&&s.x0===m.entry_x&&s.x1===m.exit_x),'holding interval');
  assert(capture.layout.xaxis2.matches==='x','linked axes declaration');
  assert(ids.tradeFacts.innerHTML.includes(`${Number(m.volume).toLocaleString('zh-CN',{maximumFractionDigits:4})}手`),'lot quantity visible');
  assert(ids.tradeFacts.innerHTML.includes(m.entry_execution_datetime),'actual natural execution clock visible');
  assert(m.r_multiple===null&&ids.metrics.innerHTML.includes('N/A'),'unfrozen R is N/A');
  get("selectedPeriods.clear();['day30','day10','monthly','weekly','daily','intraday'].forEach(p=>selectedPeriods.add(p));render()");
  const panels=capture.traces.filter(t=>t.type==='candlestick');
  assert(panels.length===(m.draw_intraday?6:5),'only admitted minute panels');
  if(m.draw_intraday)minuteEpisodes++;
  for(let j=1;j<panels.length;j++)assert(capture.layout[`xaxis${j+1}`].matches==='x','all selected period axes match');
  assert(ids.periodNote.innerHTML.includes('本地')||ids.periodNote.innerHTML.includes('核准'),'minute availability disclosure');
  get("selectedPeriods.clear();selectedPeriods.add('day30');selectedPeriods.add('daily');render()");
 }
 assert(minuteEpisodes===8,'8 locally admitted minute episodes');
 get("resultEl.value='profit';apply()");assert(get('filtered.length')===8,'eight profit episodes');
 get("resultEl.value='loss';apply()");assert(get('filtered.length')===10,'ten loss episodes');
 get("resultEl.value='flat';apply()");assert(get('filtered.length')===0,'no invented flat episodes');
 get("resultEl.value='all';apply()");const before=get('active');ids.next.onclick();assert(get('active')===(before+1)%18,'next navigation');ids.prev.onclick();assert(get('active')===before,'previous navigation');
 get("sortEl.value='price_desc';apply()");const prices=get('filtered.map(r=>r.meta.price_change_pct)');assert(prices.every((v,i)=>i===0||v<=prices[i-1]),'raw underlying price-move sorting');
 get("productEl.value=records[0].meta.product;apply()");assert(get('filtered.every(r=>r.meta.product===productEl.value)'),'product filter');
 return {status:'PASS_STATIC_JS_AND_SYNTHETIC_DOM_LOGIC',compiled_scripts:3,checks,episodes:18,minute_episodes:minuteEpisodes,
  real_browser:false,browser_validation:'blocked_by_file_protocol_policy',actual_plotly_rendering:false,actual_pointer_zoom:false,
  linked_zoom:'layout axes.matches and shared ranges checked; actual browser event/render not verified',network_calls:0};
}
