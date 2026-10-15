import {state,storageGet,storageSet,emit} from './state.js';
import {api} from './api.js';
import {$,empty,toast,showError} from './ui.js';
import {t} from './i18n.js';
import {cardHTML,bindCards,renderStations} from './stations.js';
let favoriteItems=[];
function guestIds(){try{return JSON.parse(storageGet('gef-favorites','[]')).filter(x=>Number.isSafeInteger(x)&&x>0).slice(0,200)}catch{return []}}
export async function refreshFavorites(){
 try{
  if(state.user){const result=await api('/favorites');favoriteItems=result.items;state.favorites=new Set(result.items.map(s=>s.id))}
  else state.favorites=new Set(guestIds());
  updateCount();if(state.page==='favorites')await renderFavorites();
 }catch(error){if(state.page==='favorites')showError(error)}
}
function updateCount(){$('#favorite-count').textContent=String(state.favorites.size)}
export async function toggleFavorite(station){
 try{
  const saved=state.favorites.has(station.id);
  if(state.user){await api('/favorites/'+station.id,{method:saved?'DELETE':'PUT'});if(saved)state.favorites.delete(station.id);else state.favorites.add(station.id)}
  else{if(saved)state.favorites.delete(station.id);else state.favorites.add(station.id);storageSet('gef-favorites',JSON.stringify([...state.favorites]));toast(t('guestFavoriteNote'))}
  updateCount();renderStations();if(state.page==='favorites')await refreshFavorites();
 }catch(error){showError(error)}
}
export async function mergeGuestFavorites(){
 if(!state.user)return;const remaining=[];
 for(const id of guestIds())try{await api('/favorites/'+id,{method:'PUT'})}catch(error){if(error.status!==404)remaining.push(id)}
 storageSet('gef-favorites',JSON.stringify(remaining));await refreshFavorites();
}
export async function renderFavorites(){
 const root=$('#favorites-content');$('#favorite-note').textContent=t(state.user?'favoriteNote':'guestFavoriteNote');
 if(!state.favorites.size){empty(root,'noFavorites');return}
 try{
  let items=favoriteItems;
  if(!state.user){const results=await Promise.allSettled([...state.favorites].map(id=>api('/stations/'+id)));items=results.filter(r=>r.status==='fulfilled').map(r=>r.value);if(!items.length){empty(root,'stationUnavailable');return}}
  root.innerHTML='<div class="station-grid">'+items.map(s=>cardHTML(s,{favoritePage:true})).join('')+'</div>';bindCards(root,items);
 }catch(error){showError(error)}
}
