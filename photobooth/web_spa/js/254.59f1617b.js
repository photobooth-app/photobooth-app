"use strict";(globalThis["webpackChunkphotobooth_app_frontend"]=globalThis["webpackChunkphotobooth_app_frontend"]||[]).push([[254],{16254:(t,e,o)=>{o.r(e),o.d(e,{default:()=>S});var n=o(61758);function s(t,e,o,s,u,i){const a=(0,n.g2)("router-view"),r=(0,n.g2)("RouteAfterTimeout"),p=(0,n.g2)("q-page-container"),m=(0,n.g2)("q-layout");return(0,n.uX)(),(0,n.Wv)(m,{view:"hHh lpR fFf"},{default:(0,n.k6)((()=>[(0,n.bF)(p,null,{default:(0,n.k6)((()=>[(0,n.bF)(a),this.uiSettingsStore.uiSettings.show_automatic_slideshow_timeout>0?((0,n.uX)(),(0,n.Wv)(r,{key:0,route:"/slideshow/random",timeout_ms:1e3*this.uiSettingsStore.uiSettings.show_automatic_slideshow_timeout,warning_message:t.$t("MSG_WARN_BEFORE_AUTO_SLIDESHOW")},null,8,["timeout_ms","warning_message"])):(0,n.Q3)("",!0)])),_:1})])),_:1})}o(10239);var u=o(48313),i=o(20392),a=o(60455),r=o(60322),p=o(43710);const m={__name:"RouteAfterTimeout",props:{route:{type:String,required:!0},timeout_ms:{type:Number,required:!0},warning_message:{type:String,default:"Auto-starting slideshow... Click anywhere to stay on this page."},warning_time_ms:{type:Number,default:1e4}},setup(t){const e=(0,p.A)(),o=(0,a.rd)(),s=t,{idle:u,lastActive:i,reset:m}=(0,r.UQV)(s.timeout_ms),l=(0,r.wH9)({interval:1e3}),_=(0,n.EW)((()=>s.timeout_ms-(l.value-i.value))),g=(0,n.EW)((()=>s.warning_time_ms>_.value));let h=null;function c(){h=e.notify({progress:!0,message:s.warning_message,type:"info",multiline:!0,timeout:_.value,icon:"slideshow"})}function d(){h&&h()}return(0,n.xo)((()=>{d()})),(0,n.wB)(g,(t=>{t?c():d()})),(0,n.wB)(u,(t=>{t&&(d(),o.push({path:s.route}))})),(t,e)=>((0,n.uX)(),(0,n.CE)("div"))}},l=m,_=l,g=(0,n.pM)({name:"MainLayout",components:{RouteAfterTimeout:_},computed:{},setup(){const t=(0,u.q)(),e=(0,i.w)(),o=(0,a.rd)();return t.$subscribe(((t,e)=>{"counting"==e.state&&"/"!=o.path&&(console.log("counting state received, pushing to index page to countdown"),o.push("/")),"present_capture"==e.state&&o.push({path:"/itempresenter"}),"approve_capture"==e.state&&e.ask_user_for_approval&&o.push({path:"/itemapproval"})})),{uiSettingsStore:e}}});var h=o(12807),c=o(83333),d=o(71102),w=o(98582),f=o.n(w);const v=(0,h.A)(g,[["render",s]]),S=v;f()(g,"components",{QLayout:c.A,QPageContainer:d.A})}}]);