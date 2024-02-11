(()=>{"use strict";var e={65550:(e,t,o)=>{var n=o(61957),r=o(71947),l=o(60499),a=o(59835);function i(e,t,o,n,r,l){const i=(0,a.up)("router-view"),s=(0,a.up)("connection-overlay"),_=(0,a.up)("q-dialog");return(0,a.wg)(),(0,a.iD)(a.HY,null,[(0,a.Wm)(i),(0,a.Wm)(_,{modelValue:e.showConnectionOverlay,"onUpdate:modelValue":t[0]||(t[0]=t=>e.showConnectionOverlay=t),persistent:""},{default:(0,a.w5)((()=>[(0,a.Wm)(s)])),_:1},8,["modelValue"])],64)}var s=o(67575),_=o(15639),c=o(96694),E=o(33630),L=o(28339);const d=["innerHTML"];function u(e,t,o,n,r,l){const i=(0,a.up)("q-spinner"),s=(0,a.up)("q-card-section"),_=(0,a.up)("q-btn"),c=(0,a.up)("q-card-actions"),E=(0,a.up)("q-card"),L=(0,a.Q2)("close-popup");return(0,a.wg)(),(0,a.j4)(E,{class:"q-pa-sm"},{default:(0,a.w5)((()=>[(0,a.Wm)(s,{class:"row items-center"},{default:(0,a.w5)((()=>[(0,a.Wm)(i,{color:"negative",size:"2em"}),(0,a._)("span",{class:"q-ml-sm",innerHTML:e.$t("MSG_CONNECTING_TO_BACKEND")},null,8,d)])),_:1}),(0,a.Wm)(c,{align:"right"},{default:(0,a.w5)((()=>[(0,a.wy)((0,a.Wm)(_,{label:e.$t("BTN_LABEL_RELOAD_PAGE"),color:"primary",onClick:l.reloadPage},null,8,["label","onClick"]),[[L]])])),_:1})])),_:1})}const A={setup(){return{}},methods:{reloadPage(){window.location.reload()}}};var T=o(11639),h=o(44458),p=o(63190),m=o(13902),S=o(11821),O=o(68879),N=o(62146),I=o(69984),f=o.n(I);const B=(0,T.Z)(A,[["render",u]]),g=B;f()(A,"components",{QCard:h.Z,QCardSection:p.Z,QSpinner:m.Z,QCardActions:S.Z,QBtn:O.Z}),f()(A,"directives",{ClosePopup:N.Z});var R=o(91569),C=o(19302);const v=(0,a.aZ)({name:"App",components:{ConnectionOverlay:g},data(){return{}},computed:{showConnectionOverlay(){return!this.connected}},setup(){const e=(0,s.h)(),t=(0,_.B)(),o=(0,c.R)(),n=(0,E.r)(),r=(0,L.tv)();const a=(0,l.iH)(!1),i=(0,l.iH)(!1);(0,C.Z)();return console.log(o.isLoaded),setInterval((function(){const t=2e3;Date.now()-e.lastHeartbeat>t&&(a.value=!1)}),200),{connected:a,lineEstablished:i,router:r,store:e,stateStore:t,uiSettingsStore:o,mediacollectionStore:n,ConnectionOverlay:g,remoteProcedureCall:R.remoteProcedureCall}},methods:{async init(){this.uiSettingsStore.initStore(),this.mediacollectionStore.initStore(),await this.until((e=>1==this.uiSettingsStore.isLoaded)),await this.until((e=>1==this.mediacollectionStore.isLoaded)),this.initSseClient()},until(e){const t=o=>{e()?o():setTimeout((e=>t(o)),400)};return new Promise(t)},initSseClient(){this.sseClient=this.$sse.create("/sse").on("error",(e=>console.error("Failed to parse or lost connection:",e))).on("FrontendNotification",(e=>{const t=JSON.parse(e);console.warn(t),this.$q.notify({caption:t["caption"]||"Notification",message:t["message"],color:t["color"]||"info",icon:t["icon"]||"info",spinner:t["spinner"]||!1,actions:[{icon:"close",color:"white",round:!0,handler:()=>{}}]})})).on("LogRecord",(e=>{this.store.logrecords=[JSON.parse(e),...this.store.logrecords.slice(0,199)]})).on("ProcessStateinfo",(e=>{const t=JSON.parse(e);console.log("ProcessStateinfo",t),0===Object.keys(t).length&&t.constructor===Object?this.stateStore.$reset():Object.assign(this.stateStore,t)})).on("DbInsert",(e=>{const t=JSON.parse(e);console.log("received new item to add to collection:",t),this.mediacollectionStore.addMediaitem(t["mediaitem"])})).on("DbRemove",(e=>{const t=JSON.parse(e);console.log("received request to remove item from collection:",t),this.mediacollectionStore.removeMediaitem(t)})).on("InformationRecord",(e=>{Object.assign(this.store.information,JSON.parse(e))})).on("ping",(()=>{this.store.lastHeartbeat=Date.now(),this.connected=!0})).connect().then((e=>{console.log(e),console.log("SSE connected!"),this.lineEstablished=!0})).catch((e=>{console.error("Failed make initial SSE connection!",e)}))}},async created(){console.log("app created, waiting for stores to init first dataset"),this.init(),console.log("data initialization finished")}});var P=o(32074);const b=(0,T.Z)(v,[["render",i]]),G=b;f()(v,"components",{QDialog:P.Z});var M=o(23340),D=o(3746);const y=(0,M.h)((()=>{const e=(0,D.WB)();return e})),w=[{path:"/",component:()=>Promise.all([o.e(736),o.e(363)]).then(o.bind(o,37363)),children:[{path:"",component:()=>Promise.all([o.e(736),o.e(475)]).then(o.bind(o,19475))},{path:"itempresenter",component:()=>Promise.all([o.e(736),o.e(64),o.e(331)]).then(o.bind(o,13789))},{path:"itemapproval",component:()=>Promise.all([o.e(736),o.e(64),o.e(895)]).then(o.bind(o,63880))}]},{path:"/gallery",component:()=>Promise.all([o.e(736),o.e(784)]).then(o.bind(o,8784)),children:[{path:"",component:()=>Promise.all([o.e(736),o.e(64),o.e(809)]).then(o.bind(o,77917))}]},{path:"/admin",meta:{requiresAuth:!0,requiresAdmin:!0},component:()=>Promise.all([o.e(736),o.e(482)]).then(o.bind(o,38482)),children:[{path:"",component:()=>Promise.all([o.e(736),o.e(870)]).then(o.bind(o,56870))},{path:"gallery",component:()=>Promise.all([o.e(736),o.e(64),o.e(809)]).then(o.bind(o,77917))},{path:"files",component:()=>Promise.all([o.e(736),o.e(645)]).then(o.bind(o,32645))},{path:"status",component:()=>Promise.all([o.e(736),o.e(617)]).then(o.bind(o,82617))},{path:"help",component:()=>Promise.all([o.e(736),o.e(433)]).then(o.bind(o,86433))},{path:"playground",component:()=>Promise.all([o.e(736),o.e(877)]).then(o.bind(o,18877))},{name:"config",path:"config/:section?",component:()=>Promise.all([o.e(736),o.e(796)]).then(o.bind(o,68796))}]},{path:"/standalone",component:()=>Promise.all([o.e(736),o.e(223)]).then(o.bind(o,4223)),children:[{path:"gallery",component:()=>Promise.all([o.e(736),o.e(64),o.e(809)]).then(o.bind(o,77917))}]},{path:"/:catchAll(.*)*",component:()=>o.e(162).then(o.bind(o,45162))}],F=w,k=(0,M.BC)((function(){const e=L.r5,t=(0,L.p7)({scrollBehavior:(e,t,o)=>o?{savedPosition:o}:{left:0,top:0},routes:F,history:e("")});return t}));async function V(e,t){const o=e(G);o.use(r.Z,t);const n="function"===typeof y?await y({}):y;o.use(n);const a=(0,l.Xl)("function"===typeof k?await k({store:n}):k);return n.use((({store:e})=>{e.router=a})),{app:o,store:n,router:a}}var U=o(66611),W=o(28423),H=o(23175),Z=o(42913),Y=o(46858),X=o(6827);const Q={config:{notify:{}},components:{QInput:U.Z,QSlider:W.Z,QToggle:H.Z,QSelect:Z.Z,QTooltip:Y.Z},plugins:{Notify:X.Z}},j="";async function q({app:e,router:t,store:o},n){let r=!1;const l=e=>{try{return t.resolve(e).href}catch(o){}return Object(e)===e?null:e},a=e=>{if(r=!0,"string"===typeof e&&/^https?:\/\//.test(e))return void(window.location.href=e);const t=l(e);null!==t&&(window.location.href=t,window.location.reload())},i=window.location.href.replace(window.location.origin,"");for(let _=0;!1===r&&_<n.length;_++)try{await n[_]({app:e,router:t,store:o,ssrContext:null,redirect:a,urlPath:i,publicPath:j})}catch(s){return s&&s.url?void a(s.url):void console.error("[Quasar] boot error:",s)}!0!==r&&(e.use(t),e.mount("#q-app"))}V(n.ri,Q).then((e=>{const[t,n]=void 0!==Promise.allSettled?["allSettled",e=>e.map((e=>{if("rejected"!==e.status)return e.value.default;console.error("[Quasar] boot error:",e.reason)}))]:["all",e=>e.map((e=>e.default))];return Promise[t]([Promise.resolve().then(o.bind(o,49580)),Promise.resolve().then(o.bind(o,91569)),Promise.resolve().then(o.bind(o,65955)),Promise.resolve().then(o.bind(o,25176))]).then((t=>{const o=n(t).filter((e=>"function"===typeof e));q(e,o)}))}))},91569:(e,t,o)=>{o.r(t),o.d(t,{api:()=>l,default:()=>i,remoteProcedureCall:()=>a});var n=o(23340),r=o(76081);const l=r.Z.create({baseURL:"/"});function a(e){l.get(e).then((e=>{console.log(e)})).catch((e=>{console.log("error remoteprocedurecall"),console.log(e)}))}const i=(0,n.xr)((({app:e})=>{e.config.globalProperties.$axios=r.Z,e.config.globalProperties.$api=l}))},49580:(e,t,o)=>{o.r(t),o.d(t,{default:()=>A});var n=o(23340),r=o(32395),l=o(59835);const a={__name:"ColorPicker",props:["model-value"],emits:["update:model-value"],setup(e,{emit:t}){const o=t;function n(e){o("update:model-value",e)}return(e,t)=>{const o=(0,l.up)("q-color"),r=(0,l.up)("q-popup-proxy"),a=(0,l.up)("q-icon"),i=(0,l.up)("q-input");return(0,l.wg)(),(0,l.j4)(i,{"model-value":e.modelValue,"onUpdate:modelValue":n,rules:["anyColor"]},{append:(0,l.w5)((()=>[(0,l.Wm)(a,{name:"colorize",class:"cursor-pointer"},{default:(0,l.w5)((()=>[(0,l.Wm)(r,{cover:"","transition-show":"scale","transition-hide":"scale"},{default:(0,l.w5)((()=>[(0,l.Wm)(o,{"model-value":e.modelValue,"onUpdate:modelValue":n},null,8,["model-value"])])),_:1})])),_:1})])),_:1},8,["model-value"])}}};var i=o(66611),s=o(22857),_=o(52765),c=o(40056),E=o(69984),L=o.n(E);const d=a,u=d;L()(a,"components",{QInput:i.Z,QIcon:s.Z,QPopupProxy:_.Z,QColor:c.Z});const A=(0,n.xr)((async({app:e})=>{e.component("BlitzForm",r.lU),e.component("BlitzListForm",r.$C),e.component("ColorPicker",u)}))},25176:(e,t,o)=>{o.r(t),o.d(t,{default:()=>i});var n=o(76647);const r={BTN_LABEL_BACK:"Back",BTN_LABEL_CANCEL:"Cancel",BTN_LABEL_DELETE_IMAGE:"Delete",BTN_LABEL_DELETE_ALL_MEDIA_FILES:"Delete all media files",BTN_LABEL_FILES_CREATE_NEW_FOLDER:"Create folder",BTN_LABEL_FILES_DELETE_SELECTED:"Delete selected",BTN_LABEL_FILES_DOWNLOAD_ZIP:"Download ZIP",BTN_LABEL_FILES_NEW_FOLDER:"New folder",BTN_LABEL_FILES_UPLOAD_FILE:"Upload file",BTN_LABEL_GALLERY_DELETE:"Delete",BTN_LABEL_GALLERY_DOWNLOAD:"Download",BTN_LABEL_GALLERY_FILTER:"Filter",BTN_LABEL_GALLERY_PRINT:"Print",BTN_LABEL_INSTALL_SERVICE:"Install service",BTN_LABEL_MAINPAGE_TO_ADMIN:"Admin",BTN_LABEL_MAINPAGE_TO_GALLERY:"Gallery",BTN_LABEL_MAINPAGE_TAKE_ANIMATION:"Capture an animation",BTN_LABEL_MAINPAGE_TAKE_COLLAGE:"Create a collage",BTN_LABEL_MAINPAGE_TAKE_PHOTO:"Take a picture",BTN_LABEL_MAINPAGE_TAKE_VIDEO:"Capture a video",BTN_LABEL_PERSIST_CONFIG:"Save",BTN_LABEL_REBOOT:"Reboot",BTN_LABEL_REBOOT_HOST:"Reboot host",BTN_LABEL_RELOAD_PAGE:"Reload",BTN_LABEL_RELOAD_SERVICE:"Reload service",BTN_LABEL_RESET_CONFIG:"Reset",BTN_LABEL_RESTART_SERVICE:"Restart service",BTN_LABEL_RESTORE_CONFIG:"Restore",BTN_LABEL_SHUTDOWN:"Shutdown",BTN_LABEL_SHUTDOWN_HOST:"Shutdown host",BTN_LABEL_UNINSTALL_SERVICE:"Uninstall service",MSG_APP_READY:"...",MSG_APPROVE_COLLAGE_ITEM_XXX_COUNT_TOTAL:"Got",MSG_APPROVE_COLLAGE_ITEM_COUNT_XXX_TOTAL:"of",MSG_APPROVE_COLLAGE_ITEM_COUNT_TOTAL_XXX:"captures total",MSG_APPROVE_COLLAGE_ITEM_APPROVE:"Awesome, next!",MSG_APPROVE_COLLAGE_ITEM_CANCEL_COLLAGE:"Abort",MSG_APPROVE_COLLAGE_ITEM_RETRY:"Try again!",MSG_CONFIG_PERSIST_OK:"Config persisted and reloaded from server. If changed hardware settings, pls reload/restart services!",MSG_CONFIRM_DELETE_ALL_MEDIA_FILES:"Are you sure to delete all media items from gallery?",MSG_CONFIRM_DELETE_IMAGE:"Are you sure to delete the image?",MSG_CONFIRM_INSTALL_SERVICE:"You sure to install the service?",MSG_CONFIRM_SHUTDOWN:"You sure to shutdown the system?",MSG_CONFIRM_REBOOT:"You sure to reboot the system?",MSG_CONFIRM_RESTART_SERVICE:"You sure to restart the service?",MSG_CONFIRM_UNINSTALL_SERVICE:"You sure to uninstall the service?",MSG_CONNECTING_TO_BACKEND:"Connecting to server. Please wait for autoconnect or try reload.",MSG_ERROR_NOT_FOUND:"Oops. Nothing here...",TAB_LABEL_DASHBOARD:"Dashboard",TAB_LABEL_GALLERY:"Gallery",TAB_LABEL_CONFIG:"Config",TAB_LABEL_FILES:"Files",TAB_LABEL_STATUS:"Status",TAB_LABEL_HELP:"Help",TEXT_PLACEHOLDER_SEARCH:"Search",TITLE_ADMIN_CENTER:"Admin center",TITLE_FILES_NEW_FOLDER_DIALOG:"New folder name",TITLE_FILES_UPLOAD_FILES_DIALOG:"Upload files to current folder",TITLE_FILES_WORKING_DIR:"Working directory",TITLE_ITEM_APPROVAL:"Nice?",TITLE_MAINTAIN_GALLERY:"Maintain gallery",TITLE_SERVER_CONTROL:"Server control",TITLE_LOCAL_UI_SETTINGS:"Local UI Settings"},l={BTN_LABEL_BACK:"Zurück",BTN_LABEL_CANCEL:"Abbrechen",BTN_LABEL_DELETE_IMAGE:"Löschen",BTN_LABEL_DELETE_ALL_MEDIA_FILES:"Alle Medien-Dateien löschen",BTN_LABEL_FILES_CREATE_NEW_FOLDER:"Ordner erstellen",BTN_LABEL_FILES_DELETE_SELECTED:"Ausgewählte löschen",BTN_LABEL_FILES_DOWNLOAD_ZIP:"ZIP herunterladen",BTN_LABEL_FILES_NEW_FOLDER:"Neuer Ordner",BTN_LABEL_FILES_UPLOAD_FILE:"Datei hochladen",BTN_LABEL_GALLERY_DELETE:"Löschen",BTN_LABEL_GALLERY_DOWNLOAD:"Herunterladen",BTN_LABEL_GALLERY_FILTER:"Filter",BTN_LABEL_GALLERY_PRINT:"Drucken",BTN_LABEL_INSTALL_SERVICE:"Service installieren",BTN_LABEL_MAINPAGE_TO_ADMIN:"Admin",BTN_LABEL_MAINPAGE_TO_GALLERY:"Gallerie",BTN_LABEL_MAINPAGE_TAKE_ANIMATION:"Animation",BTN_LABEL_MAINPAGE_TAKE_COLLAGE:"Collage",BTN_LABEL_MAINPAGE_TAKE_PHOTO:"Foto",BTN_LABEL_MAINPAGE_TAKE_VIDEO:"Video",BTN_LABEL_PERSIST_CONFIG:"Speichern",BTN_LABEL_REBOOT:"Neu starten",BTN_LABEL_REBOOT_HOST:"Host neu starten",BTN_LABEL_RELOAD_PAGE:"Neu laden",BTN_LABEL_RELOAD_SERVICE:"Service neu laden",BTN_LABEL_RESET_CONFIG:"Zurücksetzen",BTN_LABEL_RESTART_SERVICE:"Service neu starten",BTN_LABEL_RESTORE_CONFIG:"Wiederherstellen",BTN_LABEL_SHUTDOWN:"Herunterfahren",BTN_LABEL_SHUTDOWN_HOST:"Host herunterfahren",BTN_LABEL_UNINSTALL_SERVICE:"Service deinstallieren",MSG_APP_READY:"...",MSG_APPROVE_COLLAGE_ITEM_XXX_COUNT_TOTAL:"",MSG_APPROVE_COLLAGE_ITEM_COUNT_XXX_TOTAL:"von",MSG_APPROVE_COLLAGE_ITEM_COUNT_TOTAL_XXX:"Fotos aufgenommen",MSG_APPROVE_COLLAGE_ITEM_APPROVE:"Sieht gut aus, weiter!",MSG_APPROVE_COLLAGE_ITEM_CANCEL_COLLAGE:"Abbrechen",MSG_APPROVE_COLLAGE_ITEM_RETRY:"Nochmal versuchen!",MSG_CONFIRM_DELETE_ALL_MEDIA_FILES:"Wirklich alle Medien-Dateien aus der Gallerie löschen?",MSG_CONFIRM_DELETE_IMAGE:"Bild wirklich löschen?",MSG_CONFIRM_INSTALL_SERVICE:"Service wirklich installieren?",MSG_CONFIRM_SHUTDOWN:"System wirklich herunterfahren?",MSG_CONFIRM_REBOOT:"System wirklich neu starten?",MSG_CONFIRM_RESTART_SERVICE:"Service wirklich neu starten?",MSG_CONFIRM_UNINSTALL_SERVICE:"Service wirklich deinstallieren?",MSG_CONNECTING_TO_BACKEND:"Verbindung zum Server wird hergestellt. Bitte auf automatische Verbindung warten oder neu laden.",MSG_ERROR_NOT_FOUND:"Huch, hier gibt es nichts zu sehen...",TAB_LABEL_DASHBOARD:"Übersicht",TAB_LABEL_GALLERY:"Gallerie",TAB_LABEL_CONFIG:"Einstellungen",TAB_LABEL_FILES:"Dateien",TAB_LABEL_STATUS:"Status",TAB_LABEL_HELP:"Hilfe",TEXT_PLACEHOLDER_SEARCH:"Suchen",TITLE_ADMIN_CENTER:"Administration",TITLE_FILES_NEW_FOLDER_DIALOG:"Name des neuen Ordners",TITLE_FILES_UPLOAD_FILES_DIALOG:"Dateien in das aktuelle Verzeichnis hochladen",TITLE_FILES_WORKING_DIR:"Arbeitsverzeichnis",TITLE_ITEM_APPROVAL:"Zufrieden?",TITLE_MAINTAIN_GALLERY:"Wartung der Gallerie",TITLE_SERVER_CONTROL:"Server Steuerung",TITLE_LOCAL_UI_SETTINGS:"Lokale Einstellungen der Oberfläche"},a={"en-US":r,"de-DE":l},i=({app:e})=>{const t=localStorage.getItem("locale"),o=t||"en-US";t?console.log("Loaded last locale: ",t):console.log("No locale found, using default en-US");const r=(0,n.o)({locale:o,legacy:!1,messages:a});e.use(r)}},65955:(e,t,o)=>{o.r(t),o.d(t,{default:()=>l});var n=o(23340),r=o(32681);const l=(0,n.xr)((({app:e})=>{e.use(r.ZP)}))},67575:(e,t,o)=>{o.d(t,{h:()=>l});var n=o(3746),r=(o(91569),o(60499));o(6827);const l=(0,n.Q_)("main-store",(()=>{const e=(0,r.iH)([]),t=(0,r.iH)({cpu1_5_15:[null,null,null],active_threads:null,memory:{total:null,available:null,percent:null,used:null,free:null},cma:{CmaTotal:null,CmaFree:null},disk:{total:null,used:null,free:null,percent:null},backends:{primary:{},secondary:{}},version:null,platform_system:null,platform_release:null,platform_machine:null,platform_python_version:null,platform_node:null,platform_cpu_count:null,data_directory:null,python_executable:null}),o=(0,r.iH)(null);return{information:t,lastHeartbeat:o,logrecords:e}}))},33630:(e,t,o)=>{o.d(t,{r:()=>a});var n=o(3746),r=o(91569);const l={INIT:0,DONE:1,WIP:2,ERROR:3},a=(0,n.Q_)("mediacollection-store",{state:()=>({collection:[],mostRecentItemId:null,storeState:l.INIT}),actions:{initStore(e=!1){console.log("loading store"),this.isLoaded&&0==e?console.log("items loaded once already, skipping"):(this.storeState=l.WIP,r.api.get("/mediacollection/getitems").then((e=>{console.log(e),this.collection=e.data,this.storeState=l.DONE})).catch((e=>{console.log(e),this.storeState=l.ERROR})))},getIndexOfItemId(e){return this.collection.findIndex((t=>t.id===e))},addMediaitem(e){this.collection.unshift(e)},removeMediaitem(e){const t=this.collection.splice(this.getIndexOfItemId(e.id),1);0==t.length?console.log("no item removed from collection, maybe it was deleted by UI earlier already"):console.log(`${t.length} mediaitem deleted`)}},getters:{isLoaded(){return this.storeState===l.DONE},isLoading(){return this.storeState===l.WIP},collection_number_of_items(){return this.collection.length}}})},15639:(e,t,o)=>{o.d(t,{B:()=>r});var n=o(3746);const r=(0,n.Q_)("state-store",{state:()=>({state:null,typ:null,total_captures_to_take:null,remaining_captures_to_take:null,number_captures_taken:null,duration:null,confirmed_captures_collection:[],last_captured_mediaitem:null,ask_user_for_approval:null}),actions:{},getters:{}})},96694:(e,t,o)=>{o.d(t,{R:()=>i});var n=o(3746),r=o(91569),l=o(57674);const a={INIT:0,DONE:1,WIP:2,ERROR:3},i=(0,n.Q_)("ui-settings-store",{state:()=>({uiSettings:{PRIMARY_COLOR:"#196cb0",SECONDARY_COLOR:"#b8124f",show_takepic_on_frontpage:null,show_takecollage_on_frontpage:null,show_takeanimation_on_frontpage:null,show_takevideo_on_frontpage:null,show_gallery_on_frontpage:null,show_admin_on_frontpage:null,livestream_mirror_effect:null,FRONTPAGE_TEXT:null,TAKEPIC_TEXT:null,TAKEPIC_MSG_TIME:null,TAKEPIC_MSG_TEXT:null,AUTOCLOSE_NEW_ITEM_ARRIVED:null,GALLERY_EMPTY_MSG:null,gallery_show_qrcode:null,gallery_show_filter:null,gallery_filter_userselectable:null,gallery_show_download:null,gallery_show_delete:null,gallery_show_print:null},storeState:a.INIT}),actions:{initStore(e=!1){console.log("loadUiSettings"),this.isLoaded&&0==e?console.log("settings loaded once already, skipping"):(this.storeState=a.WIP,r.api.get("/config/ui").then((e=>{console.log("loadUiSettings finished successfully"),console.log(e.data),(0,l.Z)("primary",e.data["PRIMARY_COLOR"]),(0,l.Z)("secondary",e.data["SECONDARY_COLOR"]),this.uiSettings=e.data,this.storeState=a.DONE})).catch((e=>{console.log("loadUiSettings failed"),this.storeState=a.ERROR})))}},getters:{isLoaded(){return this.storeState===a.DONE},isLoading(){return this.storeState===a.WIP}}})}},t={};function o(n){var r=t[n];if(void 0!==r)return r.exports;var l=t[n]={exports:{}};return e[n].call(l.exports,l,l.exports,o),l.exports}o.m=e,(()=>{var e=[];o.O=(t,n,r,l)=>{if(!n){var a=1/0;for(c=0;c<e.length;c++){for(var[n,r,l]=e[c],i=!0,s=0;s<n.length;s++)(!1&l||a>=l)&&Object.keys(o.O).every((e=>o.O[e](n[s])))?n.splice(s--,1):(i=!1,l<a&&(a=l));if(i){e.splice(c--,1);var _=r();void 0!==_&&(t=_)}}return t}l=l||0;for(var c=e.length;c>0&&e[c-1][2]>l;c--)e[c]=e[c-1];e[c]=[n,r,l]}})(),(()=>{o.n=e=>{var t=e&&e.__esModule?()=>e["default"]:()=>e;return o.d(t,{a:t}),t}})(),(()=>{o.d=(e,t)=>{for(var n in t)o.o(t,n)&&!o.o(e,n)&&Object.defineProperty(e,n,{enumerable:!0,get:t[n]})}})(),(()=>{o.f={},o.e=e=>Promise.all(Object.keys(o.f).reduce(((t,n)=>(o.f[n](e,t),t)),[]))})(),(()=>{o.u=e=>"js/"+(64===e?"chunk-common":e)+"."+{64:"6142cd31",162:"664415f6",223:"73810866",331:"9c662fff",363:"b93512d5",433:"6b2c748a",475:"41915beb",482:"2c7615af",617:"93d995df",645:"9b8f13ba",784:"4f9ff826",796:"dc06d8f6",809:"b5e9c17d",870:"6bfd067c",877:"fa5005ec",895:"22bae780"}[e]+".js"})(),(()=>{o.miniCssF=e=>"css/"+e+"."+{331:"d08e2765",796:"0d14ffdb",809:"6f7e3f0a",895:"d08e2765"}[e]+".css"})(),(()=>{o.g=function(){if("object"===typeof globalThis)return globalThis;try{return this||new Function("return this")()}catch(e){if("object"===typeof window)return window}}()})(),(()=>{o.o=(e,t)=>Object.prototype.hasOwnProperty.call(e,t)})(),(()=>{var e={},t="photobooth-app-frontend:";o.l=(n,r,l,a)=>{if(e[n])e[n].push(r);else{var i,s;if(void 0!==l)for(var _=document.getElementsByTagName("script"),c=0;c<_.length;c++){var E=_[c];if(E.getAttribute("src")==n||E.getAttribute("data-webpack")==t+l){i=E;break}}i||(s=!0,i=document.createElement("script"),i.charset="utf-8",i.timeout=120,o.nc&&i.setAttribute("nonce",o.nc),i.setAttribute("data-webpack",t+l),i.src=n),e[n]=[r];var L=(t,o)=>{i.onerror=i.onload=null,clearTimeout(d);var r=e[n];if(delete e[n],i.parentNode&&i.parentNode.removeChild(i),r&&r.forEach((e=>e(o))),t)return t(o)},d=setTimeout(L.bind(null,void 0,{type:"timeout",target:i}),12e4);i.onerror=L.bind(null,i.onerror),i.onload=L.bind(null,i.onload),s&&document.head.appendChild(i)}}})(),(()=>{o.r=e=>{"undefined"!==typeof Symbol&&Symbol.toStringTag&&Object.defineProperty(e,Symbol.toStringTag,{value:"Module"}),Object.defineProperty(e,"__esModule",{value:!0})}})(),(()=>{o.p=""})(),(()=>{if("undefined"!==typeof document){var e=(e,t,o,n,r)=>{var l=document.createElement("link");l.rel="stylesheet",l.type="text/css";var a=o=>{if(l.onerror=l.onload=null,"load"===o.type)n();else{var a=o&&("load"===o.type?"missing":o.type),i=o&&o.target&&o.target.href||t,s=new Error("Loading CSS chunk "+e+" failed.\n("+i+")");s.code="CSS_CHUNK_LOAD_FAILED",s.type=a,s.request=i,l.parentNode.removeChild(l),r(s)}};return l.onerror=l.onload=a,l.href=t,o?o.parentNode.insertBefore(l,o.nextSibling):document.head.appendChild(l),l},t=(e,t)=>{for(var o=document.getElementsByTagName("link"),n=0;n<o.length;n++){var r=o[n],l=r.getAttribute("data-href")||r.getAttribute("href");if("stylesheet"===r.rel&&(l===e||l===t))return r}var a=document.getElementsByTagName("style");for(n=0;n<a.length;n++){r=a[n],l=r.getAttribute("data-href");if(l===e||l===t)return r}},n=n=>new Promise(((r,l)=>{var a=o.miniCssF(n),i=o.p+a;if(t(a,i))return r();e(n,i,null,r,l)})),r={143:0};o.f.miniCss=(e,t)=>{var o={331:1,796:1,809:1,895:1};r[e]?t.push(r[e]):0!==r[e]&&o[e]&&t.push(r[e]=n(e).then((()=>{r[e]=0}),(t=>{throw delete r[e],t})))}}})(),(()=>{var e={143:0};o.f.j=(t,n)=>{var r=o.o(e,t)?e[t]:void 0;if(0!==r)if(r)n.push(r[2]);else{var l=new Promise(((o,n)=>r=e[t]=[o,n]));n.push(r[2]=l);var a=o.p+o.u(t),i=new Error,s=n=>{if(o.o(e,t)&&(r=e[t],0!==r&&(e[t]=void 0),r)){var l=n&&("load"===n.type?"missing":n.type),a=n&&n.target&&n.target.src;i.message="Loading chunk "+t+" failed.\n("+l+": "+a+")",i.name="ChunkLoadError",i.type=l,i.request=a,r[1](i)}};o.l(a,s,"chunk-"+t,t)}},o.O.j=t=>0===e[t];var t=(t,n)=>{var r,l,[a,i,s]=n,_=0;if(a.some((t=>0!==e[t]))){for(r in i)o.o(i,r)&&(o.m[r]=i[r]);if(s)var c=s(o)}for(t&&t(n);_<a.length;_++)l=a[_],o.o(e,l)&&e[l]&&e[l][0](),e[l]=0;return o.O(c)},n=globalThis["webpackChunkphotobooth_app_frontend"]=globalThis["webpackChunkphotobooth_app_frontend"]||[];n.forEach(t.bind(null,0)),n.push=t.bind(null,n.push.bind(n))})();var n=o.O(void 0,[736],(()=>o(65550)));n=o.O(n)})();