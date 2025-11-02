"""
Utilities for deduplicating intelligence items across sources
"""
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
from difflib import SequenceMatcher
import logging

logger = logging.getLogger(__name__)


def normalize_url(url: str) -> str:
    """
    Normalize URL by removing tracking parameters and standardizing format

    This helps identify duplicate articles that have different URLs due to:
    - Tracking parameters (utm_*, fbclid, etc.)
    - AMP versions
    - Mobile vs desktop versions
    - Trailing slashes
    - URL encoding differences

    Args:
        url: Original URL string

    Returns:
        Normalized URL string
    """
    if not url:
        return url

    try:
        parsed = urlparse(url.strip())

        # Remove common tracking parameters
        query_params = parse_qs(parsed.query, keep_blank_values=False)
        tracking_params = [
            'utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content',
            'fbclid', 'gclid', 'msclkid',  # Ad tracking
            'mc_cid', 'mc_eid',  # MailChimp
            '_ga', '_gl',  # Google Analytics
            'ref', 'source', 'share',  # Generic tracking
            'ncid',  # News tracking
        ]

        for param in tracking_params:
            query_params.pop(param, None)

        # Rebuild query string without tracking params
        clean_query = urlencode(query_params, doseq=True) if query_params else ''

        # Normalize path
        path = parsed.path

        # Remove AMP versions
        path = path.replace('/amp/', '/').replace('/amp', '')
        if path.endswith('.amp'):
            path = path[:-4]

        # Remove mobile versions
        path = path.replace('/m/', '/').replace('/mobile/', '/')

        # Remove trailing slash (except for root)
        if len(path) > 1 and path.endswith('/'):
            path = path.rstrip('/')

        # Lowercase the domain for consistency
        netloc = parsed.netloc.lower()

        # Remove www. prefix for consistency
        if netloc.startswith('www.'):
            netloc = netloc[4:]

        # Rebuild URL
        normalized = urlunparse((
            parsed.scheme.lower(),
            netloc,
            path,
            '',  # params (usually empty)
            clean_query,
            ''  # fragment (remove anchors)
        ))

        return normalized

    except Exception as e:
        logger.warning(f"Failed to normalize URL '{url}': {e}")
        return url


def calculate_title_similarity(title1: str, title2: str) -> float:
    """
    Calculate similarity ratio between two article titles

    Uses SequenceMatcher to calculate how similar two strings are.
    This helps identify duplicate articles with slightly different headlines.

    Args:
        title1: First title
        title2: Second title

    Returns:
        Similarity ratio from 0.0 (completely different) to 1.0 (identical)
    """
    if not title1 or not title2:
        return 0.0

    # Normalize titles for comparison
    t1 = title1.lower().strip()
    t2 = title2.lower().strip()

    # Calculate similarity ratio
    return SequenceMatcher(None, t1, t2).ratio()


def is_similar_title(title1: str, title2: str, threshold: float = 0.85) -> bool:
    """
    Check if two titles are similar enough to be considered duplicates

    Args:
        title1: First title
        title2: Second title
        threshold: Similarity threshold (0.0-1.0). Default 0.85 = 85% similar

    Returns:
        True if titles are similar enough to be duplicates
    """
    similarity = calculate_title_similarity(title1, title2)
    return similarity >= threshold
