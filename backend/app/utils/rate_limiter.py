"""Global rate limiter for coordinating collection across all sources and customers"""

import asyncio
import logging
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, Tuple

logger = logging.getLogger(__name__)


class GlobalRateLimiter:
    """
    Global rate limiter that coordinates requests across all collectors and customers.

    Uses a sliding window approach to enforce rate limits per source type.
    This prevents overwhelming external APIs even when collecting for multiple customers in parallel.

    Example usage:
        rate_limiter = GlobalRateLimiter()
        await rate_limiter.acquire('linkedin')  # Blocks until allowed
        # ... make request
    """

    def __init__(self, custom_limits: Dict[str, Tuple[int, int]] = None):
        """
        Initialize global rate limiter

        Args:
            custom_limits: Optional dict of {source_type: (max_requests, window_seconds)}
                         If not provided, uses default conservative limits
        """
        # Default rate limits: (max_requests, window_seconds)
        # These are GLOBAL limits across all customers
        self.limits = custom_limits or {
            'linkedin': (10, 60),      # 10 requests per 60 seconds (very conservative)
            'reddit': (60, 60),        # 60 requests per minute (Reddit API limit)
            'news': (100, 60),         # 100 requests per minute
            'rss': (120, 60),          # 120 requests per minute (generous)
            'github': (60, 60),        # 60 requests per minute (GitHub API limit)
            'hackernews': (100, 60),   # 100 requests per minute
            'yahoo_finance_news': (30, 60),  # 30 requests per minute (scraping)
            'pressrelease': (60, 60),  # 60 requests per minute
            'web_scraper': (30, 60),   # 30 requests per minute (conservative)
        }

        # Track request timestamps per source type
        self.windows: Dict[str, list] = defaultdict(list)

        # Lock for thread-safe access
        self.lock = asyncio.Lock()

        logger.info(f"GlobalRateLimiter initialized with limits: {self.limits}")

    async def acquire(self, source_type: str) -> None:
        """
        Acquire permission to make a request for the given source type.

        Blocks (awaits) if rate limit is reached until a slot becomes available.
        Uses sliding window rate limiting for accurate enforcement.

        Args:
            source_type: Type of source (e.g., 'linkedin', 'reddit', 'news')
        """
        async with self.lock:
            # Get limits for this source type (default to moderate limit if unknown)
            limit, window = self.limits.get(source_type, (60, 60))

            while True:
                now = datetime.now()

                # Clean old requests outside the sliding window
                cutoff_time = now - timedelta(seconds=window)
                self.windows[source_type] = [
                    ts for ts in self.windows[source_type]
                    if ts > cutoff_time
                ]

                # Check if we can proceed
                current_count = len(self.windows[source_type])

                if current_count < limit:
                    # We have capacity - record this request and proceed
                    self.windows[source_type].append(now)
                    logger.debug(
                        f"Rate limit acquired for {source_type}: "
                        f"{current_count + 1}/{limit} in last {window}s"
                    )
                    return

                # Rate limit reached - calculate wait time
                oldest_request = self.windows[source_type][0]
                wait_time = (oldest_request + timedelta(seconds=window) - now).total_seconds()

                # Add small buffer to avoid race conditions
                wait_time = max(wait_time + 0.1, 0.1)

                logger.info(
                    f"Rate limit reached for {source_type} "
                    f"({current_count}/{limit} requests in {window}s). "
                    f"Waiting {wait_time:.1f}s..."
                )

                # Release lock while waiting so other sources can proceed
                self.lock.release()
                await asyncio.sleep(wait_time)
                await self.lock.acquire()

    async def get_stats(self, source_type: str = None) -> Dict:
        """
        Get current rate limit statistics

        Args:
            source_type: Specific source to get stats for, or None for all sources

        Returns:
            Dict with current request counts and limits
        """
        async with self.lock:
            now = datetime.now()

            if source_type:
                source_types = [source_type]
            else:
                source_types = list(self.limits.keys())

            stats = {}
            for src_type in source_types:
                limit, window = self.limits.get(src_type, (60, 60))
                cutoff_time = now - timedelta(seconds=window)

                # Count recent requests
                recent_requests = [
                    ts for ts in self.windows[src_type]
                    if ts > cutoff_time
                ]

                stats[src_type] = {
                    'current_requests': len(recent_requests),
                    'max_requests': limit,
                    'window_seconds': window,
                    'utilization': len(recent_requests) / limit if limit > 0 else 0
                }

            return stats

    async def reset(self, source_type: str = None) -> None:
        """
        Reset rate limit windows (useful for testing)

        Args:
            source_type: Specific source to reset, or None to reset all
        """
        async with self.lock:
            if source_type:
                self.windows[source_type] = []
                logger.info(f"Reset rate limiter for {source_type}")
            else:
                self.windows.clear()
                logger.info("Reset all rate limiters")


