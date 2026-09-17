"""洞察织机(InsightLoom)本地语义检索:Chroma 持久化向量库 + 本地 ONNX 嵌入。

设计要点:
- 嵌入模型 all-MiniLM-L6-v2 以 ONNX 形式在本地推理,首次使用时下载到项目内
  data/chroma_models/(通过类属性补丁重定向,兼容无 HOME 写权限的环境)。
- 笔记按二级标题(##)分块入索引,检索命中返回"小节 + 所属笔记",比整篇
  嵌入的命中粒度更细;frontmatter 不参与嵌入。
- 检索层与 LLM MOCK 开关正交:任何模式都可语义检索(嵌入不花钱、不出网调用)。
- 失败安全:chroma 或模型不可用时,search 返回空结果,链接员自动回退标签
  匹配,服务本身不受影响。
"""

from __future__ import annotations

import re
import threading
from pathlib import Path
from typing import Optional

_BASE = Path(__file__).resolve().parent.parent
_CHROMA_DIR = _BASE / "data" / "chroma"
_MODEL_DIR = _BASE / "data" / "chroma_models"
_VAULT_DIR = _BASE / "vault"

_lock = threading.Lock()
_client = None
_collection = None
_init_error: Optional[str] = None


def _frontmatter_title(text: str) -> Optional[str]:
    m = re.match(r"^---\s*\n(.*?)\n---", text, re.S)
    if not m:
        return None
    for line in m.group(1).splitlines():
        if line.startswith("title:"):
            return line.split(":", 1)[1].strip()
    return None


def _strip_frontmatter(text: str) -> str:
    if text.startswith("---"):
        m = re.match(r"^---\s*\n.*?\n---\s*\n?", text, re.S)
        if m:
            return text[m.end():]
    return text


def chunk_note(text: str) -> list[tuple[str, str]]:
    """按二级标题分块,返回 [(小节标题, 小节正文)]。"""
    body = _strip_frontmatter(text).strip()
    if not body:
        return []
    parts = re.split(r"\n(?=## )", body)
    chunks = []
    skip_titles = {"Agent 审查", "关联笔记(🌻 园丁建议)"}  # 样板段,入索引只会污染检索
    for part in parts:
        part = part.strip()
        if not part:
            continue
        title_match = re.match(r"^##\s+(.*)", part)
        section_title = title_match.group(1).strip() if title_match else "(开头)"
        if section_title in skip_titles:
            continue
        if len(part) > 1500:  # 超长小节截断,保持嵌入输入稳定
            part = part[:1500] + "…"
        chunks.append((section_title, part))
    return chunks


def _ensure() -> bool:
    """惰性初始化(线程安全);失败则记原因并永久降级。"""
    global _client, _collection, _init_error
    if _collection is not None:
        return True
    if _init_error is not None:
        return False
    with _lock:
        if _collection is not None:
            return True
        if _init_error is not None:
            return False
        try:
            # 先重定向模型缓存路径,再实例化嵌入函数(否则写 ~/.cache/chroma)
            from chromadb.utils.embedding_functions import ONNXMiniLM_L6_V2

            _MODEL_DIR.mkdir(parents=True, exist_ok=True)
            ONNXMiniLM_L6_V2.DOWNLOAD_PATH = _MODEL_DIR / ONNXMiniLM_L6_V2.MODEL_NAME

            from chromadb import PersistentClient
            from chromadb.utils.embedding_functions import DefaultEmbeddingFunction

            _client = PersistentClient(path=str(_CHROMA_DIR))
            _collection = _client.get_or_create_collection(
                "insightloom_notes",
                embedding_function=DefaultEmbeddingFunction(),
                metadata={"hnsw:space": "cosine"},
            )
            return True
        except Exception as e:  # noqa: BLE001 —— 任何初始化失败都降级为不可用
            _init_error = f"{type(e).__name__}: {e}"
            return False


def status() -> dict:
    return {
        "available": _ensure(),
        "error": _init_error,
        "indexed_chunks": _collection.count() if _ensure() else 0,
    }


def index_note(filename: str, text: str) -> int:
    """单篇笔记(重)索引:覆盖式重建该笔记全部分块。返回分块数。"""
    if not _ensure():
        return 0
    note_id = filename.replace(".md", "")
    try:
        _collection.delete(where={"note": filename})
    except Exception:  # noqa: BLE001 —— 首次索引时 where 删除可能报错,忽略
        pass
    chunks = chunk_note(text)
    if not chunks:
        return 0
    title = _frontmatter_title(text) or note_id
    try:
        _collection.add(
            ids=[f"{note_id}#{i}" for i in range(len(chunks))],
            documents=[c[1] for c in chunks],
            metadatas=[
                {"note": filename, "note_title": title, "section": c[0]} for c in chunks
            ],
        )
    except Exception as e:  # noqa: BLE001
        _init_error = f"add failed: {e}"
        return 0
    return len(chunks)


def remove_note(filename: str) -> None:
    if not _ensure():
        return
    try:
        _collection.delete(where={"note": filename})
    except Exception:  # noqa: BLE001
        pass


def reindex_vault(vault_dir: Optional[Path] = None) -> dict:
    """全量重建索引。返回 {notes, chunks}。"""
    vault = Path(vault_dir) if vault_dir else _VAULT_DIR
    if not _ensure():
        return {"notes": 0, "chunks": 0, "error": _init_error}
    try:
        _collection.delete(where={"note": {"$ne": ""}})  # 清空
    except Exception:  # noqa: BLE001
        pass
    notes = chunks = 0
    for f in sorted(vault.glob("*.md")):
        n = index_note(f.name, f.read_text(encoding="utf-8"))
        if n:
            notes += 1
            chunks += n
    return {"notes": notes, "chunks": chunks}


def search(query: str, k: int = 5) -> list[dict]:
    """语义检索:返回 [{note, title, section, snippet, score}],按相关度降序。"""
    if not query.strip() or not _ensure():
        return []
    try:
        res = _collection.query(query_texts=[query.strip()], n_results=max(1, min(k, 20)))
    except Exception as e:  # noqa: BLE001
        _init_error = f"query failed: {e}"
        return []
    out = []
    docs = (res.get("documents") or [[]])[0]
    metas = (res.get("metadatas") or [[]])[0]
    dists = (res.get("distances") or [[]])[0]
    for doc, meta, dist in zip(docs, metas, dists):
        out.append(
            {
                "note": meta.get("note", ""),
                "title": meta.get("note_title", ""),
                "section": meta.get("section", ""),
                "snippet": doc[:160].replace("\n", " "),
                "score": round(1 - float(dist), 3),  # cosine distance → 相似度
            }
        )
    return out
