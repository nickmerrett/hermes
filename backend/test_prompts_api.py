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
import random

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.prompt_loader import load_prompt_template, PromptTemplate

# Import Anthropic only if available
try:
    from anthropic import Anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

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
    Test with a model using 3-stage pipeline

    Args:
        item: Test item with baseline data
        model_url: Model API URL (optional if using template)
        model_name: Model name (optional if using template)
        prompt_type: Prompt type for legacy mode
        template: PromptTemplate instance (if using template system)
    """
    # MODE 1: Template system (3-stage pipeline)
    if template:
        # Prepare template variables
        keywords_text = f"Keywords: {', '.join(item['customer']['keywords'][:5])}" if item['customer']['keywords'] else ""
        competitors_text = f"Competitors: {', '.join(item['customer']['competitors'][:5])}" if item['customer']['competitors'] else ""

        # STAGE 1: Relevance Check
        relevance_prompt, relevance_model = template.format_prompt(
            'relevance_check',
            customer_name=item['customer']['name'],
            title=item['title'],
            content=(item['content'] or "")[:3500],
            keywords_text=keywords_text,
            competitors_text=competitors_text
        )

        # Create AI client based on template's model config
        if relevance_model.provider == 'anthropic':
            if not ANTHROPIC_AVAILABLE:
                raise ValueError("Anthropic library not available. Install with: pip install anthropic")
            client = Anthropic(
                api_key=relevance_model.api_key,
                base_url=relevance_model.api_base
            )
            client_type = 'anthropic'
        elif relevance_model.provider in ['openai', 'lmstudio']:
            api_key = relevance_model.api_key if relevance_model.api_key else "lm-studio"
            client = OpenAI(
                api_key=api_key,
                base_url=relevance_model.api_base
            )
            client_type = 'openai'
        else:
            raise ValueError(f"Unknown provider: {relevance_model.provider}")

        model_name = relevance_model.model_name
        max_tokens = relevance_model.max_tokens

        # Call relevance check
        try:
            if client_type == 'anthropic':
                response = client.messages.create(
                    model=model_name,
                    max_tokens=max_tokens,
                    messages=[{"role": "user", "content": relevance_prompt}]
                )
                relevance_text = response.content[0].text
            else:
                response = client.chat.completions.create(
                    model=model_name,
                    messages=[{"role": "user", "content": relevance_prompt}],
                    temperature=0.3,
                    max_tokens=max_tokens
                )
                relevance_text = response.choices[0].message.content

            import re
            json_match = re.search(r'\{[\s\S]*\}', relevance_text)
            if not json_match:
                return {'success': False, 'error': 'No JSON in relevance check', 'raw_response': relevance_text}
            relevance_data = json.loads(json_match.group(0))

            # If not relevant, return early
            if not relevance_data.get('is_relevant', False):
                return {
                    'success': True,
                    'data': {
                        'is_relevant': False,
                        'summary': relevance_data.get('reason', 'Not relevant'),
                        'category': 'unrelated',
                        'sentiment': 'neutral',
                        'entities': {'companies': [], 'technologies': [], 'people': []},
                        'tags': [],
                        'priority_score': 0.0,
                        'pain_points_opportunities': {'pain_points': [], 'opportunities': []}
                    },
                    'raw_response': f"Stage 1: {relevance_text}"
                }

            # STAGE 2: Core Analysis
            core_prompt, core_model = template.format_prompt(
                'core_analysis',
                customer_name=item['customer']['name'],
                title=item['title'],
                content=(item['content'] or "")[:3500],
                source_type=item.get('source_type', 'unknown'),
                keywords_text=keywords_text,
                competitors_text=competitors_text
            )

            if client_type == 'anthropic':
                response = client.messages.create(
                    model=model_name,
                    max_tokens=max_tokens,
                    messages=[{"role": "user", "content": core_prompt}]
                )
                core_text = response.content[0].text
            else:
                response = client.chat.completions.create(
                    model=model_name,
                    messages=[{"role": "user", "content": core_prompt}],
                    temperature=0.3,
                    max_tokens=max_tokens
                )
                core_text = response.choices[0].message.content

            json_match = re.search(r'\{[\s\S]*\}', core_text)
            if not json_match:
                return {'success': False, 'error': 'No JSON in core analysis', 'raw_response': core_text}
            core_data = json.loads(json_match.group(0))

            # STAGE 3: Business Insights (only for medium+ priority)
            priority_score = core_data.get('priority_score', 0.0)
            if priority_score >= 0.4:
                insights_prompt, insights_model = template.format_prompt(
                    'business_insights',
                    customer_name=item['customer']['name'],
                    title=item['title'],
                    summary=core_data.get('summary', ''),
                    category=core_data.get('category', '')
                )

                if client_type == 'anthropic':
                    response = client.messages.create(
                        model=model_name,
                        max_tokens=max_tokens,
                        messages=[{"role": "user", "content": insights_prompt}]
                    )
                    insights_text = response.content[0].text
                else:
                    response = client.chat.completions.create(
                        model=model_name,
                        messages=[{"role": "user", "content": insights_prompt}],
                        temperature=0.3,
                        max_tokens=max_tokens
                    )
                    insights_text = response.choices[0].message.content

                json_match = re.search(r'\{[\s\S]*\}', insights_text)
                if json_match:
                    insights_data = json.loads(json_match.group(0))
                    pain_points_opportunities = insights_data
                else:
                    pain_points_opportunities = {'pain_points': [], 'opportunities': []}
            else:
                pain_points_opportunities = {'pain_points': [], 'opportunities': []}
                insights_text = "Skipped (low priority)"

            # Combine results
            combined_data = {
                'is_relevant': True,
                'summary': core_data.get('summary', ''),
                'category': core_data.get('category', ''),
                'sentiment': core_data.get('sentiment', ''),
                'entities': core_data.get('entities', {'companies': [], 'technologies': [], 'people': []}),
                'tags': core_data.get('tags', []),
                'priority_score': priority_score,
                'pain_points_opportunities': pain_points_opportunities
            }

            return {
                'success': True,
                'data': combined_data,
                'raw_response': f"Stage 1: {relevance_text}\n\nStage 2: {core_text}\n\nStage 3: {insights_text if priority_score >= 0.4 else 'Skipped'}"
            }

        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'raw_response': None
            }

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

    parser.add_argument('--limit', type=int, default=10, help='Number of items to test')
    parser.add_argument('--pool-size', type=int, default=50, help='Size of item pool to randomly select from')
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

            # Show what model will be used for relevance_check (first stage)
            prompt_config = template.get_prompt('relevance_check')
            print(f"  Model for relevance_check: {prompt_config.model.model_name}")
            print(f"  Provider: {prompt_config.model.provider}")
            print(f"  API Base: {prompt_config.model.api_base}\n")
        except Exception as e:
            print(f"{Colors.RED}Error loading template: {e}{Colors.RESET}")
            return
    else:
        print(f"Model API: {args.model_url}")
        print(f"Model: {args.model}")
        print(f"Prompt: {args.prompt_type}\n")

    print(f"Test setup: {args.limit} items randomly selected from pool of {args.pool_size}\n")

    # Fetch test data pool
    print(f"Fetching pool of {args.pool_size} items...")
    all_items = get_test_items(args.api_url, args.pool_size)

    if not all_items:
        print(f"{Colors.RED}No items fetched{Colors.RESET}")
        return

    # Randomly select items from pool
    if len(all_items) > args.limit:
        items = random.sample(all_items, args.limit)
        print(f"✓ Randomly selected {args.limit} items from pool of {len(all_items)}\n")
    else:
        items = all_items
        print(f"✓ Using all {len(items)} available items\n")

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
