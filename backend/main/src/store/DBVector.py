"""
ChromaDB Vector Store CRUD Manager for Deep Researcher.
Mirrors the design of `SQLiteManager` in `DBManager.py`.
Exports a singleton `db_vector_manager` for SDK-style import.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Union
import logging
import sys

# ------------------------------------------------------------------
# Path bootstrap
# ------------------------------------------------------------------
BASE_DIR = Path(__file__).parent          # .../store/
src_dir = BASE_DIR.parent                # .../src/

for _p in [str(src_dir), str(src_dir.parent)]:
    if _p not in sys.path:
        sys.path.append(_p)

from main.src.utils.DRLogger import dr_logger
from main.src.utils.versionManagement import getAppVersion

try:
    import chromadb
    _CHROMA_AVAILABLE = True
except ImportError:
    _CHROMA_AVAILABLE = False

logging.basicConfig(level=logging.INFO)
_std_logger = logging.getLogger(__name__)


def _log_db_event(level: str, message: str, urgency: str = "none") -> None:
    """
    ## Description

    Global helper to emit log entries to the standard Python logger and `DRLogger`.

    ## Parameters

    - `level` (`str`) — `"info"`, `"success"`, or `"error"`.
    - `message` (`str`) — Event description.
    - `urgency` (`str`) — `"none"`, `"moderate"`, or `"critical"`. Defaults to `"none"`.
    """
    if level == "error":
        _std_logger.error(message)
    else:
        _std_logger.info(message)

    try:
        dr_logger.log(
            log_type=level,
            message=message,
            origin="system",
            module="DB",
            urgency=urgency,  # type: ignore
            app_version=getAppVersion(),
        )
    except Exception as e:
        _std_logger.error(f"DRLogger internal failure in DBVectorManager: {e}")


class DBVectorManager:
    """
    ## Description

    Reusable CRUD manager for a ChromaDB persistent vector collection.
    All methods accept structured Python arguments — no raw query strings.
    All methods return `{"success": bool, "message": str, "data": any | None}`.

    ## Parameters

    - `persist_directory` (`Union[str, Path]`)
      - Description: Path where ChromaDB stores data on disk.
      - Constraints: Must be a writable directory path.
      - Example: `"backend/main/src/store/database/chroma_store"`

    - `collection_name` (`str`)
      - Description: Name of the ChromaDB collection to manage.
      - Constraints: Non-empty string; alphanumeric + underscores.
      - Example: `"research_documents"`

    ## Returns

    `None`

    ## Raises

    - `RuntimeError` — when `chromadb` is not installed.

    ## Side Effects

    - Opens or creates a persistent ChromaDB client at `persist_directory`.
    - Gets or creates the collection automatically on instantiation.

    ## Debug Notes

    - Install chromadb via `uv add chromadb` if import fails.

    ## Customization

    - Pass a custom `embedding_function` to `get_or_create_collection` for non-default embeddings.
    """

    def __init__(self, persist_directory: Union[str, Path], collection_name: str) -> None:
        if not _CHROMA_AVAILABLE:
            error_msg = "chromadb is not installed. Run: uv add chromadb"
            _std_logger.error(error_msg)
            try:
                _log_db_event("error", error_msg, "critical")
            except Exception:
                pass
            raise RuntimeError(error_msg)

        self.persist_directory = str(persist_directory)
        self.collection_name = collection_name
        self._client = chromadb.PersistentClient(path=self.persist_directory)
        self._collection = self._client.get_or_create_collection(name=self.collection_name)

    def _log(self, level: str, message: str, urgency: str = "none") -> None:
        """
        ## Description

        Instance-level wrapper for global `_log_db_event`.
        Preserves existing API for methods within this class.
        """
        _log_db_event(level, message, urgency)

    def add(
        self,
        ids: List[str],
        documents: Optional[List[str]] = None,
        metadatas: Optional[List[Dict[str, Any]]] = None,
        embeddings: Optional[List[List[float]]] = None,
    ) -> Dict[str, Any]:
        """
        ## Description

        Adds one or more documents to the collection. Equivalent to INSERT.

        ## Parameters

        - `ids` (`List[str]`)
          - Description: Unique string identifiers, one per document.
          - Constraints: Non-empty. Each ID must be unique within the collection.
          - Example: `["doc-001", "doc-002"]`

        - `documents` (`Optional[List[str]]`)
          - Description: Raw text content; ChromaDB auto-embeds.
          - Constraints: Length must match `ids`.
          - Example: `["Deep learning is a subset of ML."]`

        - `metadatas` (`Optional[List[Dict[str, Any]]]`)
          - Description: Key-value metadata for filtering.
          - Constraints: Values must be `str`, `int`, `float`, or `bool`.
          - Example: `[{"source": "arxiv", "year": 2024}]`

        - `embeddings` (`Optional[List[List[float]]]`)
          - Description: Pre-computed vectors; skips ChromaDB's default embedding.
          - Constraints: Length must match `ids`.
          - Example: `[[0.1, 0.2, ...]]`

        ## Returns

        `dict`

        ```json
        { "success": true, "message": "2 document(s) added to collection '...'", "data": { "count": 2 } }
        { "success": false, "message": "ID already exists.", "data": null }
        ```

        ## Raises

        - `None` — all exceptions caught internally.

        ## Side Effects

        - Persists documents to disk. Logs via `DRLogger`.

        ## Debug Notes

        - Duplicate IDs raise `IDAlreadyExistsError`. Use `update()` to modify existing docs.

        ## Customization

        - For upsert semantics, extend to call `_collection.upsert()`.
        """
        if not ids:
            msg = "ids must be a non-empty list."
            self._log("error", msg, "moderate")
            return {"success": False, "message": msg, "data": None}

        try:
            # Check for existing IDs — chromadb 1.5.2+ silently ignores duplicates
            existing = self._collection.get(ids=ids)
            if existing.get("ids"):
                found = existing["ids"][0]
                msg = f"ID '{found}' already exists."
                self._log("error", msg, "moderate")
                return {"success": False, "message": msg, "data": None}

            kwargs: Dict[str, Any] = {"ids": ids}
            if documents is not None:
                kwargs["documents"] = documents
            if metadatas is not None:
                kwargs["metadatas"] = metadatas
            if embeddings is not None:
                kwargs["embeddings"] = embeddings

            self._collection.add(**kwargs)
            count = len(ids)
            self._log("success", f"Added {count} document(s) to '{self.collection_name}'.")
            return {
                "success": True,
                "message": f"{count} document(s) added to collection '{self.collection_name}'",
                "data": {"count": count},
            }
        except Exception as e:
            self._log("error", f"Error adding to '{self.collection_name}': {e}", "moderate")
            return {"success": False, "message": str(e), "data": None}

    def fetch_all(
        self,
        where: Optional[Dict[str, Any]] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        ## Description

        Retrieves documents from the collection with optional metadata filtering.
        Equivalent to SELECT * (with optional WHERE).

        ## Parameters

        - `where` (`Optional[Dict[str, Any]]`)
          - Description: Metadata equality filter. `None` fetches all.
          - Constraints: Values must be `str`, `int`, `float`, or `bool`.
          - Example: `{"source": "arxiv"}`

        - `limit` (`Optional[int]`)
          - Description: Max documents to return.
          - Constraints: Must be >= 1 if provided.
          - Example: `50`

        - `offset` (`Optional[int]`)
          - Description: Documents to skip (for pagination).
          - Constraints: Must be >= 0 if provided.
          - Example: `10`

        ## Returns

        `dict`

        ```json
        {
            "success": true,
            "message": "Fetched 3 document(s) from collection '...'",
            "data": { "ids": [...], "documents": [...], "metadatas": [...], "embeddings": null }
        }
        ```

        ## Raises

        - `None` — all exceptions caught internally.

        ## Side Effects

        - None (read-only).

        ## Debug Notes

        - `embeddings` are excluded from the response by default (heavy payload).

        ## Customization

        - Add `"embeddings"` to the `include` list inside `.get()` if raw vectors are needed.
        """
        try:
            kwargs: Dict[str, Any] = {"include": ["documents", "metadatas"]}
            if where is not None:
                kwargs["where"] = where
            if limit is not None:
                kwargs["limit"] = limit
            if offset is not None:
                kwargs["offset"] = offset

            result = self._collection.get(**kwargs)
            ids = result.get("ids", [])
            self._log("success", f"Fetched {len(ids)} document(s) from '{self.collection_name}'.")
            return {
                "success": True,
                "message": f"Fetched {len(ids)} document(s) from collection '{self.collection_name}'",
                "data": {
                    "ids": ids,
                    "documents": result.get("documents"),
                    "metadatas": result.get("metadatas"),
                    "embeddings": None,
                },
            }
        except Exception as e:
            self._log("error", f"Error fetching from '{self.collection_name}': {e}", "moderate")
            return {"success": False, "message": str(e), "data": None}

    def fetch_one(self, id: str) -> Dict[str, Any]:
        """
        ## Description

        Retrieves a single document by its unique string ID.
        Equivalent to SELECT * WHERE id = '...' LIMIT 1.

        ## Parameters

        - `id` (`str`)
          - Description: Unique identifier of the document to retrieve.
          - Constraints: Non-empty string previously used in `add()`.
          - Example: `"doc-001"`

        ## Returns

        `dict`

        ```json
        { "success": true, "message": "Document 'doc-001' fetched successfully", "data": { "id": "doc-001", "document": "...", "metadata": {} } }
        { "success": true, "message": "Document 'doc-001' not found in collection", "data": null }
        { "success": false, "message": "ChromaDB error", "data": null }
        ```

        ## Raises

        - `None` — all exceptions caught internally.

        ## Side Effects

        - None (read-only).

        ## Debug Notes

        - Missing ID → `success: true, data: null` (not an error — document simply doesn't exist).

        ## Customization

        - Add `"embeddings"` to the `include` list to return raw vectors.
        """
        if not id:
            msg = "id must be a non-empty string."
            self._log("error", msg, "moderate")
            return {"success": False, "message": msg, "data": None}

        try:
            result = self._collection.get(ids=[id], include=["documents", "metadatas"])
            ids = result.get("ids", [])

            if not ids:
                msg = f"Document '{id}' not found in collection '{self.collection_name}'"
                self._log("info", msg)  # Not an error, just not found
                return {
                    "success": True,
                    "message": msg,
                    "data": None,
                }

            docs = result.get("documents") or [None]
            metas = result.get("metadatas") or [None]
            self._log("success", f"Document '{id}' fetched from '{self.collection_name}'.")
            return {
                "success": True,
                "message": f"Document '{id}' fetched successfully",
                "data": {"id": ids[0], "document": docs[0], "metadata": metas[0]},
            }
        except Exception as e:
            self._log("error", f"Error fetching '{id}' from '{self.collection_name}': {e}", "moderate")
            return {"success": False, "message": str(e), "data": None}

    def update(
        self,
        ids: List[str],
        documents: Optional[List[str]] = None,
        metadatas: Optional[List[Dict[str, Any]]] = None,
        embeddings: Optional[List[List[float]]] = None,
    ) -> Dict[str, Any]:
        """
        ## Description

        Updates existing documents by their IDs. Equivalent to UPDATE WHERE id IN (...).
        Only the fields provided are overwritten.

        ## Parameters

        - `ids` (`List[str]`)
          - Description: IDs of documents to update.
          - Constraints: Non-empty. IDs should already exist in the collection.
          - Example: `["doc-001"]`

        - `documents` (`Optional[List[str]]`)
          - Description: Replacement text; triggers re-embedding.
          - Constraints: Length must match `ids`.
          - Example: `["Updated text."]`

        - `metadatas` (`Optional[List[Dict[str, Any]]]`)
          - Description: Replacement metadata (full overwrite, not a merge).
          - Constraints: Values must be `str`, `int`, `float`, or `bool`.
          - Example: `[{"version": 2}]`

        - `embeddings` (`Optional[List[List[float]]]`)
          - Description: Replacement embedding vectors.
          - Constraints: Length must match `ids`.
          - Example: `[[0.5, 0.6, ...]]`

        ## Returns

        `dict`

        ```json
        { "success": true, "message": "1 document(s) updated in collection '...'", "data": { "count": 1 } }
        { "success": false, "message": "Update requires at least one of: documents, metadatas, embeddings.", "data": null }
        ```

        ## Raises

        - `None` — all exceptions caught internally.

        ## Side Effects

        - Overwrites document fields in persistent storage. Logs via `DRLogger`.

        ## Debug Notes

        - Non-existent IDs are silently skipped by ChromaDB — no error is raised.

        ## Customization

        - For upsert (add if missing), call `_collection.upsert()` directly.
        """
        if not ids:
            msg = "ids must be a non-empty list."
            self._log("error", msg, "moderate")
            return {"success": False, "message": msg, "data": None}

        if documents is None and metadatas is None and embeddings is None:
            msg = "Update requires at least one of: documents, metadatas, embeddings."
            self._log("error", msg, "moderate")
            return {
                "success": False,
                "message": msg,
                "data": None,
            }

        try:
            kwargs: Dict[str, Any] = {"ids": ids}
            if documents is not None:
                kwargs["documents"] = documents
            if metadatas is not None:
                kwargs["metadatas"] = metadatas
            if embeddings is not None:
                kwargs["embeddings"] = embeddings

            self._collection.update(**kwargs)
            count = len(ids)
            self._log("success", f"Updated {count} document(s) in '{self.collection_name}'.")
            return {
                "success": True,
                "message": f"{count} document(s) updated in collection '{self.collection_name}'",
                "data": {"count": count},
            }
        except Exception as e:
            self._log("error", f"Error updating '{self.collection_name}': {e}", "moderate")
            return {"success": False, "message": str(e), "data": None}

    def delete(self, ids: List[str]) -> Dict[str, Any]:
        """
        ## Description

        Permanently removes documents by their IDs.
        Equivalent to DELETE WHERE id IN (...).
        `ids` is required — there is no "delete all" semantic by design.

        ## Parameters

        - `ids` (`List[str]`)
          - Description: IDs of documents to delete.
          - Constraints: Non-empty list. Non-existent IDs are silently skipped.
          - Example: `["doc-001", "doc-002"]`

        ## Returns

        `dict`

        ```json
        { "success": true, "message": "2 document(s) deleted from collection '...'", "data": { "count": 2 } }
        { "success": false, "message": "delete() requires a non-empty ids list.", "data": null }
        ```

        ## Raises

        - `None` — all exceptions caught internally.

        ## Side Effects

        - Irreversibly removes vectors and metadata from storage. Logs via `DRLogger`.

        ## Debug Notes

        - Deletion is permanent. Use metadata soft-delete if recoverability is needed.

        ## Customization

        - For metadata-based bulk deletions, extend to call `_collection.delete(where={...})`.
        """
        if not ids:
            msg = "delete() requires a non-empty ids list."
            self._log("error", msg, "moderate")
            return {
                "success": False,
                "message": msg,
                "data": None,
            }

        try:
            self._collection.delete(ids=ids)
            count = len(ids)
            self._log("success", f"Deleted {count} document(s) from '{self.collection_name}'.")
            return {
                "success": True,
                "message": f"{count} document(s) deleted from collection '{self.collection_name}'",
                "data": {"count": count},
            }
        except Exception as e:
            self._log("error", f"Error deleting from '{self.collection_name}': {e}", "moderate")
            return {"success": False, "message": str(e), "data": None}

    def collection_exists(self) -> Dict[str, Any]:
        """
        ## Description

        Health-check: verifies the collection is accessible and returns its document count.

        ## Parameters

        - `None`

        ## Returns

        `dict`

        ```json
        { "success": true, "message": "Collection '...' exists and is accessible", "data": { "collection_name": "...", "count": 42 } }
        { "success": false, "message": "Collection '...' is not accessible: ...", "data": null }
        ```

        ## Raises

        - `None` — all exceptions caught internally.

        ## Side Effects

        - None (read-only).

        ## Debug Notes

        - `count: 0` means the collection is empty, not missing.

        ## Customization

        - Use `count` to drive pagination decisions in `fetch_all()`.
        """
        try:
            count = self._collection.count()
            return {
                "success": True,
                "message": f"Collection '{self.collection_name}' exists and is accessible",
                "data": {"collection_name": self.collection_name, "count": count},
            }
        except Exception as e:
            self._log("error", f"Collection '{self.collection_name}' not accessible: {e}", "critical")
            return {
                "success": False,
                "message": f"Collection '{self.collection_name}' is not accessible: {e}",
                "data": None,
            }


