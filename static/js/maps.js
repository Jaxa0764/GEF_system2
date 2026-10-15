import {state,emit} from './state.js';
import {$,escape,hydrate,toast} from './ui.js';
import {t} from './i18n.js';
import {icon} from './icons.js';
let map,markers,userMarker,accuracyCircle,routeLayer,tiles,picker,pickerMarker,pickerCallback,manualMode=false;
let tileErrors=0,fallback=false;
const attributionHTML=text=>escape(text).replace('OpenStreetMap contributors','<a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap contributors</a>');
export function initMap(){
 if(map)return map;
 if(!window.L){$('#map-error').hidden=false;$('#map-error-text').textContent=t('e.MAP_LIBRARY');return null}
 const L=window.L;
 map=L.map('map',{zoomControl:false,attributionControl:true}).setView([41.3111,69.2406],12);
 L.control.zoom({position:'bottomright'}).addTo(map);markers=L.layerGroup().addTo(map);
 addTiles();
 map.on('dragstart',()=>{state.following=false;if(state.navigating)$('#follow').hidden=false});
 map.on('zoomend',()=>{if(state.mapStations)updateMarkers(state.mapStations)});
 map.on('click',e=>{if(manualMode){manualMode=false;emit('manual-point',{latitude:e.latlng.lat,longitude:e.latlng.lng})}});
 const observer=new ResizeObserver(()=>map.invalidateSize({pan:false}));observer.observe($('#map'));
 return map;
}
function addTiles(){
 if(!map)return;
 if(tiles)map.removeLayer(tiles);tileErrors=0;
 const url=fallback?state.config.tile_fallback_url:state.config.tile_url;
 const attribution=fallback?state.config.tile_fallback_attribution:state.config.tile_attribution;
 if(!url?.startsWith('https://')){$('#map-error').hidden=false;return}
 // Attribution is server-configured text; escape it before Leaflet inserts it.
 tiles=window.L.tileLayer(url,{maxZoom:19,attribution:attributionHTML(attribution),crossOrigin:true});
 tiles.on('tileerror',()=>{if(++tileErrors>=3)$('#map-error').hidden=false});
 tiles.on('load',()=>{if(tileErrors===0)$('#map-error').hidden=true});tiles.addTo(map);
}
export function retryTiles(){if(!map){initMap();return}if(state.config.tile_fallback_url)fallback=!fallback;$('#map-error').hidden=true;addTiles()}
export function resizeMap(){if(!map)initMap();requestAnimationFrame(()=>map?.invalidateSize({pan:false}));setTimeout(()=>map?.invalidateSize({pan:false}),120)}
export function updateMarkers(stations){
 state.mapStations=stations;if(!map||!markers)return;markers.clearLayers();
 const L=window.L,zoom=map.getZoom();
 const groups=new Map();
 for(const station of stations){
  // Spatial grouping keeps large result sets usable without a heavyweight dependency.
  const cell=zoom<13&&stations.length>50?`${Math.floor(station.latitude*100/Math.max(1,16-zoom))}:${Math.floor(station.longitude*100/Math.max(1,16-zoom))}`:String(station.id);
  if(!groups.has(cell))groups.set(cell,[]);groups.get(cell).push(station);
 }
 for(const group of groups.values()){
  const s=group[0];
  const marker=L.marker([s.latitude,s.longitude],{icon:L.divIcon({className:'station-marker',html:group.length>1?String(group.length):icon({fuel:'fuel',metan:'gas',propan:'flame',elektr:'bolt'}[state.category]),iconSize:[32,36],iconAnchor:[16,36]})});
  if(group.length>1){marker.on('click',()=>map.fitBounds(group.map(x=>[x.latitude,x.longitude]),{maxZoom:16,padding:[30,30]}))}
  else{
   const content=document.createElement('div');content.innerHTML=`<b>${escape(s.name)}</b><span>${escape(s.address)}</span><br><span class="card-status ${s.open_now?'':'closed'}">${escape(t(s.open_now?'open':'closed'))}</span><button class="button small">${escape(t('route'))}</button>`;
   $('button',content).onclick=()=>emit('route-request',s);marker.bindPopup(content);
  }
  marker.addTo(markers);
 }
}
export function showUser(origin,{center=false}={}){
 if(!map)return;const L=window.L,point=[origin.latitude,origin.longitude];
 if(userMarker)userMarker.setLatLng(point);else userMarker=L.marker(point,{icon:L.divIcon({className:'user-marker',iconSize:[17,17],iconAnchor:[8,8]}),zIndexOffset:1000}).addTo(map);
 userMarker.setIcon(L.divIcon({className:'user-marker'+(origin.kind==='manual'?' manual-marker':''),iconSize:[17,17],iconAnchor:[8,8]}));
 if(accuracyCircle){map.removeLayer(accuracyCircle);accuracyCircle=null}
 if(origin.kind==='live'&&origin.accuracy)accuracyCircle=L.circle(point,{radius:origin.accuracy,color:'#3679ed',weight:1,fillOpacity:.08}).addTo(map);
 if(center||state.following)map.panTo(point,{animate:!window.matchMedia('(prefers-reduced-motion: reduce)').matches});
}
export function drawRoute(route,{fit=true}={}){
 if(!map)return;if(routeLayer)map.removeLayer(routeLayer);
 routeLayer=window.L.geoJSON(route.geometry,{style:{color:'#16765a',weight:6,opacity:.9}}).addTo(map);
 if(fit)map.fitBounds(routeLayer.getBounds(),{padding:[40,40],maxZoom:16});
}
export function clearRoute(){if(routeLayer&&map)map.removeLayer(routeLayer);routeLayer=null}
export function follow(){if(state.origin){state.following=true;$('#follow').hidden=true;showUser(state.origin,{center:true});map?.setZoom(Math.max(15,map.getZoom()))}}
export function selectOriginOnMap(){manualMode=true;toast(t('manualHint'));map?.getContainer().focus()}
export function focusStation(station){map?.setView([station.latitude,station.longitude],15);}
export function openPicker(initial,callback){
 pickerCallback=callback;$('#picker-dialog').showModal();
 $('#picker-lat').value=initial?.latitude??'';$('#picker-lon').value=initial?.longitude??'';$('#picker-save').disabled=!initial;
 if(!window.L){toast(t('e.MAP_LIBRARY'),true);return}
 if(!picker){picker=window.L.map('picker-map').setView([41.3111,69.2406],12);window.L.tileLayer(state.config.tile_url,{maxZoom:19,attribution:attributionHTML(state.config.tile_attribution)}).addTo(picker);picker.on('click',e=>setPicker(e.latlng.lat,e.latlng.lng));new ResizeObserver(()=>picker.invalidateSize()).observe($('#picker-map'))}
 if(pickerMarker){picker.removeLayer(pickerMarker);pickerMarker=null}
 if(initial){setPicker(initial.latitude,initial.longitude);picker.setView([initial.latitude,initial.longitude],14)}
 setTimeout(()=>picker.invalidateSize(),80);
}
export function setPicker(latitude,longitude){
 const valid=Number.isFinite(latitude)&&Number.isFinite(longitude)&&Math.abs(latitude)<=90&&Math.abs(longitude)<=180;
 $('#picker-save').disabled=!valid;if(!valid)return;
 $('#picker-lat').value=latitude.toFixed(6);$('#picker-lon').value=longitude.toFixed(6);
 if(!picker)return;
 if(pickerMarker)pickerMarker.setLatLng([latitude,longitude]);
 else {pickerMarker=window.L.marker([latitude,longitude],{draggable:true}).addTo(picker);pickerMarker.on('dragend',()=>{const p=pickerMarker.getLatLng();setPicker(p.lat,p.lng)})}
}
export function initPickerControls(){
 for(const id of ['#picker-lat','#picker-lon'])$(id).oninput=()=>{const a=$('#picker-lat'),b=$('#picker-lon');if(a.value===''||b.value===''){$('#picker-save').disabled=true;return}setPicker(Number(a.value),Number(b.value))};
 $('#picker-save').onclick=()=>{const latitude=Number($('#picker-lat').value),longitude=Number($('#picker-lon').value);if($('#picker-save').disabled)return;$('#picker-dialog').close();pickerCallback?.({latitude,longitude})};
}
