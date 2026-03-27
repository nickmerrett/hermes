# AI Processing Timeout Fix - Summary

## Problem
The collection process was hanging indefinitely during AI processing with no errors. This occurred because:

1. **No timeout configuration** on AI API clients (Anthropic/OpenAI) in TWO places:
   - AI processor for article analysis
   - Clustering module for LLM tiebreaker
2. **Synchronous blocking calls** in async context blocking the event loop
3. **No circuit breaker** to handle consecutive failures
4. **No recovery mechanism** when API becomes unresponsive

## Root Cause
The AI client initialization had **no timeout parameters** in TWO locations:

### 1. AI Processor (`backend/app/processors/ai_processor.py`)
```python
# BEFORE (would hang forever if API is slow/unresponsive)
self.client = Anthropic(
    api_key=settings.anthropic_api_key,
    base_url=settings.anthropic_api_base_url
    # ❌ NO TIMEOUT!
)
```

### 2. Clustering Module (`backend/app/utils/clustering.py`)
```python
# BEFORE (LLM tiebreaker would hang during clustering)
_anthropic_client = Anthropic(
    api_key=settings.anthropic_api_key,
    base_url=settings.anthropic_api_base_url
    # ❌ NO TIMEOUT!
)
```

**Based on your logs**, the hang occurred during the clustering phase after successful AI processing. The "Batches: 100%" messages indicate sentence-transformers was creating embeddings, then the LLM tiebreaker was called to determine if stories should be clustered together, and that's where it hung.

## Solution Implemented

### 1. Added Timeout Configuration (Lines 18-19)
```python
AI_API_TIMEOUT = 60.0  # 60 seconds per API call
AI_PROCESSING_TIMEOUT = 120.0  # 120 seconds total including retries
```

### 2. Added Timeouts to Client Initialization (Lines 81-103)
```python
# Anthropic client
self.client = Anthropic(
    api_key=settings.anthropic_api_key,
    base_url=settings.anthropic_api_base_url,
    timeout=AI_API_TIMEOUT  # ✅ 60 second timeout
)

# OpenAI client
self.client = OpenAI(
    api_key=settings.openai_api_key,
    base_url=settings.openai_base_url,
    timeout=AI_API_TIMEOUT  # ✅ 60 second timeout
)
```

### 3. Created Async Wrapper with Additional Timeout (Lines 204-232)
```python
async def _call_ai_async(self, client, client_type, model_name, prompt, max_tokens):
    """
    Async wrapper for AI API calls with timeout protection
    
    Runs synchronous _call_ai in thread pool to prevent blocking
    the event loop, with an additional timeout layer for safety.
    """
    try:
        result = await asyncio.wait_for(
            asyncio.to_thread(
                self._call_ai, client, client_type, model_name, prompt, max_tokens
            ),
            timeout=AI_PROCESSING_TIMEOUT  # ✅ 120 second overall timeout
        )
        return result
    except asyncio.TimeoutError:
        logger.error(f"AI processing timeout after {AI_PROCESSING_TIMEOUT}s")
        raise Exception(f"AI processing timeout after {AI_PROCESSING_TIMEOUT} seconds")
```

### 4. Added Circuit Breaker Pattern (Lines 104-109, 270-283)
Tracks consecutive failures and temporarily disables AI processing if service is consistently failing:

```python
# Circuit breaker state
self.consecutive_failures = 0
self.max_failures_before_circuit_break = 5
self.circuit_broken = False
self.circuit_break_time = None
self.circuit_break_reset_seconds = 300  # Reset after 5 minutes

# Check at start of process_item
if self.circuit_broken:
    if (time.time() - self.circuit_break_time) > self.circuit_break_reset_seconds:
        logger.info("Circuit breaker RESET - attempting to resume")
        self.circuit_broken = False
        self.consecutive_failures = 0
    else:
        logger.warning("Circuit breaker OPEN - using defaults")
        return self._default_result(title, content)
```