def _initialize_chroma_store() -> None:
    """
    ## Description

    Ensures `database/chroma_store/` exists on disk. Runs on module import.

    ## Parameters

    - `None`

    ## Returns

    `None`

    ## Raises

    - `None` — failures are logged and swallowed so import always succeeds.

    ## Side Effects

    - Creates `store/database/chroma_store/` if absent. Logs via `DRLogger`.

    ## Debug Notes

    - Verify the process has write access to `backend/main/src/store/database/`.

    ## Customization

    - Adjust the `chroma_store_dir` path if the project layout changes.
    """
    chroma_store_dir = BASE_DIR / "database" / "chroma_store"
    try:
        chroma_store_dir.mkdir(parents=True, exist_ok=True)
        _log_db_event("success", f"ChromaDB storage directory ensured: {chroma_store_dir}")
    except Exception as e:
        _std_logger.error(f"Failed to initialize ChromaDB store directory: {e}")
        try:
            _log_db_event("error", f"Failed to initialize ChromaDB store directory: {e}", "critical")
        except Exception:
            pass


# Run on import
if not any("unittest" in arg for arg in sys.argv) and not any("pytest" in arg for arg in sys.argv):
     _initialize_chroma_store()

# Singleton export — SDK-style, mirrors DBManager pattern
_chroma_store_path = BASE_DIR / "database" / "chroma_store"

if _CHROMA_AVAILABLE:
    # This instantiation triggers two things:
    # 1. chromadb.PersistentClient(...) -> Creates the folder/database if missing.
    # 2. get_or_create_collection(...)  -> Creates the specific collection if missing.
    db_vector_manager = DBVectorManager(
        persist_directory=_chroma_store_path,
        collection_name="research_documents",
    )
else:
    db_vector_manager = None  # type: ignore
