export const state = {
  config:{}, user:null, csrf:null, page:'home', category:'fuel', sort:'default', open:false,
  grade:'AI-92',unit:'kwh',pressureUnit:'bar',query:'',pageNumber:1,stations:[],total:0,
  origin:null,originAddress:'',favorites:new Set(),route:null,navigating:false,following:false,
  adminTab:'stations',profileTab:'account',chat:[],loading:false,
};
export const events=new EventTarget();
export const emit=(name,detail)=>events.dispatchEvent(new CustomEvent(name,{detail}));
export const on=(name,fn)=>events.addEventListener(name,e=>fn(e.detail));
export function storageGet(key,fallback=null){try{return localStorage.getItem(key)??fallback}catch{return fallback}}
export function storageSet(key,value){try{localStorage.setItem(key,value)}catch{}}
