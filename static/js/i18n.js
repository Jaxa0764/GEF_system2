import {storageGet,storageSet,emit} from './state.js';
export let language=['uz','ru','en'].includes(storageGet('gef-language'))?storageGet('gef-language'):'uz';
let dictionary={};
const loaded={};
export async function setLanguage(lang){
  if(!['uz','ru','en'].includes(lang))return;
  if(!loaded[lang]){
    const response=await fetch(`/static/locales/${lang}.json`);
    if(!response.ok)throw new Error('Translation unavailable');
    loaded[lang]=await response.json();
  }
  dictionary=loaded[lang];language=lang;storageSet('gef-language',lang);
  document.documentElement.lang=lang;translate();emit('language',lang);
}
export function t(key,values={}){
  let value=dictionary[key]??key;
  for(const [k,v] of Object.entries(values))value=value.replaceAll(`{${k}}`,String(v));
  return value;
}
export function translate(root=document){
  root.querySelectorAll('[data-i18n]').forEach(el=>el.textContent=t(el.dataset.i18n));
  root.querySelectorAll('[data-placeholder]').forEach(el=>el.placeholder=t(el.dataset.placeholder));
  root.querySelectorAll('[data-aria]').forEach(el=>el.setAttribute('aria-label',t(el.dataset.aria)));
  const select=document.querySelector('#language');if(select)select.value=language;
}
export function number(value,max=0){return new Intl.NumberFormat({uz:'uz-UZ',ru:'ru-RU',en:'en-GB'}[language],{maximumFractionDigits:max}).format(value)}
export function date(value){if(!value)return t('unavailable');const d=new Date(value);if(!Number.isFinite(d.getTime()))return t('unavailable');return new Intl.DateTimeFormat({uz:'uz-UZ',ru:'ru-RU',en:'en-GB'}[language],{dateStyle:'short',timeStyle:'short',timeZone:'Asia/Tashkent'}).format(d)}
export function dist(value){return value==null?t('distanceUnknown'):value<1000?`${number(value)} ${t('meter')}`:`${number(value/1000,1)} ${t('km')}`}
export function money(value,unit){return value==null?t('unavailable'):`${number(value)} ${t('uzs')}/${t('unit_'+unit)}`}
