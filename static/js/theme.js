import {storageGet,storageSet,emit,state} from './state.js';
import {api} from './api.js';
import {icon} from './icons.js';
export let theme=storageGet('gef-theme','light');
export function setTheme(next,{save=true}={}){
  theme=next==='dark'?'dark':'light';document.documentElement.dataset.theme=theme;
  if(save)storageSet('gef-theme',theme);
  const button=document.querySelector('#theme-toggle');if(button)button.innerHTML=icon(theme==='dark'?'sun':'moon');
  const tg=window.Telegram?.WebApp;
  try{if(tg?.isVersionAtLeast?.('6.1')){tg.setHeaderColor(theme==='dark'?'#15201c':'#f6f7f3');tg.setBackgroundColor(theme==='dark'?'#15201c':'#f6f7f3')}}catch{}
  emit('theme',theme);
}
export async function savePreferences(language){if(state.user)try{await api('/me/preferences',{method:'PATCH',body:{language,theme}})}catch{} }
