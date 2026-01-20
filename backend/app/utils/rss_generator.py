"""RSS 2.0 feed generator utility"""

from datetime import datetime
from typing import List, Optional
from xml.etree.ElementTree import Element, SubElement, tostring
from xml.dom.minidom import parseString
import html


def generate_rss_feed(
    items: List[dict],
    customer_name: str,
    feed_url: str,
    feed_title: Optional[str] = None,
    feed_description: Optional[str] = None
) -> str:
    """
    Generate an RSS 2.0 XML feed from intelligence items

    Args:
        items: List of intelligence item dicts with keys:
            - title: str
            - url: str (optional)
            - summary: str (optional, from processed intelligence)
            - content: str (optional, raw content)
            - published_date: datetime (optional)
            - source_type: str
            - category: str (optional)
            - priority_score: float (optional)
            - sentiment: str (optional)
        customer_name: Name of the customer for feed title
        feed_url: URL of this RSS feed (for self-reference)
        feed_title: Optional custom feed title
        feed_description: Optional custom feed description

    Returns:
        RSS 2.0 XML string
    """
    # Create RSS root element
    rss = Element('rss')
    rss.set('version', '2.0')
    rss.set('xmlns:atom', 'http://www.w3.org/2005/Atom')

    # Create channel
    channel = SubElement(rss, 'channel')

    # Channel metadata
    title = SubElement(channel, 'title')
    title.text = feed_title or f"Hermes Intelligence Feed - {customer_name}"

    link = SubElement(channel, 'link')
    link.text = feed_url

    description = SubElement(channel, 'description')
    description.text = feed_description or f"Customer intelligence feed for {customer_name} from Hermes"

    # Add atom:link for self-reference (required by some feed validators)
    atom_link = SubElement(channel, 'atom:link')
    atom_link.set('href', feed_url)
    atom_link.set('rel', 'self')
    atom_link.set('type', 'application/rss+xml')

    # Generator
    generator = SubElement(channel, 'generator')
    generator.text = 'Hermes Customer Intelligence Platform'

    # Last build date
    last_build = SubElement(channel, 'lastBuildDate')
    last_build.text = _format_rfc822_date(datetime.utcnow())

    # Add items
    for item_data in items:
        item = SubElement(channel, 'item')

        # Title (required)
        item_title = SubElement(item, 'title')
        item_title.text = _sanitize_text(item_data.get('title', 'Untitled'))

        # Link (optional but recommended)
        if item_data.get('url'):
            item_link = SubElement(item, 'link')
            item_link.text = item_data['url']

            # GUID (use URL if available)
            guid = SubElement(item, 'guid')
            guid.set('isPermaLink', 'true')
            guid.text = item_data['url']
        else:
            # Use item ID as GUID if no URL
            guid = SubElement(item, 'guid')
            guid.set('isPermaLink', 'false')
            guid.text = f"hermes-item-{item_data.get('id', datetime.utcnow().timestamp())}"

        # Description (summary or content)
        item_desc = SubElement(item, 'description')
        desc_text = item_data.get('summary') or item_data.get('content') or ''

        # Add metadata to description
        metadata_parts = []
        if item_data.get('source_type'):
            metadata_parts.append(f"Source: {item_data['source_type']}")
        if item_data.get('category'):
            metadata_parts.append(f"Category: {item_data['category']}")
        if item_data.get('priority_score') is not None:
            priority = _get_priority_label(item_data['priority_score'])
            metadata_parts.append(f"Priority: {priority}")
        if item_data.get('sentiment'):
            metadata_parts.append(f"Sentiment: {item_data['sentiment']}")

        if metadata_parts:
            desc_text = f"{desc_text}\n\n---\n{' | '.join(metadata_parts)}"

        item_desc.text = _sanitize_text(desc_text)

        # Publication date
        if item_data.get('published_date'):
            pub_date = SubElement(item, 'pubDate')
            pub_date.text = _format_rfc822_date(item_data['published_date'])

        # Category
        if item_data.get('category'):
            category = SubElement(item, 'category')
            category.text = item_data['category']

        # Source type as category
        if item_data.get('source_type'):
            source_cat = SubElement(item, 'category')
            source_cat.text = f"source:{item_data['source_type']}"

    # Convert to string with pretty printing
    xml_str = tostring(rss, encoding='unicode')

    # Add XML declaration
    xml_declaration = '<?xml version="1.0" encoding="UTF-8"?>\n'

    # Pretty print
    try:
        dom = parseString(xml_str)
        pretty_xml = dom.toprettyxml(indent='  ')
        # Remove the XML declaration from toprettyxml (it adds its own)
        lines = pretty_xml.split('\n')
        if lines[0].startswith('<?xml'):
            lines = lines[1:]
        return xml_declaration + '\n'.join(lines)
    except Exception:
        # Fallback to non-pretty XML
        return xml_declaration + xml_str


def _format_rfc822_date(dt: datetime) -> str:
    """Format datetime as RFC 822 date string for RSS"""
    if dt is None:
        return ''
    # RFC 822 format: "Sun, 19 May 2024 15:21:36 GMT"
    return dt.strftime('%a, %d %b %Y %H:%M:%S GMT')


def _get_priority_label(score: float) -> str:
    """Convert priority score to human-readable label"""
    if score >= 0.8:
        return 'High'
    elif score >= 0.5:
        return 'Medium'
    else:
        return 'Low'


def _sanitize_text(text: str) -> str:
    """Sanitize text for XML content"""
    if not text:
        return ''
    # HTML escape special characters
    return html.escape(str(text))
