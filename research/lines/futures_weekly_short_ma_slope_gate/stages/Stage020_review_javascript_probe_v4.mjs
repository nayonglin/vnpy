import fs from 'node:fs/promises';
import crypto from 'node:crypto';
import vm from 'node:vm';
export async function run(){
 const root='/Users/mac/.codex/worktrees/weekly19-official-20261031/fian/research/lines/futures_weekly_short_ma_slope_gate';
 const path=root+'/artifacts/stage020_2026_ytd_recap_attempt002/index.html';
 const page=await fs.readFile(path,'utf8');const hash=x=>crypto.createHash('sha256').update(x).digest('hex');
 const scripts=[...page.matchAll(/<script\b([^>]*)>([\s\S]*?)<\/script>/gi)];let checks=0;const ok=(v,n)=>{checks++;if(!v)throw new Error(n)};
 ok(scripts.length===3,'inline_script_count');for(let i=0;i<scripts.length;i++)new vm.Script(scripts[i][2],{filename:'Stage020_inline_'+i+'.js'});
 ok(!/<script\b[^>]*\bsrc\s*=/i.test(page),'no_external_script');ok(!/<(?:link|iframe|img)\b[^>]*\b(?:src|href)\s*=\s*["'](?:https?:|\/\/|file:)/i.test(page),'no_active_external_resources');
 const image=page.match(/<img\b[^>]*alt="2026年度交易净值与回撤"[^>]*src="data:image\/png;base64,([A-Za-z0-9+/=]+)"/);ok(!!image,'annual_PNG_embedded');const png=await fs.readFile(root+'/artifacts/stage019_2026_ytd/2026_ytd_nav.png');ok(hash(Buffer.from(image[1],'base64'))===hash(png),'annual_PNG_exact');
 const defaults={result:'all',sort:'extreme',year:'',product:'',trade:'0'};const elements=new Map();
 function element(id){if(!elements.has(id))elements.set(id,{id,value:defaults[id]??'',checked:false,dataset:{},style:{},innerHTML:'',listeners:{},addEventListener(k,fn){this.listeners[k]=fn},insertAdjacentHTML(_,s){this.innerHTML+=s},classList:{toggle(){}}});return elements.get(id)}
 const inputs=[...page.matchAll(/<input\b([^>]*\bdata-period="([^"]+)"[^>]*)>/g)].map(m=>Object.assign(element('period_'+m[2]),{dataset:{period:m[2]},checked:/\bchecked\b/.test(m[1])}));
 const state={last:null,purges:0};const sandbox={document:{getElementById:element,querySelectorAll(){return inputs},querySelector(){return element('intraday_chip')}},Plotly:{react(t,traces,layout,config){state.last={traces,layout,config};return Promise.resolve()},purge(){state.purges++}},console:{log(){}},fetch(){throw new Error('network prohibited')},setTimeout(){throw new Error('unexpected timer')}};
 const ctx=vm.createContext(sandbox);for(const [i,m]of scripts.entries())if(i>0)vm.runInContext(m[2],ctx,{filename:'Stage020_app_'+i+'.js',timeout:15000});
 const evaluate=s=>vm.runInContext(s,ctx,{timeout:5000});ok(evaluate('records.length')===18&&evaluate('filtered.length')===18,'all18_default');ok(JSON.stringify(Array.from(evaluate('[...selectedPeriods].sort()')))===JSON.stringify(['daily','day30']),'default30day_and_daily');
 const expectedRecords=JSON.parse(await fs.readFile(root+'/artifacts/stage020_2026_ytd_recap_attempt002/records.json','utf8')); const expectedSummary=JSON.parse(await fs.readFile(root+'/artifacts/stage020_2026_ytd_recap_attempt002/summary.json','utf8'));ok(evaluate('JSON.stringify(records)')===JSON.stringify(expectedRecords),'embedded_records_exact_external_records');ok(evaluate('JSON.stringify(summary)')===JSON.stringify(expectedSummary),'embedded_summary_exact_external_summary');const records=JSON.parse(evaluate('JSON.stringify(filtered'));ok(records.reduce((s,r)=>s+r.meta.realized_pnl,0)===22380,'embedded_net22380');
 for(let i=0;i<18;i++){
  evaluate('active='+i+';render()');const r=records[i],last=state.last,marker=last.traces.find(t=>t.name==='同源成交价格');ok(marker&&JSON.stringify(marker.x)===JSON.stringify([r.meta.entry_x,r.meta.exit_x])&&JSON.stringify(marker.y)===JSON.stringify([r.meta.entry_marker_price,r.meta.exit_marker_price]),'actual36marker_data_'+i);ok(last.traces.filter(t=>t.type==='candlestick').length===2,'two_default_panels_'+i);ok(last.layout.xaxis2.matches==='x'&&JSON.stringify(last.layout.xaxis.range)===JSON.stringify(last.layout.xaxis2.range),'default_linked_axes_'+i);
 }
 evaluate('selectedPeriods.clear();periodOptions.forEach(p=>selectedPeriods.add(p.id))');
 for(let i=0;i<18;i++){
  evaluate('active='+i+';render()');const last=state.last;const n=records[i].meta.draw_intraday===1?6:5;ok(last.traces.filter(t=>t.type==='candlestick').length===n,'available_period_panels_'+i);for(let j=1;j<n;j++){const a=last.layout['xaxis'+(j+1)];ok(a.matches==='x'&&JSON.stringify(a.range)===JSON.stringify(last.layout.xaxis.range),'all_axes_share_range_'+i+'_'+j)}
 }
 for(const [kind,count]of [['profit',8],['loss',10],['flat',0]]){element('result').value=kind;element('result').onchange();ok(evaluate('filtered.length')===count,'filter_'+kind)}
 element('result').value='all';element('result').onchange();evaluate('active=17');element('next').onclick();ok(evaluate('active')===0,'next_wrap');element('prev').onclick();ok(evaluate('active')===17,'previous_wrap');
 const products=[...new Set(records.map(r=>r.meta.product))];for(const p of products){element('product').value=p;element('product').onchange();ok(evaluate('filtered.length')===records.filter(r=>r.meta.product===p).length,'product_filter_'+p)}
 element('product').value='';element('sort').value='price_asc';element('sort').onchange();ok(evaluate('filtered[0].meta.price_change_pct')===Math.min(...records.map(r=>r.meta.price_change_pct)),'raw_underlying_ascending');element('sort').value='price_desc';element('sort').onchange();ok(evaluate('filtered[0].meta.price_change_pct')===Math.max(...records.map(r=>r.meta.price_change_pct)),'raw_underlying_descending');
 const result={schema:'Stage020.independent-javascript-logic.v1',accepted:true,status:'PASS_WITH_LIMITATIONS',checks,inline_scripts_parsed:scripts.length,all18_record_marker_and_panels_checked:true,filters:{profit:8,loss:10,flat:0},shared_axes_matches_checked:true,annual_png_embedded_sha256:hash(png),html_sha256:hash(page),browser_validation:'blocked_by_file_protocol_policy',qualification:'VM syntax and lightweight DOM/Plotly-call simulation only. No browser, canvas rendering, real Plotly zoom event or actual pixel acceptance performed.',network_calls:0};return result;
}
