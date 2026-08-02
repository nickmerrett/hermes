"""MCP (Model Context Protocol) server endpoint.

Implements the MCP StreamableHTTP transport as a plain FastAPI POST endpoint.
Supports: initialize, tools/list, tools/call, ping.
Auth: JWT bearer token or hrm_ API key (handled by get_current_user dependency).
"""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timedelta
import json
import logging

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.vector_store import get_vector_store
from app.models.database import User, Customer, IntelligenceItem, ProcessedIntelligence

logger = logging.getLogger(__name__)
router = APIRouter()

_SERVER_INFO = {"name": "hermes", "version": "1.0.0"}

_TOOLS = [
    {
        "name": "list_customers",
        "description": "List all monitored customers/companies with their IDs. Use this first to get customer IDs needed by other tools.",
        "inputSchema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "search_intelligence",
        "description": (
            "Hybrid keyword + semantic search across all collected intelligence items. "
            "Returns matching items with AI-generated summaries, categories, sentiment, and priority scores."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query text"},
                "customer_id": {"type": "integer", "description": "Optional: filter by customer ID"},
                "limit": {"type": "integer", "description": "Max results 1-50 (default 20)"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_intelligence_item",
        "description": "Fetch a single intelligence item with full details: content, AI summary, entities, tags, and pain points/opportunities.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "item_id": {"type": "integer", "description": "Intelligence item ID"},
            },
            "required": ["item_id"],
        },
    },
    {
        "name": "get_analytics",
        "description": "Get platform-wide analytics: total item counts broken down by category, sentiment, and source type.",
        "inputSchema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "get_daily_summary",
        "description": "Get the last 24 hours of collected intelligence for a specific customer, including high-priority items and category breakdown.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "customer_id": {"type": "integer", "description": "Customer ID (use list_customers to get IDs)"},
            },
            "required": ["customer_id"],
        },
    },
]


def _ok(req_id, result):
    return {"jsonrpc": "2.0", "id": req_id, "result": result}


def _err(req_id, code, message):
    return {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}}


def _content(data):
    return {"content": [{"type": "text", "text": json.dumps(data, default=str, indent=2)}]}


async def _list_customers(args: dict, db: Session) -> list:
    customers = db.query(Customer).order_by(Customer.sort_order, Customer.name).all()
    return [{"id": c.id, "name": c.name, "domain": c.domain} for c in customers]


async def _search_intelligence(args: dict, db: Session) -> dict:
    query = args.get("query", "")
    customer_id = args.get("customer_id")
    limit = max(1, min(int(args.get("limit", 20)), 50))

    base_q = db.query(IntelligenceItem)
    if customer_id:
        base_q = base_q.filter(IntelligenceItem.customer_id == int(customer_id))

    pattern = f"%{query}%"
    keyword_items = base_q.filter(
        (IntelligenceItem.title.ilike(pattern)) | (IntelligenceItem.content.ilike(pattern))
    ).limit(limit * 2).all()

    scores: dict[int, float] = {}
    for item in keyword_items:
        scores[item.id] = 1.0 if query.lower() in item.title.lower() else 0.9

    try:
        vs = get_vector_store()
        where = {"customer_id": int(customer_id)} if customer_id else None
        results = vs.search(query=query, n_results=limit * 2, where=where)
        if results.get("ids") and results["ids"][0]:
            for item_id, sim in zip(results["ids"][0], results["similarities"][0]):
                iid = int(item_id)
                if sim >= 0.3:
                    boost = 1.1 if iid in scores else 1.0
                    scores[iid] = max(scores.get(iid, 0), sim * boost)
    except Exception as e:
        logger.warning(f"Vector search unavailable: {e}")

    sorted_ids = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:limit]

    output = []
    for item_id, score in sorted_ids:
        item = db.query(IntelligenceItem).filter(IntelligenceItem.id == item_id).first()
        if item:
            proc = item.processed
            output.append({
                "id": item.id,
                "title": item.title,
                "summary": proc.summary if proc else None,
                "category": proc.category if proc else None,
                "sentiment": proc.sentiment if proc else None,
                "priority_score": proc.priority_score if proc else None,
                "url": item.url,
                "published_date": item.published_date,
                "source_type": item.source_type,
                "customer_id": item.customer_id,
                "score": round(score, 3),
            })

    return {"results": output, "query": query, "total": len(output)}


async def _get_intelligence_item(args: dict, db: Session) -> dict:
    item_id = int(args.get("item_id"))
    item = db.query(IntelligenceItem).filter(IntelligenceItem.id == item_id).first()
    if not item:
        return {"error": f"Item {item_id} not found"}

    proc = item.processed
    return {
        "id": item.id,
        "title": item.title,
        "content": item.content,
        "url": item.url,
        "source_type": item.source_type,
        "customer_id": item.customer_id,
        "published_date": item.published_date,
        "collected_date": item.collected_date,
        "cluster_id": item.cluster_id,
        "is_cluster_primary": item.is_cluster_primary,
        "processing": {
            "summary": proc.summary,
            "category": proc.category,
            "sentiment": proc.sentiment,
            "priority_score": proc.priority_score,
            "entities": proc.entities,
            "tags": proc.tags,
            "pain_points_opportunities": proc.pain_points_opportunities,
        } if proc else None,
    }


