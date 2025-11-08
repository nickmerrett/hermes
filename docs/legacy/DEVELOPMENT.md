# Development Guide

This guide is for developers who want to extend or modify the Customer Intelligence Tool.

## Project Structure

```
atl-intel/
├── backend/
│   ├── app/
│   │   ├── api/              # REST API endpoints
│   │   │   ├── customers.py
│   │   │   ├── feed.py
│   │   │   ├── sources.py
│   │   │   ├── jobs.py
│   │   │   ├── search.py
│   │   │   └── analytics.py
│   │   ├── collectors/       # Data collection modules
│   │   │   ├── base.py       # Base collector class
│   │   │   ├── news_collector.py
│   │   │   ├── rss_collector.py
│   │   │   └── stock_collector.py
│   │   ├── processors/       # AI processing
│   │   │   └── ai_processor.py
│   │   ├── models/           # Data models
│   │   │   ├── database.py   # SQLAlchemy models
│   │   │   └── schemas.py    # Pydantic schemas
│   │   ├── scheduler/        # Job scheduling
│   │   │   ├── jobs.py       # APScheduler setup
│   │   │   └── collection.py # Collection orchestration
│   │   ├── core/             # Core utilities
│   │   │   ├── database.py   # Database connection
│   │   │   └── vector_store.py # ChromaDB wrapper
│   │   ├── config/           # Configuration
│   │   │   └── settings.py
│   │   └── main.py           # FastAPI application
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   ├── services/
│   │   ├── styles/
│   │   ├── App.jsx
│   │   └── main.jsx
│   └── package.json
├── config/
│   └── customers.yaml
├── data/
│   ├── db/                   # SQLite database
│   └── chroma/               # ChromaDB storage
└── docker-compose.yml
```

## Adding a New Data Collector

To add a new data source (e.g., Twitter, LinkedIn):

### 1. Create a new collector class

Create `backend/app/collectors/twitter_collector.py`:

```python
from typing import List, Dict, Any
from app.collectors.base import RateLimitedCollector
from app.models.schemas import IntelligenceItemCreate

class TwitterCollector(RateLimitedCollector):
    """Collector for Twitter/X posts"""

    def __init__(self, customer_config: Dict[str, Any]):
        super().__init__(customer_config, rate_limit=100)
        # Initialize Twitter API client
        self.api_key = settings.twitter_api_key

    def get_source_type(self) -> str:
        return "twitter"

    async def collect(self) -> List[IntelligenceItemCreate]:
        items = []

        # Check rate limit
        if not self._check_rate_limit():
            return items

        # Implement collection logic
        # Search for tweets about customer
        # Transform to IntelligenceItemCreate objects

        return items
```

### 2. Add to collection orchestration

Edit `backend/app/scheduler/collection.py`:

```python
from app.collectors.twitter_collector import TwitterCollector

# In collect_for_customer function:
if collection_config.get('twitter_enabled', False):
    try:
        collector = TwitterCollector(customer_config)
        items, error = await collector.safe_collect()
        if items:
            await save_and_process_items(items, customer, db)
            items_collected += len(items)
    except Exception as e:
        logger.error(f"Twitter collection error: {str(e)}")
```

### 3. Add configuration

Update `.env.example`:

```
TWITTER_API_KEY=your_twitter_api_key_here
```

Update `backend/app/config/settings.py`:

```python
class Settings(BaseSettings):
    # ... existing settings
    twitter_api_key: str = ""
```

### 4. Update customer config schema

In `config/customers.yaml`:

```yaml
customers:
  - name: "Example Corp"
    # ... existing config
    collection_config:
      twitter_enabled: true
```

## Modifying AI Processing

The AI processing logic is in `backend/app/processors/ai_processor.py`.

### Customizing the Prompt

Edit the `_build_prompt` method to change what Claude analyzes:

```python
def _build_prompt(self, title, content, customer_name, source_type):
    return f"""You are analyzing intelligence about {customer_name}.

    Focus on:
    - Technical innovations
    - Partnership opportunities
    - Competitive threats

    Article: {title}
    {content}

    Provide analysis in JSON format...
    """
```

### Adding New Classification Categories

1. Update the enum in `backend/app/models/schemas.py`:

```python
class CategoryType(str, Enum):
    # ... existing categories
    TECHNICAL_INNOVATION = "technical_innovation"
    REGULATORY = "regulatory"
```

2. Update the AI prompt to include new categories

3. Update frontend filters to support new categories

## Database Migrations

When modifying database models:

1. Update models in `backend/app/models/database.py`

2. For development, drop and recreate:

```bash
rm data/db/intelligence.db
docker-compose restart backend
```

3. For production, use Alembic migrations:

```bash
cd backend
alembic revision --autogenerate -m "Add new field"
alembic upgrade head
```

## Adding API Endpoints

