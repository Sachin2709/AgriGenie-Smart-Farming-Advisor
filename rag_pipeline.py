"""
AgriGenie AI – RAG Pipeline
============================
Retrieval-Augmented Generation using FAISS (primary) or ChromaDB (alternate).
Indexes the local agricultural knowledge base and retrieves relevant context
for the watsonx.ai Granite model.
"""

import os
import glob
import logging
import pickle
from pathlib import Path
from typing import List, Tuple, Optional

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────
#  Configuration from .env
# ──────────────────────────────────────────────────────────
VECTOR_STORE      = os.getenv("VECTOR_STORE", "faiss").lower()
KB_DIR            = os.getenv("KNOWLEDGE_BASE_DIR", "knowledge_base")
EMBEDDING_MODEL   = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
CHUNK_SIZE        = int(os.getenv("CHUNK_SIZE", "512"))
CHUNK_OVERLAP     = int(os.getenv("CHUNK_OVERLAP", "64"))
TOP_K             = int(os.getenv("TOP_K_RESULTS", "5"))
INDEX_PATH        = "instance/faiss_index"
CHROMA_PATH       = "instance/chroma_db"


# ──────────────────────────────────────────────────────────
#  Text Chunking Helper
# ──────────────────────────────────────────────────────────
def chunk_text(text: str, chunk_size: int = CHUNK_SIZE,
               overlap: int = CHUNK_OVERLAP) -> List[str]:
    """Split text into overlapping chunks by word boundaries."""
    words = text.split()
    chunks = []
    start = 0
    while start < len(words):
        end = min(start + chunk_size, len(words))
        chunk = " ".join(words[start:end])
        if chunk.strip():
            chunks.append(chunk)
        if end >= len(words):
            break
        start += chunk_size - overlap
    return chunks


# ──────────────────────────────────────────────────────────
#  Document Loader
# ──────────────────────────────────────────────────────────
def load_knowledge_base(kb_dir: str = KB_DIR) -> Tuple[List[str], List[dict]]:
    """
    Load all .txt/.md files from the knowledge base directory.
    Returns (chunks, metadatas) lists.
    """
    all_chunks: List[str] = []
    all_metas:  List[dict] = []

    kb_path = Path(kb_dir)
    if not kb_path.exists():
        logger.warning(f"Knowledge base directory not found: {kb_dir}")
        return [], []

    files = list(kb_path.glob("*.txt")) + list(kb_path.glob("*.md"))
    if not files:
        logger.warning("No knowledge base files found.")
        return [], []

    logger.info(f"Loading {len(files)} knowledge base files…")
    for file_path in files:
        try:
            text = file_path.read_text(encoding="utf-8", errors="ignore")
            chunks = chunk_text(text)
            for i, chunk in enumerate(chunks):
                all_chunks.append(chunk)
                all_metas.append({
                    "source": file_path.name,
                    "chunk_id": i,
                    "topic": file_path.stem.replace("_", " ").title()
                })
        except Exception as exc:
            logger.error(f"Error loading {file_path}: {exc}")

    logger.info(f"Loaded {len(all_chunks)} chunks from {len(files)} files")
    return all_chunks, all_metas


# ──────────────────────────────────────────────────────────
#  FAISS Vector Store
# ──────────────────────────────────────────────────────────
class FAISSVectorStore:
    def __init__(self):
        self.index = None
        self.chunks: List[str] = []
        self.metas:  List[dict] = []
        self.embedder = None
        self._load_embedder()

    def _load_embedder(self):
        try:
            from sentence_transformers import SentenceTransformer
            self.embedder = SentenceTransformer(EMBEDDING_MODEL)
            logger.info(f"Embedding model loaded: {EMBEDDING_MODEL}")
        except Exception as exc:
            logger.error(f"Failed to load embedding model: {exc}")
            self.embedder = None

    def build_index(self, chunks: List[str], metas: List[dict]):
        """Build FAISS index from text chunks."""
        if not chunks or self.embedder is None:
            return
        try:
            import faiss
            import numpy as np
            embeddings = self.embedder.encode(chunks, show_progress_bar=False,
                                               batch_size=32)
            embeddings = embeddings.astype("float32")
            dim = embeddings.shape[1]
            self.index = faiss.IndexFlatIP(dim)   # Inner product (cosine after normalise)
            faiss.normalize_L2(embeddings)
            self.index.add(embeddings)
            self.chunks = chunks
            self.metas  = metas
            self._save_index()
            logger.info(f"FAISS index built with {self.index.ntotal} vectors (dim={dim})")
        except Exception as exc:
            logger.error(f"Error building FAISS index: {exc}")

    def _save_index(self):
        os.makedirs(INDEX_PATH, exist_ok=True)
        try:
            import faiss, numpy as np
            faiss.write_index(self.index, f"{INDEX_PATH}/index.faiss")
            with open(f"{INDEX_PATH}/chunks.pkl", "wb") as f:
                pickle.dump((self.chunks, self.metas), f)
            logger.info("FAISS index saved to disk")
        except Exception as exc:
            logger.error(f"Error saving FAISS index: {exc}")

    def load_index(self) -> bool:
        try:
            import faiss
            idx_file = f"{INDEX_PATH}/index.faiss"
            pkl_file = f"{INDEX_PATH}/chunks.pkl"
            if not (os.path.exists(idx_file) and os.path.exists(pkl_file)):
                return False
            self.index = faiss.read_index(idx_file)
            with open(pkl_file, "rb") as f:
                self.chunks, self.metas = pickle.load(f)
            logger.info(f"FAISS index loaded: {self.index.ntotal} vectors")
            return True
        except Exception as exc:
            logger.error(f"Error loading FAISS index: {exc}")
            return False

    def search(self, query: str, top_k: int = TOP_K) -> List[Tuple[str, dict, float]]:
        """Returns list of (chunk, metadata, score) tuples."""
        if self.index is None or self.embedder is None:
            return []
        try:
            import faiss, numpy as np
            qvec = self.embedder.encode([query]).astype("float32")
            faiss.normalize_L2(qvec)
            scores, indices = self.index.search(qvec, min(top_k, self.index.ntotal))
            results = []
            for score, idx in zip(scores[0], indices[0]):
                if idx >= 0:
                    results.append((self.chunks[idx], self.metas[idx], float(score)))
            return results
        except Exception as exc:
            logger.error(f"FAISS search error: {exc}")
            return []


