#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_connectome.py —— 用真实 circuit.json 画「真实连接组网络图」
两层：
  1) 功能回路层（role）：把 607 种神经元按真实类型归入 10 个功能角色，
     角色间连边 = 该两组神经元之间真实突触权重之和（有向、加权）。
  2) 枢纽类型层（type hub）：取总突触权重最高的若干种神经元，
     在最强类型间连边上做 Fruchterman-Reingold 力导向布局，真实坐标内嵌。
所有数值均来自 MaleCNS v1.0 真实边权重。输出自包含 connectome.html。
"""
import json, math, random, os
from collections import defaultdict, Counter
from flylife_real import role_of

HERE = os.path.dirname(os.path.abspath(__file__))
c = json.load(open(os.path.join(HERE, "circuit.json")))
nodes = c["nodes"]          # id -> type
edges = c["edges"]          # (pre, post, w)

ROLE_ORDER = ["sensory_food", "sensory_light", "sensory_wind", "sensory_mate",
              "reward", "motor_flee", "motor_court", "motor_feed",
              "motor_approach", "inter"]
ROLE_CN = {
    "sensory_food": "嗅觉/味觉·觅食", "sensory_light": "视觉·光",
    "sensory_wind": "风觉·逃逸触发", "sensory_mate": "配偶鸣叫听觉",
    "reward": "多巴胺/血清素·奖赏", "motor_flee": "运动·逃逸",
    "motor_court": "运动·求偶", "motor_feed": "运动·取食",
    "motor_approach": "运动·趋近", "inter": "中间处理",
}
ROLE_COLOR = {
    "sensory_food": "#5ad19a", "sensory_light": "#ffd166", "sensory_wind": "#56d4ff",
    "sensory_mate": "#ff9ecf", "reward": "#ff9f43", "motor_flee": "#ff6b6b",
    "motor_court": "#c792ea", "motor_feed": "#6ea8ff", "motor_approach": "#2fd9c0",
    "inter": "#8b93a7",
}

# ---------- 角色层 ----------
role_count = Counter()
for t in nodes.values():
    role_count[role_of(t)] += 1
role_edge = defaultdict(float)
for pre, post, w in edges:
    rp = role_of(nodes.get(pre, "")); ro = role_of(nodes.get(post, ""))
    if rp and ro:
        role_edge[(rp, ro)] += w
present = [r for r in ROLE_ORDER if role_count.get(r, 0) > 0]
# 环形布局
R = 320
role_pos = {}
for i, r in enumerate(present):
    ang = 2 * math.pi * i / len(present) - math.pi / 2
    role_pos[r] = (R * math.cos(ang) + R + 40, R * math.sin(ang) + R + 40)
role_edges = []
for (a, b), w in role_edge.items():
    if a in present and b in present and w > 0:
        role_edges.append({"a": a, "b": b, "w": round(w, 1)})
role_max_w = max((e["w"] for e in role_edges), default=1)

# ---------- 枢纽类型层（力导向） ----------
tw = Counter()
for pre, post, w in edges:
    tw[nodes.get(pre, "")] += w
    tw[nodes.get(post, "")] += w
top_types = [t for t, _ in tw.most_common(70) if t]
idx = {t: i for i, t in enumerate(top_types)}
type_role_map = {t: role_of(t) for t in top_types}
type_count = Counter(nodes.values())
hub_edges = []
for pre, post, w in edges:
    if pre in nodes and post in nodes:
        a = nodes[pre]; b = nodes[post]
        if a in idx and b in idx and a != b:
            hub_edges.append((idx[a], idx[b], w))
hub_edges.sort(key=lambda x: x[2], reverse=True)
hub_edges = hub_edges[:500]
n = len(top_types)


def fruchterman_reingold(n, adj, iters=300, seed=7):
    rnd = random.Random(seed)
    pos = [[rnd.uniform(-1, 1), rnd.uniform(-1, 1)] for _ in range(n)]
    W = H = 2.0
    k = 1.0 * math.sqrt(W * H / max(n, 1))
    for it in range(iters):
        disp = [[0.0, 0.0] for _ in range(n)]
        for i in range(n):
            for j in range(i + 1, n):
                dx = pos[i][0] - pos[j][0]; dy = pos[i][1] - pos[j][1]
                d = math.hypot(dx, dy) or 0.01
                rep = k * k / d
                disp[i][0] += dx / d * rep; disp[i][1] += dy / d * rep
                disp[j][0] -= dx / d * rep; disp[j][1] -= dy / d * rep
        for (a, b, w) in adj:
            dx = pos[a][0] - pos[b][0]; dy = pos[a][1] - pos[b][1]
            d = math.hypot(dx, dy) or 0.01
            att = (d * d / k) * (w / wmax_adj)
            disp[a][0] -= dx / d * att; disp[a][1] -= dy / d * att
            disp[b][0] += dx / d * att; disp[b][1] += dy / d * att
        t = max(0.05, 1.0 - it / iters) * 0.5
        for i in range(n):
            d = math.hypot(disp[i][0], disp[i][1]) or 0.01
            pos[i][0] += disp[i][0] / d * min(d, t)
            pos[i][1] += disp[i][1] / d * min(d, t)
    return pos


wmax_adj = max((e[2] for e in hub_edges), default=1)
pos = fruchterman_reingold(n, hub_edges)
xs = [p[0] for p in pos]; ys = [p[1] for p in pos]
minx, maxx = min(xs), max(xs); miny, maxy = min(ys), max(ys)
VB = 1000
hub_nodes = []
for i, t in enumerate(top_types):
    x = (pos[i][0] - minx) / (maxx - minx or 1) * (VB - 80) + 40
    y = (pos[i][1] - miny) / (maxy - miny or 1) * (VB - 80) + 40
    cnt = type_count.get(t, 1)
    hub_nodes.append({"id": i, "t": t, "role": type_role_map[t],
                      "count": cnt, "x": round(x, 1), "y": round(y, 1),
                      "r": round(4 + 9 * math.sqrt(cnt / 60), 1)})
hub_edges_out = [{"a": a, "b": b, "w": round(w, 1)} for (a, b, w) in hub_edges]
hub_max_w = max((e["w"] for e in hub_edges_out), default=1)

payload = {
    "role": {
        "present": present, "cn": ROLE_CN, "color": ROLE_COLOR,
        "count": {r: role_count.get(r, 0) for r in present},
        "pos": {r: [round(x, 1), round(y, 1)] for r, (x, y) in role_pos.items()},
        "edges": role_edges, "maxw": round(role_max_w, 1),
    },
    "hub": {
        "nodes": hub_nodes, "edges": hub_edges_out,
        "color": ROLE_COLOR, "maxw": round(hub_max_w, 1),
    },
}

TEMPLATE = r"""<!doctype html>
<html lang="zh">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>真实果蝇连接组网络图</title>
<style>
  :root{--bg:#0f1320;--card:#1a2030;--ink:#e8ecf5;--mut:#8b93a7;--acc:#ffd166;}
  *{box-sizing:border-box}
  body{margin:0;background:var(--bg);color:var(--ink);font-family:-apple-system,"PingFang SC",sans-serif;padding:24px}
  h1{font-size:20px;margin:0 0 4px}
  .sub{color:var(--mut);font-size:13px;margin-bottom:18px}
  .grid{display:grid;grid-template-columns:1fr 1fr;gap:16px}
  @media(max-width:900px){.grid{grid-template-columns:1fr}}
  .card{background:var(--card);border-radius:12px;padding:16px;margin-bottom:16px}
  .card h2{font-size:14px;margin:0 0 6px;color:var(--acc)}
  .card p{font-size:12px;color:var(--mut);margin:0 0 10px}
  svg{width:100%;height:auto;display:block;background:#0b0f1a;border-radius:10px}
  .tip{position:fixed;pointer-events:none;background:#000d;color:#fff;padding:6px 9px;border-radius:8px;font-size:12px;opacity:0;transition:opacity .1s;z-index:9}
  .legend{display:flex;flex-wrap:wrap;gap:8px;margin-top:10px}
  .lg{display:flex;align-items:center;gap:5px;font-size:11px;color:var(--mut)}
  .dot{width:10px;height:10px;border-radius:50%}
  .note{font-size:12px;color:var(--mut);line-height:1.6}
  .note b{color:var(--ink)}
</style>
</head>
<body>
  <h1>🧠 真实果蝇连接组网络图</h1>
  <div class="sub">数据：MaleCNS v1.0 真实突触权重（5,396 神经元 / 289,144 真实边）· 纯模拟科普，非真实放电复现</div>

  <div class="grid">
    <div class="card">
      <h2>① 功能回路层（10 个真实角色）</h2>
      <p>节点=功能角色（神经元类型归组），连线=该两组神经元之间的<b>真实突触权重之和</b>（有向）。线越粗权重越大。</p>
      <svg id="svgRole" viewBox="0 0 680 680"></svg>
      <div class="legend" id="lgRole"></div>
    </div>
    <div class="card">
      <h2>② 枢纽类型层（最强 70 种神经元）</h2>
      <p>取总突触权重最高的 70 种神经元类型，在最强类型间连边上做力导向布局。悬停查看类型名/数量/角色。</p>
      <svg id="svgHub" viewBox="0 0 1000 1000"></svg>
      <div class="legend" id="lgHub"></div>
    </div>
  </div>

  <div class="card">
    <h2>诚实边界</h2>
    <div class="note">
      <b>真实的部分：</b>连边权重是 MaleCNS v1.0 连接组的真实突触权重；节点是真实果蝇脑里的真实神经元类型与真实接线。<br>
      <b>模拟的部分：</b>连接组只是一张「接线图」，不是会思考的大脑。本图展示的是<b>静态接线结构</b>（谁连谁、连多强），
      不展示随时间的神经放电；力导向布局仅为可读性，<b>不代表真实空间位置</b>。<br>
      <b>定位：</b>模拟 / 科普 / 叙事素材，不声称复现意识或真实行为。
    </div>
  </div>

  <div class="tip" id="tip"></div>

<script>
const P = __DATA__;
const tip = document.getElementById('tip');
function showTip(e, txt){tip.textContent=txt;tip.style.opacity=1;tip.style.left=(e.clientX+12)+'px';tip.style.top=(e.clientY+12)+'px';}
function hideTip(){tip.style.opacity=0;}
const svgNS="http://www.w3.org/2000/svg";

// ---- 角色层 ----
(function(){
  const svg=document.getElementById('svgRole'); const R=P.role;
  const cx=340, cy=340, rad=240;
  R.edges.forEach(e=>{
    const a=R.pos[e.a], b=R.pos[e.b];
    if(!a||!b || e.a===e.b) return;
    const mx=(a[0]+b[0])/2, my=(a[1]+b[1])/2;
    const dx=b[0]-a[0], dy=b[1]-a[1], len=Math.hypot(dx,dy)||1;
    const ux=dx/len, uy=dy/len, off=34;
    const x1=a[0]+ux*off, y1=a[1]+uy*off, x2=b[0]-ux*off, y2=b[1]-uy*off;
    const ln=document.createElementNS(svgNS,'line');
    ln.setAttribute('x1',x1);ln.setAttribute('y1',y1);ln.setAttribute('x2',x2);ln.setAttribute('y2',y2);
    ln.setAttribute('stroke',R.color[e.a]);ln.setAttribute('stroke-opacity',0.5);
    ln.setAttribute('stroke-width',1+6*Math.sqrt(e.w/R.maxw));
    ln.setAttribute('marker-end','url(#arr)');
    svg.appendChild(ln);
  });
  const defs=document.createElementNS(svgNS,'defs');
  defs.innerHTML='<marker id="arr" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto"><path d="M0,0 L6,3 L0,6 Z" fill="#8b93a7"/></marker>';
  svg.appendChild(defs);
  R.present.forEach(r=>{
    const p=R.pos[r];
    const g=document.createElementNS(svgNS,'g');
    const c=document.createElementNS(svgNS,'circle');
    c.setAttribute('cx',p[0]);c.setAttribute('cy',p[1]);c.setAttribute('r',30);
    c.setAttribute('fill',R.color[r]);c.setAttribute('fill-opacity',0.85);
    g.appendChild(c);
    const t=document.createElementNS(svgNS,'text');
    t.setAttribute('x',p[0]);t.setAttribute('y',p[1]+4);t.setAttribute('text-anchor','middle');
    t.setAttribute('fill','#0f1320');t.setAttribute('font-size','11');t.setAttribute('font-weight','600');
    t.textContent=R.cn[r].split('·')[0];
    g.appendChild(t);
    const lab=document.createElementNS(svgNS,'text');
    lab.setAttribute('x',p[0]);lab.setAttribute('y',p[1]+46);lab.setAttribute('text-anchor','middle');
    lab.setAttribute('fill','#8b93a7');lab.setAttribute('font-size','10');
    lab.textContent=R.count[r]+' 神经元';
    g.appendChild(lab);
    g.addEventListener('mousemove',e=>showTip(e,`${R.cn[r]} · ${R.count[r]} 个真实神经元`));
    g.addEventListener('mouseleave',hideTip);
    svg.appendChild(g);
  });
  const lg=document.getElementById('lgRole');
  R.present.forEach(r=>{const d=document.createElement('div');d.className='lg';
    d.innerHTML=`<span class="dot" style="background:${R.color[r]}"></span>${R.cn[r]}`;lg.appendChild(d);});
})();

// ---- 枢纽类型层 ----
(function(){
  const svg=document.getElementById('svgHub'); const H=P.hub;
  const adj={}; H.edges.forEach(e=>{(adj[e.a]=adj[e.a]||[]).push(e);(adj[e.b]=adj[e.b]||[]).push(e);});
  H.edges.forEach(e=>{
    const a=H.nodes[e.a], b=H.nodes[e.b];
    const ln=document.createElementNS(svgNS,'line');
    ln.setAttribute('x1',a.x);ln.setAttribute('y1',a.y);ln.setAttribute('x2',b.x);ln.setAttribute('y2',b.y);
    ln.setAttribute('stroke','#6ea8ff');ln.setAttribute('stroke-opacity',0.10);
    ln.setAttribute('stroke-width',0.4+2.2*Math.sqrt(e.w/H.maxw));
    ln.setAttribute('data-a',e.a);ln.setAttribute('data-b',e.b);
    svg.appendChild(ln);
  });
  H.nodes.forEach(nd=>{
    const g=document.createElementNS(svgNS,'g');g.setAttribute('data-id',nd.id);
    const c=document.createElementNS(svgNS,'circle');
    c.setAttribute('cx',nd.x);c.setAttribute('cy',nd.y);c.setAttribute('r',nd.r);
    c.setAttribute('fill',H.color[nd.role]);c.setAttribute('fill-opacity',0.9);
    c.setAttribute('stroke','#0b0f1a');c.setAttribute('stroke-width','1');
    g.appendChild(c);
    g.addEventListener('mousemove',e=>{
      showTip(e,`${nd.t} · ${nd.count} 个神经元 · ${H.color?'':''}${roleName(nd.role)}`);
      svg.querySelectorAll('line').forEach(l=>{
        const on=(+l.getAttribute('data-a')===nd.id||+l.getAttribute('data-b')===nd.id);
        l.setAttribute('stroke-opacity',on?0.9:0.03);
        l.setAttribute('stroke',on?'#ffd166':'#6ea8ff');
      });
      svg.querySelectorAll('g[data-id]').forEach(o=>o.setAttribute('opacity',o.getAttribute('data-id')===String(nd.id)?1:0.25));
    });
    g.addEventListener('mouseleave',()=>{
      hideTip();
      svg.querySelectorAll('line').forEach(l=>{l.setAttribute('stroke-opacity',0.12);l.setAttribute('stroke','#6ea8ff');});
      svg.querySelectorAll('g[data-id]').forEach(o=>o.setAttribute('opacity',1));
    });
    svg.appendChild(g);
  });
  const lg=document.getElementById('lgHub');
  Object.keys(H.color).forEach(r=>{if(H.nodes.some(n=>n.role===r)){const d=document.createElement('div');d.className='lg';
    d.innerHTML=`<span class="dot" style="background:${H.color[r]}"></span>${roleName(r)}`;lg.appendChild(d);}});
  function roleName(r){return {'sensory_food':'嗅觉/味觉','sensory_light':'视觉','sensory_wind':'风觉','sensory_mate':'配偶听觉','reward':'奖赏','motor_flee':'逃逸','motor_court':'求偶','motor_feed':'取食','motor_approach':'趋近','inter':'中间处理'}[r]||r;}
})();
</script>
</body></html>
"""

out = os.path.join(HERE, "connectome.html")
html = TEMPLATE.replace("__DATA__", json.dumps(payload, ensure_ascii=False))
with open(out, "w", encoding="utf-8") as fp:
    fp.write(html)
print("连接组网络图已生成：", out)
print("角色层节点：", len(payload["role"]["present"]), " 角色间连边：", len(payload["role"]["edges"]))
print("枢纽层节点：", len(payload["hub"]["nodes"]), " 枢纽连边：", len(payload["hub"]["edges"]))