Create a new router or extend existing ones in `backend/app/api/`:

```python
# backend/app/api/new_feature.py
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.database import get_db

router = APIRouter()

@router.get("/new-endpoint")
async def new_endpoint(db: Session = Depends(get_db)):
    # Implementation
    return {"result": "data"}
```

Then include in `backend/app/main.py`:

```python
from app.api import new_feature

app.include_router(
    new_feature.router,
    prefix="/api/new-feature",
    tags=["new-feature"]
)
```

## Frontend Development

### Adding a New Component

Create in `frontend/src/components/NewComponent.jsx`:

```javascript
import React from 'react'

function NewComponent({ data }) {
  return (
    <div>
      {/* Component JSX */}
    </div>
  )
}

export default NewComponent
```

### Adding New API Calls

Create or extend `frontend/src/services/api.js`:

```javascript
import axios from 'axios'

const API_URL = import.meta.env.VITE_API_URL || '/api'

export const getCustomers = async () => {
  const response = await axios.get(`${API_URL}/customers`)
  return response.data
}

export const triggerCollection = async (customerId) => {
  await axios.post(`${API_URL}/jobs/trigger`, {
    customer_id: customerId
  })
}
```

## Testing

### Backend Tests

```bash
cd backend
pytest tests/

# With coverage
pytest --cov=app tests/
```

### Frontend Tests

```bash
cd frontend
npm test
```

## Environment Variables

All environment variables are defined in:
- `.env.example` - Template with defaults
- `backend/app/config/settings.py` - Settings class

When adding new variables:
1. Add to `.env.example`
2. Add to `Settings` class
3. Document in `GETTING_STARTED.md`

## Logging

Configure logging level in `.env`:

```
LOG_LEVEL=DEBUG  # DEBUG, INFO, WARNING, ERROR
```

Add logging to your code:

```python
import logging
logger = logging.getLogger(__name__)

logger.debug("Debug message")
logger.info("Info message")
logger.error("Error message")
```

## Performance Optimization

### Database Queries

Use indexes on frequently queried fields:

```python
# In models/database.py
class IntelligenceItem(Base):
    # ...
    published_date = Column(DateTime, index=True)
```

### Vector Store

Batch operations when possible:

```python
vector_store.add_items_batch(
    item_ids=[1, 2, 3],
    texts=["text1", "text2", "text3"]
)
```

### API Response

Use pagination for large result sets:

```python
@router.get("/items")
async def get_items(
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0)
):
    # Return paginated results
```

## Debugging

### Backend Debugging

1. Add print statements or use debugger:

```python
import pdb; pdb.set_trace()
```

2. Check logs:

```bash
docker-compose logs -f backend
```

3. Access container:

```bash
docker-compose exec backend bash
```

### Database Inspection

```bash
# Access SQLite database
docker-compose exec backend bash
sqlite3 /app/data/db/intelligence.db

# Run queries
SELECT * FROM customers;
SELECT COUNT(*) FROM intelligence_items;
```

## Common Development Tasks

### Reset Everything

```bash
make clean
make start
```

### Update Dependencies

Backend:
```bash
cd backend
pip install new-package
pip freeze > requirements.txt
```

Frontend:
```bash
cd frontend
npm install new-package
```

### Update Docker Images

```bash
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

## Contributing Guidelines

1. Create feature branches from `main`
2. Follow existing code style
3. Add tests for new features
4. Update documentation
5. Keep commits focused and descriptive
6. Test locally before pushing

## Troubleshooting

### Import Errors

Ensure PYTHONPATH includes app directory:

```bash
export PYTHONPATH=/app:$PYTHONPATH
```

### Database Locked

SQLite is single-writer. Ensure only one process accesses DB at a time.

### Memory Issues

Limit embedding model memory:

```python
# In vector_store.py
self.embedding_model = SentenceTransformer(
    self.embedding_model_name,
    device='cpu'  # Force CPU to save memory
)
```

## Architecture Decisions

### Why SQLite?

- Simple setup, no separate container
- Sufficient for MVP (1000s of items)
- Easy to backup (single file)
- Can migrate to PostgreSQL later if needed

### Why ChromaDB?

- Easy vector storage without infrastructure
- Built-in similarity search
- Persistent storage
- Can scale to 100k+ documents

### Why APScheduler?

- Lightweight, no separate message queue
- Sufficient for periodic jobs
- Can migrate to Celery for complex workflows

## Next Steps for Development

- [ ] Add authentication/authorization
- [ ] Implement email digest feature
- [ ] Add LinkedIn collector
- [ ] Create mobile-responsive UI
- [ ] Add export functionality (PDF, CSV)
- [ ] Implement user preferences
- [ ] Add real-time updates (WebSocket)
- [ ] Create admin dashboard
- [ ] Add data visualization charts
- [ ] Implement A/B testing for prompts
