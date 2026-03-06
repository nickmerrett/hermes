#!/usr/bin/env python3
"""Test script to diagnose AI configuration issues"""

import sys
import os

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.config.settings import settings

print("=" * 80)
print("AI CONFIGURATION DIAGNOSTIC")
print("=" * 80)

print("\n📋 ENVIRONMENT VARIABLES:")
print(f"  AI_PROVIDER: {settings.ai_provider}")
print(f"  AI_PROVIDER_CHEAP: {settings.ai_provider_cheap}")
print(f"  AI_MODEL: {settings.ai_model}")
print(f"  AI_MODEL_CHEAP: {settings.ai_model_cheap}")

print("\n🔑 API KEYS:")
print(f"  ANTHROPIC_API_KEY: {'✓ Set' if settings.anthropic_api_key else '✗ NOT SET'}")
print(f"  OPENAI_API_KEY: {'✓ Set' if settings.openai_api_key else '✗ NOT SET'}")

print("\n🌐 API BASE URLS:")
print(f"  ANTHROPIC_API_BASE_URL: {settings.anthropic_api_base_url}")
print(f"  OPENAI_BASE_URL: {settings.openai_base_url}")

print("\n" + "=" * 80)
print("TESTING AI PROCESSOR INITIALIZATION")
print("=" * 80)

try:
    from app.processors.ai_processor import AIProcessor
    print("\n✓ AIProcessor import successful")

    print("\nAttempting to initialize AIProcessor (economy model)...")
    processor = AIProcessor()
    print("✓ AIProcessor initialized successfully!")
    print(f"  Provider: {processor.provider}")
    print(f"  Model: {processor.model}")
    print(f"  Client Type: {processor.client_type}")

except Exception as e:
    print("\n✗ FAILED to initialize AIProcessor!")
    print(f"  Error: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 80)
print("TESTING DATABASE AI CONFIG")
print("=" * 80)

try:
    from app.core.database import get_db
    from app.models.database import PlatformSettings

    db = next(get_db())
    ai_config = db.query(PlatformSettings).filter(
        PlatformSettings.key == 'ai_config'
    ).first()

    if ai_config:
        print("\n✓ Platform AI config found in database:")
        print(f"  {ai_config.value}")
    else:
        print("\n⚠ No ai_config found in database")
        print("  This is OK - will use environment defaults")

except Exception as e:
    print("\n✗ Failed to check database config")
    print(f"  Error: {e}")

print("\n" + "=" * 80)
print("RECOMMENDATIONS")
print("=" * 80)

issues = []

if settings.ai_provider == 'anthropic' and not settings.anthropic_api_key:
    issues.append("ANTHROPIC_API_KEY is not set but AI_PROVIDER=anthropic")

if settings.ai_provider_cheap == 'anthropic' and not settings.anthropic_api_key:
    issues.append("ANTHROPIC_API_KEY is not set but AI_PROVIDER_CHEAP=anthropic")

if settings.ai_provider == 'openai' and not settings.openai_api_key:
    issues.append("OPENAI_API_KEY is not set but AI_PROVIDER=openai")

if settings.ai_provider_cheap == 'openai' and not settings.openai_api_key:
    issues.append("OPENAI_API_KEY is not set but AI_PROVIDER_CHEAP=openai")

if issues:
    print("\n⚠ ISSUES FOUND:")
    for i, issue in enumerate(issues, 1):
        print(f"  {i}. {issue}")
    print("\nPlease update your .env file with the required API keys.")
else:
    print("\n✓ Configuration looks good!")

print("\n" + "=" * 80)
