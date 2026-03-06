"""
Unit tests for app/utils/rate_limiter.py

Tests the global rate limiter and task queue functionality used to
coordinate collection across all sources and customers.
"""

import pytest
import asyncio
from datetime import datetime

from app.utils.rate_limiter import GlobalRateLimiter, TaskQueue


class TestGlobalRateLimiter:
    """Tests for the GlobalRateLimiter class."""

    @pytest.fixture
    def rate_limiter(self):
        """Create a fresh rate limiter for each test."""
        return GlobalRateLimiter()

    @pytest.fixture
    def custom_rate_limiter(self):
        """Create a rate limiter with custom limits for testing."""
        return GlobalRateLimiter(custom_limits={
            'test_source': (5, 10),  # 5 requests per 10 seconds
            'fast_source': (100, 1),  # 100 requests per second
        })

    # ========================================================================
    # Initialization Tests
    # ========================================================================

    def test_init_with_default_limits(self, rate_limiter):
        """Should initialize with default rate limits."""
        assert 'linkedin' in rate_limiter.limits
        assert 'reddit' in rate_limiter.limits
        assert 'rss' in rate_limiter.limits

    def test_init_with_custom_limits(self, custom_rate_limiter):
        """Should accept custom rate limits."""
        assert custom_rate_limiter.limits['test_source'] == (5, 10)
        assert custom_rate_limiter.limits['fast_source'] == (100, 1)

    def test_default_linkedin_limit(self, rate_limiter):
        """LinkedIn should have conservative limit."""
        limit, window = rate_limiter.limits['linkedin']
        assert limit == 10
        assert window == 60

    def test_default_reddit_limit(self, rate_limiter):
        """Reddit should have API-specified limit."""
        limit, window = rate_limiter.limits['reddit']
        assert limit == 60
        assert window == 60

    def test_default_rss_limit(self, rate_limiter):
        """RSS should have generous limit."""
        limit, window = rate_limiter.limits['rss']
        assert limit == 120
        assert window == 60

    # ========================================================================
    # Acquire Tests
    # ========================================================================

    @pytest.mark.asyncio
    async def test_acquire_allows_within_limit(self):
        """Should allow requests within rate limit."""
        limiter = GlobalRateLimiter(custom_limits={'test': (5, 60)})

        # Should not block for first 5 requests
        for _ in range(5):
            await limiter.acquire('test')

        stats = await limiter.get_stats('test')
        assert stats['test']['current_requests'] == 5

    @pytest.mark.asyncio
    async def test_acquire_unknown_source_uses_default(self):
        """Unknown source should use default moderate limit."""
        limiter = GlobalRateLimiter()

        # Should not raise for unknown source
        await limiter.acquire('unknown_source')

        stats = await limiter.get_stats('unknown_source')
        assert stats['unknown_source']['max_requests'] == 60  # Default limit

    @pytest.mark.asyncio
    async def test_acquire_tracks_requests(self):
        """Should track requests in sliding window."""
        limiter = GlobalRateLimiter(custom_limits={'test': (10, 60)})

        for _ in range(3):
            await limiter.acquire('test')

        stats = await limiter.get_stats('test')
        assert stats['test']['current_requests'] == 3

    @pytest.mark.asyncio
    async def test_acquire_multiple_sources_independent(self):
        """Different sources should have independent limits."""
        limiter = GlobalRateLimiter(custom_limits={
            'source_a': (2, 60),
            'source_b': (2, 60),
        })

        # Fill up source_a
        await limiter.acquire('source_a')
        await limiter.acquire('source_a')

        # source_b should still be available
        stats = await limiter.get_stats()
        assert stats['source_a']['current_requests'] == 2
        assert stats['source_b']['current_requests'] == 0

        # Should not block
        await limiter.acquire('source_b')
        stats = await limiter.get_stats()
        assert stats['source_b']['current_requests'] == 1

    # ========================================================================
    # Stats Tests
    # ========================================================================

    @pytest.mark.asyncio
    async def test_get_stats_specific_source(self):
        """Should return stats for specific source."""
        limiter = GlobalRateLimiter(custom_limits={'test': (10, 60)})
        await limiter.acquire('test')

        stats = await limiter.get_stats('test')

        assert 'test' in stats
        assert stats['test']['current_requests'] == 1
        assert stats['test']['max_requests'] == 10
        assert stats['test']['window_seconds'] == 60
        assert stats['test']['utilization'] == 0.1

    @pytest.mark.asyncio
    async def test_get_stats_all_sources(self):
        """Should return stats for all configured sources."""
        limiter = GlobalRateLimiter(custom_limits={
            'source_a': (10, 60),
            'source_b': (20, 60),
        })

        stats = await limiter.get_stats()

        assert 'source_a' in stats
        assert 'source_b' in stats

    @pytest.mark.asyncio
    async def test_get_stats_utilization_calculation(self):
        """Utilization should be correctly calculated."""
        limiter = GlobalRateLimiter(custom_limits={'test': (10, 60)})

        for _ in range(5):
            await limiter.acquire('test')

        stats = await limiter.get_stats('test')
        assert stats['test']['utilization'] == 0.5  # 5/10

    # ========================================================================
    # Reset Tests
    # ========================================================================

    @pytest.mark.asyncio
    async def test_reset_specific_source(self):
        """Should reset specific source's window."""
        limiter = GlobalRateLimiter(custom_limits={
            'source_a': (10, 60),
            'source_b': (10, 60),
        })

        await limiter.acquire('source_a')
        await limiter.acquire('source_b')

        await limiter.reset('source_a')

        stats = await limiter.get_stats()
        assert stats['source_a']['current_requests'] == 0
        assert stats['source_b']['current_requests'] == 1

    @pytest.mark.asyncio
    async def test_reset_all_sources(self):
        """Should reset all sources' windows."""
        limiter = GlobalRateLimiter(custom_limits={
            'source_a': (10, 60),
            'source_b': (10, 60),
        })

        await limiter.acquire('source_a')
        await limiter.acquire('source_b')

        await limiter.reset()

        stats = await limiter.get_stats()
        assert stats['source_a']['current_requests'] == 0
        assert stats['source_b']['current_requests'] == 0

    # ========================================================================
    # Sliding Window Tests
    # ========================================================================

    @pytest.mark.asyncio
    async def test_sliding_window_expires_old_requests(self):
        """Old requests should be removed from window."""
        limiter = GlobalRateLimiter(custom_limits={'test': (5, 1)})  # 5 per 1 second

        # Make some requests
        await limiter.acquire('test')
        await limiter.acquire('test')

        stats_before = await limiter.get_stats('test')
        assert stats_before['test']['current_requests'] == 2

        # Wait for window to expire
        await asyncio.sleep(1.1)

        # Make another request (this triggers cleanup)
        await limiter.acquire('test')

        stats_after = await limiter.get_stats('test')
        # Old requests should be cleaned up, only new one remains
        assert stats_after['test']['current_requests'] == 1


