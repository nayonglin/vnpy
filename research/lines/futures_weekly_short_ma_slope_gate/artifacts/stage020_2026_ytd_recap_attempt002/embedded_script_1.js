
(function(){const original=Plotly.react;Plotly.react=function(target,traces,layout,config){
if(target==='chart'&&typeof filtered!=='undefined'&&filtered[active]){
 const m=filtered[active].meta,f=v=>Number(v).toLocaleString('zh-CN',{maximumFractionDigits:4});
 const field=document.getElementById('tradeFacts');
 if(field)field.innerHTML=`<b>${m.direction==='long'?'多头':'空头'} · ${f(m.volume)}手</b>　开仓 ${m.entry_execution_datetime} @ ${f(m.entry_price)}　→　平仓 ${m.exit_execution_datetime} @ ${f(m.exit_price)}<br>信号：${m.signal}；退出：${m.exit_reason}；本轮滑点及手续费 ${f(m.round_cost)}元。<br>精确交割epoch：${m.physical_epoch_id}；日K前史 ${m.exact_pre_bars}/300、后史 ${m.exact_post_bars}/50（按真实上市历史与10月30日截断）。<br>${m.minute_disclosure}；缺交易日后分钟MA重新预热；可见MA40空值 ${m.intraday_ma40_warmup_missing_bars} 根。`;
}return original.call(this,target,traces,layout,config);};})();
