const $=s=>document.querySelector(s);let filter="pending",posts=[];
const cfg=()=>({t:localStorage.getItem("gh_token"),r:localStorage.getItem("gh_repo")});
const api=async(path,opt={})=>{const {t,r}=cfg();const res=await fetch(`https://api.github.com/repos/${r}/${path}`,{...opt,headers:{Authorization:`Bearer ${t}`,Accept:"application/vnd.github+json",...(opt.headers||{})}});if(!res.ok)throw new Error(res.status);return res.json()};
const dec=b=>new TextDecoder().decode(Uint8Array.from(atob(b),c=>c.charCodeAt(0)));
const enc=s=>btoa(String.fromCharCode(...new TextEncoder().encode(s)));
async function load(){
  $("#status").textContent="Loading…";
  try{const files=await api("contents/data/posts?ref=main");
    posts=await Promise.all(files.filter(f=>f.name.endsWith(".json")).map(async f=>{const j=await api(`contents/data/posts/${f.name}?ref=main`);return {...JSON.parse(dec(j.content.replace(/\n/g,""))),_sha:j.sha,_file:f.name}}));
  }catch(e){posts=[];if(String(e).includes("404")){$("#status").textContent="No posts yet";render();return}$("#status").textContent="Could not load ("+e.message+"). Check token.";$("#login").hidden=false;return}
  posts.sort((a,b)=>a.scheduled_for.localeCompare(b.scheduled_for));
  const n=posts.filter(p=>p.status=="pending").length;$("#status").textContent=n+" waiting for review";render();
}
async function save(p,changes,msg){
  const {_sha,_file,...clean}=p;Object.assign(clean,changes);
  const body=JSON.stringify(clean,Object.keys(clean).sort(),2)+"\n";
  const res=await api(`contents/data/posts/${_file}`,{method:"PUT",body:JSON.stringify({message:msg+" "+p.id,content:enc(body),sha:_sha,branch:"main"})});
  Object.assign(p,changes,{_sha:res.content.sha});render();
}
const mediaUrl=(r,rel)=>`https://raw.githubusercontent.com/${r}/media/${rel}`;
function render(){
  const {r}=cfg();const list=$("#list");list.innerHTML="";
  posts.filter(p=>p.status==filter).forEach(p=>{
    const c=document.createElement("div");c.className="card";
    const when=new Date(p.scheduled_for).toLocaleString([], {weekday:"short",month:"short",day:"numeric",hour:"2-digit",minute:"2-digit"});
    const media=(p.media||[]).map(m=>m.endsWith(".mp4")?`<video controls playsinline preload="metadata" poster="${p.cover_path?mediaUrl(r,p.cover_path):""}" src="${mediaUrl(r,m)}"></video>`:`<img loading="lazy" src="${mediaUrl(r,m)}">`).join("");
    c.innerHTML=`<div class="media">${media||"<p style='color:#fff;padding:20px'>No media yet</p>"}</div><div class="body">
    <div class="meta">${p.kind=="reel"?'<span class="pill reel">REEL</span>':`<span class="pill">${p.kind}</span>`}<span class="pill">${when}</span><span class="pill">📍 ${p.location_name||"no location"}${p.location_id?"":" (name only)"}</span></div>
    ${(p.warnings||[]).map(w=>`<div class="warn">⚠ ${w}</div>`).join("")}
    <div class="cap"></div><div class="btns"></div></div>`;
    c.querySelector(".cap").textContent=p.caption;
    const b=c.querySelector(".btns");
    const btn=(t,cls,fn)=>{const x=document.createElement("button");x.textContent=t;x.className=cls;x.onclick=fn;b.append(x)};
    if(p.status=="pending"){
      btn("Approve","ok",()=>save(p,{status:"approved"},"approve"));
      btn("Edit","ed",()=>{const cap=c.querySelector(".cap");const ta=document.createElement("textarea");ta.value=p.caption;cap.replaceWith(ta);b.innerHTML="";btn("Save edit","ok",()=>save(p,{caption:ta.value},"edit caption"));btn("Cancel","ed",render)});
      btn("Reject","no",()=>save(p,{status:"rejected"},"reject"));
    }else if(p.status=="approved"||p.status=="rejected"){btn("Undo","un",()=>save(p,{status:"pending"},"undo"))}
    list.append(c);
  });
  if(!list.children.length)list.innerHTML="<p style='padding:20px'>Nothing here.</p>";
}
document.querySelectorAll("#tabs button").forEach(b=>b.onclick=()=>{filter=b.dataset.f;document.querySelectorAll("#tabs button").forEach(x=>x.classList.toggle("on",x==b));render()});
$("#save").onclick=()=>{localStorage.setItem("gh_token",$("#token").value.trim());localStorage.setItem("gh_repo",$("#repo").value.trim());$("#login").hidden=true;load()};
if(!cfg().t){$("#login").hidden=false}else load();
