import {productsHTML} from './stations.js';
import {state,emit} from './state.js';
import {api} from './api.js';
import {$,$$,escape,toast,errorText,busy} from './ui.js';
import {t,language,date} from './i18n.js';
import {icon} from './icons.js';
let pending=false;
export function renderChat(){
 $('#ai-mode').textContent=t(state.config.ai_configured?'aiConfigured':'databaseMode');
 const root=$('#chat-messages');
 if(!state.chat.length){root.innerHTML=`<div class="empty-state">${icon('spark')}<h3>${escape(t('chatWelcome'))}</h3><p>${escape(t('chatWelcomeDescription'))}</p></div>`;return}
 root.innerHTML=state.chat.map((item,index)=>`<div class="chat-bubble ${item.role==='user'?'mine':''}">${escape(item.message)}${item.mode?`<small class="tiny">${escape(t(item.mode==='llm'?'llmMode':'databaseMode'))}</small>`:''}</div>${item.stations?.length?`<div class="chat-results">${item.stations.map(s=>`<div class="chat-result"><div><b>${escape(s.name)}</b><p class="tiny muted">${escape(s.address)}</p><span class="card-status ${s.open_now?'':'closed'}">${escape(t(s.open_now?'open':'closed'))}</span><div class="chat-products">${productsHTML(s,s.categories.includes(item.category)?item.category:s.categories[0])}</div><p class="tiny muted">${escape(t('updated'))}: ${escape(date(s.updated_at))}</p></div><button class="button small" data-chat-station="${s.id}" data-chat-index="${index}">${escape(t('route'))}</button></div>`).join('')}</div>`:''}`).join('')+(pending?`<div class="chat-bubble"><span class="loader"></span> ${escape(t('thinking'))}</div>`:'');
 $$('[data-chat-station]',root).forEach(b=>b.onclick=()=>{const s=state.chat[Number(b.dataset.chatIndex)].stations.find(x=>x.id===Number(b.dataset.chatStation));emit('route-request',s)});root.scrollTop=root.scrollHeight;
}
export async function sendMessage(message){
 if(pending||!message.trim())return;pending=true;state.chat.push({role:'user',message:message.trim()});$('#chat-input').value='';renderChat();busy($('#chat-form button'),true);
 try{const o=state.origin;const result=await api('/assistant',{method:'POST',body:{message:message.trim(),language,origin:o?{latitude:o.latitude,longitude:o.longitude}:null}});state.chat.push({role:'assistant',...result});if(result.needs_location)toast(t('locationForAI'))}
 catch(error){state.chat.push({role:'assistant',message:errorText(error),mode:'database'})}
 finally{pending=false;renderChat();busy($('#chat-form button'),false)}
}
export function initChat(){$('#chat-form').onsubmit=e=>{e.preventDefault();sendMessage($('#chat-input').value)};$$('[data-question]').forEach(b=>b.onclick=()=>sendMessage(t(b.dataset.question)));renderChat()}
