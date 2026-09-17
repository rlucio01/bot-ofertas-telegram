"""A página HTML do painel de controle (servida por painel.py)."""

PAGINA = r"""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Bot de Ofertas — Painel</title>
<style>
  :root{
    --bg:#0f1216; --card:#171b22; --card2:#1e232c; --bd:#2a303b; --tx:#e7ebf0;
    --mut:#95a0b0; --ac:#ff6a3d; --ac2:#ff8a63; --ok:#25c281; --warn:#e0b341; --err:#e8574a;
  }
  @media (prefers-color-scheme:light){
    :root{ --bg:#f2f4f7; --card:#fff; --card2:#f7f9fb; --bd:#dde2e9; --tx:#1b2230;
           --mut:#5a6472; --ac:#f2542d; --ac2:#e0431c; }
  }
  *{box-sizing:border-box}
  body{margin:0;font-family:'Segoe UI',system-ui,sans-serif;background:var(--bg);color:var(--tx);
       line-height:1.5;font-size:15px}
  .wrap{max-width:820px;margin:0 auto;padding:20px 16px 60px}
  header{display:flex;align-items:center;gap:14px;flex-wrap:wrap;margin:8px 0 22px}
  header h1{font-size:20px;margin:0;font-weight:700}
  header h1 .em{font-size:22px}
  .pill{display:inline-flex;align-items:center;gap:7px;font-size:13px;font-weight:600;
        padding:5px 12px;border-radius:99px;background:var(--card2);border:1px solid var(--bd)}
  .dot{width:9px;height:9px;border-radius:99px;background:var(--mut)}
  .dot.on{background:var(--ok);box-shadow:0 0 0 3px rgba(37,194,129,.2)}
  .grow{flex:1}
  button{font:inherit;cursor:pointer;border:0;border-radius:9px;padding:10px 16px;font-weight:600;
         background:var(--card2);color:var(--tx);border:1px solid var(--bd);transition:.15s}
  button:hover{border-color:var(--ac)}
  button:disabled{opacity:.5;cursor:not-allowed}
  button.pri{background:var(--ac);color:#fff;border-color:var(--ac)}
  button.pri:hover{background:var(--ac2)}
  button.stop{background:var(--err);color:#fff;border-color:var(--err)}
  .card{background:var(--card);border:1px solid var(--bd);border-radius:14px;padding:18px 18px;
        margin-bottom:16px}
  .card h2{font-size:15px;margin:0 0 14px;display:flex;align-items:center;gap:8px}
  .card h2 .n{width:22px;height:22px;border-radius:99px;background:var(--ac);color:#fff;font-size:13px;
              display:grid;place-items:center;font-weight:700}
  .grp{font-size:12px;text-transform:uppercase;letter-spacing:.5px;color:var(--mut);
       margin:16px 0 8px;font-weight:700}
  .grp:first-of-type{margin-top:0}
  .fld{margin-bottom:12px}
  .fld label{display:flex;align-items:center;gap:8px;font-weight:600;font-size:13.5px;margin-bottom:4px}
  .fld .tick{font-size:12px}
  .fld input{width:100%;padding:9px 11px;border-radius:8px;border:1px solid var(--bd);
             background:var(--bg);color:var(--tx);font:inherit}
  .fld input:focus{outline:0;border-color:var(--ac)}
  .fld .help{font-size:12.5px;color:var(--mut);margin-top:3px}
  .row{display:flex;gap:10px;flex-wrap:wrap;align-items:center}
  .log{background:#0a0c10;color:#cdd6e0;font-family:'Cascadia Code',Consolas,monospace;font-size:12.5px;
       border-radius:9px;padding:12px;height:230px;overflow:auto;white-space:pre-wrap;border:1px solid var(--bd)}
  @media (prefers-color-scheme:light){.log{background:#12151b;color:#cdd6e0}}
  .muted{color:var(--mut);font-size:13px}
  .toast{position:fixed;bottom:20px;left:50%;transform:translateX(-50%);background:var(--ok);color:#fff;
         padding:10px 18px;border-radius:10px;font-weight:600;opacity:0;transition:.3s;pointer-events:none}
  .toast.show{opacity:1}
  .toast.err{background:var(--err)}
  .ids{margin-top:10px}
  .idbtn{display:block;width:100%;text-align:left;margin-top:6px}
  .nichos-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(190px,1fr));gap:8px}
  .nicho{display:flex;align-items:center;gap:9px;padding:10px 12px;border:1px solid var(--bd);
         border-radius:10px;background:var(--bg);cursor:pointer;user-select:none;transition:.12s}
  .nicho:hover{border-color:var(--ac)}
  .nicho.on{border-color:var(--ac);background:color-mix(in srgb,var(--ac) 14%,transparent)}
  .nicho .emo{font-size:19px}
  .nicho .nm{font-size:13.5px;font-weight:600}
  .nicho .ck{margin-left:auto;font-size:13px;color:var(--ac);opacity:0}
  .nicho.on .ck{opacity:1}
  .hide{display:none}
  a{color:var(--ac2)}
</style>
</head>
<body>
<div class="wrap">
  <header>
    <h1><span class="em">🔥</span> Bot de Ofertas</h1>
    <span class="grow"></span>
    <span class="pill"><span class="dot" id="dot"></span><span id="stt">verificando…</span></span>
    <button class="pri" id="btnBot" onclick="toggleBot()">Ligar bot</button>
  </header>

  <!-- 1. Configuração -->
  <div class="card">
    <h2><span class="n">1</span> Configuração</h2>
    <div id="campos"></div>
    <div class="row" style="margin-top:14px">
      <button class="pri" onclick="salvar()">💾 Salvar</button>
      <button onclick="detectarIds()">🔎 Detectar IDs do Telegram</button>
      <span class="muted" id="salvoMsg"></span>
    </div>
    <div class="ids hide" id="idsBox"></div>
  </div>

  <!-- Categorias -->
  <div class="card">
    <h2><span class="n">🎯</span> Categorias do canal</h2>
    <p class="muted" style="margin:-6px 0 12px">
      Marque os nichos que você quer no canal. <b>Nada marcado = pega ofertas de tudo.</b>
    </p>
    <div class="nichos-grid" id="nichosGrid">carregando…</div>
    <div class="row" style="margin-top:14px">
      <button class="pri" onclick="salvarNichos()">💾 Salvar categorias</button>
      <button onclick="limparNichos()">Limpar (pegar tudo)</button>
      <span class="muted" id="nichosMsg"></span>
    </div>
  </div>

  <!-- 2. Instalação e testes -->
  <div class="card">
    <h2><span class="n">2</span> Instalação e testes</h2>
    <div class="row">
      <button onclick="acao('instalar-navegador')" id="a_nav">⬇️ Instalar navegador</button>
      <button onclick="acao('ml-login')" id="a_ml">🔑 Login Mercado Livre</button>
      <button onclick="acao('testar-ml')">🧪 Testar ML</button>
      <button onclick="acao('testar-shopee')">🧪 Testar Shopee</button>
      <button onclick="acao('testar-amazon')">🧪 Testar Amazon</button>
    </div>
    <p class="muted" style="margin:10px 0 6px">Saída:</p>
    <div class="log" id="logAcao">—</div>
  </div>

  <!-- 3. Bot -->
  <div class="card">
    <h2><span class="n">3</span> Bot ao vivo</h2>
    <div class="log" id="logBot">O bot está desligado. Configure acima e clique em “Ligar bot”.</div>
  </div>

  <p class="muted" style="text-align:center">
    Roda tudo no seu PC. Feche a janela preta para desligar o painel.
  </p>
</div>
<div class="toast" id="toast"></div>

<script>
const $ = s => document.querySelector(s);
let CFG = {}, statusAtual = {};

const CAMPOS = [
  ["TELEGRAM_BOT_TOKEN","Token do bot","Telegram",true,"Crie no @BotFather com /newbot e cole aqui."],
  ["TELEGRAM_OWNER_ID","Seu user ID","Telegram",false,"Use “Detectar IDs” depois de salvar o token."],
  ["TELEGRAM_CHAT_ID","ID do canal","Telegram",false,"O canal onde o bot posta. Use “Detectar IDs”."],
  ["ML_ETIQUETA","Etiqueta do afiliado","Mercado Livre",false,"A “Etiqueta em uso” do Linkbuilder."],
  ["AMAZON_TAG","Tag de associado","Amazon",false,"Sua tag do Amazon Associados (ex: seunome-20)."],
  ["AMAZON_CREDENTIAL_ID","Creators API — ID","Amazon",false,"Opcional (busca automática oficial)."],
  ["AMAZON_CREDENTIAL_SECRET","Creators API — Secret","Amazon",true,"Opcional. Aparece só uma vez."],
  ["SHOPEE_APP_ID","App ID","Shopee",false,"Painel de afiliados > “Abrir API”."],
  ["SHOPEE_APP_SECRET","App Secret","Shopee",true,"Painel de afiliados > “Abrir API”."],
];

function montarCampos(){
  let html = "", grupo = "";
  for(const [k,rot,grp,seg,ajuda] of CAMPOS){
    if(grp!==grupo){ html += `<div class="grp">${grp}</div>`; grupo = grp; }
    const set = CFG[k+"__set"];
    const tick = set ? `<span class="tick" style="color:var(--ok)">✓ preenchido</span>` : "";
    const ph = seg && set ? "•••••• (preenchido — deixe em branco para manter)" : "";
    html += `<div class="fld">
      <label>${rot} ${tick}</label>
      <input id="f_${k}" type="${seg?'password':'text'}" placeholder="${ph}" value="${seg?'':(CFG[k]||'')}">
      <div class="help">${ajuda}</div></div>`;
  }
  $("#campos").innerHTML = html;
}

async function carregarCfg(){ CFG = await (await fetch("/api/config")).json(); montarCampos(); }

async function salvar(){
  const body = {};
  for(const [k] of CAMPOS){ body[k] = $("#f_"+k).value.trim(); }
  await fetch("/api/config",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});
  toast("Configuração salva!");
  await carregarCfg(); atualizar();
}

async function detectarIds(){
  const box = $("#idsBox"); box.classList.remove("hide");
  box.innerHTML = `<p class="muted">Consultando o Telegram…</p>`;
  const r = await (await fetch("/api/detectar-ids",{method:"POST",headers:{"Content-Type":"application/json"},body:"{}"})).json();
  if(r.erro){ box.innerHTML = `<p class="muted" style="color:var(--warn)">${r.erro}</p>`; return; }
  if(r.vazio){
    box.innerHTML = `<p class="muted">Nada encontrado ainda. No Telegram: mande <b>/start</b> e <b>/id</b> para o
      bot, e <b>encaminhe um post do canal</b> para ele. Depois clique de novo.</p>`; return;
  }
  let h = "";
  if(r.pessoas.length){ h += `<p class="muted">Clique no <b>seu usuário</b> (define o dono):</p>`;
    for(const p of r.pessoas) h += `<button class="idbtn" onclick="setId('TELEGRAM_OWNER_ID','${p.id}')">👤 ${p.nome} — <code>${p.id}</code></button>`; }
  if(r.canais.length){ h += `<p class="muted" style="margin-top:10px">Clique no <b>seu canal</b>:</p>`;
    for(const c of r.canais) h += `<button class="idbtn" onclick="setId('TELEGRAM_CHAT_ID','${c.id}')">📢 ${c.nome} — <code>${c.id}</code></button>`; }
  box.innerHTML = h;
}
function setId(campo,val){ $("#f_"+campo).value = val; toast("Preenchido — não esqueça de salvar."); }

async function acao(nome){
  const r = await (await fetch("/api/acao",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({nome})})).json();
  if(r.erro){ toast(r.erro,true); return; }
  if(nome==="ml-login") toast("Abrindo o Chrome… faça login e feche o navegador.");
  else if(nome==="instalar-navegador") toast("Baixando (~120 MB), acompanhe a saída.");
}

async function toggleBot(){
  const rota = statusAtual.bot_rodando ? "/api/stop" : "/api/start";
  await fetch(rota,{method:"POST"}); atualizar();
}

async function atualizar(){
  statusAtual = await (await fetch("/api/status")).json();
  const on = statusAtual.bot_rodando;
  $("#dot").className = "dot" + (on?" on":"");
  $("#stt").textContent = on ? "Bot rodando" : (statusAtual.pronto ? "Pronto para ligar" : "Falta configurar");
  const b = $("#btnBot"); b.textContent = on ? "Desligar bot" : "Ligar bot";
  b.className = on ? "stop" : "pri";
  b.disabled = !on && !statusAtual.pronto;
  $("#a_nav").textContent = statusAtual.navegador ? "✓ Navegador instalado" : "⬇️ Instalar navegador";
  $("#a_ml").textContent = statusAtual.sessao_ml ? "✓ Login ML feito (refazer)" : "🔑 Login Mercado Livre";
}

async function puxarLogs(){
  const [lb, la] = await Promise.all([
    fetch("/api/logs?bot").then(r=>r.json()),
    fetch("/api/logs?acao").then(r=>r.json()),
  ]);
  if(lb.linhas.length){ const e=$("#logBot"); const b=e.scrollTop+e.clientHeight>=e.scrollHeight-30;
    e.textContent = lb.linhas.join("\n"); if(b) e.scrollTop = e.scrollHeight; }
  if(la.linhas.length){ const e=$("#logAcao"); const b=e.scrollTop+e.clientHeight>=e.scrollHeight-30;
    e.textContent = la.linhas.join("\n"); if(b) e.scrollTop = e.scrollHeight; }
}

let NICHOS_SEL = new Set();
async function carregarNichos(){
  const r = await (await fetch("/api/nichos")).json();
  NICHOS_SEL = new Set(r.selecionados || []);
  $("#nichosGrid").innerHTML = r.catalogo.map(n =>
    `<div class="nicho${NICHOS_SEL.has(n.chave)?' on':''}" data-k="${n.chave}" onclick="toggleNicho('${n.chave}')">
       <span class="emo">${n.emoji}</span><span class="nm">${n.nome}</span><span class="ck">✓</span>
     </div>`).join("");
  atualizarMsgNichos();
}
function toggleNicho(k){
  if(NICHOS_SEL.has(k)) NICHOS_SEL.delete(k); else NICHOS_SEL.add(k);
  document.querySelector(`.nicho[data-k="${k}"]`).classList.toggle("on");
  atualizarMsgNichos();
}
function atualizarMsgNichos(){
  const n = NICHOS_SEL.size;
  $("#nichosMsg").textContent = n===0 ? "pegando de todas as categorias" : `${n} nicho(s) selecionado(s)`;
}
async function salvarNichos(){
  await fetch("/api/nichos",{method:"POST",headers:{"Content-Type":"application/json"},
    body:JSON.stringify({selecionados:[...NICHOS_SEL]})});
  toast(statusAtual.bot_rodando ? "Salvo! Desligue e ligue o bot para aplicar." : "Categorias salvas!");
}
function limparNichos(){
  NICHOS_SEL.clear();
  document.querySelectorAll(".nicho.on").forEach(e=>e.classList.remove("on"));
  atualizarMsgNichos();
}

let toastT;
function toast(msg,err){ const t=$("#toast"); t.textContent=msg; t.className="toast show"+(err?" err":"");
  clearTimeout(toastT); toastT=setTimeout(()=>t.className="toast"+(err?" err":""),3200); }

carregarCfg(); carregarNichos(); atualizar(); puxarLogs();
setInterval(atualizar, 2500);
setInterval(puxarLogs, 1500);
</script>
</body>
</html>
"""
