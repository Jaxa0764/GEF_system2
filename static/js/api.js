import {state,emit} from './state.js';
export class ApiError extends Error{constructor(code,status=0,fields={}){super(code);this.code=code;this.status=status;this.fields=fields}}
export async function api(path,{method='GET',body,signal,timeout=22000}={}){
  const controller=new AbortController();const timer=setTimeout(()=>controller.abort(),timeout);
  signal?.addEventListener('abort',()=>controller.abort(),{once:true});
  try{
    const headers={'X-GEF-Request':'1'};
    if(state.csrf)headers['X-CSRF-Token']=state.csrf;
    if(state.token)headers['X-Session-Token']=state.token;
    if(body && !(body instanceof FormData))headers['Content-Type']='application/json';
    const response=await fetch('/api'+path,{method,headers,credentials:'same-origin',cache:'no-store',body:body?(body instanceof FormData?body:JSON.stringify(body)):undefined,signal:controller.signal});
    let data;try{data=await response.json()}catch{throw new ApiError('SERVER_ERROR',response.status)}
    if(!response.ok){if(response.status===401&&state.user){state.user=null;state.csrf=null;state.token=null;try{localStorage.removeItem('gef-token')}catch{}emit('session-expired')}throw new ApiError(data.error?.code||'SERVER_ERROR',response.status,data.error?.fields)}
    return data;
  }catch(error){if(error instanceof ApiError)throw error;throw new ApiError(error.name==='AbortError'?'TIMEOUT':'NETWORK_ERROR')}
  finally{clearTimeout(timer)}
}
export function query(values){const q=new URLSearchParams();Object.entries(values).forEach(([k,v])=>{if(v!==null&&v!==undefined&&v!=='')q.set(k,String(v))});return q.toString()}
