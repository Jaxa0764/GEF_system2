import {state,on,emit} from './state.js';
import {api} from './api.js';
import {$,$$,hydrate,toast,showError} from './ui.js';
import {setLanguage,t,language} from './i18n.js';
import {setTheme,theme,savePreferences} from './theme.js';
import {initMap,resizeMap,showUser,updateMarkers,retryTiles,openPicker,setPicker,initPickerControls,follow} from './maps.js';
import {requestPosition,resumePermission,setManualOrigin,reverseAddress} from './location.js';
import {loadStations,renderStations,updateFilters} from './stations.js';
import {refreshFavorites,toggleFavorite,renderFavorites} from './favorites.js';
import {loadSession,renderProfile,updateAccount} from './auth.js';
import {prepareRoute,renderRoute} from './navigation.js';
import {initChat,renderChat} from './assistant.js';
import {renderAdmin,selectAdminTab,editStation} from './admin.js';
import {initTelegram} from './telegram.js';
const pages={home:'/',favorites:'/favorites',assistant:'/assistant',profile:'/profile',admin:'/admin'};
let poll=null,lastPositionRefresh=0,channel=null;
function pageFromPath(){return Object.entries(pages).find(([,path])=>location.pathname===path)?.[0]||'home'}
export function showPage(page,{historyUpdate=true}={}){
 if(!pages[page])page='home';if(page==='admin'&&state.user?.role!=='admin')page='profile';state.page=page;
 $$('main>.page').forEach(p=>p.hidden=p.id!=='page-'+page);
 $$('[data-page]').forEach(a=>{const selected=a.dataset.page===page;a.classList.toggle('selected',selected);a.setAttribute('aria-current',selected?'page':'false')});
 $('#crumb').dataset.i18n=page;$('#crumb').textContent=t(page);
 if(historyUpdate&&location.pathname!==pages[page])history.pushState({},'',pages[page]);
 if(page==='home'){resizeMap();renderStations()}if(page==='favorites')refreshFavorites();if(page==='profile')renderProfile();if(page==='assistant')renderChat();if(page==='admin')renderAdmin();
 try{const tg=window.Telegram?.WebApp;if(page==='home')tg?.BackButton?.hide();else tg?.BackButton?.show()}catch{}
}
function resetPage(){state.pageNumber=1;updateFilters();loadStations()}
function chooseOrigin(){openPicker(state.origin,point=>{setManualOrigin(point.latitude,point.longitude);emit('origin-selected',point)})}
function wire(){
 document.addEventListener('invalid',e=>{const input=e.target;if(!input.validity||input.validity.customError)return;let message=t('checkFields');if(input.validity.valueMissing)message=t('validationRequired');else if(input.validity.tooShort)message=t('validationShort',{min:input.minLength});else if(input.validity.rangeOverflow||input.validity.rangeUnderflow)message=t('validationRange');input.setCustomValidity(message);input.dataset.gefValidation='1'},true);
 document.addEventListener('input',e=>{if(e.target.dataset?.gefValidation){e.target.setCustomValidity('');delete e.target.dataset.gefValidation}},true);
 $$('[data-page]').forEach(a=>a.onclick=e=>{e.preventDefault();showPage(a.dataset.page)});$('#admin-link').onclick=e=>{e.preventDefault();showPage('admin')};$('#account-button').onclick=()=>showPage('profile');window.addEventListener('popstate',()=>showPage(pageFromPath(),{historyUpdate:false}));
 $('#language').onchange=async e=>{try{await setLanguage(e.target.value);await savePreferences(language)}catch(error){showError(error)}};$('#theme-toggle').onclick=()=>{setTheme(theme==='light'?'dark':'light');savePreferences(language)};
 $('#refresh-stations').onclick=()=>loadStations();$('#locate').onclick=()=>requestPosition().then(origin=>showUser(origin,{center:true})).catch(()=>{});$('#manual-origin').onclick=chooseOrigin;$('#follow').onclick=follow;$('#retry-map').onclick=retryTiles;
 $$('[data-category]').forEach(b=>b.onclick=()=>{state.category=b.dataset.category;resetPage()});$$('[data-sort]').forEach(b=>b.onclick=()=>{const next=b.dataset.sort;if(next==='nearest'&&!state.origin){toast(t('needOrigin'));chooseOrigin();return}state.sort=next;resetPage()});
 $('#open-now').onchange=e=>{state.open=e.target.checked;resetPage()};$('#grade').onchange=e=>{state.grade=e.target.value;resetPage()};$('#billing-unit').onchange=e=>{state.unit=e.target.value;resetPage()};$('#pressure-unit').onchange=e=>{state.pressureUnit=e.target.value;resetPage()};
 let searchTimer;$('#station-search').oninput=e=>{const value=e.target.value;clearTimeout(searchTimer);searchTimer=setTimeout(()=>{state.query=value;resetPage()},350)};
 $$('[data-close]').forEach(b=>b.onclick=()=>$('#'+b.dataset.close).close());$$('[data-admin-tab]').forEach(b=>b.onclick=()=>selectAdminTab(b.dataset.adminTab));$('#add-station').onclick=()=>editStation();
 initPickerControls();$('#picker-locate').onclick=async()=>{try{const p=await requestPosition({apply:false});setPicker(p.coords.latitude,p.coords.longitude)}catch(error){showError(error)}};initChat();
 on('page',page=>showPage(page));on('choose-origin',chooseOrigin);on('favorite-toggle',toggleFavorite);on('favorites-refresh',refreshFavorites);on('stations-refresh',()=>loadStations({silent:true}));on('route-request',station=>prepareRoute(station));
 on('session-expired',()=>{updateAccount();refreshFavorites();if(state.page==='profile')renderProfile();toast(t('e.AUTH_REQUIRED'),true)});
 on('position',origin=>{showUser(origin,{center:lastPositionRefresh===0});if(Date.now()-lastPositionRefresh>30000){lastPositionRefresh=Date.now();loadStations({silent:true})}});on('origin-selected',()=>loadStations({silent:true}));
 on('language',()=>{hydrate();updateAccount();renderStations();updateMarkers(state.mapStations||[]);if(state.page==='favorites')renderFavorites();if(state.page==='assistant')renderChat();if(state.route)renderRoute();if(state.origin){$('#origin-label').textContent=t(state.origin.kind==='live'?'liveOrigin':'manualOrigin');reverseAddress(true)}if(state.page==='admin'&&!$('#station-dialog').open)renderAdmin();if($('#profile-language'))$('#profile-language').value=language});
 on('theme',value=>{if($('#profile-theme'))$('#profile-theme').value=value});on('admin-changed',()=>{try{channel?.postMessage('stations-updated')}catch{}});
 const online=()=>{$('#offline').hidden=navigator.onLine;if(navigator.onLine)loadStations({silent:true})};window.addEventListener('online',online);window.addEventListener('offline',online);$('#offline').hidden=navigator.onLine;
 try{channel=new BroadcastChannel('gef-system');channel.onmessage=()=>{if(!document.hidden)loadStations({silent:true})}}catch{}
 document.addEventListener('visibilitychange',()=>{if(document.hidden){clearInterval(poll);poll=null}else{loadStations({silent:true});refreshFavorites();startPolling()}});window.addEventListener('focus',()=>{if(!state.loading&&!document.hidden)loadStations({silent:true})});
}
function startPolling(){if(poll||document.hidden)return;poll=setInterval(()=>{if(!state.loading&&!document.hidden){loadStations({silent:true});if(state.page==='favorites')refreshFavorites()}},Math.max(15,state.config.poll_seconds||25)*1000)}
async function boot(){
 setTheme(theme);try{await setLanguage(language)}catch{document.documentElement.lang='uz'}
 try{state.config=await api('/config',{timeout:8000})}catch(error){toast(t('e.'+error.code),true)}
 hydrate();wire();initMap();updateFilters();$('#splash').hidden=true;initTelegram();window.addEventListener('load',()=>initTelegram(),{once:true});
 try{await loadSession();await refreshFavorites()}catch(error){toast(t('e.'+error.code),true)}
 showPage(pageFromPath(),{historyUpdate:false});loadStations();resumePermission();startPolling();
}
boot().catch(error=>{$('#splash').hidden=true;toast(t('e.SERVER_ERROR'),true);console.error('GEF initialization failed',error?.code||error?.name)});
