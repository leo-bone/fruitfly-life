#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FlyLife —— 一只果蝇的"数字一生"模拟引擎（纯标准库，无外部依赖）

设计原则（诚实声明）：
- 本程序用 *真实果蝇神经回路的命名与连接方向*（来自 Drosophila 神经科学文献）
  作为"生物底子"，但连接权重是示意性的，并非 MaleCNS 实测权重。
- 它不声称复现某只真实果蝇的意识；它是"用真实回路结构驱动一段被设计的人生"。
- 价值在于：叙事 + 科普 + 内容素材，每只果蝇的一生都唯一、可生成、可分享。

真实引用的回路（命名来自文献）：
- ORN→AL→MB(KC)→MBON：嗅觉与联想学习（果蝇嗅觉=局部敏感哈希 FlyHash 的生物学原型）
- PAM 多巴胺 / PPL 厌恶：奖赏与惩罚
- GF（巨纤维）→ 逃逸运动：对捕食者的闪电逃跑
- aCC→P1→JCX：求偶鸣叫与求偶行为
- 视觉 vPN 检测捕食者剪影
"""
import random
import math
import json

# ---------- 神经回路（组名 = 文献中的真实结构） ----------
# type: sensory / inter / mod / motor
GROUPS = {
    "ORN":      ("sensory", 50),   # 嗅觉受体神经元
    "photo":    ("sensory", 40),   # 光/视觉感受器
    "mechano":  ("sensory", 30),   # 机械/风觉（捕食者逼近）
    "AL":       ("inter",   60),   # 嗅球（ antennal lobe ）
    "MB_KC":    ("inter",  120),   # 蘑菇体 KC 细胞（联想记忆）
    "MBON":     ("inter",   40),   # 蘑菇体输出（效价）
    "LH":       ("inter",   40),   # 外侧角（先天气味 valence）
    "vPN":      ("inter",   40),   # 视觉投射神经元
    "GF":       ("inter",   10),   # 巨纤维（逃逸命令）
    "aCC":      ("sensory", 20),   # 听觉（配偶鸣叫）
    "P1":       ("inter",   10),   # 求偶命令神经元
    "JCX":      ("inter",   10),   # 求偶中枢
    "PAM":      ("mod",     15),   # 多巴胺（奖赏）
    "PPL":      ("mod",      5),   # 厌恶（惩罚）
    "M_feed":   ("motor",   10),   # 取食
    "M_approach":("motor",  10),   # 接近
    "M_flee":   ("motor",   10),   # 逃跑
    "M_court":  ("motor",   10),   # 求偶
    "M_rest":   ("motor",   10),   # 静止
}

# 连接（from, to, 权重符号与强度）——方向取自文献，权重为示意
W = [
    ("ORN","AL",0.8),("AL","MB_KC",0.6),("MB_KC","MBON",0.5),
    ("AL","LH",0.7),("LH","M_approach",0.4),("LH","M_feed",0.3),
    ("photo","vPN",0.9),("vPN","GF",0.8),("mechano","GF",0.9),
    ("GF","M_flee",1.0),
    ("aCC","P1",0.9),("P1","JCX",0.8),("JCX","M_court",0.9),
    ("MBON","M_feed",0.3),("MBON","M_approach",0.3),
    ("PAM","MB_KC",0.2),   # 奖赏增强记忆
    ("PPL","GF",0.3),      # 惩罚促进逃跑
]

# ---------- 生命阶段 ----------
def stage_of(age, lifespan):
    r = age / lifespan
    if r < 0.18:  return "幼虫期"      # 卵+幼虫+蛹，无外界交互，只是发育
    if r < 0.30:  return "羽化成虫"    # 破蛹出生
    if r < 0.55:  return "青年期"
    if r < 0.80:  return "壮年期"
    return "老年期"

STAGE_EVENTS = {
    "羽化成虫": "从蛹中挣脱，翅膀第一次展开，迎来第一个清晨。",
    "青年期":   "开始独立觅食，学习哪里的果实最甜。",
    "壮年期":   "体魄与经验俱佳，频繁在领地间穿梭。",
    "老年期":   "反应变慢，翅膀磨损，更多时间静静停驻。",
}

class Fly:
    def __init__(self, seed=None):
        self.rng = random.Random(seed)
        self.seed = seed if seed is not None else self.rng.randint(0, 999999)
        self.rng = random.Random(self.seed)
        self.lifespan = self.rng.randint(28, 60)   # 模拟"天"
        self.age = 0
        self.energy = 100.0
        self.health = 100.0
        self.mate_count = 0
        self.offspring = 0
        self.predator_escapes = 0
        self.predator_hits = 0
        self.food_found = 0
        self.alive = True
        self.activity = {k: 0.0 for k in GROUPS}
        self.log = []
        self.series = {"energy": [], "health": [], "GF": [], "MBON": [], "PAM": [], "M_court": []}

    def step(self, day_events):
        """推进一步（= 一个模拟日）。day_events: dict 描述当天世界。"""
        if not self.alive:
            return
        self.age += 1
        a = self.activity
        # --- 感觉输入 ---
        a["ORN"]   = day_events.get("food", 0.3)
        a["photo"] = day_events.get("light", 0.8)
        a["mechano"] = day_events.get("wind", 0.05)
        a["aCC"]   = day_events.get("mate_signal", 0.0)

        # --- 神经传播（rate-based，带衰减与饱和） ---
        new = dict(a)
        for (f, t, w) in W:
            new[t] = new.get(t, 0.0) + w * a[f]
        for k in a:
            # 衰减 + tanh 饱和
            a[k] = max(0.0, min(1.0, 0.6 * a[k] + 0.7 * math.tanh(new.get(k, 0.0))))

        # --- 奖赏/惩罚调制 ---
        if day_events.get("ate", False):
            a["PAM"] = 1.0
            self.energy = min(100.0, self.energy + 25)
            self.food_found += 1
        else:
            self.energy -= self.rng.uniform(3, 7)
        if day_events.get("predator", False):
            if a["M_flee"] > 0.5 and self.rng.random() < 0.7:
                self.predator_escapes += 1
                a["PAM"] = 0.6
            else:
                self.predator_hits += 1
                self.health -= self.rng.uniform(15, 35)
                a["PPL"] = 1.0
        if day_events.get("mate_signal", 0.0) > 0.5 and a["M_court"] > 0.5:
            self.mate_count += 1
            self.offspring += self.rng.randint(8, 20)
            a["PAM"] = 1.0

        # --- 老年衰退 ---
        if self.age / self.lifespan > 0.8:
            self.health -= self.rng.uniform(0.5, 2.0)

        # --- 记录 ---
        self.series["energy"].append(round(self.energy, 1))
        self.series["health"].append(round(self.health, 1))
        self.series["GF"].append(round(a["GF"], 3))
        self.series["MBON"].append(round(a["MBON"], 3))
        self.series["PAM"].append(round(a["PAM"], 3))
        self.series["M_court"].append(round(a["M_court"], 3))

        # --- 死亡判定 ---
        if self.energy <= 0:
            self.alive = False
            self.death_cause = "饥饿——连续多日找不到成熟的果实"
        elif self.health <= 0:
            self.alive = False
            self.death_cause = "被捕食者所伤，伤口感染未能恢复"
        elif self.age >= self.lifespan:
            self.alive = False
            self.death_cause = "寿终——在熟悉的果实旁安静停下"

    def run(self):
        born = False
        while self.alive and self.age < self.lifespan + 1:
            stage = stage_of(self.age, self.lifespan)
            ev = {"food": 0.3, "light": 0.8, "wind": 0.05, "mate_signal": 0.0,
                  "ate": False, "predator": False}
            if stage in ("青年期", "壮年期", "老年期"):
                # 觅食：多数日子能吃到
                if self.rng.random() < 0.75:
                    ev["ate"] = True
                    ev["food"] = self.rng.uniform(0.6, 1.0)
                # 求偶信号（壮年期概率高）
                if stage == "壮年期" and self.rng.random() < 0.5:
                    ev["mate_signal"] = self.rng.uniform(0.5, 1.0)
                # 捕食者（老年反应慢，命中率高）
                if self.rng.random() < (0.18 if stage != "老年期" else 0.28):
                    ev["predator"] = True
                    ev["wind"] = self.rng.uniform(0.6, 1.0)
            if stage in STAGE_EVENTS and (len(self.log) == 0 or self.log[-1][1] != stage):
                self.log.append((self.age, stage, STAGE_EVENTS[stage]))
            self.step(ev)
        return self

    def story(self):
        lines = [f"🪰 编号 #{self.seed} 的果蝇 · 模拟寿命 {self.lifespan} 天"]
        for (age, stage, txt) in self.log:
            lines.append(f"  [第{age}天 · {stage}] {txt}")
        if self.predator_escapes:
            lines.append(f"  · 一生躲过捕食者 {self.predator_escapes} 次"
                         + (f"，被击中 {self.predator_hits} 次" if self.predator_hits else "，从未失手"))
        if self.mate_count:
            lines.append(f"  · 求偶成功 {self.mate_count} 次，留下约 {self.offspring} 枚卵")
        if self.food_found:
            lines.append(f"  · 找到成熟果实 {self.food_found} 次")
        lines.append(f"  ✝ 结局：{getattr(self,'death_cause','未知')}（终年 {self.age} 天）")
        return "\n".join(lines)

def simulate_population(n=20, seed_base=1000):
    """批量模拟，挑出最有故事的一只（用于内容素材）。"""
    flies = []
    for i in range(n):
        f = Fly(seed=seed_base + i).run()
        flies.append(f)
    # 评分：故事性 = 逃生次数 + 求偶 + 非平庸死因
    def score(f):
        return f.predator_escapes * 3 + f.mate_count * 2 + (1 if "寿终" not in f.death_cause else 0)
    flies.sort(key=score, reverse=True)
    return flies

if __name__ == "__main__":
    f = Fly(seed=4827).run()
    print(f.story())
    print("\n--- 神经活动序列已记录，可导入 HTML 可视化 ---")
