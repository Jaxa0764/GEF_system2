import {haversine,geometryProgress} from './geometry.js';
import {state,on,emit} from './state.js';
import {api} from './api.js';
import {$,escape,toast,showError,modal,closeModal,tr,busy} from './ui.js';
import {t,dist,number} from './i18n.js';
import {ensureOrigin,requestPosition,startTracking,stopTracking} from './location.js';
import {drawRoute,clearRoute,follow,resizeMap,focusStation} from './maps.js';
let destination=null,routing=false,lastReroute=0,arrivalPrompt=false,activeAt=0,routeSequence=0;
export function externalNavigation(s=destination){return s?`https://yandex.com/maps/?rtext=~${s.latitude}%2C${s.longitude}&rtt=auto`:''}
export async function prepareRoute(station,{reroute=false}={}){
 if(routing)return;
 if(!reroute){await stopNavigation({clear:false,silent:true});destination=station;arrivalPrompt=false;state.route=null;emit('page','home');resizeMap();focusStation(station)}
 const seq=++routeSequence;routing=true;renderRoute('loadingRoute');
 try{
  const origin=await ensureOrigin();
  if(!state.config.routing_configured)throw {code:'ROUTING_UNCONFIGURED'};
  const route=await api('/routes',{method:'POST',body:{station_id:station.id,latitude:origin.latitude,longitude:origin.longitude,origin_kind:origin.kind,route_id:reroute?state.route?.route_id:null}});
  if(seq!==routeSequence)return;
  state.route={...route,station};lastReroute=Date.now();drawRoute(route,{fit:!reroute});renderRoute();
 }catch(error){if(seq!==routeSequence)return;state.navigating=false;state.following=false;stopTracking();renderRoute(null,error)}
 finally{routing=false}
}
export function renderRoute(status=null,error=null){
 const panel=$('#route-panel');if(!destination){panel.hidden=true;return}panel.hidden=false;
 const route=state.route;
 const remaining=state.navigating&&state.origin&&route?geometryProgress(state.origin,route.geometry.coordinates).remaining_m:null;
 const minutes=route?Math.max(1,Math.round((remaining===null?route.duration_s:route.duration_s*Math.min(1,remaining/(route.distance_m||1))))/60):null;
 panel.innerHTML=`<div class="route-heading"><div><p class="tiny muted">${escape(t(state.navigating?'navigationActive':'destination'))}</p><h3>${escape(destination.name)}</h3>${route?`<p>${escape(dist(remaining??route.distance_m))} · ${escape(number(minutes))} ${escape(t('minutes'))}</p>`:''}</div><button class="icon-button" id="close-route" aria-label="${escape(t('close'))}">×</button></div>${status?`<p class="tiny">${escape(t(status))}</p>`:''}${error?`<p class="form-error">${escape(t('e.'+(error.code||'NETWORK_ERROR')))}</p>`:''}<div class="route-actions">${route?`<button class="button ${state.navigating?'secondary':''}" id="start-stop-route">${escape(t(state.navigating?'stopNavigation':'startNavigation'))}</button>${state.navigating?`<button class="button secondary" id="route-follow">${tr('follow')}</button>`:''}`:`<button class="button" id="retry-route">${tr('retry')}</button><button class="button secondary" id="route-location">${tr('myLocation')}</button><button class="button secondary" id="route-manual">${tr('chooseOrigin')}</button>`}<a class="button secondary" href="${externalNavigation()}" target="_blank" rel="noopener noreferrer">${escape(t('externalNavigation'))} ↗</a></div><p class="tiny muted">${tr('navigationNote')}</p>${route?.steps?.length?`<details><summary>${escape(t('maneuvers'))} (${route.steps.length})</summary><ol>${route.steps.map(step=>`<li>${escape(t('turn.'+step.type))}${step.modifier?' · '+escape(t('direction.'+step.modifier)):''}${step.name?' · '+escape(step.name):''} — ${escape(dist(step.distance_m))}</li>`).join('')}</ol></details>`:''}`;
 $('#close-route').onclick=()=>stopNavigation({clear:true});
 if($('#start-stop-route'))$('#start-stop-route').onclick=()=>state.navigating?stopNavigation({clear:true}):startNavigation();
 if($('#route-follow'))$('#route-follow').onclick=follow;
 if($('#retry-route'))$('#retry-route').onclick=()=>prepareRoute(destination);
 if($('#route-location'))$('#route-location').onclick=()=>requestPosition().then(()=>prepareRoute(destination)).catch(()=>{});
 if($('#route-manual'))$('#route-manual').onclick=()=>emit('choose-origin');
}
async function startNavigation(){
 if(!state.route)return;
 try{
  if(state.origin?.kind!=='live'||Date.now()-state.origin.timestamp>60000){await requestPosition();await prepareRoute(destination);if(!state.route)return}
  startTracking(async error=>{state.navigating=false;state.following=false;stopTracking();renderRoute(null,error);toast(t('e.'+error.code),true)});
  if(state.route.route_id)await api(`/navigation/${state.route.route_id}/start`,{method:'POST'});
  state.navigating=true;state.following=true;activeAt=Date.now();arrivalPrompt=false;follow();renderRoute();
 }catch(error){stopTracking();state.navigating=false;renderRoute(null,error)}
}
export async function stopNavigation({clear=true,silent=false}={}){
 const id=state.route?.route_id,wasActive=state.navigating;
 state.navigating=false;state.following=false;stopTracking();$('#follow').hidden=true;
 if(id&&wasActive&&state.user)try{await api(`/navigation/${id}/stop`,{method:'POST'})}catch(error){if(!silent)showError(error)}
 if(clear){routeSequence++;state.route=null;destination=null;clearRoute();$('#route-panel').hidden=true}
}
async function confirmArrival(){
 if(arrivalPrompt||!state.user||!state.route?.route_id)return;arrivalPrompt=true;
 const station=destination;
 const box=modal('arrivalTitle',`<p>${escape(t('arrivalConfirm',{name:station.name}))}</p><div class="dialog-actions"><button class="button secondary" id="arrival-cancel">${tr('cancel')}</button><button class="button" id="arrival-confirm">${tr('confirmArrival')}</button></div><p class="tiny muted">${tr('arrivalNote')}</p>`);
 $('#arrival-cancel',box).onclick=closeModal;
 $('#arrival-confirm',box).onclick=async()=>{
  const button=$('#arrival-confirm',box);busy(button,true);
  try{
   const origin=await requestPosition();
   if(origin.kind!=='live')throw {code:'ARRIVAL_UNCONFIRMED'};
   await api('/visits',{method:'POST',body:{route_id:state.route.route_id,latitude:origin.latitude,longitude:origin.longitude,accuracy:origin.accuracy,position_timestamp:new Date(origin.timestamp).toISOString(),confirmed:true}});
   state.navigating=false;state.following=false;stopTracking();await stopNavigation({clear:true,silent:true});closeModal();ratingDialog(station);
  }catch(error){showError(error);busy(button,false)}
 };
}
export function ratingDialog(station){
 let stars=0;const box=modal('rateStation',`<p>${escape(station.name)}</p><div class="star-picker" role="group" aria-label="${escape(t('rating'))}">${[1,2,3,4,5].map(n=>`<button type="button" data-star="${n}" aria-label="${n} ${escape(t('stars'))}" aria-pressed="false">☆</button>`).join('')}</div><button class="button" id="save-rating" disabled>${tr('save')}</button>`);
 box.querySelectorAll('[data-star]').forEach(button=>button.onclick=()=>{stars=Number(button.dataset.star);box.querySelectorAll('[data-star]').forEach(b=>{const selected=Number(b.dataset.star)<=stars;b.textContent=selected?'★':'☆';b.classList.toggle('selected',selected);b.setAttribute('aria-pressed',String(Number(b.dataset.star)===stars))});$('#save-rating',box).disabled=false});
 $('#save-rating',box).onclick=async()=>{busy($('#save-rating',box),true);try{await api(`/stations/${station.id}/rating`,{method:'POST',body:{stars}});closeModal();toast(t('ratingSaved'));emit('favorites-refresh');emit('stations-refresh')}catch(error){showError(error);busy($('#save-rating',box),false)}};
}
on('position',async origin=>{
 if(!state.navigating||!state.route||!destination)return;
 const progress=geometryProgress(origin,state.route.geometry.coordinates);
 if(origin.accuracy!==null&&origin.accuracy<=200&&progress.offRoute>Math.max(60,origin.accuracy*2)&&Date.now()-lastReroute>20000&&!routing){await prepareRoute(destination,{reroute:true});return}
 if(Date.now()-activeAt>45000&&origin.kind==='live'&&origin.accuracy>0&&origin.accuracy<=100&&haversine([origin.latitude,origin.longitude],[destination.latitude,destination.longitude])<=Math.max(40,Math.min(100,origin.accuracy*1.5)))confirmArrival();
 // Avoid replacing focused route controls on every GPS update.
 const heading=$('#route-panel .route-heading p:not(.tiny)');
 if(heading)heading.textContent=`${dist(progress.remaining_m)} · ${number(Math.max(1,Math.round(state.route.duration_s*Math.min(1,progress.remaining_m/(state.route.distance_m||1))/60)))} ${t('minutes')}`;
});
document.addEventListener('visibilitychange',()=>{if(document.hidden)stopTracking();else if(state.navigating){try{startTracking(error=>{state.navigating=false;renderRoute(null,error)})}catch(error){state.navigating=false;renderRoute(null,error)}}});
