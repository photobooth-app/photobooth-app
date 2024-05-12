import{G as S,Q as b}from"./GalleryImageDetail-BxTB5xrj.js";import{v as E,J as g,K as C,L as P,d as A,t as u,M as m,_ as h,E as L,N as k,l as O,k as I,F as d,f as M,n as T,p as o,q as a,Q as _,H as f,B as r,D as l}from"./index-kXb7mYGE.js";import{Q as G}from"./QPageSticky-B22pb0Bv.js";import{Q}from"./QPage-CUmIaTGK.js";import"./QHeader-BpzF4RtY.js";import"./QLayout-s_iV4Fst.js";import"./QLinearProgress-BMvxbFCs.js";import"./use-panel-BzhE9cbD.js";import"./selection-B1atnzSX.js";import"./format-CJebrXOQ.js";import"./open-url-M0sZck_j.js";const $=E({name:"QBanner",props:{...g,inlineActions:Boolean,dense:Boolean,rounded:Boolean},setup(e,{slots:t}){const{proxy:{$q:c}}=C(),n=P(e,c),v=A(()=>"q-banner row items-center"+(e.dense===!0?" q-banner--dense":"")+(n.value===!0?" q-banner--dark q-dark":"")+(e.rounded===!0?" rounded-borders":"")),s=A(()=>`q-banner__actions row items-center justify-end col-${e.inlineActions===!0?"auto":"all"}`);return()=>{const i=[u("div",{class:"q-banner__avatar col-auto row items-center self-start"},m(t.avatar)),u("div",{class:"q-banner__content col text-body2"},m(t.default))],p=m(t.action);return p!==void 0&&i.push(u("div",{class:s.value},p)),u("div",{class:v.value+(e.inlineActions===!1&&p!==void 0?" q-banner--top-padding":""),role:"alert"},i)}}}),q={components:{},setup(){const e=L(),t=k(),c=O(),n=I();return{mainStore:e,mediacollectionStore:t,stateStore:n,configurationStore:c,GalleryImageDetail:S,remoteProcedureCall:d}},data(){return{}},computed:{imgToApproveSrc:{get(){return this.stateStore.last_captured_mediaitem&&this.stateStore.last_captured_mediaitem.preview}}},mounted(){},methods:{userConfirm(){d("/api/actions/confirm"),this.$router.push("/")},userReject(){d("/api/actions/reject"),this.$router.push("/")},userAbort(){d("/api/actions/abort"),this.$router.push("/")}}},B={class:"text-h5"},R={class:"text-subtitle2"};function x(e,t,c,n,v,s){return M(),T(Q,{id:"itemapproval-page",class:"fullscreen flex flex-center"},{default:o(()=>[a(b,{src:s.imgToApproveSrc,fit:"contain",style:{height:"95%"}},null,8,["src"]),a(G,{position:"bottom",offset:[0,25]},{default:o(()=>[a($,{rounded:"","inline-actions":""},{action:o(()=>[a(_,{id:"item-approval-button-reject",color:"negative","no-caps":"",class:"",onClick:t[0]||(t[0]=i=>s.userReject())},{default:o(()=>[a(f,{left:"",size:"xl",name:"thumb_down"}),r("div",null,l(e.$t("MSG_APPROVE_COLLAGE_ITEM_RETRY")),1)]),_:1}),a(_,{id:"item-approval-button-abort",flat:"",color:"grey","no-caps":"",class:"",onClick:t[1]||(t[1]=i=>s.userAbort())},{default:o(()=>[a(f,{left:"",size:"xl",name:"cancel"}),r("div",null,l(e.$t("MSG_APPROVE_COLLAGE_ITEM_CANCEL_COLLAGE")),1)]),_:1}),a(_,{id:"item-approval-button-approve",color:"positive","no-caps":"",onClick:t[2]||(t[2]=i=>s.userConfirm())},{default:o(()=>[a(f,{left:"",size:"xl",name:"thumb_up"}),r("div",null,[r("div",null,l(e.$t("MSG_APPROVE_COLLAGE_ITEM_APPROVE")),1)])]),_:1})]),default:o(()=>[r("div",null,[r("div",B,l(e.$t("TITLE_ITEM_APPROVAL")),1),r("div",R,l(e.$t("MSG_APPROVE_COLLAGE_ITEM_NO_OF_TOTAL",{no:n.stateStore.number_captures_taken,total:n.stateStore.total_captures_to_take})),1)])]),_:1})]),_:1})]),_:1})}const Y=h(q,[["render",x],["__file","ItemApprovalPage.vue"]]);export{Y as default};