# ──────────────────────────────────────────────────────────
#  ChromaDB Vector Store
# ──────────────────────────────────────────────────────────
class ChromaVectorStore:
    COLLECTION = "agrigenie_kb"

    def __init__(self):
        self.client = None
        self.collection = None
        self._init_client()

    def _init_client(self):
        try:
            import chromadb
            from chromadb.config import Settings
            self.client = chromadb.PersistentClient(path=CHROMA_PATH)
            self.collection = self.client.get_or_create_collection(
                name=self.COLLECTION,
                metadata={"hnsw:space": "cosine"}
            )
            logger.info("ChromaDB client initialised")
        except Exception as exc:
            logger.error(f"ChromaDB init error: {exc}")

    def build_index(self, chunks: List[str], metas: List[dict]):
        if not self.collection:
            return
        try:
            # Clear existing and re-add
            try:
                self.client.delete_collection(self.COLLECTION)
            except Exception:
                pass
            self.collection = self.client.get_or_create_collection(
                self.COLLECTION,
                metadata={"hnsw:space": "cosine"}
            )
            ids = [f"doc_{i}" for i in range(len(chunks))]
            batch_size = 100
            for i in range(0, len(chunks), batch_size):
                self.collection.add(
                    documents=chunks[i:i+batch_size],
                    metadatas=metas[i:i+batch_size],
                    ids=ids[i:i+batch_size]
                )
            logger.info(f"ChromaDB index built with {len(chunks)} documents")
        except Exception as exc:
            logger.error(f"Error building ChromaDB index: {exc}")

    def load_index(self) -> bool:
        if self.collection and self.collection.count() > 0:
            logger.info(f"ChromaDB has {self.collection.count()} documents")
            return True
        return False

    def search(self, query: str, top_k: int = TOP_K) -> List[Tuple[str, dict, float]]:
        if not self.collection:
            return []
        try:
            results = self.collection.query(
                query_texts=[query],
                n_results=min(top_k, self.collection.count())
            )
            output = []
            if results and results["documents"]:
                for doc, meta, dist in zip(
                    results["documents"][0],
                    results["metadatas"][0],
                    results["distances"][0]
                ):
                    score = 1.0 - dist  # convert distance to similarity
                    output.append((doc, meta, score))
            return output
        except Exception as exc:
            logger.error(f"ChromaDB search error: {exc}")
            return []


# ──────────────────────────────────────────────────────────
#  RAG Manager (singleton)
# ──────────────────────────────────────────────────────────
class RAGManager:
    def __init__(self):
        self._store = None
        self._initialized = False

    def initialize(self, force_rebuild: bool = False):
        """Initialize the vector store; rebuild index if needed."""
        if self._initialized and not force_rebuild:
            return

        logger.info(f"Initializing RAG pipeline (backend: {VECTOR_STORE})")

        if VECTOR_STORE == "chroma":
            self._store = ChromaVectorStore()
        else:
            self._store = FAISSVectorStore()

        # Try loading existing index
        loaded = not force_rebuild and self._store.load_index()

        if not loaded:
            logger.info("Building new vector index from knowledge base…")
            chunks, metas = load_knowledge_base()
            if chunks:
                self._store.build_index(chunks, metas)
            else:
                logger.warning("No documents to index; RAG will be disabled")

        self._initialized = True

    def retrieve(self, query: str, top_k: int = TOP_K) -> str:
        """
        Retrieve relevant context from the knowledge base for a query.
        Returns a formatted context string to be injected into the LLM prompt.
        """
        if not self._initialized:
            self.initialize()

        if self._store is None:
            return ""

        results = self._store.search(query, top_k=top_k)
        if not results:
            return ""

        parts = []
        for i, (chunk, meta, score) in enumerate(results, 1):
            topic = meta.get("topic", "Agricultural Knowledge")
            parts.append(f"[Source {i}: {topic}]\n{chunk}")

        return "\n\n".join(parts)

    def rebuild(self):
        """Force rebuild the index."""
        self._initialized = False
        self.initialize(force_rebuild=True)

    @property
    def is_ready(self) -> bool:
        return self._initialized


# Global singleton
rag_manager = RAGManager()
