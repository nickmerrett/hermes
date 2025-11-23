#!/usr/bin/env python3
"""
Test if timezone fix is working in the API
"""

import sys
sys.path.insert(0, '/app')

from datetime import datetime
import json

print("=" * 80)
print("TESTING TIMEZONE FIX")
print("=" * 80)
print()

# Test 1: Check Pydantic version
print("Test 1: Pydantic Version")
print("-" * 80)
try:
    import pydantic
    print(f"  Pydantic version: {pydantic.VERSION}")
except Exception as e:
    print(f"  Error: {e}")
print()

# Test 2: Check if CustomJSONResponse exists
print("Test 2: CustomJSONResponse Class")
print("-" * 80)
try:
    from app.main import CustomJSONResponse
    print("  ✓ CustomJSONResponse imported successfully")

    # Test the encoder directly
    test_data = {
        "published_date": datetime(2025, 11, 11, 12, 0, 0),
        "test": "value"
    }

    response = CustomJSONResponse(content=test_data)
    body = response.body.decode()
    print(f"  Response body: {body}")

    if '"published_date":"2025-11-11T12:00:00Z"' in body:
        print("  ✓ CustomJSONResponse adds 'Z' suffix correctly")
    elif '"published_date":"2025-11-11T12:00:00"' in body:
        print("  ✗ CustomJSONResponse NOT adding 'Z' suffix")
    else:
        print(f"  ? Unexpected format in response")

except Exception as e:
    print(f"  ✗ Error: {e}")
    import traceback
    traceback.print_exc()
print()

# Test 3: Check if FastAPI is using CustomJSONResponse
print("Test 3: FastAPI Configuration")
print("-" * 80)
try:
    from app.main import app
    print(f"  FastAPI default_response_class: {app.default_response_class}")

    if 'CustomJSONResponse' in str(app.default_response_class):
        print("  ✓ FastAPI is configured to use CustomJSONResponse")
    else:
        print("  ✗ FastAPI NOT using CustomJSONResponse")
        print("  → This is the problem!")

except Exception as e:
    print(f"  ✗ Error: {e}")
print()

# Test 4: Test Pydantic model serialization
print("Test 4: Pydantic Model Serialization")
print("-" * 80)
try:
    from app.models.schemas import IntelligenceItemResponse
    from datetime import datetime

    # Create a test item
    test_item = IntelligenceItemResponse(
        id=1,
        customer_id=1,
        title="Test",
        source_type="test",
        published_date=datetime(2025, 11, 11, 12, 0, 0),
        collected_date=datetime(2025, 11, 11, 13, 0, 0),
        cluster_id=None,
        is_cluster_primary=False,
        source_tier=None,
        cluster_member_count=1
    )

    # Serialize with model_dump/dict
    if hasattr(test_item, 'model_dump'):
        # Pydantic v2
        dumped = test_item.model_dump()
        print("  Using Pydantic v2 (model_dump)")
    else:
        # Pydantic v1
        dumped = test_item.dict()
        print("  Using Pydantic v1 (dict)")

    print(f"  published_date type: {type(dumped['published_date'])}")
    print(f"  published_date value: {dumped['published_date']}")

    if isinstance(dumped['published_date'], str):
        print("  ⚠️  Pydantic already converted datetime to string")
        print("  → CustomJSONResponse encoder won't see datetime objects!")
        if dumped['published_date'].endswith('Z'):
            print("  ✓ But Pydantic added 'Z' suffix")
        else:
            print("  ✗ Pydantic did NOT add 'Z' suffix")
            print("  → Need to configure Pydantic serialization")
    else:
        print("  ✓ Pydantic keeps datetime as object (CustomJSONResponse can handle it)")

except Exception as e:
    print(f"  ✗ Error: {e}")
    import traceback
    traceback.print_exc()
print()

# Test 5: Make actual API request
print("Test 5: Actual API Response")
print("-" * 80)
try:
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)
    response = client.get("/api/feed?limit=1")

    print(f"  Status code: {response.status_code}")

    if response.status_code == 200:
        data = response.json()
        if data.get('items') and len(data['items']) > 0:
            first_item = data['items'][0]
            pub_date = first_item.get('published_date', 'N/A')
            print(f"  published_date: {pub_date}")

            if pub_date.endswith('Z'):
                print("  ✓✓✓ SUCCESS! Date has 'Z' suffix")
            else:
                print("  ✗✗✗ FAILURE! Date missing 'Z' suffix")
        else:
            print("  No items in response")
    else:
        print(f"  API error: {response.text}")

except Exception as e:
    print(f"  ✗ Error: {e}")
    import traceback
    traceback.print_exc()
print()

print("=" * 80)
print("DIAGNOSIS")
print("=" * 80)
print()
print("If Test 4 shows 'Pydantic already converted datetime to string':")
print("  → The issue is Pydantic serializes BEFORE CustomJSONResponse")
print("  → Need to configure Pydantic model serialization")
print()
print("If Test 3 shows FastAPI NOT using CustomJSONResponse:")
print("  → Code changes not applied or old code still running")
print("  → Check if image was actually rebuilt and deployed")
print()