class TaskQueue:
    """
    Async task queue with worker pool for parallel collection.

    Allows multiple customers/sources to be collected concurrently while
    respecting global rate limits.

    Example usage:
        queue = TaskQueue(max_concurrent=4)
        await queue.start_workers()

        for customer in customers:
            await queue.add_task(collect_customer, customer, rate_limiter)

        await queue.wait_completion()
    """

    def __init__(self, max_concurrent: int = 4):
        """
        Initialize task queue

        Args:
            max_concurrent: Maximum number of concurrent workers
        """
        self.queue = asyncio.Queue()
        self.max_concurrent = max_concurrent
        self.workers = []
        self.running = False

        # Track results
        self.results = []
        self.errors = []

        logger.info(f"TaskQueue initialized with {max_concurrent} workers")

    async def add_task(self, task_func, *args, **kwargs):
        """
        Add a task to the queue

        Args:
            task_func: Async function to execute
            *args: Positional arguments for task_func
            **kwargs: Keyword arguments for task_func
        """
        await self.queue.put((task_func, args, kwargs))
        logger.debug(f"Task added to queue: {task_func.__name__}")

    async def worker(self, worker_id: int):
        """
        Worker that processes tasks from the queue

        Args:
            worker_id: Unique identifier for this worker
        """
        logger.info(f"Worker {worker_id} started")

        while self.running:
            try:
                # Get task with timeout so we can check self.running periodically
                try:
                    task_func, args, kwargs = await asyncio.wait_for(
                        self.queue.get(),
                        timeout=1.0
                    )
                except asyncio.TimeoutError:
                    continue

                logger.info(f"Worker {worker_id} processing: {task_func.__name__}")

                try:
                    # Execute the task
                    result = await task_func(*args, **kwargs)
                    self.results.append(result)
                    logger.info(f"Worker {worker_id} completed: {task_func.__name__}")

                except Exception as e:
                    error_msg = f"Worker {worker_id} task {task_func.__name__} failed: {e}"
                    logger.error(error_msg, exc_info=True)
                    self.errors.append(error_msg)

                finally:
                    self.queue.task_done()

            except Exception as e:
                logger.error(f"Worker {worker_id} error: {e}", exc_info=True)

        logger.info(f"Worker {worker_id} stopped")

    async def start_workers(self):
        """Start the worker pool"""
        self.running = True
        self.workers = [
            asyncio.create_task(self.worker(i))
            for i in range(self.max_concurrent)
        ]
        logger.info(f"Started {len(self.workers)} workers")

    async def wait_completion(self):
        """Wait for all queued tasks to complete"""
        logger.info("Waiting for all tasks to complete...")
        await self.queue.join()
        logger.info("All tasks completed")

    async def stop_workers(self):
        """Stop all workers"""
        logger.info("Stopping workers...")
        self.running = False

        # Wait for workers to finish
        for worker in self.workers:
            await worker

        self.workers = []
        logger.info("All workers stopped")

    def get_results(self) -> list:
        """Get all task results"""
        return self.results

    def get_errors(self) -> list:
        """Get all task errors"""
        return self.errors
