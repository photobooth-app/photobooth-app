"use strict";(globalThis["webpackChunkphotobooth_app_frontend"]=globalThis["webpackChunkphotobooth_app_frontend"]||[]).push([[889],{30889:(t,e,o)=>{o.r(e),o.d(e,{default:()=>C});var l=o(59835),a=o(86970);const n={class:"row col-xs-12 col-sm-4 col-md-3 col-lg-3"},r=(0,l._)("div",{class:"text-h5"},"Maintenance",-1),d={class:"q-gutter-sm q-ma-md"},i={class:"row"},s=(0,l._)("div",{class:"text-h5"},"Log Records",-1),u=(0,l._)("thead",null,[(0,l._)("tr",{class:"text-left"},[(0,l._)("th",null,"Level"),(0,l._)("th",null,"Time"),(0,l._)("th",null,"Name"),(0,l._)("th",null,"Function Name"),(0,l._)("th",null,"LineNo"),(0,l._)("th",{style:{width:"100%"}},"Message")])],-1);function m(t,e,o,m,_,c){const w=(0,l.up)("q-card-section"),f=(0,l.up)("q-card"),p=(0,l.up)("QBtn"),h=(0,l.up)("q-markup-table"),g=(0,l.up)("q-page");return(0,l.wg)(),(0,l.j4)(g,{padding:""},{default:(0,l.w5)((()=>[(0,l._)("div",n,[(0,l.Wm)(f,{style:{},class:"q-pa-md q-ma-md"},{default:(0,l.w5)((()=>[(0,l.Wm)(w,null,{default:(0,l.w5)((()=>[r,(0,l._)("div",d,[(0,l._)("div",null," CPU: "+(0,a.zw)(t.store.information["cpu1_5_15"][0])+"% / "+(0,a.zw)(t.store.information["cpu1_5_15"][1])+"% / "+(0,a.zw)(t.store.information["cpu1_5_15"][2])+"% ",1),(0,l._)("div",null," No. active threads: "+(0,a.zw)(t.store.information["active_threads"]),1),(0,l._)("div",null," Free disk: "+(0,a.zw)((t.store.information["disk"]["free"]/1024**3).toFixed(1))+"GB ",1),(0,l._)("div",null," Memory: "+(0,a.zw)((t.store.information["memory"]["total"]/1024**3).toFixed(1))+"GB total "+(0,a.zw)((t.store.information["memory"]["free"]/1024**3).toFixed(1))+"GB free "+(0,a.zw)((t.store.information["memory"]["available"]/1024**3).toFixed(1))+"GB available ",1),(0,l._)("div",null," Cma: "+(0,a.zw)((t.store.information["cma"]["CmaTotal"]/1024).toFixed(1))+"MB total / "+(0,a.zw)((t.store.information["cma"]["CmaFree"]/1024).toFixed(1))+"MB free ",1)])])),_:1})])),_:1})]),(0,l.Wm)(f,{class:"q-pa-md q-mt-md"},{default:(0,l.w5)((()=>[(0,l._)("div",i,[s,(0,l.Wm)(p,{href:"/debug/log/latest",target:"_blank"},{default:(0,l.w5)((()=>[(0,l.Uk)("download log")])),_:1})]),(0,l.Wm)(h,null,{default:(0,l.w5)((()=>[u,(0,l._)("tbody",null,[((0,l.wg)(!0),(0,l.iD)(l.HY,null,(0,l.Ko)(this.store.logrecords,((t,e)=>((0,l.wg)(),(0,l.iD)("tr",{key:e},[(0,l._)("td",null,(0,a.zw)(t.level),1),(0,l._)("td",null,(0,a.zw)(t.time),1),(0,l._)("td",null,(0,a.zw)(t.name),1),(0,l._)("td",null,(0,a.zw)(t.funcName),1),(0,l._)("td",null,(0,a.zw)(t.lineno),1),(0,l._)("td",null,(0,a.zw)(t.message),1)])))),128))])])),_:1})])),_:1})])),_:1})}var _=o(67575),c=o(91569),w=o(68879);const f=(0,l.aZ)({name:"MainLayout",components:{QBtn:w.Z},setup(){const t=(0,_.h)();return{store:t,remoteProcedureCall:c.remoteProcedureCall}}});var p=o(11639),h=o(69885),g=o(44458),v=o(63190),z=o(20990),b=o(66933),k=o(69984),q=o.n(k);const x=(0,p.Z)(f,[["render",m]]),C=x;q()(f,"components",{QPage:h.Z,QCard:g.Z,QCardSection:v.Z,QBadge:z.Z,QMarkupTable:b.Z})}}]);