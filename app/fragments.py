"""残页拼合：最短重叠拼接与残页定位。

拼合规则
--------
- 独立录入 2～8 张具名残页，每张 1～100 个 Unicode 码点，名称不可重复；
  原样比较码点，空白与标点照常参与，不做任何规范化。
- 全文被更长页包含的残页、以及同文重复页中录入较晚者不参与拼接，
  但仍须在全文中定位。
- 其余残页每张使用一次：按前页后缀与后页前缀的最长重叠（可为零）
  顺序拼接，求全文码点数最少的结果；并列先取全文码点字典序最小，
  再取参与拼接的录入序号序列最小。

取舍的正确性
------------
参与拼接的残页两两不含、两两不同文，故相邻页的最长重叠必小于两页
各自的长度：每页至少贡献一个码点，首页自位置 0 起、各页起点严格
递增，同一全文只能由唯一一种顺序拼出。因此「全文码点数最少 →
全文码点字典序最小」两级取舍已唯一确定拼接顺序，第三级（录入序号
序列最小）仅作稳妥兜底。子集动态规划按 (长度, 全文, 顺序) 元组序
逐状态取最小：同一 (子集, 末页) 之下，部分全文更短者无论后续如何
拼接都更优；等长时部分全文码点字典序更小者追加相同后缀后仍更小，
故逐状态剪枝安全。
"""


def _overlap(prev: str, nxt: str) -> int:
    """prev 后缀与 nxt 前缀的最长重叠长度（可为零）。"""
    limit = min(len(prev), len(nxt))
    for k in range(limit, 0, -1):
        if prev.endswith(nxt[:k]):
            return k
    return 0


def assemble(fragments: list) -> dict:
    """拼合残页，返回 {"text", "length", "order", "pages"}。

    fragments 为 [{"name", "text"}]（按录入顺序）。返回：
      text／length：拼合全文及其码点数；
      order：参与拼接的残页按拼接顺序排列（index 从 1 起，附 name）；
      pages：按录入顺序逐张给出 participates、reason（不参与原因：
        "contained"＝全文被更长页包含，"duplicate"＝同文重复页中录入
        较晚；参与为 None）与 span（该页在全文中最早出现的 Unicode
        码点半开区间 [start, end)）。
    """
    texts = [f["text"] for f in fragments]
    n = len(fragments)

    # 参与判定：同文重复页取录入最早者；全文被更长页包含者不参与
    participates = []
    reasons = []
    for i, text in enumerate(texts):
        if any(texts[j] == text for j in range(i)):
            participates.append(False)
            reasons.append("duplicate")
        elif any(len(texts[j]) > len(text) and text in texts[j] for j in range(n)):
            participates.append(False)
            reasons.append("contained")
        else:
            participates.append(True)
            reasons.append(None)

    players = [i for i in range(n) if participates[i]]
    ptexts = [texts[i] for i in players]
    m = len(players)  # ≥ 1：最长文本的最早录入者必然参与

    # 两两最长重叠：ov[a][b]＝players[a] 后缀与 players[b] 前缀的重叠
    ov = [[0] * m for _ in range(m)]
    for a in range(m):
        for b in range(m):
            if a != b:
                ov[a][b] = _overlap(ptexts[a], ptexts[b])

    # 子集 DP：dp[(mask, b)]＝(长度, 部分全文, 顺序)，按元组序取最小。
    # 全长＝各页长度和 − 相邻重叠和，故长度最小即重叠和最大。
    dp = {}
    for a in range(m):
        dp[(1 << a, a)] = (len(ptexts[a]), ptexts[a], (a,))
    for mask in range(1, 1 << m):
        for b in range(m):
            prev_mask = mask ^ (1 << b)
            if not (mask >> b) & 1 or prev_mask == 0:
                continue
            best = None
            for a in range(m):
                if not (prev_mask >> a) & 1:
                    continue
                plen, ptext, porder = dp[(prev_mask, a)]
                o = ov[a][b]
                cand = (
                    plen + len(ptexts[b]) - o,
                    ptext + ptexts[b][o:],
                    porder + (b,),
                )
                if best is None or cand < best:
                    best = cand
            dp[(mask, b)] = best

    full = (1 << m) - 1
    total, text, order = min(dp[(full, b)] for b in range(m))

    pages = []
    for i, f in enumerate(fragments):
        # 每张残页必在全文出现：参与页按拼合位置出现，不参与页含于
        # 某张参与页（同文代表页或更长页，沿包含链必达参与页）
        start = text.find(texts[i])
        pages.append(
            {
                "index": i + 1,
                "name": f["name"],
                "participates": participates[i],
                "reason": reasons[i],
                "span": [start, start + len(texts[i])],
            }
        )

    return {
        "text": text,
        "length": total,
        "order": [
            {"index": players[p] + 1, "name": fragments[players[p]]["name"]}
            for p in order
        ],
        "pages": pages,
    }