### 5. Enhanced Error Handling (Lines 454-477)
```python
except asyncio.TimeoutError:
    self.consecutive_failures += 1
    logger.error(f"AI processing timeout (failure {self.consecutive_failures}/5)")
    
    if self.consecutive_failures >= 5:
        self.circuit_broken = True
        logger.error("Circuit breaker OPENED")
    
    return self._default_result(title, content)

except Exception as e:
    self.consecutive_failures += 1
    logger.error(f"Error processing item (failure {self.consecutive_failures}/5): {e}")
    
    if self.consecutive_failures >= 5:
        self.circuit_broken = True
        logger.error("Circuit breaker OPENED")
    
    return self._default_result(title, content)
```

### 6. Fixed Clustering Module Timeouts (`backend/app/utils/clustering.py`)
```python
# Added timeout to LLM client for clustering tiebreaker
_anthropic_client = Anthropic(
    api_key=settings.anthropic_api_key,
    base_url=settings.anthropic_api_base_url,
    timeout=60.0  # ✅ 60 second timeout
)

_openai_client = OpenAI(
    api_key=settings.openai_api_key,
    base_url=settings.openai_base_url,
    timeout=60.0  # ✅ 60 second timeout
)
```

### 7. Added Performance Logging (Lines 171-189)
```python
start_time = time.time()
try:
    # ... make API call ...
    duration = time.time() - start_time
    logger.debug(f"AI API call completed in {duration:.2f}s (model: {model_name})")
except Exception as e:
    duration = time.time() - start_time
    logger.error(f"AI API call failed after {duration:.2f}s: {e}")
    raise
```

## Benefits

1. **No More Hanging**: Timeouts ensure calls never hang indefinitely (both AI processing AND clustering)
2. **Better Resource Usage**: Async wrapper prevents blocking the event loop
3. **Graceful Degradation**: Circuit breaker prevents cascading failures
4. **Automatic Recovery**: Circuit breaker resets after 5 minutes
5. **Better Monitoring**: Performance logging helps identify slow API calls
6. **Failure Tracking**: Consecutive failure counter helps diagnose issues
7. **Clustering Protection**: LLM tiebreaker in clustering now has timeout protection

## Testing

To test the fix:

```bash
# Run a collection
cd backend
python -c "from app.scheduler.collection import run_collection; run_collection()"

# Monitor logs for timeout messages
tail -f logs/app.log | grep -E "timeout|Circuit breaker|AI API call"
```

## Configuration

Adjust timeouts in `backend/app/processors/ai_processor.py` if needed:

```python
AI_API_TIMEOUT = 60.0  # Increase if API is consistently slow
AI_PROCESSING_TIMEOUT = 120.0  # Overall timeout including retries
```

Adjust circuit breaker settings:

```python
self.max_failures_before_circuit_break = 5  # Number of failures before opening
self.circuit_break_reset_seconds = 300  # Seconds before attempting reset
```

## Monitoring

Watch for these log messages:

**AI Processing:**
- `AI API call completed in X.XXs` - Normal operation
- `AI processing timeout after 120s` - Timeout occurred
- `Circuit breaker OPENED` - Too many failures, AI disabled temporarily
- `Circuit breaker RESET` - Attempting to resume after cooldown
- `Circuit breaker OPEN - using defaults` - Skipping AI while circuit is open

**Clustering:**
- `Batches: 100%` - Sentence-transformers creating embeddings (normal)
- `Item X assigned to cluster Y` - Clustering working normally
- `Error clustering item X` - Clustering failed (now won't hang)

**What Your Logs Showed:**
Your logs showed successful API calls (`HTTP/1.1 200 OK`) followed by embedding creation (`Batches: 100%`), then silence. This indicated the hang was in the clustering LLM tiebreaker, which is now fixed.

## Next Steps

1. Monitor logs after deployment to tune timeout values
2. Consider adding metrics/alerts for circuit breaker events
3. Review API provider status if timeouts are frequent
4. Consider implementing retry with exponential backoff at API level