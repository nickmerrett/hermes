"""Text cleaning utilities for embedding preparation"""

import re
import html


def clean_text_for_embedding(title: str, content: str = None) -> str:
    """
    Prepare clean text for embedding generation.

    Strips HTML, markdown, URLs, and other markup from content,
    then combines with title.

    Args:
        title: Article/item title (assumed already clean)
        content: Raw content (may contain HTML, markdown, etc.)

    Returns:
        Clean text suitable for embedding generation
    """
    clean_content = strip_markup(content) if content else ''

    if clean_content:
        return f"{title}\n\n{clean_content}"
    return title


def strip_markup(text: str) -> str:
    """
    Remove HTML, markdown, and other markup from text.

    Handles:
    - HTML tags, entities, script/style blocks
    - URLs (http/https, data URIs, base64-encoded)
    - Markdown formatting (bold, italic, links, headers, images, code)
    - Excessive whitespace

    Args:
        text: Raw text potentially containing markup

    Returns:
        Clean plain text
    """
    if not text:
        return ''

    # --- HTML ---

    # Remove script and style blocks entirely
    text = re.sub(r'<script[^>]*>.*?</script>', ' ', text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<style[^>]*>.*?</style>', ' ', text, flags=re.DOTALL | re.IGNORECASE)

    # Remove HTML comments
    text = re.sub(r'<!--.*?-->', ' ', text, flags=re.DOTALL)

    # Replace block-level tags with newlines for readability
    text = re.sub(r'<(?:br|p|div|li|tr|h[1-6])[^>]*/?\s*>', '\n', text, flags=re.IGNORECASE)

    # Remove all remaining HTML tags
    text = re.sub(r'<[^>]+>', ' ', text)

    # Decode HTML entities (&amp; &nbsp; &#8217; etc.)
    text = html.unescape(text)

    # Normalize non-breaking spaces and other unicode whitespace to regular spaces
    text = text.replace('\xa0', ' ')
    text = text.replace('\u200b', '')  # zero-width space

    # --- Markdown links/images (before URL stripping so URLs inside [] () are intact) ---

    # Remove images: ![alt](url)
    text = re.sub(r'!\[[^\]]*\]\([^)]*\)', ' ', text)

    # Convert links to just the text: [text](url) -> text
    text = re.sub(r'\[([^\]]*)\]\([^)]*\)', r'\1', text)

    # --- URLs ---

    # Remove URLs (http, https, ftp, data URIs)
    text = re.sub(r'https?://\S+', ' ', text)
    text = re.sub(r'ftp://\S+', ' ', text)
    text = re.sub(r'data:\S+', ' ', text)

    # Remove headers: # ## ### etc.
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)

    # Remove bold/italic markers: **text** *text* __text__ _text_
    text = re.sub(r'\*{1,3}([^*]+)\*{1,3}', r'\1', text)
    text = re.sub(r'_{1,3}(\S[^_]*\S)_{1,3}', r'\1', text)

    # Remove strikethrough: ~~text~~
    text = re.sub(r'~~([^~]+)~~', r'\1', text)

    # Remove code blocks and inline code
    text = re.sub(r'```[^`]*```', ' ', text, flags=re.DOTALL)
    text = re.sub(r'`([^`]*)`', r'\1', text)

    # Remove horizontal rules
    text = re.sub(r'^[\s]*[-*_]{3,}[\s]*$', '', text, flags=re.MULTILINE)

    # Remove blockquote markers
    text = re.sub(r'^>\s?', '', text, flags=re.MULTILINE)

    # --- Whitespace cleanup ---

    # Collapse multiple spaces/tabs to single space
    text = re.sub(r'[ \t]+', ' ', text)
    # Collapse 3+ newlines to double newline
    text = re.sub(r'\n{3,}', '\n\n', text)
    # Strip leading/trailing whitespace per line
    text = '\n'.join(line.strip() for line in text.split('\n'))
    # Strip overall
    text = text.strip()

    return text
