import {t,translate} from './i18n.js';
import {paintIcons,icon} from './icons.js';
export const $=(selector,root=document)=>root.querySelector(selector);
export const $$=(selector,root=document)=>[...root.querySelectorAll(selector)];
export const escape=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
export const tr=key=>`<span data-i18n="${escape(key)}">${escape(t(key))}</span>`;
export function hydrate(root=document){translate(root);paintIcons(root)}
export function toast(message,error=false){const el=document.createElement('div');el.className='toast'+(error?' error':'');el.textContent=message;$('#toasts').append(el);setTimeout(()=>el.remove(),6500)}
export function errorText(error){return t('e.'+(error.code||'NETWORK_ERROR'))+(error.fields&&Object.keys(error.fields).length?' '+t('checkFields'):'')}
export function showError(error,container){if(container){container.textContent=errorText(error);container.hidden=false}else toast(errorText(error),true)}
export function empty(container,key,action=null){container.innerHTML=`<div class="empty-state">${icon('map')}<p data-i18n="${key}">${escape(t(key))}</p>${action?`<button class="button secondary">${escape(t('retry'))}</button>`:''}</div>`;if(action)$('button',container).onclick=action}
export function modal(title,html){$('#modal').dataset.context='';$('#modal-title').textContent=t(title);if(t(title)!==title)$('#modal-title').dataset.i18n=title;else delete $('#modal-title').dataset.i18n;$('#modal-body').innerHTML=html;hydrate($('#modal'));if(!$('#modal').open)$('#modal').showModal();return $('#modal-body')}
export function closeModal(){$('#modal').close()}
export function busy(button,active){if(!button)return;button.disabled=active;button.setAttribute('aria-busy',String(active))}
export function safeUrl(url){try{const p=new URL(url);return p.protocol==='https:'?p.href:'#'}catch{return '#'}}
export function formField(key,name,type='text',value='',extra=''){return `<label>${tr(key)}<input name="${name}" type="${type}" value="${escape(value)}" ${extra}></label>`}
