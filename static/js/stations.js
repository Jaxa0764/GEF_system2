import {state,emit,on} from './state.js';
import {api,query} from './api.js';
import {$,$$,escape,tr,showError,empty,modal,hydrate,toast} from './ui.js';
import {t,language,number,date,dist,money} from './i18n.js';
import {icon} from './icons.js';
import {updateMarkers} from './maps.js';
import {ratingDialog} from './navigation.js';
let generation=0,detailStation=null;
export function productsHTML(station,category=state.category){
 const products=station.products?.filter(p=>p.category===category)||[];
 return products.map(p=>`<div class="product-row ${p.available?'':'unavailable'}"><span>${escape(p.name)}${!p.available?' · '+escape(t('outOfStock')):''}</span><strong>${p.price===null?escape(t('unavailable')):escape(number(p.price))} <span class="product-unit">${p.price===null?'':escape(t('uzs')+'/'+t('unit_'+p.unit))}</span></strong></div>${p.pressure!==null?`<p class="product-extra">${escape(t('pressure'))}: ${escape(number(p.pressure,1))} ${escape(p.pressure_unit||'')} · ${escape(t(p.pressure_fresh?'recentReading':'staleReading'))}<br>${escape(date(p.pressure_at))}</p>`:''}${category==='elektr'?`<p class="product-extra">${p.power_kw===null?escape(t('powerUnavailable')):escape(number(p.power_kw))+' kW'} · ${escape(p.connectors?.join(', ')||t('connectorsUnavailable'))}${p.connector_available!==null?'<br>'+escape(t('connectorAvailable',{n:p.connector_available})):''}</p>`:''}`).join('')||`<p class="tiny muted">${escape(t('unavailable'))}</p>`;
}
function hoursShort(s){if(s.is_24h)return '24/7';const weekday=new Intl.DateTimeFormat('en-GB',{weekday:'short',timeZone:'Asia/Tashkent'}).format(new Date());const day=['Mon','Tue','Wed','Thu','Fri','Sat','Sun'].indexOf(weekday);return s.hours?.[String(day)]?.map(x=>x.join('–')).join(', ')||t('closed')}
export function cardHTML(station,{favoritePage=false}={}){
 const s=station,c=state.category,kind=s.categories?.includes(c)?c:s.categories?.[0]||c,saved=state.favorites.has(s.id);
 return `<article class="station-card" data-station="${s.id}"><div class="card-head"><div class="card-ident"><span class="card-symbol">${icon({fuel:'fuel',metan:'gas',propan:'flame',elektr:'bolt'}[kind])}</span><div><button class="card-name" data-action="detail">${escape(s.name)}</button><span class="card-status ${s.open_now?'':'closed'}"><i></i>${escape(t(s.open_now?'open':'closed'))} · ${escape(hoursShort(s))}</span>${s.demo?`<span class="demo-label">${escape(t('demo'))}</span>`:''}</div></div>${!favoritePage?`<button class="favorite-button ${saved?'saved':''}" data-action="favorite" aria-label="${escape(t(saved?'removeFavorite':'addFavorite'))}" aria-pressed="${saved}">${icon('heart')}</button>`:''}</div><p class="card-address">${escape(s.address)}</p><div class="card-data">${s.unavailable?`<p class="form-error">${escape(t('stationUnavailable'))}</p>`:productsHTML(s,kind)}</div><div class="card-meta"><span class="rating">${icon('star')}${s.rating===null?escape(t('noRatings')):`${escape(number(s.rating,1))} <span class="muted">(${s.rating_count})</span>`}</span><span class="card-distance">${s.distance_m!==null?`${escape(t('approximateDistance'))}: ${escape(dist(s.distance_m))}`:escape(t('distanceUnknown'))}</span></div><p class="card-updated">${escape(t('updated'))}: ${escape(date(s.updated_at))}</p><div class="card-bottom">${favoritePage?`<button class="button secondary" data-action="delete">${icon('trash')}${escape(t('delete'))}</button><button class="button" data-action="route" ${s.unavailable?'disabled':''}>${escape(t('start'))}${icon('arrow')}</button>`:`<button class="button secondary" data-action="detail">${escape(t('details'))}</button><button class="button" data-action="route">${icon('route')}${escape(t('route'))}</button>`}</div></article>`;
}
export function bindCards(root,stations){
 const items=new Map(stations.map(s=>[String(s.id),s]));
 $$('[data-station]',root).forEach(card=>{const station=items.get(card.dataset.station);$$('[data-action]',card).forEach(button=>button.onclick=()=>{const action=button.dataset.action;if(action==='detail')details(station);if(action==='route')emit('route-request',station);if(['favorite','delete'].includes(action))emit('favorite-toggle',station)})});
}
export async function loadStations({silent=false}={}){
 const version=++generation;state.loading=true;
 const status=$('#station-state');if(!silent){status.innerHTML='';$('#station-grid').innerHTML='<div class="skeleton"></div>'.repeat(3)}
 try{
  const o=state.origin;
  const result=await api('/stations?'+query({category:state.category,sort:state.sort,open_now:state.open,grade:state.category==='fuel'?state.grade:null,unit:state.category==='elektr'?state.unit:null,pressure_unit:state.pressureUnit,latitude:o?.latitude,longitude:o?.longitude,page:state.pageNumber,per_page:9,q:state.query}));
  if(version!==generation)return;
  state.stations=result.items;state.total=result.total;state.lastResult=result;renderStations();
  updateMarkers(result.map_items||result.items);
  status.innerHTML='';if(!result.total)empty(status,'noStations');
  $('#connection').classList.remove('failed');$('#connection').innerHTML='<i></i>'+escape(t('connected'));
 }catch(error){if(version!==generation)return;$('#station-grid').innerHTML='';$('#pagination').innerHTML='';state.stations=[];updateMarkers([]);status.innerHTML=`<div class="notice danger"><span>${escape(t('e.'+error.code))}</span><button class="button small secondary" id="station-retry">${escape(t('retry'))}</button></div>`;$('#station-retry').onclick=()=>loadStations();$('#connection').classList.add('failed');$('#connection').innerHTML='<i></i>'+escape(t('connectionError'))}
 finally{if(version===generation)state.loading=false}
}
export function renderStations(){
 $('#station-grid').innerHTML=state.stations.map(s=>cardHTML(s)).join('');bindCards($('#station-grid'),state.stations);
 $('#result-count').textContent=t('resultCount',{n:number(state.total)});
 $('#comparison-note').textContent=t(state.sort==='cheapest'?'comparisonNote':state.category==='metan'||state.category==='propan'?'pressureNote':'rankingNote')+(state.total>(state.lastResult?.map_limit||1000)?' '+t('mapLimit',{n:1000}):'');
 const pages=Math.ceil(state.total/9);$('#pagination').innerHTML=pages>1?`<button class="button secondary small" id="previous-page" ${state.pageNumber===1?'disabled':''}>← ${escape(t('previous'))}</button><span>${number(state.pageNumber)} / ${number(pages)}</span><button class="button secondary small" id="next-page" ${state.pageNumber===pages?'disabled':''}>${escape(t('next'))} →</button>`:'';
 if($('#previous-page'))$('#previous-page').onclick=()=>{state.pageNumber--;loadStations()};if($('#next-page'))$('#next-page').onclick=()=>{state.pageNumber++;loadStations()};
}
export async function details(station){
 let s=station;
 if(!s.products){try{s=await api('/stations/'+s.id)}catch(error){showError(error);return}}
 const description=s.descriptions?.[language]||Object.values(s.descriptions||{}).find(Boolean)||'';
 const fallback=description&&!s.descriptions?.[language];
 const box=modal(s.name,`<p class="muted">${escape(s.address)}</p>${s.demo?`<p class="notice">${escape(t('demoWarning'))}</p>`:''}<div class="detail-section"><p>${escape(description)}</p>${fallback?`<p class="tiny muted">${escape(t('descriptionFallback'))}</p>`:''}<p class="card-status ${s.open_now?'':'closed'}">${escape(t(s.open_now?'open':'closed'))}</p><p class="tiny muted">${escape(t('operationalNote'))}</p></div>${(s.categories||[]).map(c=>`<div class="detail-section"><h3>${escape(t(c))}</h3>${productsHTML(s,c)}</div>`).join('')}<div class="detail-section"><h3>${escape(t('hours'))}</h3>${s.is_24h?'<p>24/7</p>':Object.entries(s.hours||{}).map(([day,hours])=>`<p>${escape(t('day_'+day))}: ${hours.length?escape(hours.map(x=>x.join('–')).join(', ')):escape(t('closed'))}</p>`).join('')}<p class="tiny muted">Asia/Tashkent</p></div><p class="tiny muted">${escape(t('updated'))}: ${escape(date(s.updated_at))}</p><div class="dialog-actions"><button class="button secondary" id="detail-favorite">${escape(t(state.favorites.has(s.id)?'removeFavorite':'addFavorite'))}</button><button class="button" id="detail-route">${escape(t('route'))}</button></div><button class="text-button" id="detail-rating">${escape(t('rateStation'))}</button>`);
 detailStation=s;$('#modal').dataset.context='station';
 $('#detail-route',box).onclick=()=>{$('#modal').close();emit('route-request',s)};
 $('#detail-favorite',box).onclick=()=>{emit('favorite-toggle',s);$('#modal').close()};
 $('#detail-rating',box).onclick=()=>{if(!state.user){toast(t('signInForRating'));return}ratingDialog(s)};
}
export function updateFilters(){
 $$('[data-category]').forEach(b=>{b.classList.toggle('selected',b.dataset.category===state.category);b.setAttribute('aria-pressed',String(b.dataset.category===state.category))});
 $$('[data-sort]').forEach(b=>{b.classList.toggle('selected',b.dataset.sort===state.sort);b.setAttribute('aria-pressed',String(b.dataset.sort===state.sort))});
 $('#grade-label').hidden=state.category!=='fuel';$('#unit-label').hidden=state.category!=='elektr';$('#pressure-label').hidden=!['metan','propan'].includes(state.category);
}

on('language',()=>{if($('#modal').open&&$('#modal').dataset.context==='station'&&detailStation)details(detailStation)});