async def _get_analytics(args: dict, db: Session) -> dict:
    total = db.query(IntelligenceItem).count()
    by_cat = {
        c: n for c, n in db.query(
            ProcessedIntelligence.category, func.count(ProcessedIntelligence.id)
        ).group_by(ProcessedIntelligence.category).all() if c
    }
    by_sent = {
        s: n for s, n in db.query(
            ProcessedIntelligence.sentiment, func.count(ProcessedIntelligence.id)
        ).group_by(ProcessedIntelligence.sentiment).all() if s
    }
    by_src = {
        s: n for s, n in db.query(
            IntelligenceItem.source_type, func.count(IntelligenceItem.id)
        ).group_by(IntelligenceItem.source_type).all()
    }
    yesterday = datetime.utcnow() - timedelta(days=1)
    recent = db.query(IntelligenceItem).filter(IntelligenceItem.collected_date >= yesterday).count()
    high_pri = db.query(ProcessedIntelligence).filter(ProcessedIntelligence.priority_score > 0.7).count()

    return {
        "total_items": total,
        "recent_24h": recent,
        "high_priority": high_pri,
        "by_category": by_cat,
        "by_sentiment": by_sent,
        "by_source": by_src,
    }


async def _get_daily_summary(args: dict, db: Session) -> dict:
    customer_id = int(args.get("customer_id"))
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        return {"error": f"Customer {customer_id} not found"}

    yesterday = datetime.utcnow() - timedelta(days=1)

    not_filtered = (
        IntelligenceItem.ignored.is_(False),
        IntelligenceItem.is_cluster_primary.is_(True),
        ~ProcessedIntelligence.category.in_(['unrelated', 'advertisement'])
        | ProcessedIntelligence.category.is_(None),
    )

    items = db.query(IntelligenceItem).join(
        ProcessedIntelligence, IntelligenceItem.id == ProcessedIntelligence.item_id, isouter=True
    ).filter(
        IntelligenceItem.customer_id == customer_id,
        IntelligenceItem.collected_date >= yesterday,
        *not_filtered,
    ).order_by(
        ProcessedIntelligence.priority_score.desc().nullslast(),
        IntelligenceItem.collected_date.desc(),
    ).limit(20).all()

    by_cat = {
        c: n for c, n in db.query(
            ProcessedIntelligence.category, func.count(ProcessedIntelligence.id)
        ).join(
            IntelligenceItem, IntelligenceItem.id == ProcessedIntelligence.item_id
        ).filter(
            IntelligenceItem.customer_id == customer_id,
            IntelligenceItem.collected_date >= yesterday,
            *not_filtered,
        ).group_by(ProcessedIntelligence.category).all() if c
    }

    high_pri = db.query(IntelligenceItem).join(
        ProcessedIntelligence, IntelligenceItem.id == ProcessedIntelligence.item_id
    ).filter(
        IntelligenceItem.customer_id == customer_id,
        IntelligenceItem.collected_date >= yesterday,
        ProcessedIntelligence.priority_score >= 0.7,
        *not_filtered,
    ).count()

    return {
        "customer_id": customer_id,
        "customer_name": customer.name,
        "period": "last_24_hours",
        "total_items": len(items),
        "high_priority_count": high_pri,
        "by_category": by_cat,
        "items": [
            {
                "id": item.id,
                "title": item.title,
                "summary": item.processed.summary if item.processed else None,
                "category": item.processed.category if item.processed else None,
                "priority_score": item.processed.priority_score if item.processed else None,
                "sentiment": item.processed.sentiment if item.processed else None,
                "url": item.url,
                "source_type": item.source_type,
                "collected_date": item.collected_date,
            }
            for item in items
        ],
    }


_HANDLERS = {
    "list_customers": _list_customers,
    "search_intelligence": _search_intelligence,
    "get_intelligence_item": _get_intelligence_item,
    "get_analytics": _get_analytics,
    "get_daily_summary": _get_daily_summary,
}


@router.post("")
async def mcp_endpoint(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """MCP StreamableHTTP endpoint. Accepts JSON-RPC 2.0 requests."""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Parse error"}})

    req_id = body.get("id")
    method = body.get("method", "")
    params = body.get("params", {})

    if method == "initialize":
        return JSONResponse(_ok(req_id, {
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {}},
            "serverInfo": _SERVER_INFO,
        }))

    if method in ("notifications/initialized", "ping"):
        return JSONResponse(_ok(req_id, {}))

    if method == "tools/list":
        return JSONResponse(_ok(req_id, {"tools": _TOOLS}))

    if method == "tools/call":
        name = params.get("name")
        arguments = params.get("arguments", {})
        handler = _HANDLERS.get(name)
        if not handler:
            return JSONResponse(_err(req_id, -32601, f"Unknown tool: {name}"))
        try:
            result = await handler(arguments, db)
            return JSONResponse(_ok(req_id, _content(result)))
        except Exception as e:
            logger.error(f"MCP tool error [{name}]: {e}", exc_info=True)
            return JSONResponse(_err(req_id, -32603, str(e)))

    return JSONResponse(_err(req_id, -32601, f"Method not found: {method}"))
