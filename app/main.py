"""异文对读台 FastAPI 入口。"""

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .collation import (
    EditionError,
    alignment_audit,
    block_move,
    collate,
    distinguishing_window,
    edition,
    provenance,
    relationships,
)
from .fragments import assemble

MAX_POINTS = 300
MIN_WITNESSES = 2
MAX_WITNESSES = 4
MIN_FRAGMENTS = 2
MAX_FRAGMENTS = 8
MAX_FRAGMENT_POINTS = 100

STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(title="异文对读台")


class WitnessIn(BaseModel):
    name: str
    text: str


class SelectionIn(BaseModel):
    # 坐标类型：char＝字符坐标，gap＝间隙坐标
    type: str
    # 字符坐标 1…m；间隙坐标 0…m
    index: int
    # 所选读法；缺字／无插入为空串
    reading: str


class CollateRequest(BaseModel):
    base: str
    witnesses: list[WitnessIn]


class RelationshipsRequest(BaseModel):
    base: str
    witnesses: list[WitnessIn]


class AlignmentAuditRequest(BaseModel):
    base: str
    witnesses: list[WitnessIn]


class DistinguishingWindowRequest(BaseModel):
    base: str
    witnesses: list[WitnessIn]


class BlockMoveRequest(BaseModel):
    base: str
    witnesses: list[WitnessIn]


class FragmentIn(BaseModel):
    name: str
    text: str


class FragmentsRequest(BaseModel):
    fragments: list[FragmentIn]


class EditionRequest(BaseModel):
    base: str
    witnesses: list[WitnessIn]
    # 仅记录非默认选择；缺省或空列表表示全部依底本
    selections: list[SelectionIn] = Field(default_factory=list)


class ProvenanceRequest(BaseModel):
    base: str
    witnesses: list[WitnessIn]
    # 待鉴文本：与底本、抄本同规则校验并对齐到底本坐标
    query: str


def _validate(base: str, witnesses: list[WitnessIn]):
    """底本与抄本输入校验（对读、校定共用）。"""
    if not 1 <= len(base) <= MAX_POINTS:
        raise HTTPException(
            status_code=400, detail=f"底本长度须为 1～{MAX_POINTS} 个 Unicode 码点"
        )
    if not MIN_WITNESSES <= len(witnesses) <= MAX_WITNESSES:
        raise HTTPException(
            status_code=400,
            detail=f"抄本数量须为 {MIN_WITNESSES}～{MAX_WITNESSES} 份",
        )
    names = []
    for w in witnesses:
        name = w.name.strip()
        if not name:
            raise HTTPException(status_code=400, detail="抄本名称不能为空")
        if name in names:
            raise HTTPException(status_code=400, detail=f"抄本名称重复：{name}")
        if not 1 <= len(w.text) <= MAX_POINTS:
            raise HTTPException(
                status_code=400,
                detail=f"抄本「{name}」长度须为 1～{MAX_POINTS} 个 Unicode 码点",
            )
        names.append(name)
    return [{"name": w.name.strip(), "text": w.text} for w in witnesses]


def _validate_fragments(pages: list[FragmentIn]):
    """残页录入校验：2～8 张具名残页，每张 1～100 码点，名称不重复。"""
    if not MIN_FRAGMENTS <= len(pages) <= MAX_FRAGMENTS:
        raise HTTPException(
            status_code=400,
            detail=f"残页数量须为 {MIN_FRAGMENTS}～{MAX_FRAGMENTS} 张",
        )
    names = []
    for p in pages:
        name = p.name.strip()
        if not name:
            raise HTTPException(status_code=400, detail="残页名称不能为空")
        if name in names:
            raise HTTPException(status_code=400, detail=f"残页名称重复：{name}")
        if not 1 <= len(p.text) <= MAX_FRAGMENT_POINTS:
            raise HTTPException(
                status_code=400,
                detail=f"残页「{name}」长度须为 1～{MAX_FRAGMENT_POINTS} 个 Unicode 码点",
            )
        names.append(name)
    return [{"name": p.name.strip(), "text": p.text} for p in pages]


@app.post("/api/collate")
def api_collate(req: CollateRequest):
    witnesses = _validate(req.base, req.witnesses)
    return collate(req.base, witnesses)


@app.post("/api/relationships")
def api_relationships(req: RelationshipsRequest):
    witnesses = _validate(req.base, req.witnesses)
    result = relationships(req.base, witnesses)
    return {
        "base": {"text": req.base, "length": len(req.base)},
        "witnesses": [
            {"name": w["name"], "text": w["text"], "length": len(w["text"])}
            for w in witnesses
        ],
        "relationships": result,
    }


@app.post("/api/edition")
def api_edition(req: EditionRequest):
    witnesses = _validate(req.base, req.witnesses)
    selections = [sel.model_dump() for sel in req.selections]
    try:
        result = edition(req.base, witnesses, selections)
    except EditionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "base": {"text": req.base, "length": len(req.base)},
        "witnesses": [
            {"name": w["name"], "text": w["text"], "length": len(w["text"])}
            for w in witnesses
        ],
        "selections": selections,
        "edition": result,
    }


@app.post("/api/provenance")
def api_provenance(req: ProvenanceRequest):
    witnesses = _validate(req.base, req.witnesses)
    if not 1 <= len(req.query) <= MAX_POINTS:
        raise HTTPException(
            status_code=400, detail=f"待鉴文本长度须为 1～{MAX_POINTS} 个 Unicode 码点"
        )
    result = provenance(req.base, witnesses, req.query)
    return {
        "base": {"text": req.base, "length": len(req.base)},
        "witnesses": [
            {"name": w["name"], "text": w["text"], "length": len(w["text"])}
            for w in witnesses
        ],
        "query": {"text": req.query, "length": len(req.query)},
        "provenance": result,
    }


@app.post("/api/alignment-audit")
def api_alignment_audit(req: AlignmentAuditRequest):
    witnesses = _validate(req.base, req.witnesses)
    result = alignment_audit(req.base, witnesses)
    return {
        "base": {"text": req.base, "length": len(req.base)},
        "witnesses": [
            {"name": w["name"], "text": w["text"], "length": len(w["text"])}
            for w in witnesses
        ],
        "audit": result,
    }


@app.post("/api/distinguishing-window")
def api_distinguishing_window(req: DistinguishingWindowRequest):
    witnesses = _validate(req.base, req.witnesses)
    result = distinguishing_window(req.base, witnesses)
    return {
        "base": {"text": req.base, "length": len(req.base)},
        "witnesses": [
            {"name": w["name"], "text": w["text"], "length": len(w["text"])}
            for w in witnesses
        ],
        "distinguishing_window": result,
    }


@app.post("/api/block-move")
def api_block_move(req: BlockMoveRequest):
    witnesses = _validate(req.base, req.witnesses)
    result = block_move(req.base, witnesses)
    return {
        "base": {"text": req.base, "length": len(req.base)},
        "witnesses": [
            {"name": w["name"], "text": w["text"], "length": len(w["text"])}
            for w in witnesses
        ],
        "block_move": result,
    }


@app.post("/api/fragments")
def api_fragments(req: FragmentsRequest):
    fragments = _validate_fragments(req.fragments)
    result = assemble(fragments)
    return {
        "fragments": [
            {
                "index": i + 1,
                "name": f["name"],
                "text": f["text"],
                "length": len(f["text"]),
            }
            for i, f in enumerate(fragments)
        ],
        "assembly": result,
    }


@app.get("/api/health")
def api_health():
    return {"status": "ok"}


app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
