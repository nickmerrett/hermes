#!/usr/bin/env python3
"""Diagnose embedding issues - check if embeddings are corrupted"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import SessionLocal
from app.models.database import IntelligenceItem
from app.core.vector_store import get_vector_store
from app.utils.clustering import cosine_similarity
from app.utils.text_cleaning import clean_text_for_embedding
import numpy as np


def diagnose_embeddings(item_ids: list):
    """Check if stored embeddings match what we'd generate fresh"""
    db = SessionLocal()
    vector_store = get_vector_store()

    print(f"\n{'='*60}")
    print("EMBEDDING DIAGNOSTICS")
    print(f"{'='*60}\n")

    items_data = []

    for item_id in item_ids:
        item = db.query(IntelligenceItem).filter(IntelligenceItem.id == item_id).first()
        if not item:
            print(f"Item {item_id}: NOT FOUND")
            continue

        # Get stored embedding
        stored_emb = vector_store.get_embedding(item_id)

        # Get stored document from ChromaDB
        try:
            result = vector_store.collection.get(
                ids=[str(item_id)],
                include=['documents', 'embeddings']
            )
            stored_doc = result['documents'][0] if result['documents'] else None
        except Exception:
            stored_doc = None

        # Generate fresh embedding from title+content (with markup stripped)
        text_for_embedding = clean_text_for_embedding(item.title, item.content)
        fresh_emb = vector_store.embedding_model.encode(text_for_embedding).tolist()

        # Generate title-only embedding for comparison
        title_emb = vector_store.embedding_model.encode(item.title).tolist()

        print(f"Item {item_id}: {item.title[:60]}...")
        print(f"  Source: {item.source_type}")
        print(f"  Content length: {len(item.content or '')} chars")
        print(f"  Stored doc length: {len(stored_doc or '')} chars")

        if stored_emb:
            print(f"  Stored embedding dim: {len(stored_emb)}")
            print(f"  Stored embedding norm: {np.linalg.norm(stored_emb):.4f}")
            print(f"  Fresh embedding norm: {np.linalg.norm(fresh_emb):.4f}")

            # Check if stored matches fresh
            stored_vs_fresh = cosine_similarity(stored_emb, fresh_emb)
            print(f"  Stored vs Fresh similarity: {stored_vs_fresh:.4f}")

            if stored_vs_fresh < 0.99:
                print("  ⚠️  MISMATCH! Stored embedding doesn't match fresh generation")
        else:
            print("  ⚠️  NO STORED EMBEDDING")

        items_data.append({
            'id': item_id,
            'title': item.title,
            'stored_emb': stored_emb,
            'fresh_emb': fresh_emb,
            'title_emb': title_emb,
            'content_len': len(item.content or '')
        })
        print()

    # Pairwise comparison
    print(f"\n{'='*60}")
    print("PAIRWISE SIMILARITY COMPARISON")
    print(f"{'='*60}\n")

    for i in range(len(items_data)):
        for j in range(i + 1, len(items_data)):
            a = items_data[i]
            b = items_data[j]

            print(f"Items {a['id']} vs {b['id']}:")
            print(f"  A: {a['title'][:50]}...")
            print(f"  B: {b['title'][:50]}...")

            if a['stored_emb'] and b['stored_emb']:
                stored_sim = cosine_similarity(a['stored_emb'], b['stored_emb'])
                print(f"  Stored embedding similarity: {stored_sim:.4f}")

            fresh_sim = cosine_similarity(a['fresh_emb'], b['fresh_emb'])
            print(f"  Fresh embedding similarity:  {fresh_sim:.4f}")

            title_sim = cosine_similarity(a['title_emb'], b['title_emb'])
            print(f"  Title-only similarity:       {title_sim:.4f}")

            print()

    db.close()


if __name__ == "__main__":
    # Default: check the Rio Tinto CBA deal items
    default_ids = [4651, 4650, 4639, 4587, 4582, 4564]

    if len(sys.argv) > 1:
        item_ids = [int(x) for x in sys.argv[1:]]
    else:
        item_ids = default_ids
        print(f"Usage: python {sys.argv[0]} <item_id1> <item_id2> ...")
        print(f"Using default IDs: {default_ids}")

    diagnose_embeddings(item_ids)
