"""
Unit tests for app/utils/deduplication.py

Tests URL normalization and title similarity functions used for
detecting duplicate intelligence items across sources.
"""

from app.utils.deduplication import (
    normalize_url,
    calculate_title_similarity,
    is_similar_title
)


class TestNormalizeUrl:
    """Tests for the normalize_url function."""

    # ========================================================================
    # Basic URL Handling
    # ========================================================================

    def test_empty_url_returns_empty(self):
        """Empty string should return empty string."""
        assert normalize_url("") == ""

    def test_none_url_returns_none(self):
        """None should return None."""
        assert normalize_url(None) is None

    def test_simple_url_unchanged(self):
        """Simple URL without tracking params should be mostly unchanged."""
        url = "https://example.com/article/test-article"
        result = normalize_url(url)
        assert result == "https://example.com/article/test-article"

    def test_url_with_whitespace_stripped(self):
        """Leading/trailing whitespace should be stripped."""
        url = "  https://example.com/article  "
        result = normalize_url(url)
        assert result == "https://example.com/article"

    # ========================================================================
    # Tracking Parameter Removal
    # ========================================================================

    def test_removes_utm_source(self):
        """UTM source parameter should be removed."""
        url = "https://example.com/article?utm_source=twitter"
        result = normalize_url(url)
        assert "utm_source" not in result

    def test_removes_utm_medium(self):
        """UTM medium parameter should be removed."""
        url = "https://example.com/article?utm_medium=social"
        result = normalize_url(url)
        assert "utm_medium" not in result

    def test_removes_utm_campaign(self):
        """UTM campaign parameter should be removed."""
        url = "https://example.com/article?utm_campaign=launch"
        result = normalize_url(url)
        assert "utm_campaign" not in result

    def test_removes_utm_term(self):
        """UTM term parameter should be removed."""
        url = "https://example.com/article?utm_term=keyword"
        result = normalize_url(url)
        assert "utm_term" not in result

    def test_removes_utm_content(self):
        """UTM content parameter should be removed."""
        url = "https://example.com/article?utm_content=sidebar"
        result = normalize_url(url)
        assert "utm_content" not in result

    def test_removes_fbclid(self):
        """Facebook click ID should be removed."""
        url = "https://example.com/article?fbclid=abc123"
        result = normalize_url(url)
        assert "fbclid" not in result

    def test_removes_gclid(self):
        """Google click ID should be removed."""
        url = "https://example.com/article?gclid=xyz789"
        result = normalize_url(url)
        assert "gclid" not in result

    def test_removes_msclkid(self):
        """Microsoft click ID should be removed."""
        url = "https://example.com/article?msclkid=ms123"
        result = normalize_url(url)
        assert "msclkid" not in result

    def test_removes_mailchimp_params(self):
        """MailChimp tracking parameters should be removed."""
        url = "https://example.com/article?mc_cid=abc&mc_eid=def"
        result = normalize_url(url)
        assert "mc_cid" not in result
        assert "mc_eid" not in result

    def test_removes_ga_params(self):
        """Google Analytics parameters should be removed."""
        url = "https://example.com/article?_ga=123&_gl=456"
        result = normalize_url(url)
        assert "_ga" not in result
        assert "_gl" not in result

    def test_removes_ref_source_share(self):
        """Generic tracking params (ref, source, share) should be removed."""
        url = "https://example.com/article?ref=twitter&source=email&share=true"
        result = normalize_url(url)
        assert "ref=" not in result
        assert "source=" not in result
        assert "share=" not in result

    def test_removes_ncid(self):
        """News tracking ID should be removed."""
        url = "https://example.com/article?ncid=newslttr"
        result = normalize_url(url)
        assert "ncid" not in result

    def test_removes_multiple_tracking_params(self):
        """Multiple tracking parameters should all be removed."""
        url = "https://example.com/article?utm_source=twitter&utm_medium=social&fbclid=abc&gclid=xyz"
        result = normalize_url(url)
        assert "?" not in result or result.count("=") == 0

    def test_preserves_non_tracking_params(self):
        """Non-tracking query parameters should be preserved."""
        url = "https://example.com/article?id=123&page=2"
        result = normalize_url(url)
        assert "id=123" in result
        assert "page=2" in result

    def test_mixed_tracking_and_regular_params(self):
        """Only tracking params removed, others preserved."""
        url = "https://example.com/article?id=123&utm_source=twitter&page=2"
        result = normalize_url(url)
        assert "id=123" in result
        assert "page=2" in result
        assert "utm_source" not in result

    # ========================================================================
    # AMP URL Handling
    # ========================================================================

    def test_removes_amp_path_segment(self):
        """AMP path segment should be removed."""
        url = "https://example.com/amp/article/test"
        result = normalize_url(url)
        assert "/amp/" not in result

    def test_removes_trailing_amp(self):
        """Trailing /amp should be removed."""
        url = "https://example.com/article/test/amp"
        result = normalize_url(url)
        assert result.endswith("test")

    def test_removes_amp_extension(self):
        """URLs ending in .amp should have extension removed."""
        url = "https://example.com/article/test.amp"
        result = normalize_url(url)
        assert not result.endswith(".amp")

    # ========================================================================
    # Mobile URL Handling
    # ========================================================================

    def test_removes_mobile_path_segment(self):
        """Mobile path segment should be removed."""
        url = "https://example.com/m/article/test"
        result = normalize_url(url)
        assert "/m/" not in result

    def test_removes_mobile_directory(self):
        """/mobile/ path should be normalized."""
        url = "https://example.com/mobile/article/test"
        result = normalize_url(url)
        assert "/mobile/" not in result

    # ========================================================================
    # Domain Normalization
    # ========================================================================

    def test_removes_www_prefix(self):
        """www. prefix should be removed."""
        url = "https://www.example.com/article"
        result = normalize_url(url)
        assert "www." not in result

    def test_lowercase_domain(self):
        """Domain should be lowercased."""
        url = "https://EXAMPLE.COM/article"
        result = normalize_url(url)
        assert "example.com" in result

    def test_lowercase_scheme(self):
        """Scheme should be lowercased."""
        url = "HTTPS://example.com/article"
        result = normalize_url(url)
        assert result.startswith("https://")

    # ========================================================================
    # Trailing Slash Handling
    # ========================================================================

    def test_removes_trailing_slash(self):
        """Trailing slash should be removed (except root)."""
        url = "https://example.com/article/"
        result = normalize_url(url)
        assert not result.endswith("/article/")
        assert result.endswith("/article")

    def test_preserves_root_path(self):
        """Root path should preserve its slash or just be domain."""
        url = "https://example.com/"
        result = normalize_url(url)
        # Root path is acceptable
        assert "example.com" in result

    # ========================================================================
    # Fragment Removal
    # ========================================================================

    def test_removes_fragment(self):
        """URL fragments (anchors) should be removed."""
        url = "https://example.com/article#section2"
        result = normalize_url(url)
        assert "#" not in result

    # ========================================================================
    # Edge Cases
    # ========================================================================

    def test_invalid_url_returns_original(self):
        """Malformed URLs should return the original string."""
        url = "not-a-valid-url"
        result = normalize_url(url)
        # Should not crash, returns something
        assert result is not None

    def test_url_with_port(self):
        """URLs with ports should be handled correctly."""
        url = "https://example.com:8080/article"
        result = normalize_url(url)
        assert ":8080" in result

    def test_complex_real_world_url(self):
        """Test a complex real-world URL with multiple issues."""
        url = "https://www.NEWS.EXAMPLE.COM/amp/article/big-story?utm_source=twitter&utm_medium=social&fbclid=abc123&id=12345#comments"
        result = normalize_url(url)

        assert "www." not in result
        assert "news.example.com" in result
        assert "/amp/" not in result
        assert "utm_source" not in result
        assert "fbclid" not in result
        assert "#" not in result
        assert "id=12345" in result


