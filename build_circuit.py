#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_circuit.py —— 从真实 MaleCNS v1.0 权重表抽取「真实功能回路子图」
（这是用户要的「用 1.1GB 真实权重表、但简化」的核心步骤）

做法：
1. 读 annotations（神经元类型注释），建立 bodyId -> type 映射
2. 按真实果蝇回路关键词挑节点：逃逸 GF、求偶 aCC/P1/JCX、嗅觉 ORN/AL/MB
3. 读 connectome-weights（1.1GB 边表），只保留「两端都在选中集合」的真实边
4. 输出 circuit.json（很小，几百~几千节点），交给 flylife_real.py 跑

依赖：pyarrow（pip install pyarrow）。数据用 ../stonkfly-cn/fetch_data.sh 下载。
"""
import os, json, argparse

# 真实果蝇回路关键词（来自 Drosophila 神经科学文献，type 列实测可命中）
# 短缩写（含数字，易误匹配）走「大小写敏感 + 词边界」；长词走大小写不敏感子串。
CIRCUITS = {
    "escape":    ["GF", "TTMn", "Ttm", "Terg"],          # 巨纤维逃逸：GF→TTMn→肌肉
    "courtship": ["aCC", "P1", "pIP10", "mAL", "vAB"],    # 求偶：aCC/P1/pIP10/mAL/vAB
    "olfactory": ["ORN", "AL", "KC", "MBON", "PAM", "LH"],# 嗅觉：ORN→AL→(MB:K C/MBON/PAM, LH)
}
ALL_KEYS = [k for v in CIRCUITS.values() for k in v]

import re
# 短缩写（含数字/字母混合）用「前缀 + 仅前词边界」匹配，避免 P1 误中 DNp18，
# 同时允许 GFC3 / P1a / mALD1 这类带后缀的真实类型命中。
_SHORT = {"GF", "P1", "aCC", "TTM", "Ttm", "vAB", "mAL", "AL"}
def match_type(t, k):
    if k in _SHORT:
        return re.search(r"(?<![\w])" + re.escape(k), t) is not None
    return k.lower() in t.lower()

def load_feather(path):
    """读 feather 为 pyarrow Table（不依赖 pandas）。"""
    import pyarrow.feather as pf
    return pf.read_table(path)

def _col(table, *candidates):
    """按候选列名（忽略大小写）返回列名，找不到返回 None。"""
    for c in table.column_names:
        if c.lower() in candidates:
            return c
    return None

def build(weights_path, annot_path, out_path, max_per_type=60, circuits=("escape","courtship","olfactory")):
    print("[1/4] 读神经元注释表 ...")
    ann = load_feather(annot_path)
    print("    注释列:", list(ann.column_names))
    # 找 body id 列与 type 列（真实表含 bodyId / type）
    idcol = _col(ann, "bodyid", "body", "bodyid_v2", "bodyid_v3") or ann.column_names[0]
    typecol = _col(ann, "type", "celltype", "type_v2")
    assert typecol, f"找不到 type 列，可用列：{list(ann.column_names)}"
    body2type = {}
    for b, t in zip(ann.column(idcol).to_pylist(), ann.column(typecol).to_pylist()):
        body2type[str(b)] = str(t)

    print("[2/4] 按真实回路关键词挑节点 ...")
    chosen = set()
    per_type_count = {}
    keys = [k for c in circuits for k in CIRCUITS[c]]
    for body, t in body2type.items():
        for k in keys:
            if match_type(t, k):
                per_type_count[t] = per_type_count.get(t, 0) + 1
                if per_type_count[t] <= max_per_type:
                    chosen.add(body)
                break
    print(f"    选中节点数: {len(chosen)}（覆盖类型示例: {list(per_type_count)[:12]}）")

    print("[3/4] 读 1.1GB 边表，抽取真实子图（只保留两端都在选中集合的边）...")
    wt = load_feather(weights_path)
    print("    边表列:", list(wt.column_names))
    precol = next(c for c in wt.column_names if "pre" in c.lower())
    postcol = next(c for c in wt.column_names if "post" in c.lower())
    wcol = next((c for c in wt.column_names if c.lower() in ("weight","count","synapses","nsyn")), wt.column_names[-1])
    pre_list = wt.column(precol).to_pylist()
    post_list = wt.column(postcol).to_pylist()
    w_list = wt.column(wcol).to_pylist() if wcol in wt.column_names else [1.0] * wt.num_rows
    nodes, edges = {}, []
    for a, b, w in zip(pre_list, post_list, w_list):
        a, b = str(a), str(b)
        if a in chosen and b in chosen:
            nodes.setdefault(a, body2type.get(a, "?"))
            nodes.setdefault(b, body2type.get(b, "?"))
            edges.append([a, b, float(w) if wcol in wt.column_names else 1.0])
    # 若选中集合里部分节点无出/入边，也保留为孤立节点（保证类型完整）
    for b in chosen:
        nodes.setdefault(b, body2type.get(b, "?"))
    print(f"    抽取真实边数: {len(edges)}，涉及节点: {len(nodes)}")

    out = {"nodes": nodes, "edges": edges, "circuits": list(circuits)}
    with open(out_path, "w") as f:
        json.dump(out, f)
    print(f"[4/4] 已写出子图: {out_path}")
    return out

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    d = os.path.dirname(__file__)
    ap.add_argument("--weights", default=os.path.join(d, "..", "stonkfly-cn", "male-cns-data",
        "connectome-weights-male-cns-v1.0-minconf-0.5.feather"))
    ap.add_argument("--annot", default=os.path.join(d, "..", "stonkfly-cn", "male-cns-data",
        "body-annotations-male-cns-v1.0-minconf-0.5.feather"))
    ap.add_argument("--out", default=os.path.join(d, "circuit.json"))
    ap.add_argument("--max_per_type", type=int, default=60)
    ap.add_argument("--circuits", nargs="*", default=["escape","courtship","olfactory"])
    a = ap.parse_args()
    build(a.weights, a.annot, a.out, a.max_per_type, a.circuits)
