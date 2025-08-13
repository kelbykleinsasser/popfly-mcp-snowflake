#!/usr/bin/env python3
import re
import json

# Test the regex pattern
test_strings = [
    '1 rows returned: [{"TOTAL_AGENCY_MODE_PAYMENTS": "9350.00"}]',
    '0 rows returned: []',
    '3 rows returned: [{"a": 1}, {"b": 2}, {"c": 3}]'
]

pattern = r'\d+\s+rows returned:\s*(\[.*\])'

for test_str in test_strings:
    print(f"Testing: {test_str[:50]}...")
    match = re.search(pattern, test_str, re.DOTALL)
    if match:
        print(f"  ✅ Matched! JSON: {match.group(1)[:50]}...")
        try:
            data = json.loads(match.group(1))
            print(f"  ✅ Valid JSON with {len(data)} items")
        except:
            print(f"  ❌ Invalid JSON")
    else:
        print(f"  ❌ No match!")