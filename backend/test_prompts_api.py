#!/usr/bin/env python3
"""
Test and compare AI prompts using API (no database access needed).

This script:
1. Fetches test items via API (frontier model baseline)
2. Re-processes them with test model/prompt
3. Compares results and shows metrics
"""

import requests
import json
import asyncio
from typing import List, Dict, Any, Optional
import argparse
from openai import OpenAI
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.prompt_loader import load_prompt_template, PromptTemplate
from anthropic import Anthropic

# Color codes for terminal output
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    RESET = '\033[0m'
    BOLD = '\033[1m'


def get_test_items(api_url: str, limit: int = 10) -> List[Dict[str, Any]]:
    """Fetch test items from API"""
    url = f"{api_url}/api/testing/test-data"
    params = {'limit': limit}

    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        return data['items']
    except Exception as e:
        print(f"{Colors.RED}Error fetching test data: {e}{Colors.RESET}")
        return []


def build_prompt_small(title: str, content: str, customer_name: str,
                       keywords: List[str], competitors: List[str]) -> str:
    """Build simplified prompt for small models"""
    keywords_text = f"Keywords: {', '.join(keywords[:5])}" if keywords else ""
    competitors_text = f"Competitors: {', '.join(competitors[:5])}" if competitors else ""

    return f"""Analyze this article about {customer_name}.

CONTENT:
Title: {title}
Text: {content[:2500]}

{keywords_text}
{competitors_text}

TASK: Output JSON ONLY with these fields:

1. "is_relevant": true or false
   - FIRST: Check if "{customer_name}" appears in the title or content
   - If NOT mentioned → MUST be false
   - If mentioned → true only if it's real company news (not ads/deals)

2. "summary": 2-3 sentences explaining what happened and why it matters

3. "category": ONE of these:
   product_update, financial, market_news, competitor, challenge, opportunity, leadership, partnership, advertisement, unrelated, other

4. "sentiment": positive, negative, neutral, or mixed

5. "entities": Extract these:
   {{"companies": ["list all companies"], "technologies": ["list tech/products"], "people": ["list people"]}}

6. "tags": List 3-5 relevant tags

7. "pain_points_opportunities":
   {{"pain_points": ["2-3 words", "2-3 words"], "opportunities": ["2-3 words", "2-3 words"]}}

   CRITICAL: Each item must be 2-3 words MAXIMUM. Examples:
   GOOD: "Network outage", "Budget cuts", "Market expansion"
   BAD: "Customers experiencing service issues" (too long!)

   If none found, use empty arrays: {{"pain_points": [], "opportunities": []}}

8. "priority_score": Number from 0.0 to 1.0
   - 0.8-1.0: Major news (leadership changes, big launches, competitive threats)
   - 0.4-0.7: Normal news (product updates, partnerships)
   - 0.1-0.3: Minor news
   - 0.0: Not relevant or ads

IMPORTANT:
- Output ONLY valid JSON, no other text
- If {customer_name} not mentioned → is_relevant MUST be false
- Pain points/opportunities: 2-3 words each, NO sentences

JSON:"""


