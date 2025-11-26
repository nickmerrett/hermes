#!/usr/bin/env python3
"""
Test and compare AI prompts using existing database items as baseline.

This script:
1. Loads processed items from the database (frontier model baseline)
2. Re-processes them with test model/prompt
3. Compares results and shows metrics
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import SessionLocal
from app.models.database import IntelligenceItem, ProcessedIntelligence, Customer
from app.processors.ai_processor import AIProcessor
from openai import OpenAI
import json
import asyncio
from typing import List, Dict, Any
import argparse
from datetime import datetime

# Color codes for terminal output
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    RESET = '\033[0m'
    BOLD = '\033[1m'


def get_test_items(db, limit: int = 10) -> List[tuple]:
    """Get random items with their frontier model results as baseline"""
    items = db.query(IntelligenceItem).join(
        ProcessedIntelligence,
        IntelligenceItem.id == ProcessedIntelligence.item_id
    ).join(
        Customer,
        IntelligenceItem.customer_id == Customer.id
    ).filter(
        ProcessedIntelligence.summary.isnot(None),
        IntelligenceItem.content.isnot(None)
    ).order_by(
        IntelligenceItem.id.desc()
    ).limit(limit).all()

    results = []
    for item in items:
        customer = db.query(Customer).filter(Customer.id == item.customer_id).first()
        results.append((item, item.processed, customer))

    return results


async def test_with_custom_model(
    title: str,
    content: str,
    customer: Customer,
    api_base_url: str,
    model_name: str,
    prompt_builder,
    use_small_prompt: bool = True
) -> Dict[str, Any]:
    """Test with a custom model (like Qwen via LM Studio)"""

    # Build the prompt
    if use_small_prompt:
        # Temporarily set tier to small
        original_tier = prompt_builder.model_tier
        prompt_builder.model_tier = "small"
        prompt = prompt_builder._build_prompt(
            title=title,
            content=content,
            customer_name=customer.name,
            source_type="test",
            keywords=customer.keywords or [],
            competitors=customer.competitors or [],
            priority_keywords=[],
            is_trusted_source=False
        )
        prompt_builder.model_tier = original_tier
    else:
        prompt = prompt_builder._build_prompt_frontier(
            title=title,
            content=content,
            customer_name=customer.name,
            source_type="test",
            keywords=customer.keywords or [],
            competitors=customer.competitors or [],
            priority_keywords=[],
            is_trusted_source=False
        )

    # Call the model
    client = OpenAI(
        api_key="not-needed",  # LM Studio doesn't require API key
        base_url=api_base_url
    )

    try:
        response = client.chat.completions.create(
            model=model_name,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=1500
        )
        response_text = response.choices[0].message.content

        # Parse response
        import re
        json_match = re.search(r'\{[\s\S]*\}', response_text)
        if json_match:
            json_str = json_match.group(0)
            data = json.loads(json_str)
            return {
                'success': True,
                'data': data,
                'raw_response': response_text
            }
        else:
            return {
                'success': False,
                'error': 'No JSON found in response',
                'raw_response': response_text
            }
    except Exception as e:
        return {
            'success': False,
            'error': str(e),
            'raw_response': None
        }


def compare_results(baseline: ProcessedIntelligence, test_result: Dict[str, Any]) -> Dict[str, Any]:
    """Compare test result against baseline"""
    if not test_result['success']:
        return {
            'valid': False,
            'error': test_result.get('error', 'Unknown error')
        }

    data = test_result['data']
    comparison = {
        'valid': True,
        'relevance_match': data.get('is_relevant') == (baseline.category not in ['unrelated', 'advertisement']),
        'category_match': data.get('category') == baseline.category,
        'sentiment_match': data.get('sentiment') == baseline.sentiment,
        'pain_points_word_count': [],
        'opportunities_word_count': [],
        'has_pain_points': False,
        'has_opportunities': False,
    }

    # Check pain points word count compliance
    ppo = data.get('pain_points_opportunities', {})
    if isinstance(ppo, dict):
        pain_points = ppo.get('pain_points', [])
        opportunities = ppo.get('opportunities', [])

        comparison['has_pain_points'] = len(pain_points) > 0
        comparison['has_opportunities'] = len(opportunities) > 0

        for pp in pain_points:
            word_count = len(str(pp).split())
            comparison['pain_points_word_count'].append(word_count)

        for opp in opportunities:
            word_count = len(str(opp).split())
            comparison['opportunities_word_count'].append(word_count)

    # Word count violations (> 3 words)
    comparison['pain_points_violations'] = [wc for wc in comparison['pain_points_word_count'] if wc > 3]
    comparison['opportunities_violations'] = [wc for wc in comparison['opportunities_word_count'] if wc > 3]

    return comparison


def print_summary(results: List[Dict[str, Any]]):
    """Print summary statistics"""
    total = len(results)
    valid = sum(1 for r in results if r['comparison']['valid'])

    print(f"\n{Colors.BOLD}=== TEST SUMMARY ==={Colors.RESET}")
    print(f"Total items tested: {total}")
    print(f"Valid JSON responses: {valid}/{total} ({valid/total*100:.1f}%)")

    if valid == 0:
        print(f"{Colors.RED}No valid responses to analyze{Colors.RESET}")
        return

    valid_results = [r for r in results if r['comparison']['valid']]

    # Accuracy metrics
    relevance_acc = sum(1 for r in valid_results if r['comparison']['relevance_match']) / valid
    category_acc = sum(1 for r in valid_results if r['comparison']['category_match']) / valid
    sentiment_acc = sum(1 for r in valid_results if r['comparison']['sentiment_match']) / valid

    print(f"\n{Colors.BOLD}Accuracy vs Baseline:{Colors.RESET}")
    print(f"  Relevance: {relevance_acc*100:.1f}%")
    print(f"  Category:  {category_acc*100:.1f}%")
    print(f"  Sentiment: {sentiment_acc*100:.1f}%")

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
            print(f"    {Colors.RED}Violations: {len(all_pp_violations)} items with {all_pp_violations} words{Colors.RESET}")
    else:
        print(f"  Pain points: N/A (none generated)")

    if total_opp > 0:
        opp_compliance = (total_opp - len(all_opp_violations)) / total_opp * 100
        print(f"  Opportunities: {opp_compliance:.1f}% (≤3 words)")
        if all_opp_violations:
            print(f"    {Colors.RED}Violations: {len(all_opp_violations)} items with {all_opp_violations} words{Colors.RESET}")
    else:
        print(f"  Opportunities: N/A (none generated)")


def print_detailed_result(item_num: int, item: IntelligenceItem, baseline: ProcessedIntelligence,
                         test_result: Dict[str, Any], comparison: Dict[str, Any]):
    """Print detailed comparison for one item"""
    print(f"\n{Colors.BOLD}{'='*80}{Colors.RESET}")
    print(f"{Colors.BOLD}Item {item_num}: {item.title[:60]}...{Colors.RESET}")
    print(f"{'='*80}")

    if not comparison['valid']:
        print(f"{Colors.RED}❌ FAILED: {comparison.get('error', 'Unknown error')}{Colors.RESET}")
        if test_result.get('raw_response'):
            print(f"\nRaw response:\n{test_result['raw_response'][:500]}")
        return

    data = test_result['data']

    # Relevance
    rel_icon = "✅" if comparison['relevance_match'] else "❌"
    print(f"\n{Colors.BOLD}Relevance:{Colors.RESET} {rel_icon}")
    print(f"  Baseline: {baseline.category not in ['unrelated', 'advertisement']}")
    print(f"  Test:     {data.get('is_relevant')}")

    # Category
    cat_icon = "✅" if comparison['category_match'] else "❌"
    print(f"\n{Colors.BOLD}Category:{Colors.RESET} {cat_icon}")
    print(f"  Baseline: {baseline.category}")
    print(f"  Test:     {data.get('category')}")

    # Sentiment
    sent_icon = "✅" if comparison['sentiment_match'] else "❌"
    print(f"\n{Colors.BOLD}Sentiment:{Colors.RESET} {sent_icon}")
    print(f"  Baseline: {baseline.sentiment}")
    print(f"  Test:     {data.get('sentiment')}")

    # Pain points & opportunities
    ppo = data.get('pain_points_opportunities', {})
    if isinstance(ppo, dict):
        print(f"\n{Colors.BOLD}Pain Points & Opportunities:{Colors.RESET}")

        pain_points = ppo.get('pain_points', [])
        for i, pp in enumerate(pain_points, 1):
            wc = len(str(pp).split())
            icon = "✅" if wc <= 3 else f"{Colors.RED}❌ ({wc} words){Colors.RESET}"
            print(f"  PP{i}: {icon} {pp}")

        opportunities = ppo.get('opportunities', [])
        for i, opp in enumerate(opportunities, 1):
            wc = len(str(opp).split())
            icon = "✅" if wc <= 3 else f"{Colors.RED}❌ ({wc} words){Colors.RESET}"
            print(f"  OP{i}: {icon} {opp}")


async def main():
    parser = argparse.ArgumentParser(description='Test AI prompts against baseline')
    parser.add_argument('--limit', type=int, default=10, help='Number of items to test')
    parser.add_argument('--api-base', default='http://localhost:1234/v1', help='API base URL')
    parser.add_argument('--model', default='qwen/qwen3-vl-4b', help='Model name')
    parser.add_argument('--prompt-type', choices=['small', 'frontier'], default='small',
                       help='Which prompt to test')
    parser.add_argument('--verbose', action='store_true', help='Show detailed results for each item')

    args = parser.parse_args()

    print(f"{Colors.BOLD}{Colors.BLUE}=== Prompt Testing Framework ==={Colors.RESET}")
    print(f"API: {args.api_base}")
    print(f"Model: {args.model}")
    print(f"Prompt: {args.prompt_type}")
    print(f"Test items: {args.limit}")
    print()

    # Get test data
    db = SessionLocal()
    try:
        print("Loading test items from database...")
        test_items = get_test_items(db, args.limit)
        print(f"Loaded {len(test_items)} items\n")

        if not test_items:
            print(f"{Colors.RED}No items found in database{Colors.RESET}")
            return

        # Create AI processor for prompt building
        ai_processor = AIProcessor(db)

        # Test each item
        results = []
        for i, (item, baseline, customer) in enumerate(test_items, 1):
            print(f"Testing {i}/{len(test_items)}: {item.title[:60]}...")

            test_result = await test_with_custom_model(
                title=item.title,
                content=item.content or "",
                customer=customer,
                api_base_url=args.api_base,
                model_name=args.model,
                prompt_builder=ai_processor,
                use_small_prompt=(args.prompt_type == 'small')
            )

            comparison = compare_results(baseline, test_result)

            results.append({
                'item': item,
                'baseline': baseline,
                'customer': customer,
                'test_result': test_result,
                'comparison': comparison
            })

            if args.verbose:
                print_detailed_result(i, item, baseline, test_result, comparison)

        # Print summary
        print_summary(results)

    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(main())
