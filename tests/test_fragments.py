"""残页拼合规则测试。

直接运行：python tests/test_fragments.py
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.fragments import assemble  # noqa: E402


def pages(*texts):
    return [{"name": f"页{i + 1}", "text": t} for i, t in enumerate(texts)]


def by_index(res):
    return {p["index"]: p for p in res["pages"]}


def test_overlap_join_basic():
    # 后缀「时习之」与前缀重叠 3 码点
    res = assemble(pages("学而时习之", "时习之，不亦说乎"))
    assert res["text"] == "学而时习之，不亦说乎"
    assert res["length"] == 10
    assert [o["index"] for o in res["order"]] == [1, 2]
    spans = {p["index"]: p["span"] for p in res["pages"]}
    assert spans[1] == [0, 5]
    assert spans[2] == [2, 10]
    assert all(p["participates"] for p in res["pages"])


def test_zero_overlap_lexicographic_tie():
    # 无重叠：两种顺序同为 4 码点，取全文码点字典序最小者
    res = assemble(pages("cd", "ab"))
    assert res["text"] == "abcd"
    assert res["length"] == 4
    assert [o["index"] for o in res["order"]] == [2, 1]


def test_max_overlap_wins():
    # 链式重叠 1＋1 最长：全长 7 优于其他任何顺序
    res = assemble(pages("abc", "cde", "efg"))
    assert res["text"] == "abcdefg"
    assert res["length"] == 7
    assert [o["index"] for o in res["order"]] == [1, 2, 3]
    spans = {p["index"]: p["span"] for p in res["pages"]}
    assert spans[1] == [0, 3]
    assert spans[2] == [2, 5]
    assert spans[3] == [4, 7]


def test_contained_page_excluded_but_located():
    # 「abc」被更长的「xabcy」包含、「b」被两者包含：均不参与但仍定位
    res = assemble(pages("xabcy", "abc", "b"))
    assert res["text"] == "xabcy"
    assert [o["index"] for o in res["order"]] == [1]
    by = by_index(res)
    assert by[1]["participates"] is True and by[1]["reason"] is None
    assert by[2]["participates"] is False and by[2]["reason"] == "contained"
    assert by[3]["participates"] is False and by[3]["reason"] == "contained"
    assert by[1]["span"] == [0, 5]
    assert by[2]["span"] == [1, 4]
    assert by[3]["span"] == [2, 3]


def test_containment_chain():
    # 包含链：只有最长页参与，其余沿链定位
    res = assemble(pages("ab", "abc", "abcd"))
    assert res["text"] == "abcd"
    assert [o["index"] for o in res["order"]] == [3]
    by = by_index(res)
    assert [by[i]["reason"] for i in (1, 2, 3)] == ["contained", "contained", None]
    assert by[1]["span"] == [0, 2]
    assert by[2]["span"] == [0, 3]
    assert by[3]["span"] == [0, 4]


def test_duplicate_page_later_excluded():
    # 同文重复页取录入最早者参与，较晚者不参与但定位相同
    res = assemble(pages("ab", "cd", "ab"))
    assert res["text"] == "abcd"
    assert [o["index"] for o in res["order"]] == [1, 2]
    by = by_index(res)
    assert by[1]["participates"] is True and by[1]["reason"] is None
    assert by[3]["participates"] is False and by[3]["reason"] == "duplicate"
    assert by[3]["span"] == [0, 2]


def test_all_duplicates_but_one():
    res = assemble(pages("ab", "ab", "ab"))
    assert res["text"] == "ab"
    assert [o["index"] for o in res["order"]] == [1]
    assert [p["participates"] for p in res["pages"]] == [True, False, False]
    assert [p["reason"] for p in res["pages"]] == [None, "duplicate", "duplicate"]
    assert [p["span"] for p in res["pages"]] == [[0, 2], [0, 2], [0, 2]]


def test_earliest_occurrence_span():
    # 「ab」在拼合全文中出现多次时取最早出现区间
    res = assemble(pages("abab", "ab"))
    by = by_index(res)
    assert by[2]["participates"] is False and by[2]["reason"] == "contained"
    assert by[2]["span"] == [0, 2]


def test_whitespace_and_punctuation_participate():
    # 空白与标点照常参与：重叠含全角逗号与空格
    res = assemble(pages("a， b", "， b c"))
    assert res["text"] == "a， b c"
    assert res["length"] == 6
    # 不做规范化：全角「，」与半角「,」是不同码点，互不重叠；
    # 两种顺序同为 6 码点，按码点字典序半角逗号（U+002C）在前者胜
    res2 = assemble(pages("a，b", "a,b"))
    assert res2["text"] == "a,ba，b"
    assert [o["index"] for o in res2["order"]] == [2, 1]


def test_unicode_codepoints():
    # 码点原样比较：emoji 单码点参与重叠；两向重叠同为 1、全长同为 3，
    # 按码点字典序「a」(U+0061) 小于「😀」(U+1F600)，故 a😀 在前者胜
    res = assemble(pages("😀a", "a😀"))
    assert res["text"] == "a😀a"
    assert res["length"] == 3
    assert [o["index"] for o in res["order"]] == [2, 1]
    spans = {p["index"]: p["span"] for p in res["pages"]}
    assert spans[1] == [1, 3]
    assert spans[2] == [0, 2]


def test_order_uses_input_indices_and_names():
    frags = [
        {"name": "乙页", "text": "cde"},
        {"name": "甲页", "text": "abc"},
    ]
    res = assemble(frags)
    assert res["text"] == "abcde"
    assert [(o["index"], o["name"]) for o in res["order"]] == [(2, "甲页"), (1, "乙页")]
    by = by_index(res)
    assert by[1]["name"] == "乙页" and by[1]["span"] == [2, 5]
    assert by[2]["name"] == "甲页" and by[2]["span"] == [0, 3]


def test_eight_fragments():
    # 上限 8 张：互无重叠，按字典序取最小全文
    res = assemble(pages("h", "g", "f", "e", "d", "c", "b", "a"))
    assert res["text"] == "abcdefgh"
    assert res["length"] == 8
    assert [o["index"] for o in res["order"]] == [8, 7, 6, 5, 4, 3, 2, 1]
    for p in res["pages"]:
        assert p["span"] == [8 - p["index"], 9 - p["index"]]


def test_spans_cover_fragment_text():
    # 每张残页的最早出现区间都与原文逐码点相同
    frags = pages("天地人", "地人間", "間外", "地")
    res = assemble(frags)
    assert res["text"] == "天地人間外"
    by = by_index(res)
    assert by[4]["participates"] is False and by[4]["reason"] == "contained"
    text = res["text"]
    for p, f in zip(res["pages"], frags):
        s, e = p["span"]
        assert text[s:e] == f["text"]
    assert by[4]["span"] == [1, 2]


def test_longer_duplicate_container():
    # 更长页自身是同文重复页时，其最早录入者参与，被包含页仍定位
    res = assemble(pages("ab", "xabx", "xabx"))
    assert res["text"] == "xabx"
    assert [o["index"] for o in res["order"]] == [2]
    by = by_index(res)
    assert by[1]["reason"] == "contained" and by[1]["span"] == [1, 3]
    assert by[2]["participates"] is True
    assert by[3]["reason"] == "duplicate" and by[3]["span"] == [0, 4]


def run_all():
    for name, fn in sorted(
        ((k, v) for k, v in globals().items() if k.startswith("test_")),
        key=lambda kv: kv[0],
    ):
        fn()
        print(f"PASS {name}")
    print("全部测试通过。")


if __name__ == "__main__":
    run_all()