async def test_with_model(item: Dict, model_url: str = None, model_name: str = None,
                         prompt_type: str = "small", template: Optional[PromptTemplate] = None) -> Dict[str, Any]:
    """
    Test with a model

    Args:
        item: Test item with baseline data
        model_url: Model API URL (optional if using template)
        model_name: Model name (optional if using template)
        prompt_type: Prompt type for legacy mode
        template: PromptTemplate instance (if using template system)
    """
    # MODE 1: Template system
    if template:
        # Prepare template variables
        keywords_text = f"Keywords: {', '.join(item['customer']['keywords'][:5])}" if item['customer']['keywords'] else ""
        competitors_text = f"Competitors: {', '.join(item['customer']['competitors'][:5])}" if item['customer']['competitors'] else ""

        # Get formatted prompt and model config from template
        prompt, model_config = template.format_prompt(
            'intelligence_analysis',
            customer_name=item['customer']['name'],
            title=item['title'],
            content=(item['content'] or "")[:3500],
            source_type=item.get('source_type', 'unknown'),
            keywords_text=keywords_text,
            competitors_text=competitors_text
        )

        # Create AI client based on template's model config
        if model_config.provider == 'anthropic':
            client = Anthropic(
                api_key=model_config.api_key,
                base_url=model_config.api_base
            )
            client_type = 'anthropic'
        elif model_config.provider in ['openai', 'lmstudio']:
            api_key = model_config.api_key if model_config.api_key else "lm-studio"
            client = OpenAI(
                api_key=api_key,
                base_url=model_config.api_base
            )
            client_type = 'openai'
        else:
            raise ValueError(f"Unknown provider: {model_config.provider}")

        model_name = model_config.model_name
        max_tokens = model_config.max_tokens

    # MODE 2: Legacy mode (manual model/prompt specification)
    else:
        # Build prompt using hardcoded function
        if prompt_type == "small":
            prompt = build_prompt_small(
                title=item['title'],
                content=item['content'] or "",
                customer_name=item['customer']['name'],
                keywords=item['customer']['keywords'],
                competitors=item['customer']['competitors']
            )
        else:
            # For frontier, we'd need to import the full prompt
            # For now, just use small
            prompt = build_prompt_small(
                title=item['title'],
                content=item['content'] or "",
                customer_name=item['customer']['name'],
                keywords=item['customer']['keywords'],
                competitors=item['customer']['competitors']
            )

        # Call model with OpenAI-compatible API
        client = OpenAI(
            api_key="not-needed",
            base_url=model_url
        )
        client_type = 'openai'
        max_tokens = 1500

    # Call AI model
    try:
        if client_type == 'anthropic':
            response = client.messages.create(
                model=model_name,
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": prompt}]
            )
            response_text = response.content[0].text
        elif client_type == 'openai':
            response = client.chat.completions.create(
                model=model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=max_tokens
            )
            response_text = response.choices[0].message.content
        else:
            raise ValueError(f"Unknown client type: {client_type}")

        # Parse JSON
        import re
        json_match = re.search(r'\{[\s\S]*\}', response_text)
        if json_match:
            data = json.loads(json_match.group(0))
            return {
                'success': True,
                'data': data,
                'raw_response': response_text
            }
        else:
            return {
                'success': False,
                'error': 'No JSON found',
                'raw_response': response_text
            }
    except Exception as e:
        return {
            'success': False,
            'error': str(e),
            'raw_response': None
        }


def compare_results(baseline: Dict, test_result: Dict) -> Dict:
    """Compare test against baseline"""
    if not test_result['success']:
        return {
            'valid': False,
            'error': test_result.get('error', 'Unknown error')
        }

    data = test_result['data']
    baseline_relevant = baseline['category'] not in ['unrelated', 'advertisement']

    comparison = {
        'valid': True,
        'relevance_match': data.get('is_relevant') == baseline_relevant,
        'category_match': data.get('category') == baseline['category'],
        'sentiment_match': data.get('sentiment') == baseline['sentiment'],
        'pain_points_word_count': [],
        'opportunities_word_count': [],
    }

    # Check word counts
    ppo = data.get('pain_points_opportunities', {})
    if isinstance(ppo, dict):
        for pp in ppo.get('pain_points', []):
            comparison['pain_points_word_count'].append(len(str(pp).split()))
        for opp in ppo.get('opportunities', []):
            comparison['opportunities_word_count'].append(len(str(opp).split()))

    comparison['pain_points_violations'] = [wc for wc in comparison['pain_points_word_count'] if wc > 3]
    comparison['opportunities_violations'] = [wc for wc in comparison['opportunities_word_count'] if wc > 3]

    return comparison


