import {state,storageGet} from './state.js';
import {setTheme} from './theme.js';
import {api} from './api.js';
export let telegram=null;
export function initTelegram(){
 const tg=window.Telegram?.WebApp;if(!tg?.initData)return false;if(telegram===tg)return true;telegram=tg;
 try{tg.ready();tg.expand();if(!storageGet('gef-theme'))setTheme(tg.colorScheme,{save:false});
   const update=()=>{document.documentElement.style.setProperty('--tg-viewport',`${tg.viewportStableHeight||window.innerHeight}px`);const safe=tg.contentSafeAreaInset||{};for(const key of ['bottom','top'])document.documentElement.style.setProperty(`--tg-content-safe-area-inset-${key}`,`${safe[key]||0}px`)};
   update();tg.onEvent('viewportChanged',update);if(tg.isVersionAtLeast?.('8.0'))tg.onEvent('contentSafeAreaChanged',update);
   tg.BackButton?.onClick(()=>{if(document.querySelector('dialog[open]'))document.querySelector('dialog[open]').close();else history.back()});
 }catch{}
 if(state.config.telegram_configured)api('/telegram/verify',{method:'POST',body:{init_data:tg.initData}}).catch(()=>{});
 return true;
}
export function openTelegram(url){try{if(telegram?.openTelegramLink){telegram.openTelegramLink(url);return}}catch{}window.open(url,'_blank','noopener,noreferrer')}
export function telegramPosition(){
 return new Promise((resolve,reject)=>{
  const manager=telegram?.LocationManager;
  if(!manager||!telegram.isVersionAtLeast?.('8.0'))return reject({code:'LOCATION_UNSUPPORTED'});
  let settled=false;const timer=setTimeout(()=>{if(!settled){settled=true;reject({code:'LOCATION_TIMEOUT'})}},12000);
  const finish=(data)=>{if(settled)return;settled=true;clearTimeout(timer);if(!data)return reject({code:'LOCATION_DENIED'});resolve({coords:{latitude:data.latitude,longitude:data.longitude,accuracy:data.horizontal_accuracy,heading:data.course,speed:data.speed},timestamp:Date.now()})};
  try{manager.init(()=>{if(!manager.isLocationAvailable)finish(null);else manager.getLocation(finish)})}catch{clearTimeout(timer);reject({code:'LOCATION_UNAVAILABLE'})}
 });
}
