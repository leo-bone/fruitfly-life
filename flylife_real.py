#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
flylife_real.py —— 用「真实连接组子图」驱动果蝇的一生
权重来自 MaleCNS v1.0（经 build_circuit.py 抽取），不再是示意性权重。

与 flylife.py 的区别：神经动力学跑在真实边权重上；行为读出按真实神经元类型映射。
其余人生叙事（出生/求偶/遇险/死亡）与世界模型相同。
"""
import json, math, random

# 真实神经元类型 -> 角色（按 Drosophila 文献里的类型命名匹配）
ROLE_RULES = {
    "sensory_food": ["ORN", "GRN"],          # 嗅觉/味觉 -> 食物
    "sensory_light": ["Lamina", "Medulla", "L1", "Mi1", "Lawf"],  # 视觉
    "sensory_wind": ["GF", "wind"],          # 风觉/逃逸触发
    "sensory_mate": ["aCC", "vAB", "pIP10"], # 配偶鸣叫听觉
    "reward": ["PAM", "PPL"],                # 多巴胺/血清素（奖赏/惩罚）
    "motor_flee": ["GF", "TERG", "Ttm", "DLG"],
    "motor_court": ["P1", "JCX", "mAL", "vAB"],
    "motor_feed": ["MBON", "LH", "SEG"],
    "motor_approach": ["MBON", "LH"],
}

import re
# 与 build_circuit 一致的精确匹配：短缩写（GF/P1/aCC/Ttm/vAB/mAL/AL）用「前词边界」前缀，
# 避免 P1 误中 DNp18 之类；长词走大小写不敏感子串。
_SHORT = {"GF", "P1", "aCC", "TTM", "Ttm", "vAB", "mAL", "AL"}
def match_type(t, k):
    if k in _SHORT:
        return re.search(r"(?<![\w])" + re.escape(k), t) is not None
    return k.lower() in t.lower()

def role_of(t):
    for role, keys in ROLE_RULES.items():
        for k in keys:
            if match_type(t, k):
                return role
    return "inter"

class RealFly:
    def __init__(self, circuit, seed=None):
        self.nodes = circuit["nodes"]            # id -> type
        self.ids = list(self.nodes.keys())
        self.idx = {i: k for k, i in enumerate(self.ids)}
        self.type = [self.nodes[i] for i in self.ids]
        self.role = [role_of(t) for t in self.type]
        n = len(self.ids)
        # 邻接（出边）：pre -> list of (post, weight)
        self.out = [[] for _ in range(n)]
        for (pre, post, w) in circuit["edges"]:
            if pre in self.idx and post in self.idx:
                self.out[self.idx[pre]].append((self.idx[post], w))
        self.act = [0.0] * n
        self.rng = random.Random(seed)
        self.seed = seed if seed is not None else self.rng.randint(0, 999999)
        self.rng = random.Random(self.seed)
        self.lifespan = self.rng.randint(28, 60)
        self.age = 0; self.energy = 100.0; self.health = 100.0
        self.mate_count = 0; self.offspring = 0; self.escapes = 0; self.hits = 0; self.food = 0
        self.alive = True; self.log = []
        self.n_edges = len(circuit["edges"])
        self.series = {"energy": [], "health": [], "GF": [], "MBON": [], "PAM": [], "M_court": []}
        # 角色 -> 节点索引组
        self.byrole = {}
        for i, r in enumerate(self.role):
            self.byrole.setdefault(r, []).append(i)

    def inject(self, role, val):
        for i in self.byrole.get(role, []):
            self.act[i] = max(self.act[i], val)

    def mean(self, role):
        xs = self.byrole.get(role, [])
        return sum(self.act[i] for i in xs) / len(xs) if xs else 0.0

    def step(self, ev):
        if not self.alive: return
        self.age += 1
        # 感觉输入（真实类型节点）
        self.inject("sensory_food", ev.get("food", 0.3))
        self.inject("sensory_light", ev.get("light", 0.8))
        self.inject("sensory_wind", ev.get("wind", 0.05))
        self.inject("sensory_mate", ev.get("mate_signal", 0.0))
        # 真实边传播（归一化权重，rate-based + 衰减）
        new = list(self.act)
        for i in range(len(self.act)):
            s = 0.0; wsum = 0.0
            for (j, w) in self.out[i]:
                s += w * self.act[j]; wsum += abs(w)
            if wsum: s /= wsum
            new[i] = max(0.0, min(1.0, 0.55 * self.act[i] + 0.7 * math.tanh(s)))
        self.act = new
        # 奖赏/惩罚
        if ev.get("ate"):
            self.inject("reward", 1.0); self.energy = min(100.0, self.energy + 25); self.food += 1
        else:
            self.energy -= self.rng.uniform(3, 7)
        if ev.get("predator"):
            if self.mean("motor_flee") > 0.4 and self.rng.random() < 0.7:
                self.escapes += 1; self.inject("reward", 0.6)
            else:
                self.hits += 1; self.health -= self.rng.uniform(15, 35)
        if ev.get("mate_signal", 0.0) > 0.5 and self.mean("motor_court") > 0.35:
            self.mate_count += 1; self.offspring += self.rng.randint(8, 20); self.inject("reward", 1.0)
        if self.age / self.lifespan > 0.8:
            self.health -= self.rng.uniform(0.5, 2.0)
        # 记录
        self.series["energy"].append(round(self.energy, 1))
        self.series["health"].append(round(self.health, 1))
        self.series["GF"].append(round(self.mean("motor_flee"), 3))
        self.series["MBON"].append(round(self.mean("motor_feed"), 3))
        self.series["PAM"].append(round(self.mean("reward"), 3))
        self.series["M_court"].append(round(self.mean("motor_court"), 3))
        # 死亡
        if self.energy <= 0: self.alive = False; self.death_cause = "饥饿——连续多日找不到成熟果实"
        elif self.health <= 0: self.alive = False; self.death_cause = "被捕食者所伤，伤口感染未能恢复"
        elif self.age >= self.lifespan: self.alive = False; self.death_cause = "寿终——在熟悉的果实旁安静停下"

    def run(self):
        while self.alive and self.age < self.lifespan + 1:
            r = self.age / self.lifespan
            stage = "幼虫期" if r < 0.18 else "羽化成虫" if r < 0.30 else "青年期" if r < 0.55 else "壮年期" if r < 0.80 else "老年期"
            ev = {"food":0.3,"light":0.8,"wind":0.05,"mate_signal":0.0,"ate":False,"predator":False}
            if stage in ("青年期","壮年期","老年期"):
                if self.rng.random() < 0.75: ev["ate"] = True; ev["food"] = self.rng.uniform(0.6,1.0)
                if stage == "壮年期" and self.rng.random() < 0.5: ev["mate_signal"] = self.rng.uniform(0.5,1.0)
                if self.rng.random() < (0.18 if stage != "老年期" else 0.28): ev["predator"] = True; ev["wind"] = self.rng.uniform(0.6,1.0)
            self.step(ev)
        return self

    def story(self):
        lines = [f"🪰 编号 #{self.seed} · 真实连接组驱动 · {len(self.ids)} 节点 / {self.n_edges} 真实边 · 模拟寿命 {self.lifespan} 天"]
        if self.escapes: lines.append(f"  · 躲过捕食 {self.escapes} 次" + (f"，被击中 {self.hits} 次" if self.hits else "，从未失手"))
        if self.mate_count: lines.append(f"  · 求偶 {self.mate_count} 次，约 {self.offspring} 枚卵")
        if self.food: lines.append(f"  · 找到果实 {self.food} 次")
        lines.append(f"  ✝ {getattr(self,'death_cause','未知')}（终年 {self.age} 天）")
        return "\n".join(lines)

if __name__ == "__main__":
    import sys
    cpath = sys.argv[1] if len(sys.argv) > 1 else "circuit.json"
    with open(cpath) as f: circuit = json.load(f)
    f = RealFly(circuit, seed=4827).run()
    print(f.story())