def print_detailed_comparison(item_num: int, item: Dict, test_result: Dict, comparison: Dict):
    """Print detailed side-by-side comparison for one item"""
    print(f"\n{Colors.BOLD}{'='*100}{Colors.RESET}")
    print(f"{Colors.BOLD}Item {item_num}: {item['title'][:80]}...{Colors.RESET}")
    print(f"{'='*100}")

    baseline = item['baseline']

    if not comparison['valid']:
        print(f"{Colors.RED}❌ FAILED: {comparison.get('error', 'Unknown')}{Colors.RESET}")
        return

    data = test_result['data']

    # Side-by-side comparison table
    print(f"\n{'Field':<20} {'Baseline':<40} {'Test Result':<40} {'Match'}")
    print(f"{'-'*20} {'-'*40} {'-'*40} {'-'*5}")

    # Relevance
    baseline_rel = baseline['category'] not in ['unrelated', 'advertisement']
    test_rel = data.get('is_relevant', False)
    match_icon = "✅" if comparison['relevance_match'] else f"{Colors.RED}❌{Colors.RESET}"
    print(f"{'is_relevant':<20} {str(baseline_rel):<40} {str(test_rel):<40} {match_icon}")

    # Category
    match_icon = "✅" if comparison['category_match'] else f"{Colors.RED}❌{Colors.RESET}"
    print(f"{'category':<20} {baseline['category']:<40} {data.get('category', 'N/A'):<40} {match_icon}")

    # Sentiment
    match_icon = "✅" if comparison['sentiment_match'] else f"{Colors.RED}❌{Colors.RESET}"
    print(f"{'sentiment':<20} {baseline['sentiment']:<40} {data.get('sentiment', 'N/A'):<40} {match_icon}")

    # Priority score
    baseline_priority = baseline.get('priority_score', 0.0)
    test_priority = data.get('priority_score', 0.0)
    diff = abs(baseline_priority - test_priority)
    diff_color = Colors.GREEN if diff < 0.2 else Colors.YELLOW if diff < 0.4 else Colors.RED
    print(f"{'priority_score':<20} {baseline_priority:<40.2f} {test_priority:<40.2f} {diff_color}Δ{diff:.2f}{Colors.RESET}")

    # Summary comparison
    print(f"\n{Colors.BOLD}Summary:{Colors.RESET}")
    print(f"  Baseline: {baseline.get('summary', 'N/A')[:200]}")
    print(f"  Test:     {data.get('summary', 'N/A')[:200]}")

    # Pain points & opportunities
    ppo_baseline = baseline.get('pain_points_opportunities', {})
    ppo_test = data.get('pain_points_opportunities', {})

    print(f"\n{Colors.BOLD}Pain Points:{Colors.RESET}")
    baseline_pp = ppo_baseline.get('pain_points', []) if isinstance(ppo_baseline, dict) else []
    test_pp = ppo_test.get('pain_points', []) if isinstance(ppo_test, dict) else []
    print(f"  Baseline: {baseline_pp}")
    for i, pp in enumerate(test_pp, 1):
        wc = len(str(pp).split())
        icon = "✅" if wc <= 3 else f"{Colors.RED}❌ ({wc} words){Colors.RESET}"
        print(f"  Test {i}:   {icon} {pp}")

    print(f"\n{Colors.BOLD}Opportunities:{Colors.RESET}")
    baseline_opp = ppo_baseline.get('opportunities', []) if isinstance(ppo_baseline, dict) else []
    test_opp = ppo_test.get('opportunities', []) if isinstance(ppo_test, dict) else []
    print(f"  Baseline: {baseline_opp}")
    for i, opp in enumerate(test_opp, 1):
        wc = len(str(opp).split())
        icon = "✅" if wc <= 3 else f"{Colors.RED}❌ ({wc} words){Colors.RESET}"
        print(f"  Test {i}:   {icon} {opp}")


def print_summary(results: List[Dict], verbose: bool = False):
    """Print summary statistics"""
    total = len(results)
    valid = sum(1 for r in results if r['comparison']['valid'])

    print(f"\n{Colors.BOLD}=== TEST SUMMARY ==={Colors.RESET}")
    print(f"Total items: {total}")
    print(f"Valid responses: {valid}/{total} ({valid/total*100:.1f}%)")

    if valid == 0:
        print(f"{Colors.RED}No valid responses{Colors.RESET}")
        return

    valid_results = [r for r in results if r['comparison']['valid']]

    # Accuracy
    rel_acc = sum(1 for r in valid_results if r['comparison']['relevance_match']) / valid
    cat_acc = sum(1 for r in valid_results if r['comparison']['category_match']) / valid
    sent_acc = sum(1 for r in valid_results if r['comparison']['sentiment_match']) / valid

    print(f"\n{Colors.BOLD}Accuracy vs Baseline:{Colors.RESET}")
    print(f"  Relevance: {rel_acc*100:.1f}%")
    print(f"  Category:  {cat_acc*100:.1f}%")
    print(f"  Sentiment: {sent_acc*100:.1f}%")

    # Word count compliance
    all_pp_violations = []
    all_opp_violations = []
    for r in valid_results:
        all_pp_violations.extend(r['comparison']['pain_points_violations'])
        all_opp_violations.extend(r['comparison']['opportunities_violations'])

    total_pp = sum(len(r['comparison']['pain_points_word_count']) for r in valid_results)
    total_opp = sum(len(r['comparison']['opportunities_word_count']) for r in valid_results)

    print(f"\n{Colors.BOLD}Word Count Compliance:{Colors.RESET}")
    if total_pp > 0:
        pp_compliance = (total_pp - len(all_pp_violations)) / total_pp * 100
        print(f"  Pain points: {pp_compliance:.1f}% (≤3 words)")
        if all_pp_violations:
            print(f"    {Colors.RED}Violations: {len(all_pp_violations)} with {all_pp_violations} words{Colors.RESET}")
    else:
        print(f"  Pain points: N/A")

    if total_opp > 0:
        opp_compliance = (total_opp - len(all_opp_violations)) / total_opp * 100
        print(f"  Opportunities: {opp_compliance:.1f}% (≤3 words)")
        if all_opp_violations:
            print(f"    {Colors.RED}Violations: {len(all_opp_violations)} with {all_opp_violations} words{Colors.RESET}")
    else:
        print(f"  Opportunities: N/A")

    # Print detailed comparisons if verbose
    if verbose:
        print(f"\n{Colors.BOLD}{'='*100}{Colors.RESET}")
        print(f"{Colors.BOLD}DETAILED COMPARISONS{Colors.RESET}")
        print(f"{Colors.BOLD}{'='*100}{Colors.RESET}")
        for i, r in enumerate(results, 1):
            print_detailed_comparison(i, r['item'], r['test_result'], r['comparison'])


