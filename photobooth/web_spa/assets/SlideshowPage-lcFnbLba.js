import{Q as m}from"./QPage-DAiiHfxw.js";import{d as u,W as d,A as f,B as _,o as h,f as o,k as p,l as g,n,g as i,m as s}from"./index-DMTCEbHD.js";import{_ as v,I as x}from"./ItemNotAvailableError-BK-J11-u.js";import"./QImg-F7_Ct8Qf.js";import"./_plugin-vue_export-helper-DlAUqK2U.js";const w={key:0,class:"full-height full-width"},I={key:1,class:"full-height"},k=5e3,C=u({__name:"SlideshowPage",setup(M){const e=d(),a=f(0);let t;function r(){c(),clearTimeout(t),l()}function l(){t=window.setInterval(r,k)}function c(){a.value=Math.floor(Math.random()*e.collection.length)}return _(()=>{l()}),h(()=>{clearInterval(t)}),(B,T)=>(o(),p(m,{id:"slideshow-page",class:"row justify-center items-center flex flex-center absolute-full"},{default:g(()=>[n(e).collection_number_of_items>0?(o(),i("div",w,[s(v,{item:n(e).collection[a.value]},null,8,["item"])])):(o(),i("div",I,[s(x)]))]),_:1}))}});export{C as default};