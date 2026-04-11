"""
Unit tests for app/core/vector_store.py

Focuses on the VectorStore methods that interact with ChromaDB,
using mocked ChromaDB collections so no real model or disk I/O is needed.
"""

import pytest
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_vector_store():
    """Return a VectorStore with all heavy dependencies mocked out."""
    with patch('app.core.vector_store.chromadb.PersistentClient'), \
         patch('app.core.vector_store.SentenceTransformer'), \
         patch('app.core.vector_store.os.makedirs'):
        from app.core.vector_store import VectorStore
        vs = VectorStore.__new__(VectorStore)
        vs.collection = MagicMock()
        vs.embedding_model = MagicMock()
        return vs


# ---------------------------------------------------------------------------
# get_embeddings_batch
# ---------------------------------------------------------------------------

class TestGetEmbeddingsBatch:
    """Tests for VectorStore.get_embeddings_batch."""

    def test_empty_ids_returns_empty_dict(self):
        """Passing an empty list should short-circuit and return {} without querying ChromaDB."""
        vs = _make_vector_store()
        result = vs.get_embeddings_batch([])
        assert result == {}
        vs.collection.get.assert_not_called()

    def test_returns_dict_keyed_by_int_id(self):
        """Result keys should be ints matching the input item IDs."""
        vs = _make_vector_store()
        vs.collection.get.return_value = {
            'ids': ['1', '2', '3'],
            'embeddings': [[1.0, 0.0], [0.0, 1.0], [0.5, 0.5]],
        }

        result = vs.get_embeddings_batch([1, 2, 3])

        assert set(result.keys()) == {1, 2, 3}
        assert result[1] == [1.0, 0.0]
        assert result[2] == [0.0, 1.0]
        assert result[3] == [0.5, 0.5]

    def test_single_chromadb_call_for_multiple_ids(self):
        """ChromaDB collection.get must be called exactly once regardless of id count."""
        vs = _make_vector_store()
        vs.collection.get.return_value = {
            'ids': ['10', '20', '30', '40', '50'],
            'embeddings': [[float(i)] * 3 for i in range(5)],
        }

        vs.get_embeddings_batch([10, 20, 30, 40, 50])

        vs.collection.get.assert_called_once()

    def test_ids_passed_as_strings_to_chromadb(self):
        """ChromaDB expects string IDs; verify conversion happens correctly."""
        vs = _make_vector_store()
        vs.collection.get.return_value = {'ids': [], 'embeddings': []}

        vs.get_embeddings_batch([7, 42])

        call_kwargs = vs.collection.get.call_args
        ids_arg = call_kwargs[1].get('ids') or call_kwargs[0][0]
        assert ids_arg == ['7', '42']

    def test_missing_items_omitted_from_result(self):
        """Items not found in ChromaDB (None embeddings) should be absent from result."""
        vs = _make_vector_store()
        # ChromaDB may return None for embeddings it doesn't have
        vs.collection.get.return_value = {
            'ids': ['1', '2'],
            'embeddings': [[1.0, 0.0], None],
        }

        result = vs.get_embeddings_batch([1, 2])

        assert 1 in result
        assert 2 not in result  # None embedding filtered out

    def test_chromadb_error_returns_empty_dict(self):
        """If ChromaDB raises, the method should catch and return {} rather than propagate."""
        vs = _make_vector_store()
        vs.collection.get.side_effect = Exception("ChromaDB unavailable")

        result = vs.get_embeddings_batch([1, 2, 3])

        assert result == {}

    def test_no_results_returns_empty_dict(self):
        """When ChromaDB returns no results, return empty dict."""
        vs = _make_vector_store()
        vs.collection.get.return_value = {'ids': [], 'embeddings': []}

        result = vs.get_embeddings_batch([99, 100])

        assert result == {}


# ---------------------------------------------------------------------------
# add_item / add_items_batch — StopIteration conversion
# ---------------------------------------------------------------------------

class TestAddItemStopIteration:
    """StopIteration from ChromaDB must be re-raised as RuntimeError so it
    can propagate safely through asyncio.to_thread futures (PEP 479)."""

    def test_add_item_converts_stop_iteration(self):
        vs = _make_vector_store()
        vs.embedding_model.encode.return_value = MagicMock(tolist=lambda: [0.1, 0.2])
        vs.collection.upsert.side_effect = StopIteration("internal chroma error")

        with pytest.raises(RuntimeError, match="StopIteration"):
            vs.add_item(item_id=1, text="test", metadata={})

    def test_add_items_batch_converts_stop_iteration(self):
        vs = _make_vector_store()
        vs.embedding_model.encode.return_value = MagicMock(tolist=lambda: [[0.1, 0.2]])
        vs.collection.upsert.side_effect = StopIteration("internal chroma error")

        with pytest.raises(RuntimeError, match="StopIteration"):
            vs.add_items_batch(item_ids=[1], texts=["test"])

    def test_add_item_other_exceptions_propagate_unchanged(self):
        vs = _make_vector_store()
        vs.embedding_model.encode.return_value = MagicMock(tolist=lambda: [0.1, 0.2])
        vs.collection.upsert.side_effect = ValueError("some other error")

        with pytest.raises(ValueError):
            vs.add_item(item_id=1, text="test", metadata={})
