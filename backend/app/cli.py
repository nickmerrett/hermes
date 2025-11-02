#!/usr/bin/env python
"""
Command Line Interface for ATL Intelligence Platform

Provides commands for running collections, managing data, and system operations.
"""

import sys
import argparse
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.scheduler.collection import run_collection, purge_old_items


def collect_command(args):
    """Run data collection"""
    print("Starting collection...")
    print("=" * 60)

    if args.customer_id:
        print(f"Collecting for customer ID: {args.customer_id}")
        run_collection(customer_id=args.customer_id)
    else:
        print("Collecting for all customers")
        run_collection()

    print("=" * 60)
    print("Collection complete!")


def purge_command(args):
    """Purge old intelligence items"""
    print(f"Purging items older than {args.days} days...")
    print("=" * 60)

    purge_old_items(retention_days=args.days)

    print("=" * 60)
    print("Purge complete!")


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description='ATL Intelligence Platform CLI',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run collection for all customers
  python app/cli.py collect

  # Run collection for specific customer
  python app/cli.py collect --customer-id 1

  # Purge old items (default: 90 days)
  python app/cli.py purge

  # Purge items older than 30 days
  python app/cli.py purge --days 30
        """
    )

    subparsers = parser.add_subparsers(title='commands', dest='command', required=True)

    # Collect command
    collect_parser = subparsers.add_parser(
        'collect',
        help='Run data collection from all configured sources'
    )
    collect_parser.add_argument(
        '--customer-id',
        type=int,
        help='Collect for specific customer ID only'
    )
    collect_parser.set_defaults(func=collect_command)

    # Purge command
    purge_parser = subparsers.add_parser(
        'purge',
        help='Purge old intelligence items from database'
    )
    purge_parser.add_argument(
        '--days',
        type=int,
        default=90,
        help='Number of days to retain (default: 90)'
    )
    purge_parser.set_defaults(func=purge_command)

    # Parse arguments
    args = parser.parse_args()

    # Execute command
    try:
        args.func(args)
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
