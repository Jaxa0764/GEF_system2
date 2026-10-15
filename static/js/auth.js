import {state,emit,storageGet} from './state.js';
import {api} from './api.js';
import {$,$$,escape,tr,hydrate,formField,busy,toast,showError,modal,closeModal} from './ui.js';
import {t,language,date} from './i18n.js';
import {setLanguage} from './i18n.js';
import {icon} from './icons.js';
import {setTheme,theme,savePreferences} from './theme.js';
import {mergeGuestFavorites,refreshFavorites} from './favorites.js';
import {openTelegram} from './telegram.js';
let authMode='login';
export async function loadSession(){
 const result=await api('/me');state.user=result.user;state.csrf=result.csrf_token;
 if(state.user){if(!storageGet('gef-language'))await setLanguage(state.user.language);if(!storageGet('gef-theme'))setTheme(state.user.theme)}
 updateAccount();return result;
}
export function updateAccount(){
 $('#admin-link').hidden=state.user?.role!=='admin';$('#account-button').textContent=state.user?state.user.first_name.slice(0,1).toUpperCase():'';if(!state.user)$('#account-button').innerHTML=icon('user');
}
export function recoveryDialog(code){
 const box=modal('recoveryTitle',`<p>${tr('recoveryDescription')}</p><code class="recovery-code">${escape(code)}</code><div class="dialog-actions"><button class="button secondary" id="copy-recovery">${tr('copy')}</button><button class="button" id="close-recovery">${tr('savedCode')}</button></div>`);
 $('#close-recovery',box).onclick=closeModal;
 $('#copy-recovery',box).onclick=async()=>{try{await navigator.clipboard.writeText(code);toast(t('copied'))}catch{toast(t('copyManually'))}};
}
async function authenticated(result){
 state.user=result.user;state.csrf=result.csrf_token;updateAccount();emit('account-changed');await mergeGuestFavorites();renderProfile();if(result.recovery_code)recoveryDialog(result.recovery_code);
}
export function renderProfile(){
 const root=$('#profile-content');
 if(!state.user){renderAuth(root);return}
 const u=state.user;
 root.innerHTML=`<div class="profile-layout"><aside class="panel profile-nav"><div class="profile-summary"><span class="profile-avatar">${u.has_avatar?`<img src="/api/me/avatar" width="45" height="45" class="profile-avatar" alt="${escape(t('avatar'))}">`:escape(u.first_name[0])}</span><div><b>${escape(u.first_name+' '+u.last_name)}</b><span class="tiny muted">@${escape(u.username)}</span></div></div><nav>${[['account','user'],['support','help'],['telegram','send'],['settings','settings']].map(([key,ic])=>`<button data-profile-tab="${key}" class="${state.profileTab===key?'selected':''}">${icon(ic)}${tr(key==='telegram'?'telegramChat':key)}</button>`).join('')}</nav><button id="logout">${icon('logout')}${tr('logout')}</button></aside><div class="panel profile-content" id="profile-panel"></div></div>`;
 $$('[data-profile-tab]',root).forEach(button=>button.onclick=()=>{state.profileTab=button.dataset.profileTab;renderProfile()});
 $('#logout').onclick=async()=>{try{await api('/auth/logout',{method:'POST'});state.user=null;state.csrf=null;updateAccount();await refreshFavorites();renderProfile();emit('account-changed')}catch(error){showError(error)}};
 const panel=$('#profile-panel');if(state.profileTab==='account')renderAccount(panel);if(state.profileTab==='support')renderSupport(panel);if(state.profileTab==='settings')renderSettings(panel);if(state.profileTab==='telegram'){panel.innerHTML=`<h2>${tr('telegramChat')}</h2><p class="muted">${tr('telegramDescription')}</p><button class="button" id="support-telegram">${tr('openTelegram')}</button>`;$('#support-telegram').onclick=()=>openTelegram(state.config.support_url)}
 hydrate(root);
}
function renderAuth(root){
 root.innerHTML=`<div class="panel auth-panel"><div class="tabs"><button data-auth="login" class="${authMode==='login'?'selected':''}">${tr('signIn')}</button><button data-auth="register" class="${authMode==='register'?'selected':''}">${tr('register')}</button></div><h2>${tr(authMode==='register'?'createAccount':authMode==='recover'?'resetPassword':'welcomeBack')}</h2><p class="muted tiny">${tr(authMode==='recover'?'resetDescription':'accountDescription')}</p><form id="auth-form" class="form-stack">${authMode==='register'?`<div class="form-grid">${formField('firstName','first_name','text','','required maxlength="80" autocomplete="given-name"')}${formField('lastName','last_name','text','','required maxlength="80" autocomplete="family-name"')}</div>`:''}${formField('username','username','text','','required minlength="3" maxlength="32" pattern="[A-Za-z0-9_]+" autocomplete="username" autocapitalize="none"')}${authMode==='recover'?formField('recoveryCode','recovery_code','text','','required minlength="20" maxlength="200" autocomplete="off"'):''}${formField(authMode==='recover'?'newPassword':'password','password','password','','required minlength="8" maxlength="128" autocomplete="'+(authMode==='login'?'current-password':'new-password')+'"')}${authMode!=='login'?formField('confirmPassword','confirm_password','password','','required minlength="8" maxlength="128" autocomplete="new-password"'):''}${authMode==='register'?`<label class="checkbox-label"><input name="confirmed" type="checkbox" required>${tr('confirmData')}</label>`:''}<p class="form-error" id="auth-error" role="alert" hidden></p><button class="button publish" type="submit" id="auth-submit" ${authMode==='register'?'disabled':''}>${tr(authMode==='register'?'register':authMode==='recover'?'resetPassword':'signIn')}</button></form>${authMode==='login'?`<button id="forgot-password" class="text-button">${tr('forgotPassword')}</button>`:''}</div>`;
 $$('[data-auth]',root).forEach(b=>b.onclick=()=>{authMode=b.dataset.auth;renderAuth(root)});
 if($('#forgot-password'))$('#forgot-password').onclick=()=>{authMode='recover';renderAuth(root)};
 const form=$('#auth-form');const validate=()=>{const a=form.elements.password,b=form.elements.confirm_password;if(b)b.setCustomValidity(a.value===b.value?'':t('passwordMismatch'));if(authMode==='register')$('#auth-submit').disabled=!form.checkValidity()};form.oninput=validate;
 form.onsubmit=async event=>{event.preventDefault();validate();if(!form.reportValidity())return;const values=Object.fromEntries(new FormData(form));delete values.confirm_password;if(authMode==='register'){values.confirm_password=form.elements.confirm_password.value;values.confirmed=form.elements.confirmed.checked}busy($('#auth-submit'),true);$('#auth-error').hidden=true;
  try{const result=await api('/auth/'+(authMode==='register'?'register':authMode==='recover'?'recover':'login'),{method:'POST',body:values});if(authMode==='recover'){authMode='login';renderAuth(root);recoveryDialog(result.recovery_code);toast(t('passwordReset'))}else await authenticated(result)}catch(error){showError(error,$('#auth-error'));busy($('#auth-submit'),false)}
 };
 hydrate(root);
}
function renderAccount(panel){
 const u=state.user;panel.innerHTML=`<h2>${tr('account')}</h2><form id="name-form" class="form-stack"><div class="form-grid">${formField('firstName','first_name','text',u.first_name,'required maxlength="80"')}${formField('lastName','last_name','text',u.last_name,'required maxlength="80"')}</div><div><button class="button" type="submit">${tr('save')}</button></div><p class="form-error" id="name-error" hidden></p></form><h3>${tr('avatar')}</h3><form id="avatar-form" class="form-stack"><label>${tr('avatarDescription')}<input name="file" type="file" accept="image/png,image/jpeg,image/webp" required></label><div><button class="button secondary" type="submit">${tr('uploadAvatar')}</button></div></form><h3>${tr('changePassword')}</h3><form id="password-form" class="form-stack">${formField('currentPassword','current_password','password','','required maxlength="128" autocomplete="current-password"')}${formField('newPassword','new_password','password','','required minlength="8" maxlength="128" autocomplete="new-password"')}${formField('confirmPassword','confirm_password','password','','required minlength="8" maxlength="128" autocomplete="new-password"')}<div><button class="button secondary" type="submit">${tr('changePassword')}</button></div><p class="form-error" id="password-error" hidden></p></form>`;
 $('#name-form').onsubmit=async e=>{e.preventDefault();const b=$('button',e.target);busy(b,true);try{const r=await api('/me',{method:'PATCH',body:Object.fromEntries(new FormData(e.target))});state.user=r.user;toast(t('saved'));updateAccount()}catch(error){showError(error,$('#name-error'))}finally{busy(b,false)}};
 $('#avatar-form').onsubmit=async e=>{e.preventDefault();const b=$('button',e.target);busy(b,true);try{await api('/me/avatar',{method:'POST',body:new FormData(e.target)});state.user.has_avatar=true;toast(t('saved'));renderProfile()}catch(error){showError(error)}finally{busy(b,false)}};
 $('#password-form').onsubmit=async e=>{e.preventDefault();const f=e.target;if(f.elements.new_password.value!==f.elements.confirm_password.value){toast(t('passwordMismatch'),true);return}const b=$('button',f);busy(b,true);try{const r=await api('/me/password',{method:'POST',body:{current_password:f.elements.current_password.value,new_password:f.elements.new_password.value}});f.reset();recoveryDialog(r.recovery_code)}catch(error){showError(error,$('#password-error'))}finally{busy(b,false)}};
}
async function renderSupport(panel){
 panel.innerHTML=`<h2>${tr('support')}</h2><form id="support-form" class="form-stack"><label>${tr('describeProblem')}<textarea name="message" required minlength="5" maxlength="4000" rows="5"></textarea></label><div><button class="button" type="submit">${tr('send')}</button></div><p class="form-error" id="support-error" hidden></p></form><h3>${tr('yourRequests')}</h3><div id="support-history"></div>`;
 const history=async()=>{try{const result=await api('/support');if(!$('#support-history'))return;$('#support-history').innerHTML=result.items.length?result.items.map(item=>`<div class="support-item"><span class="pill">${escape(t('status.'+item.status))}</span><span class="tiny muted"> #${item.id} · ${escape(date(item.created_at))}</span><p>${escape(item.message)}</p></div>`).join(''):`<p class="tiny muted">${tr('noSupport')}</p>`}catch(error){showError(error)}};
 $('#support-form').onsubmit=async e=>{e.preventDefault();const b=$('button',e.target);busy(b,true);try{await api('/support',{method:'POST',body:Object.fromEntries(new FormData(e.target))});e.target.reset();toast(t('supportSaved'));await history()}catch(error){showError(error,$('#support-error'))}finally{busy(b,false)}};
 await history();
}
function renderSettings(panel){
 panel.innerHTML=`<h2>${tr('settings')}</h2><div class="form-stack"><label>${tr('language')}<select id="profile-language"><option value="uz">UZB</option><option value="ru">RU</option><option value="en">ENG</option></select></label><label>${tr('theme')}<select id="profile-theme"><option value="light" data-i18n="light">${tr('light')}</option><option value="dark" data-i18n="dark">${tr('dark')}</option></select></label><p class="tiny muted">${tr('settingsSavedLocally')}</p><h3>${tr('locationPrivacy')}</h3><p class="muted tiny">${tr('privacyDescription')}</p></div>`;
 $('#profile-language').value=language;$('#profile-theme').value=theme;
 $('#profile-language').onchange=async e=>{await setLanguage(e.target.value);await savePreferences(language)};
 $('#profile-theme').onchange=async e=>{setTheme(e.target.value);await savePreferences(language)};
}