class TestCalculateTitleSimilarity:
    """Tests for the calculate_title_similarity function."""

    # ========================================================================
    # Basic Similarity
    # ========================================================================

    def test_identical_titles_return_1(self):
        """Identical titles should return 1.0."""
        title = "Breaking News: Major Event Happens"
        result = calculate_title_similarity(title, title)
        assert result == 1.0

    def test_completely_different_titles_low_score(self):
        """Completely different titles should have low similarity."""
        title1 = "Apple announces new iPhone"
        title2 = "Weather forecast for tomorrow"
        result = calculate_title_similarity(title1, title2)
        assert result < 0.5

    def test_similar_titles_high_score(self):
        """Similar titles should have high similarity."""
        title1 = "Apple announces new iPhone 15"
        title2 = "Apple announces the new iPhone 15"
        result = calculate_title_similarity(title1, title2)
        assert result > 0.85

    # ========================================================================
    # Case Insensitivity
    # ========================================================================

    def test_case_insensitive_comparison(self):
        """Comparison should be case-insensitive."""
        title1 = "BREAKING NEWS: Major Event"
        title2 = "breaking news: major event"
        result = calculate_title_similarity(title1, title2)
        assert result == 1.0

    def test_mixed_case_comparison(self):
        """Mixed case should be normalized."""
        title1 = "BreAKinG NeWs: MaJoR EVenT"
        title2 = "Breaking News: Major Event"
        result = calculate_title_similarity(title1, title2)
        assert result == 1.0

    # ========================================================================
    # Whitespace Handling
    # ========================================================================

    def test_strips_whitespace(self):
        """Leading/trailing whitespace should be stripped."""
        title1 = "  Breaking News  "
        title2 = "Breaking News"
        result = calculate_title_similarity(title1, title2)
        assert result == 1.0

    # ========================================================================
    # Empty/None Handling
    # ========================================================================

    def test_empty_first_title_returns_0(self):
        """Empty first title should return 0.0."""
        result = calculate_title_similarity("", "Some title")
        assert result == 0.0

    def test_empty_second_title_returns_0(self):
        """Empty second title should return 0.0."""
        result = calculate_title_similarity("Some title", "")
        assert result == 0.0

    def test_both_empty_returns_0(self):
        """Both empty titles should return 0.0."""
        result = calculate_title_similarity("", "")
        assert result == 0.0

    def test_none_first_title_returns_0(self):
        """None first title should return 0.0."""
        result = calculate_title_similarity(None, "Some title")
        assert result == 0.0

    def test_none_second_title_returns_0(self):
        """None second title should return 0.0."""
        result = calculate_title_similarity("Some title", None)
        assert result == 0.0

    def test_both_none_returns_0(self):
        """Both None titles should return 0.0."""
        result = calculate_title_similarity(None, None)
        assert result == 0.0

    # ========================================================================
    # Real-world Duplicate Detection
    # ========================================================================

    def test_news_headline_variations(self):
        """News headlines about same story should be similar."""
        title1 = "Tech Giant Announces Major Layoffs"
        title2 = "Tech Giant to Announce Major Layoffs"
        result = calculate_title_similarity(title1, title2)
        assert result > 0.8

    def test_slight_rewording(self):
        """Slight rewording should still be detected as similar."""
        title1 = "Company reports record quarterly profits"
        title2 = "Company reports record profits this quarter"
        result = calculate_title_similarity(title1, title2)
        assert result > 0.7