async def main():
    parser = argparse.ArgumentParser(
        description='Test prompts via API',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Use template system (RECOMMENDED)
  python test_prompts_api.py --template qwen3-4b --limit 20

  # Use template with absolute path
  python test_prompts_api.py --template /path/to/custom.yaml --limit 20

  # Legacy mode with manual model specification
  python test_prompts_api.py --model-url http://localhost:1234/v1 --model qwen/qwen3-vl-4b --limit 20
        """
    )
    parser.add_argument('--api-url', default='http://localhost:8000', help='Hermes API URL')

    # Template system (recommended)
    parser.add_argument('--template', '-t', help='Prompt template name or absolute path (e.g., "qwen3-4b" or "/path/to/template.yaml")')

    # Legacy manual specification (only used if --template not specified)
    parser.add_argument('--model-url', default='http://localhost:1234/v1', help='LM Studio API URL (legacy mode)')
    parser.add_argument('--model', default='ibm/granite-4.0-h-micro', help='Model name (legacy mode)')
    parser.add_argument('--prompt-type', choices=['small', 'frontier'], default='small', help='Prompt type (legacy mode)')

    parser.add_argument('--limit', type=int, default=10, help='Number of items')
    parser.add_argument('--verbose', '-v', action='store_true', help='Show detailed side-by-side comparison')

    args = parser.parse_args()

    print(f"{Colors.BOLD}{Colors.BLUE}=== Prompt Testing (API Mode) ==={Colors.RESET}")
    print(f"Hermes API: {args.api_url}")

    # Load template if specified
    template = None
    if args.template:
        try:
            print(f"Loading template: {args.template}")
            template = load_prompt_template(args.template)
            print(f"✓ Template loaded: {len(template.prompts)} prompts, {len(template.models)} models")

            # Show what model will be used for intelligence_analysis
            prompt_config = template.get_prompt('intelligence_analysis')
            print(f"  Model for intelligence_analysis: {prompt_config.model.model_name}")
            print(f"  Provider: {prompt_config.model.provider}")
            print(f"  API Base: {prompt_config.model.api_base}\n")
        except Exception as e:
            print(f"{Colors.RED}Error loading template: {e}{Colors.RESET}")
            return
    else:
        print(f"Model API: {args.model_url}")
        print(f"Model: {args.model}")
        print(f"Prompt: {args.prompt_type}\n")

    print(f"Test items: {args.limit}\n")

    # Fetch test data
    print("Fetching test items...")
    items = get_test_items(args.api_url, args.limit)
    print(f"Loaded {len(items)} items\n")

    if not items:
        return

    # Test each item
    results = []
    for i, item in enumerate(items, 1):
        print(f"Testing {i}/{len(items)}: {item['title'][:60]}...")

        test_result = await test_with_model(
            item=item,
            model_url=args.model_url if not template else None,
            model_name=args.model if not template else None,
            prompt_type=args.prompt_type,
            template=template
        )

        comparison = compare_results(item['baseline'], test_result)

        results.append({
            'item': item,
            'test_result': test_result,
            'comparison': comparison
        })

    # Summary
    print_summary(results, verbose=args.verbose)


if __name__ == "__main__":
    asyncio.run(main())
