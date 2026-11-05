const pause=ms=>new Promise(resolve=>setTimeout(resolve,ms));
const check=(ok,message)=>{if(!ok)throw Error(message)};
const el=id=>document.getElementById(id);
const pick=async(id,value)=>{el(id).value=value;el(id).dispatchEvent(new Event('change'));await pause(220)};
const setPeriods=async ids=>{for(const p of ids){const n=document.querySelector(`[data-period=${p}]`);if(!n.checked)n.click()}for(const n of document.querySelectorAll('[data-period]:checked'))if(!ids.includes(n.dataset.period))n.click();await pause(250)};
const expected=(r,field,side)=>{
 const data=r[field],day=r.meta[side+'_date'];let i;
 if(field==='daily')i=data.date.indexOf(day);
 else if(field==='monthly')i=data.label.indexOf(day.slice(0,7));
 else i=data.label.findIndex(label=>{const b=label.match(/\d{4}-\d{2}-\d{2}/g);return b&&b.length===2&&b[0]<=day&&day<=b[1]});
 check(i>=0,`no containing candle ${r.meta.open_trade_id}/${field}/${side}`);return data.x[i];
};
for(let i=0;i<60&&!el('chart')._fullLayout;i++)await pause(100);
check(el('trade').options.length===141,'annual overlap count');
check(summary.source_version.endsWith('/2015-01-01'),'continuous 2015 source');
check(summary.scope_mode==='calendar_overlap','annual overlap scope');
check(summary.calendar_year_pnl===-102655&&summary.scoped_closed_pnl===-100360,'annual versus full-cycle PnL');
check(summary.calendar_year_open_equity===316340&&summary.calendar_year_end_equity===213685,'annual boundary equities');
check(records.filter(r=>r.meta.entry_date<'2017-01-01').length===2,'incoming trades retained');
check(records.filter(r=>r.meta.exit_date>'2017-12-31').length===5,'outgoing trades retained');
check(records.reduce((a,r)=>a+r.meta.calendar_year_pnl,0)===-102655,'contribution conservation');
check([...document.querySelectorAll('[data-period]:checked')].map(n=>n.dataset.period).join(',')==='day30,daily','default periods');
check(el('rejected-ledger').querySelectorAll('tbody tr').length===0,'no rejected openings in 2017');
await pick('result','profit');check(el('trade').options.length===40,'profit count');
await pick('result','loss');check(el('trade').options.length===101,'loss count');
await pick('result','all');
await pick('year','2016');check(el('trade').options.length===2,'opening-year filter preserves incoming visibility');
await pick('year','');
let incoming=[...el('trade').options].find(x=>x.textContent.includes('2016-12-12→2017-01-16'));
check(incoming,'incoming SM option');await pick('trade',incoming.value);
check(el('episodeNote').textContent.includes('区间开始前已开仓'),'incoming status');
check(el('episodeNote').textContent.includes('2017年贡献'),'per-trade year contribution');
let outgoing=[...el('trade').options].find(x=>x.textContent.includes('2017-11-20→2018-01-02'));
check(outgoing,'outgoing palm option');await pick('trade',outgoing.value);
check(el('episodeNote').textContent.includes('区间结束后才平仓'),'outgoing status');
const chart=el('chart');
await setPeriods(['day30','day10','monthly','weekly','daily']);
for(const [i,field] of ['day30','day10','monthly','weekly','daily'].entries()){
 const r=filtered[active],xref=axisRef('x',i);
 for(const [side,color] of [['entry','#2563eb'],['exit','#9333ea']]){
  const shape=chart.layout.shapes.find(s=>s.type==='line'&&s.xref===xref&&s.line.color===color);
  check(shape?.x0===expected(r,field,side),`actual ${field} ${side} shape`);
 }
 const mark=chart.data.find(t=>t.name==='同源成交价格'&&t.xaxis===xref);
 check(mark.x[0]===expected(r,field,'entry')&&mark.x[1]===expected(r,field,'exit'),`actual ${field} markers`);
}
await setPeriods(['weekly']);check(chart.layout.shapes.some(s=>s.type==='line'&&s.x0===expected(filtered[active],'weekly','exit')),'weekly only');
await setPeriods(['monthly','weekly','daily']);check(chart._fullLayout.xaxis3.matches==='x','three-panel linked zoom');
const range=chart._fullLayout.xaxis.range;
await Plotly.relayout(chart,{'xaxis.range':[range[0]+2,range[1]-2]});
check(chart._fullLayout.xaxis3.range.every((v,i)=>v===chart._fullLayout.xaxis.range[i]),'zoom synchronization');
await setPeriods(['weekly','daily']);
await pick('trade','0');el('next').click();await pause(200);check(el('trade').value==='1','next');
el('prev').click();await pause(200);check(el('trade').value==='0','previous');
let mapped=0;
for(const r of records)for(const field of ['day30','day10','monthly','weekly','daily'])for(const side of ['entry','exit']){
 const option=periodOptions.find(o=>o.field===field);
 check(candleX(r,option,r.meta[side+'_date'],r.meta[side+'_x'])===expected(r,field,side),'all source date to candle mappings');mapped++;
}
const same=records.find(r=>expected(r,'weekly','entry')===expected(r,'weekly','exit'));
check(same,'same-week example');await pick('trade',String(filtered.indexOf(same)));
check(chart.layout.annotations.some(a=>a.text==='开仓 / 平仓'),'combined same-candle label');
const worst=records.reduce((a,b)=>b.meta.realized_pnl<a.meta.realized_pnl?b:a);
await pick('trade',String(filtered.indexOf(worst)));
await Plotly.relayout(chart,{'xaxis.range':[worst.meta.entry_x-35,worst.meta.exit_x+35]});
el('chart').scrollIntoView({block:'start'});await pause(350);
check(window.recapErrors.length===0,window.recapErrors.join(','));
return JSON.stringify({status:'PASS',records:141,mapped_endpoints:mapped,incoming:2,outgoing:5,
 year_pnl:summary.calendar_year_pnl,full_cycle_pnl:summary.scoped_closed_pnl,console_errors:0,
 screenshot_cycle:worst.meta.open_trade_id,screenshot_contract:worst.meta.vt_symbol});
