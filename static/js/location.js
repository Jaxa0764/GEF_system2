import {state,emit} from './state.js';
import {api,query} from './api.js';
import {language,t} from './i18n.js';
import {$,showError} from './ui.js';
import {telegramPosition,telegram} from './telegram.js';
let watchId=null,requestPending=null,lastGeocode=0,lastGeoPoint=null;
const errorMap={1:'LOCATION_DENIED',2:'LOCATION_UNAVAILABLE',3:'LOCATION_TIMEOUT'};
export const locationError=error=>({code:error.code&&typeof error.code==='string'?error.code:errorMap[error.code]||'LOCATION_UNAVAILABLE'});
export function acceptPosition(position){
 const {latitude,longitude,accuracy,heading,speed}=position.coords;
 if(!Number.isFinite(latitude)||!Number.isFinite(longitude)||Math.abs(latitude)>90||Math.abs(longitude)>180)throw {code:'LOCATION_INVALID'};
 if(Date.now()-position.timestamp>60000)throw {code:'LOCATION_STALE'};
 state.origin={latitude,longitude,accuracy:Number.isFinite(accuracy)?accuracy:null,heading:Number.isFinite(heading)&&speed>1?heading:null,timestamp:position.timestamp,kind:'live'};
 $('#origin-label').textContent=t('liveOrigin');$('#location-hint').hidden=true;
 $('#address').textContent=state.originAddress||`${latitude.toFixed(5)}, ${longitude.toFixed(5)}`;
 const box=$('#location-status');box.hidden=true;
 if(accuracy>200){box.textContent=t('poorAccuracy',{accuracy:Math.round(accuracy)});box.hidden=false}
 emit('position',state.origin);reverseAddress();return state.origin;
}
function browserPosition(){return new Promise((resolve,reject)=>{
 if(!navigator.geolocation)return reject({code:'LOCATION_UNSUPPORTED'});
 if(!window.isSecureContext)return reject({code:'HTTPS_REQUIRED'});
 navigator.geolocation.getCurrentPosition(resolve,error=>reject(locationError(error)),{enableHighAccuracy:true,timeout:10000,maximumAge:0});
})}
export async function requestPosition({display=true,apply=true}={}){
 if(requestPending&&apply)return requestPending;
 const work=async()=>{
  $('#locate').classList.add('busy');
  try{
   let position;try{position=await browserPosition()}catch(error){if(telegram?.LocationManager)position=await telegramPosition();else throw error}
   return apply?acceptPosition(position):position;
  }catch(error){if(display){const box=$('#location-status');box.hidden=false;box.className='notice danger';box.textContent=t('e.'+locationError(error).code)+' '+t('manualRecovery')}throw locationError(error)}
  finally{$('#locate').classList.remove('busy');if(apply)requestPending=null}
 };
 const promise=work();if(apply)requestPending=promise;return promise;
}
export function setManualOrigin(latitude,longitude){
 stopTracking();state.origin={latitude,longitude,accuracy:null,timestamp:Date.now(),kind:'manual'};state.originAddress='';
 $('#origin-label').textContent=t('manualOrigin');$('#address').textContent=`${latitude.toFixed(5)}, ${longitude.toFixed(5)}`;
 $('#location-hint').hidden=true;$('#location-status').hidden=true;emit('position',state.origin);reverseAddress(true);
}
export async function ensureOrigin(){if(state.origin?.kind==='manual')return state.origin;if(state.origin?.kind==='live'&&Date.now()-state.origin.timestamp<60000)return state.origin;return requestPosition()}
export async function resumePermission(){try{const result=await navigator.permissions?.query({name:'geolocation'});if(result?.state==='granted')await requestPosition({display:false})}catch{}}
export function startTracking(onError){
 if(watchId!==null)return;
 if(!navigator.geolocation?.watchPosition||!window.isSecureContext)throw {code:'NAV_UNSUPPORTED'};
 watchId=navigator.geolocation.watchPosition(position=>{try{acceptPosition(position)}catch(error){onError?.(error)}},error=>onError?.(locationError(error)),{enableHighAccuracy:true,timeout:15000,maximumAge:0});
}
export function stopTracking(){if(watchId!==null){navigator.geolocation?.clearWatch(watchId);watchId=null}}
export async function reverseAddress(force=false){
 const o=state.origin;if(!o||!state.config.geocoding_configured)return;
 const key=`${o.latitude.toFixed(3)},${o.longitude.toFixed(3)},${language}`;
 if(!force&&(Date.now()-lastGeocode<30000||key===lastGeoPoint))return;
 lastGeocode=Date.now();lastGeoPoint=key;
 try{const result=await api('/geocode?'+query({latitude:o.latitude,longitude:o.longitude,language}));if(state.origin?.kind===o.kind&&Math.abs(state.origin.latitude-o.latitude)<0.001&&Math.abs(state.origin.longitude-o.longitude)<0.001){state.originAddress=result.address;$('#address').textContent=result.address}}catch{}
}
