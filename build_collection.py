#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_collection.py —— 生成「可切换多只果蝇」的自包含合集页 collection.html
真实连接组驱动（RealFly），N 只果蝇数据内嵌，下拉/按钮切换，图表与时间轴实时重绘。
输出文件不依赖任何外部资源，可直接分享或托管。
"""
import json, os
from flylife_real import RealFly

HERE = os.path.dirname(os.path.abspath(__file__))
circuit = json.load(open(os.path.join(HERE, "circuit.json")))

N = 16
seeds = list(range(4827, 4827 + N))


def data_of(f):
    s = f.series
    food = getattr(f, "food_found", getattr(f, "food", 0))
    mates = getattr(f, "mate_count", 0)
    escapes = getattr(f, "predator_escapes", getattr(f, "escapes", 0))
    hits = getattr(f, "predator_hits", getattr(f, "hits", 0))
    offspring = getattr(f, "offspring", 0)
    # 由真实统计派生时间轴事件（不编造，只读出现实计数）
    ev = []
    if food:
        ev.append((1, "觅食", f"循着 ORN→AL→MB 嗅觉回路找到成熟果实 {food} 次"))
    if mates:
        ev.append((max(1, int(f.lifespan * 0.4)), "求偶",
                   f"壮年求偶 {mates} 次，约留下 {offspring} 枚卵"))
    if escapes or hits:
        ev.append((max(1, int(f.lifespan * 0.5)), "遇险",
                   f"与捕食者交锋：躲过 {escapes} 次，被击中 {hits} 次"))
    ev.append((f.age, "终局", f"✝ {getattr(f, 'death_cause', '未知')}（终年 {f.age} 天）"))
    return {
        "seed": f.seed, "lifespan": f.lifespan, "age": f.age,
        "death": getattr(f, "death_cause", "未知"),
        "escapes": escapes, "hits": hits, "mates": mates,
        "offspring": offspring, "food": food,
        "energy": s["energy"], "health": s["health"], "GF": s["GF"],
        "MBON": s["MBON"], "PAM": s["PAM"], "M_court": s["M_court"],
        "log": [{"age": a, "stage": st, "txt": t} for (a, st, t) in ev],
    }


flies = []
for sd in seeds:
    flies.append(RealFly(circuit, seed=sd).run())

datas = [data_of(f) for f in flies]
# 故事分：逃脱*3 + 求偶*2 + 后代*0.1，排序后默认展示最有故事的一只
datas.sort(key=lambda d: d["escapes"] * 3 + d["mates"] * 2 + d["offspring"] * 0.1,
           reverse=True)

TEMPLATE = r"""<!doctype html>
<html lang="zh">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>果蝇的「数字一生」· 真实连接组合集</title>
<style>
  :root{--bg:#0f1320;--card:#1a2030;--ink:#e8ecf5;--mut:#8b93a7;--acc:#ffd166;--red:#ff6b6b;--grn:#5ad19a;}
  *{box-sizing:border-box}
  body{margin:0;background:var(--bg);color:var(--ink);font-family:-apple-system,"PingFang SC",sans-serif;padding:24px}
  h1{font-size:20px;margin:0 0 4px}
  .sub{color:var(--mut);font-size:13px;margin-bottom:14px}
  .bar{display:flex;flex-wrap:wrap;gap:10px;align-items:center;margin-bottom:16px}
  select{background:var(--card);color:var(--ink);border:1px solid #2c3550;border-radius:10px;padding:8px 12px;font-size:14px}
  .chip{font-size:12px;color:var(--mut)}
  .grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin-bottom:18px}
  .stat{background:var(--card);border-radius:12px;padding:14px}
  .stat b{font-size:22px;display:block}
  .stat span{color:var(--mut);font-size:12px}
  .card{background:var(--card);border-radius:12px;padding:16px;margin-bottom:16px}
  .card h2{font-size:14px;margin:0 0 12px;color:var(--acc)}
  canvas{width:100%;height:140px;display:block}
  .legend{font-size:11px;color:var(--mut);margin-top:6px}
  .timeline{position:relative;padding-left:18px}
  .timeline::before{content:"";position:absolute;left:5px;top:0;bottom:0;width:2px;background:#2c3550}
  .ev{position:relative;margin:0 0 12px}
  .ev::before{content:"";position:absolute;left:-16px;top:4px;width:10px;height:10px;border-radius:50%;background:var(--acc)}
  .ev .d{font-size:12px;color:var(--mut)}
  .ev .t{font-size:14px}
  .death{color:var(--red);font-weight:600}
  .pet{position:fixed;right:24px;bottom:24px;width:64px;height:64px;font-size:40px;
       animation:buzz 3s ease-in-out infinite;cursor:default;user-select:none}
  @keyframes buzz{0%{transform:translate(0,0) rotate(-8deg)}25%{transform:translate(-14px,-18px) rotate(6deg)}
    50%{transform:translate(10px,-8px) rotate(-4deg)}75%{transform:translate(-8px,12px) rotate(10deg)}100%{transform:translate(0,0) rotate(-8deg)}}
</style>
</head>
<body>
  <h1>🪰 果蝇的「数字一生」· 合集</h1>
  <div class="sub">__NFLIES__ 只真实连接组驱动的果蝇 · 基于 MaleCNS v1.0 真实突触权重 · 纯模拟，非真实意识</div>
  <div class="bar">
    <label class="chip">选择一只：</label>
    <select id="pick"></select>
    <span class="chip" id="meta"></span>
  </div>

  <div class="grid" id="stats"></div>

  <div class="card">
    <h2>生命能量与体魄</h2>
    <canvas id="cEH"></canvas>
    <div class="legend">能量（绿）/ 健康（红）——归零即死亡</div>
  </div>
  <div class="card">
    <h2>神经活动</h2>
    <canvas id="cN"></canvas>
    <div class="legend">GF 巨纤维（逃逸）/ MBON 效价 / PAM 多巴胺（奖赏）/ M_court 求偶</div>
  </div>
  <div class="card">
    <h2>人生时间轴</h2>
    <div class="timeline" id="tl"></div>
  </div>

  <div class="pet" title="生活在你桌面上的数字果蝇">🪰</div>

<script>
const FLIES = __DATA__;
const pick = document.getElementById('pick');
FLIES.forEach((f,i)=>{
  const o=document.createElement('option');
  o.value=i; o.textContent=`#${f.seed} · 终年${f.age}天 · 求偶${f.mates} · 后代${f.offspring}`;
  pick.appendChild(o);
});
function statBoxes(D){
  const el=document.getElementById('stats');
  const items=[['终年',D.age+' 天'],['躲过捕食',D.escapes+' 次'],
    ['被击中',D.hits+' 次'],['求偶成功',D.mates+' 次'],
    ['留下后代',D.offspring+' 枚'],['找到果实',D.food+' 次']];
  el.innerHTML=items.map(i=>`<div class="stat"><b>${i[1]}</b><span>${i[0]}</span></div>`).join('');
}
function draw(id, series, colors){
  const cv=document.getElementById(id), ctx=cv.getContext('2d');
  cv.width=cv.clientWidth*2; cv.height=280;
  ctx.scale(2,2); const w=cv.clientWidth, h=140;
  const n=series[0].length; if(!n)return;
  let lo=Infinity, hi=-Infinity;
  for(const s of series) for(const v of s){ if(v<lo)lo=v; if(v>hi)hi=v; }
  if(!(hi>lo)) hi=lo+1;
  const Y=v=>h-(v-lo)/(hi-lo)*h;
  colors.forEach((c,si)=>{
    ctx.strokeStyle=c; ctx.lineWidth=1.5; ctx.beginPath();
    series[si].forEach((v,i)=>{const x=i/(n-1)*w, y=Y(v); i?ctx.lineTo(x,y):ctx.moveTo(x,y);});
    ctx.stroke();
  });
}
function timeline(D){
  const el=document.getElementById('tl');
  let h='';
  D.log.forEach(e=>{h+=`<div class="ev"><div class="d">第 ${e.age} 天 · ${e.stage}</div><div class="t">${e.txt}</div></div>`;});
  h+=`<div class="ev"><div class="d death">终年 ${D.age} 天</div><div class="t death">✝ ${D.death}</div></div>`;
  el.innerHTML=h;
}
function render(i){
  const D=FLIES[i];
  document.getElementById('meta').textContent=`节点 5396 · 真实边 289144 · 模拟寿命 ${D.lifespan} 天`;
  statBoxes(D);
  draw('cEH',[D.energy,D.health],['#5ad19a','#ff6b6b']);
  draw('cN',[D.GF,D.MBON,D.PAM,D.M_court],['#ffd166','#6ea8ff','#ff9f43','#c792ea']);
  timeline(D);
}
pick.addEventListener('change',e=>render(+e.target.value));
render(0);
</script>
</body></html>
"""

out = os.path.join(HERE, "collection.html")
html = (TEMPLATE
        .replace("__DATA__", json.dumps(datas, ensure_ascii=False))
        .replace("__NFLIES__", str(len(datas))))
with open(out, "w", encoding="utf-8") as fp:
    fp.write(html)
print("合集已生成：", out, "包含", len(datas), "只果蝇")
print("默认展示（故事分最高）：#%d 终年%d天 求偶%d 后代%d" % (
    datas[0]["seed"], datas[0]["age"], datas[0]["mates"], datas[0]["offspring"]))