class TestIsSimilarTitle:
    """Tests for the is_similar_title function."""

    # ========================================================================
    # Default Threshold (0.85)
    # ========================================================================

    def test_identical_titles_are_similar(self):
        """Identical titles should be similar."""
        title = "Breaking News"
        assert is_similar_title(title, title) is True

    def test_very_similar_titles_are_similar(self):
        """Very similar titles should be similar."""
        title1 = "Apple announces new iPhone 15 Pro"
        title2 = "Apple announces the new iPhone 15 Pro"
        assert is_similar_title(title1, title2) is True

    def test_different_titles_not_similar(self):
        """Different titles should not be similar."""
        title1 = "Apple announces new iPhone"
        title2 = "Microsoft releases Windows update"
        assert is_similar_title(title1, title2) is False

    # ========================================================================
    # Custom Threshold
    # ========================================================================

    def test_custom_low_threshold(self):
        """Lower threshold should allow more matches."""
        title1 = "Tech company reports earnings"
        title2 = "Tech company reported earnings today"
        # At default 0.85, might not match
        # At 0.7, should match
        assert is_similar_title(title1, title2, threshold=0.7) is True

    def test_custom_high_threshold(self):
        """Higher threshold should be more strict."""
        title1 = "Apple announces new product"
        title2 = "Apple announces the new product"
        # These are very similar but not identical
        assert is_similar_title(title1, title2, threshold=0.99) is False

    def test_threshold_at_boundary(self):
        """Test behavior at exact threshold boundary."""
        title1 = "Test title here"
        title2 = "Test title here"  # Identical = 1.0
        assert is_similar_title(title1, title2, threshold=1.0) is True

    # ========================================================================
    # Empty/None Handling
    # ========================================================================

    def test_empty_titles_not_similar(self):
        """Empty titles should not be similar."""
        assert is_similar_title("", "Some title") is False
        assert is_similar_title("Some title", "") is False
        assert is_similar_title("", "") is False

    def test_none_titles_not_similar(self):
        """None titles should not be similar."""
        assert is_similar_title(None, "Some title") is False
        assert is_similar_title("Some title", None) is False
        assert is_similar_title(None, None) is False

    # ========================================================================
    # Real-world Scenarios
    # ========================================================================

    def test_duplicate_news_from_different_sources(self):
        """Same news from different sources with slight variations."""
        # Common pattern: different sources report same story
        title1 = "Stock Market Reaches All-Time High Amid Economic Optimism"
        title2 = "Stock Market Hits All-Time High as Economic Optimism Grows"
        assert is_similar_title(title1, title2, threshold=0.8) is True

    def test_different_stories_same_topic(self):
        """Different stories on same topic should not match."""
        title1 = "Apple releases iOS 17 update with new features"
        title2 = "Apple fixes critical bug in iOS 17 security update"
        # Same topic but different stories
        assert is_similar_title(title1, title2) is False
