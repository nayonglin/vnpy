const pause=ms=>new Promise(resolve=>setTimeout(resolve,ms));
const check=(cond,msg)=>{if(!cond)throw Error(msg)};
const el=id=>document.getElementById(id);
const pick=async(id,value)=>{el(id).value=value;el(id).dispatchEvent(new Event('change'));await pause(220)};
for(let i=0;i<60&&!el('chart')._fullLayout;i++)await pause(100);
check(el('trade').options.length===167,'completed trade count');
check([...document.querySelectorAll('[data-period]:checked')].map(x=>x.dataset.period).join(',')==='day30,daily','default periods');
await pick('product','SA.CZCE');
const target=[...el('trade').options].find(x=>x.textContent.includes('2022-01-17→2022-02-14'));
check(target,'SA cycle 7 option'); await pick('trade',target.value);
document.querySelector('[data-period=weekly]').click();
document.querySelector('[data-period=day30]').click(); await pause(250);
const chart=el('chart');
const line=(xref,color)=>chart.layout.shapes.find(x=>x.type==='line'&&x.xref===xref&&x.line.color===color);
check(line('x','#9333ea')?.x0===530.5,'weekly exit must sit on Feb 12–18 candle at x=530.5');
check(line('x','#2563eb')?.x0===515.5,'weekly entry must sit on Jan 15–21 candle at x=515.5');
check(line('x2','#9333ea')?.x0===528.5,'daily exit must remain on Feb 14 at x=528.5');
check(line('x2','#2563eb')?.x0===513.5,'daily entry must remain on Jan 17 at x=513.5');
check(line('x','#9333ea').y0===chart.layout.yaxis2.domain[0],'weekly line starts at weekly volume panel');
check(line('x','#9333ea').y1===chart.layout.yaxis.domain[1],'weekly line ends at weekly price panel');
check(chart.data.find(x=>x.name==='同源成交价格'&&x.xaxis==='x').x.join(',')==='515.5,530.5','weekly fill markers align with candles');
check(chart.data.find(x=>x.name==='同源成交价格'&&x.xaxis==='x2').x.join(',')==='513.5,528.5','daily fill markers retain dates');
check(el('episodeNote').textContent.includes('触价日 2022-02-14'),'actual trigger date retained');
check(el('episodeNote').textContent.includes('模拟成交 2873'),'execution price retained');
const old=chart._fullLayout.xaxis.range;
await Plotly.relayout(chart,{'xaxis.range':[old[0]+2,old[1]-2]});
check(chart._fullLayout.xaxis2.range.every((v,i)=>v===chart._fullLayout.xaxis.range[i]),'linked zoom');
document.querySelector('[data-period=daily]').click(); await pause(220);
check(line('x','#9333ea')?.x0===530.5,'weekly-only alignment');
document.querySelector('[data-period=monthly]').click(); await pause(220);
check(line('x','#9333ea')?.x0===531,'monthly exit on February candle');
check(line('x2','#9333ea')?.x0===530.5,'weekly alignment after panel reorder');
document.querySelector('[data-period=monthly]').click();
document.querySelector('[data-period=daily]').click(); await pause(220);
await pick('product',''); await pick('result','profit');check(el('trade').options.length===52,'profit filter');
await pick('result','loss');check(el('trade').options.length===115,'loss filter');
await pick('result','all');el('next').click();await pause(220);check(el('trade').value==='1','next');
el('prev').click();await pause(220);check(el('trade').value==='0','previous');
// Inspect every period on every frozen trade, independently derive membership from its labels.
let tested=0;
for(const r of records){
 for(const field of ['day30','day10','monthly','weekly','daily']){
  const option=periodOptions.find(o=>o.field===field),data=r[field];
  for(const side of ['entry','exit']){
   const day=r.meta[side+'_date'];
   let i;
   if(field==='daily')i=data.date.indexOf(day);
   else if(field==='monthly')i=data.label.indexOf(day.slice(0,7));
   else i=data.label.findIndex(label=>{const bounds=label.match(/\d{4}-\d{2}-\d{2}/g);return bounds&&bounds.length===2&&bounds[0]<=day&&day<=bounds[1]});
   check(i>=0,`missing event candle ${r.meta.open_trade_id}/${field}/${side}`);
   check(candleX(r,option,day,r.meta[side+'_x'])===data.x[i],`event mapping ${r.meta.open_trade_id}/${field}/${side}`);
   tested++;
  }
 }
}
check(candleX({weekly:{x:[5],label:['2022-02-12/2022-02-18']}},{field:'weekly',kind:'period'},'2022-02-21',8)===null,'missing period must not snap to a neighboring candle');
// Same-candle entry/exit must retain both events without labels pretending to be different bars.
await pick('product','SM.CZCE');
const same=[...el('trade').options].find(x=>x.textContent.includes('2022-01-17→2022-01-17'));
check(same,'same-day SM trade');await pick('trade',same.value);
document.querySelector('[data-period=monthly]').click();
document.querySelector('[data-period=weekly]').click();
document.querySelector('[data-period=daily]').click();await pause(220);
check(line('x','#2563eb').x0===line('x','#9333ea').x0,'same monthly candle keeps both event coordinates');
check(chart.layout.annotations.some(a=>a.text==='开仓 / 平仓'),'same candle combined label');
document.querySelector('[data-period=weekly]').click();
document.querySelector('[data-period=daily]').click();
document.querySelector('[data-period=monthly]').click();await pause(220);
// Finish on the reported example, zoomed enough to see the independent weekly/daily lines.
await pick('product','SA.CZCE');
await pick('trade',[...el('trade').options].find(x=>x.textContent.includes('2022-01-17→2022-02-14')).value);
await Plotly.relayout(chart,{'xaxis.range':[493,554]});
el('chart').scrollIntoView({block:'start'});await pause(350);
check(window.recapErrors.length===0,window.recapErrors.join(','));
return JSON.stringify({status:'PASS',mapped_endpoints:tested,records:records.length,weekly_entry_x:515.5,weekly_exit_x:530.5,daily_exit_x:528.5,console_errors:0});
