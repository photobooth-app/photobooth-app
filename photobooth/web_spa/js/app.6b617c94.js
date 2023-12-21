(()=>{"use strict";var e={73478:(e,t,o)=>{var n=o(61957),r=o(71947),l=o(60499),a=o(59835);function i(e,t,o,n,r,l){const i=(0,a.up)("router-view"),s=(0,a.up)("connection-overlay"),c=(0,a.up)("q-dialog");return(0,a.wg)(),(0,a.iD)(a.HY,null,[(0,a.Wm)(i),(0,a.Wm)(c,{modelValue:e.showConnectionOverlay,"onUpdate:modelValue":t[0]||(t[0]=t=>e.showConnectionOverlay=t),persistent:""},{default:(0,a.w5)((()=>[(0,a.Wm)(s)])),_:1},8,["modelValue"])],64)}var s=o(67575),c=o(15639),d=o(96694),u=o(33630),p=o(28339);const h=(0,a._)("span",{class:"q-ml-sm"}," Connecting to server. Please wait for autoconnect or try reload. ",-1);function m(e,t,o,n,r,l){const i=(0,a.up)("q-spinner"),s=(0,a.up)("q-card-section"),c=(0,a.up)("q-btn"),d=(0,a.up)("q-card-actions"),u=(0,a.up)("q-card"),p=(0,a.Q2)("close-popup");return(0,a.wg)(),(0,a.j4)(u,{class:"q-pa-sm"},{default:(0,a.w5)((()=>[(0,a.Wm)(s,{class:"row items-center"},{default:(0,a.w5)((()=>[(0,a.Wm)(i,{color:"negative",size:"2em"}),h])),_:1}),(0,a.Wm)(d,{align:"right"},{default:(0,a.w5)((()=>[(0,a.wy)((0,a.Wm)(c,{label:"Reload",color:"primary",onClick:l.reloadPage},null,8,["onClick"]),[[p]])])),_:1})])),_:1})}const f={setup(){return{}},methods:{reloadPage(){window.location.reload()}}};var g=o(11639),v=o(44458),b=o(63190),_=o(13902),y=o(11821),S=o(68879),w=o(62146),P=o(69984),O=o.n(P);const C=(0,g.Z)(f,[["render",m]]),E=C;O()(f,"components",{QCard:v.Z,QCardSection:b.Z,QSpinner:_.Z,QCardActions:y.Z,QBtn:S.Z}),O()(f,"directives",{ClosePopup:w.Z});var I=o(91569);const k=(0,a.aZ)({name:"App",components:{ConnectionOverlay:E},data(){return{}},computed:{showConnectionOverlay(){return!this.connected}},setup(){const e=(0,s.h)(),t=(0,c.B)(),o=(0,d.R)(),n=(0,u.r)(),r=(0,p.tv)();const a=(0,l.iH)(!1),i=(0,l.iH)(!1);return console.log(o.isLoaded),setInterval((function(){const t=2e3;Date.now()-e.lastHeartbeat>t&&(a.value=!1)}),200),{connected:a,lineEstablished:i,router:r,store:e,stateStore:t,uiSettingsStore:o,mediacollectionStore:n,ConnectionOverlay:E,remoteProcedureCall:I.remoteProcedureCall}},methods:{async init(){this.uiSettingsStore.initStore(),this.mediacollectionStore.initStore(),await this.until((e=>1==this.uiSettingsStore.isLoaded)),await this.until((e=>1==this.mediacollectionStore.isLoaded)),this.initSseClient()},until(e){const t=o=>{e()?o():setTimeout((e=>t(o)),400)};return new Promise(t)},initSseClient(){this.sseClient=this.$sse.create("/sse").on("error",(e=>console.error("Failed to parse or lost connection:",e))).on("FrontendNotification",((e,t)=>{console.warn(e,t)})).on("LogRecord",(e=>{this.store.logrecords=[JSON.parse(e),...this.store.logrecords.slice(0,199)]})).on("ProcessStateinfo",(e=>{const t=JSON.parse(e);console.log("ProcessStateinfo",t),Object.assign(this.stateStore,JSON.parse(e))})).on("DbInsert",(e=>{const t=JSON.parse(e);console.log("received new item to add to collection:",t),this.mediacollectionStore.addMediaitem(t["mediaitem"])})).on("DbRemove",(e=>{})).on("InformationRecord",(e=>{Object.assign(this.store.information,JSON.parse(e))})).on("ping",(()=>{this.store.lastHeartbeat=Date.now(),this.connected=!0})).connect().then((e=>{console.log(e),console.log("SSE connected!"),this.lineEstablished=!0})).catch((e=>{console.error("Failed make initial SSE connection!",e)}))}},async created(){console.log("app created, waiting for stores to init first dataset"),this.init(),console.log("data initialization finished")}});var N=o(32074);const T=(0,g.Z)(k,[["render",i]]),R=T;O()(k,"components",{QDialog:N.Z});var L=o(23340),Z=o(81809);const A=(0,L.h)((()=>{const e=(0,Z.WB)();return e})),Q=[{path:"/",component:()=>Promise.all([o.e(736),o.e(805)]).then(o.bind(o,11805)),children:[{path:"",component:()=>Promise.all([o.e(736),o.e(648)]).then(o.bind(o,4648))},{path:"itempresenter",component:()=>Promise.all([o.e(736),o.e(789)]).then(o.bind(o,13789))},{path:"itemapproval",component:()=>Promise.all([o.e(736),o.e(310)]).then(o.bind(o,97310))}]},{path:"/gallery",component:()=>Promise.all([o.e(736),o.e(652)]).then(o.bind(o,41652)),children:[{path:"",component:()=>Promise.all([o.e(736),o.e(547)]).then(o.bind(o,80736))}]},{path:"/admin",meta:{requiresAuth:!0,requiresAdmin:!0},component:()=>Promise.all([o.e(736),o.e(432)]).then(o.bind(o,30432)),children:[{path:"",component:()=>Promise.all([o.e(736),o.e(790)]).then(o.bind(o,73790))},{path:"gallery",component:()=>Promise.all([o.e(736),o.e(547)]).then(o.bind(o,80736))},{path:"files",component:()=>Promise.all([o.e(736),o.e(492)]).then(o.bind(o,29492))},{path:"status",component:()=>Promise.all([o.e(736),o.e(90)]).then(o.bind(o,92090))},{path:"help",component:()=>Promise.all([o.e(736),o.e(528)]).then(o.bind(o,56528))},{path:"playground",component:()=>Promise.all([o.e(736),o.e(651)]).then(o.bind(o,56651))},{path:"config",component:()=>Promise.all([o.e(736),o.e(275)]).then(o.bind(o,28275))}]},{path:"/standalone",component:()=>Promise.all([o.e(736),o.e(223)]).then(o.bind(o,4223)),children:[{path:"gallery",component:()=>Promise.all([o.e(736),o.e(547)]).then(o.bind(o,80736))}]},{path:"/:catchAll(.*)*",component:()=>o.e(99).then(o.bind(o,56099))}],j=Q,x=(0,L.BC)((function(){const e=p.r5,t=(0,p.p7)({scrollBehavior:(e,t,o)=>o?{savedPosition:o}:{left:0,top:0},routes:j,history:e("")});return t}));async function D(e,t){const o=e(R);o.use(r.Z,t);const n="function"===typeof A?await A({}):A;o.use(n);const a=(0,l.Xl)("function"===typeof x?await x({store:n}):x);return n.use((({store:e})=>{e.router=a})),{app:o,store:n,router:a}}var W=o(66611),q=o(28423),B=o(23175),F=o(42913),H=o(46858),M=o(6827);const U={config:{notify:{}},components:{QInput:W.Z,QSlider:q.Z,QToggle:B.Z,QSelect:F.Z,QTooltip:H.Z},plugins:{Notify:M.Z}},J="";async function z({app:e,router:t,store:o},n){let r=!1;const l=e=>{try{return t.resolve(e).href}catch(o){}return Object(e)===e?null:e},a=e=>{if(r=!0,"string"===typeof e&&/^https?:\/\//.test(e))return void(window.location.href=e);const t=l(e);null!==t&&(window.location.href=t,window.location.reload())},i=window.location.href.replace(window.location.origin,"");for(let c=0;!1===r&&c<n.length;c++)try{await n[c]({app:e,router:t,store:o,ssrContext:null,redirect:a,urlPath:i,publicPath:J})}catch(s){return s&&s.url?void a(s.url):void console.error("[Quasar] boot error:",s)}!0!==r&&(e.use(t),e.mount("#q-app"))}D(n.ri,U).then((e=>{const[t,n]=void 0!==Promise.allSettled?["allSettled",e=>e.map((e=>{if("rejected"!==e.status)return e.value.default;console.error("[Quasar] boot error:",e.reason)}))]:["all",e=>e.map((e=>e.default))];return Promise[t]([Promise.resolve().then(o.bind(o,36372)),Promise.resolve().then(o.bind(o,91569)),Promise.resolve().then(o.bind(o,65955))]).then((t=>{const o=n(t).filter((e=>"function"===typeof e));z(e,o)}))}))},91569:(e,t,o)=>{o.r(t),o.d(t,{api:()=>l,default:()=>i,remoteProcedureCall:()=>a});var n=o(23340),r=o(37524);const l=r.Z.create({baseURL:"/"});function a(e){l.get(e).then((e=>{console.log(e)})).catch((e=>{console.log("error remoteprocedurecall"),console.log(e)}))}const i=(0,n.xr)((({app:e})=>{e.config.globalProperties.$axios=r.Z,e.config.globalProperties.$api=l}))},36372:(e,t,o)=>{o.r(t),o.d(t,{default:()=>l});var n=o(23340),r=o(32395);const l=(0,n.xr)((async({app:e})=>{e.component("BlitzForm",r.lU),e.component("BlitzListForm",r.$C)}))},65955:(e,t,o)=>{o.r(t),o.d(t,{default:()=>l});var n=o(23340),r=o(32681);const l=(0,n.xr)((({app:e})=>{e.use(r.ZP)}))},67575:(e,t,o)=>{o.d(t,{h:()=>l});var n=o(81809),r=(o(91569),o(60499));o(6827);const l=(0,n.Q_)("main-store",(()=>{const e=(0,r.iH)([]),t=(0,r.iH)({cpu1_5_15:[null,null,null],active_threads:null,memory:{total:null,available:null,percent:null,used:null,free:null},cma:{CmaTotal:null,CmaFree:null},disk:{total:null,used:null,free:null,percent:null},backends:{primary:{},secondary:{}},version:null,platform_system:null,platform_release:null,platform_machine:null,platform_python_version:null,platform_node:null,platform_cpu_count:null,data_directory:null,python_executable:null}),o=(0,r.iH)(null);return{information:t,lastHeartbeat:o,logrecords:e}}))},33630:(e,t,o)=>{o.d(t,{r:()=>a});o(86890);var n=o(81809),r=o(91569);const l={INIT:0,DONE:1,WIP:2,ERROR:3},a=(0,n.Q_)("mediacollection-store",{state:()=>({collection:[],mostRecentItemId:null,storeState:l.INIT}),actions:{initStore(e=!1){console.log("loading store"),this.isLoaded&&0==e?console.log("items loaded once already, skipping"):(this.storeState=l.WIP,r.api.get("/mediacollection/getitems").then((e=>{console.log(e),this.collection=e.data,this.storeState=l.DONE})).catch((e=>{console.log(e),this.storeState=l.ERROR})))},getIndexOfItemId(e){return this.collection.findIndex((t=>t.id===e))},addMediaitem(e){this.collection.unshift(e)}},getters:{isLoaded(){return this.storeState===l.DONE},isLoading(){return this.storeState===l.WIP},collection_number_of_items(){return this.collection.length}}})},15639:(e,t,o)=>{o.d(t,{B:()=>r});var n=o(81809);const r=(0,n.Q_)("state-store",{state:()=>({state:null,typ:null,total_captures_to_take:null,remaining_captures_to_take:null,number_captures_taken:null,duration:null,confirmed_captures_collection:[],last_captured_mediaitem:null,ask_user_for_approval:null}),actions:{},getters:{}})},96694:(e,t,o)=>{o.d(t,{R:()=>a});var n=o(81809),r=o(91569);const l={INIT:0,DONE:1,WIP:2,ERROR:3},a=(0,n.Q_)("ui-settings-store",{state:()=>({uiSettings:{show_takepic_on_frontpage:null,show_collage_on_frontpage:null,show_gallery_on_frontpage:null,show_admin_on_frontpage:null,livestream_mirror_effect:null,FRONTPAGE_TEXT:null,TAKEPIC_MSG_TIME:null,AUTOCLOSE_NEW_ITEM_ARRIVED:null,GALLERY_EMPTY_MSG:null,gallery_show_qrcode:null,gallery_show_filter:null,gallery_filter_userselectable:null,gallery_show_download:null,gallery_show_delete:null,gallery_show_print:null},storeState:l.INIT}),actions:{initStore(e=!1){console.log("loadUiSettings"),this.isLoaded&&0==e?console.log("settings loaded once already, skipping"):(this.storeState=l.WIP,r.api.get("/config/ui").then((e=>{console.log("loadUiSettings finished successfully"),console.log(e.data),this.uiSettings=e.data,this.storeState=l.DONE})).catch((e=>{console.log("loadUiSettings failed"),this.storeState=l.ERROR})))}},getters:{isLoaded(){return this.storeState===l.DONE},isLoading(){return this.storeState===l.WIP}}})}},t={};function o(n){var r=t[n];if(void 0!==r)return r.exports;var l=t[n]={exports:{}};return e[n].call(l.exports,l,l.exports,o),l.exports}o.m=e,(()=>{var e=[];o.O=(t,n,r,l)=>{if(!n){var a=1/0;for(d=0;d<e.length;d++){for(var[n,r,l]=e[d],i=!0,s=0;s<n.length;s++)(!1&l||a>=l)&&Object.keys(o.O).every((e=>o.O[e](n[s])))?n.splice(s--,1):(i=!1,l<a&&(a=l));if(i){e.splice(d--,1);var c=r();void 0!==c&&(t=c)}}return t}l=l||0;for(var d=e.length;d>0&&e[d-1][2]>l;d--)e[d]=e[d-1];e[d]=[n,r,l]}})(),(()=>{o.n=e=>{var t=e&&e.__esModule?()=>e["default"]:()=>e;return o.d(t,{a:t}),t}})(),(()=>{o.d=(e,t)=>{for(var n in t)o.o(t,n)&&!o.o(e,n)&&Object.defineProperty(e,n,{enumerable:!0,get:t[n]})}})(),(()=>{o.f={},o.e=e=>Promise.all(Object.keys(o.f).reduce(((t,n)=>(o.f[n](e,t),t)),[]))})(),(()=>{o.u=e=>"js/"+e+"."+{90:"80f4c3bc",99:"93c6ac89",223:"3e44c3b5",275:"6687c9d3",310:"56643b9c",432:"61155a5d",492:"7da9481f",528:"2e5be924",547:"776853fd",648:"99f65e52",651:"880922bc",652:"883b9289",789:"faad2901",790:"6452d0b7",805:"e09b99aa"}[e]+".js"})(),(()=>{o.miniCssF=e=>"css/"+e+"."+{275:"0be6c807",310:"710767d8",547:"f510cc74",789:"710767d8"}[e]+".css"})(),(()=>{o.g=function(){if("object"===typeof globalThis)return globalThis;try{return this||new Function("return this")()}catch(e){if("object"===typeof window)return window}}()})(),(()=>{o.o=(e,t)=>Object.prototype.hasOwnProperty.call(e,t)})(),(()=>{var e={},t="photobooth-app-frontend:";o.l=(n,r,l,a)=>{if(e[n])e[n].push(r);else{var i,s;if(void 0!==l)for(var c=document.getElementsByTagName("script"),d=0;d<c.length;d++){var u=c[d];if(u.getAttribute("src")==n||u.getAttribute("data-webpack")==t+l){i=u;break}}i||(s=!0,i=document.createElement("script"),i.charset="utf-8",i.timeout=120,o.nc&&i.setAttribute("nonce",o.nc),i.setAttribute("data-webpack",t+l),i.src=n),e[n]=[r];var p=(t,o)=>{i.onerror=i.onload=null,clearTimeout(h);var r=e[n];if(delete e[n],i.parentNode&&i.parentNode.removeChild(i),r&&r.forEach((e=>e(o))),t)return t(o)},h=setTimeout(p.bind(null,void 0,{type:"timeout",target:i}),12e4);i.onerror=p.bind(null,i.onerror),i.onload=p.bind(null,i.onload),s&&document.head.appendChild(i)}}})(),(()=>{o.r=e=>{"undefined"!==typeof Symbol&&Symbol.toStringTag&&Object.defineProperty(e,Symbol.toStringTag,{value:"Module"}),Object.defineProperty(e,"__esModule",{value:!0})}})(),(()=>{o.p=""})(),(()=>{if("undefined"!==typeof document){var e=(e,t,o,n,r)=>{var l=document.createElement("link");l.rel="stylesheet",l.type="text/css";var a=o=>{if(l.onerror=l.onload=null,"load"===o.type)n();else{var a=o&&("load"===o.type?"missing":o.type),i=o&&o.target&&o.target.href||t,s=new Error("Loading CSS chunk "+e+" failed.\n("+i+")");s.code="CSS_CHUNK_LOAD_FAILED",s.type=a,s.request=i,l.parentNode.removeChild(l),r(s)}};return l.onerror=l.onload=a,l.href=t,o?o.parentNode.insertBefore(l,o.nextSibling):document.head.appendChild(l),l},t=(e,t)=>{for(var o=document.getElementsByTagName("link"),n=0;n<o.length;n++){var r=o[n],l=r.getAttribute("data-href")||r.getAttribute("href");if("stylesheet"===r.rel&&(l===e||l===t))return r}var a=document.getElementsByTagName("style");for(n=0;n<a.length;n++){r=a[n],l=r.getAttribute("data-href");if(l===e||l===t)return r}},n=n=>new Promise(((r,l)=>{var a=o.miniCssF(n),i=o.p+a;if(t(a,i))return r();e(n,i,null,r,l)})),r={143:0};o.f.miniCss=(e,t)=>{var o={275:1,310:1,547:1,789:1};r[e]?t.push(r[e]):0!==r[e]&&o[e]&&t.push(r[e]=n(e).then((()=>{r[e]=0}),(t=>{throw delete r[e],t})))}}})(),(()=>{var e={143:0};o.f.j=(t,n)=>{var r=o.o(e,t)?e[t]:void 0;if(0!==r)if(r)n.push(r[2]);else{var l=new Promise(((o,n)=>r=e[t]=[o,n]));n.push(r[2]=l);var a=o.p+o.u(t),i=new Error,s=n=>{if(o.o(e,t)&&(r=e[t],0!==r&&(e[t]=void 0),r)){var l=n&&("load"===n.type?"missing":n.type),a=n&&n.target&&n.target.src;i.message="Loading chunk "+t+" failed.\n("+l+": "+a+")",i.name="ChunkLoadError",i.type=l,i.request=a,r[1](i)}};o.l(a,s,"chunk-"+t,t)}},o.O.j=t=>0===e[t];var t=(t,n)=>{var r,l,[a,i,s]=n,c=0;if(a.some((t=>0!==e[t]))){for(r in i)o.o(i,r)&&(o.m[r]=i[r]);if(s)var d=s(o)}for(t&&t(n);c<a.length;c++)l=a[c],o.o(e,l)&&e[l]&&e[l][0](),e[l]=0;return o.O(d)},n=globalThis["webpackChunkphotobooth_app_frontend"]=globalThis["webpackChunkphotobooth_app_frontend"]||[];n.forEach(t.bind(null,0)),n.push=t.bind(null,n.push.bind(n))})();var n=o.O(void 0,[736],(()=>o(73478)));n=o.O(n)})();