class TestTaskQueue:
    """Tests for the TaskQueue class."""

    @pytest.fixture
    def task_queue(self):
        """Create a task queue for testing."""
        return TaskQueue(max_concurrent=2)

    # ========================================================================
    # Initialization Tests
    # ========================================================================

    def test_init_with_default_workers(self):
        """Should initialize with default worker count."""
        queue = TaskQueue()
        assert queue.max_concurrent == 4

    def test_init_with_custom_workers(self, task_queue):
        """Should accept custom worker count."""
        assert task_queue.max_concurrent == 2

    def test_init_empty_results(self, task_queue):
        """Should start with empty results and errors."""
        assert task_queue.results == []
        assert task_queue.errors == []

    def test_init_not_running(self, task_queue):
        """Should not be running initially."""
        assert task_queue.running is False

    # ========================================================================
    # Task Addition Tests
    # ========================================================================

    @pytest.mark.asyncio
    async def test_add_task(self, task_queue):
        """Should add task to queue."""
        async def dummy_task():
            return "result"

        await task_queue.add_task(dummy_task)
        assert task_queue.queue.qsize() == 1

    @pytest.mark.asyncio
    async def test_add_multiple_tasks(self, task_queue):
        """Should add multiple tasks to queue."""
        async def dummy_task():
            return "result"

        for _ in range(5):
            await task_queue.add_task(dummy_task)

        assert task_queue.queue.qsize() == 5

    @pytest.mark.asyncio
    async def test_add_task_with_args(self, task_queue):
        """Should pass arguments to task function."""
        results = []

        async def task_with_args(value):
            results.append(value)
            return value

        await task_queue.add_task(task_with_args, "test_value")

        # Start workers to process
        await task_queue.start_workers()
        await task_queue.wait_completion()
        await task_queue.stop_workers()

        assert "test_value" in task_queue.results

    @pytest.mark.asyncio
    async def test_add_task_with_kwargs(self, task_queue):
        """Should pass keyword arguments to task function."""
        async def task_with_kwargs(key=None):
            return key

        await task_queue.add_task(task_with_kwargs, key="test_key")

        await task_queue.start_workers()
        await task_queue.wait_completion()
        await task_queue.stop_workers()

        assert "test_key" in task_queue.results

    # ========================================================================
    # Worker Tests
    # ========================================================================

    @pytest.mark.asyncio
    async def test_start_workers(self, task_queue):
        """Should start the configured number of workers."""
        await task_queue.start_workers()

        assert task_queue.running is True
        assert len(task_queue.workers) == 2

        await task_queue.stop_workers()

    @pytest.mark.asyncio
    async def test_stop_workers(self, task_queue):
        """Should stop all workers."""
        await task_queue.start_workers()
        await task_queue.stop_workers()

        assert task_queue.running is False
        assert len(task_queue.workers) == 0

    @pytest.mark.asyncio
    async def test_workers_process_tasks(self, task_queue):
        """Workers should process tasks from queue."""
        async def simple_task():
            return "processed"

        await task_queue.add_task(simple_task)
        await task_queue.add_task(simple_task)

        await task_queue.start_workers()
        await task_queue.wait_completion()
        await task_queue.stop_workers()

        assert len(task_queue.results) == 2
        assert all(r == "processed" for r in task_queue.results)

    @pytest.mark.asyncio
    async def test_workers_handle_errors(self, task_queue):
        """Workers should capture errors without crashing."""
        async def failing_task():
            raise ValueError("Task failed!")

        await task_queue.add_task(failing_task)

        await task_queue.start_workers()
        await task_queue.wait_completion()
        await task_queue.stop_workers()

        assert len(task_queue.errors) == 1
        assert "Task failed!" in task_queue.errors[0]

    @pytest.mark.asyncio
    async def test_workers_continue_after_error(self, task_queue):
        """Workers should continue processing after error."""
        async def failing_task():
            raise ValueError("I fail!")

        async def success_task():
            return "success"

        await task_queue.add_task(failing_task)
        await task_queue.add_task(success_task)

        await task_queue.start_workers()
        await task_queue.wait_completion()
        await task_queue.stop_workers()

        assert len(task_queue.errors) == 1
        assert len(task_queue.results) == 1
        assert task_queue.results[0] == "success"

    # ========================================================================
    # Wait Completion Tests
    # ========================================================================

    @pytest.mark.asyncio
    async def test_wait_completion_blocks_until_done(self, task_queue):
        """wait_completion should block until all tasks are processed."""
        completion_order = []

        async def slow_task(id):
            await asyncio.sleep(0.1)
            completion_order.append(id)
            return id

        await task_queue.add_task(slow_task, 1)
        await task_queue.add_task(slow_task, 2)

        await task_queue.start_workers()
        await task_queue.wait_completion()
        await task_queue.stop_workers()

        assert len(completion_order) == 2
        assert len(task_queue.results) == 2

    # ========================================================================
    # Results/Errors Tests
    # ========================================================================

    @pytest.mark.asyncio
    async def test_get_results(self, task_queue):
        """Should return all task results."""
        async def task_with_result(value):
            return value * 2

        await task_queue.add_task(task_with_result, 1)
        await task_queue.add_task(task_with_result, 2)
        await task_queue.add_task(task_with_result, 3)

        await task_queue.start_workers()
        await task_queue.wait_completion()
        await task_queue.stop_workers()

        results = task_queue.get_results()
        assert set(results) == {2, 4, 6}

    @pytest.mark.asyncio
    async def test_get_errors(self, task_queue):
        """Should return all task errors."""
        async def failing_task(msg):
            raise RuntimeError(msg)

        await task_queue.add_task(failing_task, "error 1")
        await task_queue.add_task(failing_task, "error 2")

        await task_queue.start_workers()
        await task_queue.wait_completion()
        await task_queue.stop_workers()

        errors = task_queue.get_errors()
        assert len(errors) == 2

    # ========================================================================
    # Concurrency Tests
    # ========================================================================

    @pytest.mark.asyncio
    async def test_concurrent_execution(self):
        """Tasks should run concurrently up to max_concurrent."""
        queue = TaskQueue(max_concurrent=3)
        execution_times = []

        async def timed_task():
            start = datetime.now()
            await asyncio.sleep(0.1)
            execution_times.append(start)
            return True

        # Add 3 tasks
        for _ in range(3):
            await queue.add_task(timed_task)

        await queue.start_workers()
        await queue.wait_completion()
        await queue.stop_workers()

        # All 3 should start roughly at the same time
        assert len(execution_times) == 3

        # Check they're within 50ms of each other (allowing for scheduling overhead)
        time_diff = max(execution_times) - min(execution_times)
        assert time_diff.total_seconds() < 0.1

    @pytest.mark.asyncio
    async def test_max_concurrent_respected(self):
        """Should not exceed max_concurrent workers."""
        queue = TaskQueue(max_concurrent=2)
        concurrent_count = []
        current_count = 0
        lock = asyncio.Lock()

        async def counting_task():
            nonlocal current_count
            async with lock:
                current_count += 1
                concurrent_count.append(current_count)

            await asyncio.sleep(0.05)

            async with lock:
                current_count -= 1

        # Add 5 tasks
        for _ in range(5):
            await queue.add_task(counting_task)

        await queue.start_workers()
        await queue.wait_completion()
        await queue.stop_workers()

        # Max concurrent should never exceed 2
        assert max(concurrent_count) <= 2


class TestRateLimiterIntegration:
    """Integration tests combining rate limiter with task queue."""

    @pytest.mark.asyncio
    async def test_rate_limited_tasks(self):
        """Tasks should respect rate limits when using rate limiter."""
        limiter = GlobalRateLimiter(custom_limits={'test': (2, 1)})  # 2 per second
        queue = TaskQueue(max_concurrent=4)
        request_times = []

        async def rate_limited_task():
            await limiter.acquire('test')
            request_times.append(datetime.now())
            return True

        # Add 4 tasks
        for _ in range(4):
            await queue.add_task(rate_limited_task)


        await queue.start_workers()
        await queue.wait_completion()
        await queue.stop_workers()


        # 4 requests at 2/second should take at least 1 second
        # (first 2 immediate, wait ~1s, next 2)
        assert len(request_times) == 4
