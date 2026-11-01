
(function(){
 const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 const f=v=>Number(v).toLocaleString('zh-CN',{maximumFractionDigits:4});
 function facts(){
  const card=document.getElementById('exitReasonPanel'),field=document.getElementById('tradeFacts');
  if(typeof filtered==='undefined'||!filtered[active]){if(card)card.innerHTML='没有符合筛选条件的交易';if(field)field.innerHTML='';return null;}
  const m=filtered[active].meta,x=m.exit_explanation;
  if(field)field.innerHTML=`<b>${m.direction==='long'?'多头':'空头'} · ${f(m.volume)}手</b>　开仓 ${esc(m.entry_execution_datetime)} @ ${f(m.entry_price)}　→　平仓 ${esc(m.exit_execution_datetime)} @ ${f(m.exit_price)}<br>入场信号：${esc(m.signal)}；本轮滑点及手续费 ${f(m.round_cost)}元。<br>精确交割epoch：${esc(m.physical_epoch_id)}；日K前史 ${m.exact_pre_bars}/300、后史 ${m.exact_post_bars}/50（按真实上市历史与10月30日截断）。<br>${esc(m.minute_disclosure)}；缺交易日后分钟MA重新预热；可见MA40空值 ${m.intraday_ma40_warmup_missing_bars} 根。`;
  if(card)card.innerHTML=`<h2 style="margin:0 0 10px;font-size:20px">平仓原因：${esc(x.label)}</h2><p>${esc(x.description)}</p><p><b>当笔依据：</b>${esc(x.evidence)}</p><p><b>触发日：</b>${esc(x.signal_date)}　<b>成交交易日：</b>${esc(x.trading_date)}<br><b>实际成交：</b>${esc(x.execution_datetime)} @ ${f(x.execution_price)}，${f(x.volume)}手</p><p style="color:#667085;margin-bottom:0">原始原因：<code>${esc(x.raw_code)}</code> · ${esc(x.fill_id)}<br>触发规则按信号日判断；成交价取冻结的下一交易时段执行记录，可能与触发价不同。</p>`;
  return x;
 }
 const original=Plotly.react,purge=Plotly.purge;
 Plotly.react=function(target,traces,layout,config){
  if(target==='chart'){
   const x=facts();
   if(x){const m=filtered[active].meta,marker=traces.find(t=>t.name==='同源成交价格');
    if(marker){marker.text=[`开仓 ${esc(m.entry_execution_datetime)}<br>价格 ${f(m.entry_price)}`,`平仓：${esc(x.label)}<br>${esc(x.evidence)}<br>触发日 ${esc(x.signal_date)}<br>成交交易日 ${esc(x.trading_date)}<br>实际成交 ${esc(x.execution_datetime)} @ ${f(x.execution_price)}<br>原始原因 ${esc(x.raw_code)}`];marker.hovertemplate='%{text}<extra></extra>';}
    for(const a of layout.annotations??[])if(a.text==='平仓')a.text='平仓：'+x.label;
   }
  }
  return original.call(this,target,traces,layout,config);
 };
 Plotly.purge=function(target){if(target==='chart')facts();return purge.call(this,target);};
})();
