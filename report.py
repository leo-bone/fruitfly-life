#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成一只果蝇一生的可视化 HTML 报告（可分享 / 可当桌面宠物页面）。"""
import json
import os
from flylife import Fly, simulate_population

def make_html(fly, out_path):
    s = fly.series
    data = {
        "seed": fly.seed,
        "lifespan": fly.lifespan,
        "age": fly.age,
        "death": getattr(fly, "death_cause", "未知"),
        "escapes": getattr(fly, "predator_escapes", getattr(fly, "escapes", 0)),
        "hits": getattr(fly, "predator_hits", getattr(fly, "hits", 0)),
        "mates": fly.mate_count,
        "offspring": fly.offspring,
        "food": getattr(fly, "food_found", getattr(fly, "food", 0)),
        "energy": s["energy"],
        "health": s["health"],
        "GF": s["GF"],
        "MBON": s["MBON"],
        "PAM": s["PAM"],
        "M_court": s["M_court"],
        "log": [{"age": a, "stage": st, "txt": t} for (a, st, t) in fly.log],
    }
    html = TEMPLATE.replace("__DATA__", json.dumps(data, ensure_ascii=False))
    with open(out_path, "w", encoding="utf-8") as fp:
        fp.write(html)
    return out_path

TEMPLATE = r"""<!doctype html>
<html lang="zh">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>果蝇的一生 #__SEED__</title>
<style>
  :root{--bg:#0f1320;--card:#1a2030;--ink:#e8ecf5;--mut:#8b93a7;--acc:#ffd166;--red:#ff6b6b;--grn:#5ad19a;}
  *{box-sizing:border-box}
  body{margin:0;background:var(--bg);color:var(--ink);font-family:-apple-system,"PingFang SC",sans-serif;padding:24px}
  h1{font-size:20px;margin:0 0 4px}
  .sub{color:var(--mut);font-size:13px;margin-bottom:18px}
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
  /* 桌面宠物：一只会飞的果蝇 */
  .pet{position:fixed;right:24px;bottom:24px;width:64px;height:64px;font-size:40px;
       animation:buzz 3s ease-in-out infinite;cursor:default;user-select:none}
  @keyframes buzz{0%{transform:translate(0,0) rotate(-8deg)}25%{transform:translate(-14px,-18px) rotate(6deg)}
    50%{transform:translate(10px,-8px) rotate(-4deg)}75%{transform:translate(-8px,12px) rotate(10deg)}100%{transform:translate(0,0) rotate(-8deg)}}
</style>
</head>
<body>
  <h1>🪰 一只果蝇的「数字一生」</h1>
  <div class="sub">编号 #{__SEED__} · 基于真实果蝇神经回路结构（ORN/AL/MB/GF/P1…）驱动 · 纯模拟，非真实意识</div>

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

  <div class="pet" title="这是生活在你桌面上的数字果蝇">🪰</div>

<script>
const D = __DATA__;
function statBoxes(){
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
function timeline(){
  const el=document.getElementById('tl');
  let h='';
  D.log.forEach(e=>{h+=`<div class="ev"><div class="d">第 ${e.age} 天 · ${e.stage}</div><div class="t">${e.txt}</div></div>`;});
  h+=`<div class="ev"><div class="d death">终年 ${D.age} 天</div><div class="t death">✝ ${D.death}</div></div>`;
  el.innerHTML=h;
}
statBoxes();
draw('cEH',[D.energy,D.health],['#5ad19a','#ff6b6b']);
draw('cN',[D.GF,D.MBON,D.PAM,D.M_court],['#ffd166','#6ea8ff','#ff9f43','#c792ea']);
timeline();
</script>
</body></html>
"""

if __name__ == "__main__":
    import sys
    here = os.path.dirname(__file__)
    circuit_path = os.path.join(here, "circuit.json")
    if os.path.exists(circuit_path) and "--real" in sys.argv:
        # 真实连接组版：抽取的子图驱动
        from flylife_real import RealFly, role_of
        with open(circuit_path) as f:
            circuit = json.load(f)
        flies = []
        for i in range(20):
            flies.append(RealFly(circuit, seed=4827 + i).run())
        flies.sort(key=lambda f: f.escapes * 3 + f.mate_count * 2, reverse=True)
        tag = "real"
        print("（真实连接组模式）")
    else:
        flies = simulate_population(20, seed_base=4827)
        tag = "sim"
    best = flies[0]
    out = os.path.join(here, f"life_{tag}_{best.seed}.html")
    make_html(best, out)
    print("最有故事的一只：")
    print(best.story())
    print("\n报告已生成：", out)
