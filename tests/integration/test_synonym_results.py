#!/usr/bin/env python3
"""
Test synonym translations through production MCP
"""
import requests
import json

API_KEY = 'sk-snowflake-mcp-dZOl9vjv2Ylcg8oT0LLmumh3S9ugU6x2jdVmXVoqJqU'
BASE_URL = 'https://mcp.popfly.com'

# Test cases: query -> expected PAYMENT_TYPE
test_cases = [
    # Agency Mode (labs) synonyms
    ('Show payments for labs', 'Agency Mode'),
    ('List Popfly Labs invoices', 'Agency Mode'),
    ('agency services payments', 'Agency Mode'),
    
    # Direct Mode (self-serve) synonyms
    ('Show self-serve payments', 'Direct Mode'),
    ('List platform invoices', 'Direct Mode'),
    ('direct business payments', 'Direct Mode'),
    
    # Creator synonyms
    ('Show ambassador payments', 'Has creators'),
    ('List influencer invoices', 'Has creators'),
]

print('PRODUCTION SYNONYM TRANSLATION TEST')
print('=' * 60)

success_count = 0
total_count = len(test_cases)

for query, expected in test_cases:
    print(f'\nTesting: "{query}"')
    print(f'Expected: {expected}')
    
    headers = {
        'Authorization': f'Bearer {API_KEY}',
        'Content-Type': 'application/json'
    }
    
    payload = {
        'name': 'query_payments',
        'arguments': {
            'query': query,
            'max_rows': 3
        }
    }
    
    try:
        response = requests.post(
            f'{BASE_URL}/admins/tools/call',
            headers=headers,
            json=payload,
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            if result.get('success'):
                content = result.get('content', [])
                if content:
                    text = content[0].get('text', '')
                    if text.startswith('['):
                        data = json.loads(text)
                        if data:
                            if 'Has creators' in expected:
                                # Check for creator fields
                                has_creators = any(
                                    row.get('CREATOR_NAME') or 
                                    row.get('STRIPE_CONNECTED_ACCOUNT_NAME') 
                                    for row in data
                                )
                                if has_creators:
                                    print('  ✅ SUCCESS: Found creator data')
                                    success_count += 1
                                else:
                                    print('  ❌ FAIL: No creator data found')
                            else:
                                # Check PAYMENT_TYPE
                                payment_types = list(set(row.get('PAYMENT_TYPE', '') for row in data))
                                if expected in payment_types:
                                    print(f'  ✅ SUCCESS: Found {expected}')
                                    success_count += 1
                                elif len(payment_types) == 1 and payment_types[0] == '':
                                    print('  ❌ FAIL: PAYMENT_TYPE is empty (aggregated query?)')
                                else:
                                    print(f'  ❌ FAIL: Got {payment_types} instead of {expected}')
                        else:
                            print('  ⚠️  No results returned')
                    else:
                        print('  ❌ Unexpected response format')
            else:
                print(f'  ❌ Request failed: {result.get("error")}')
        else:
            print(f'  ❌ HTTP {response.status_code}')
            
    except Exception as e:
        print(f'  ❌ Error: {e}')

print('\n' + '=' * 60)
print(f'RESULTS: {success_count}/{total_count} tests passed')
print('=' * 60)

if success_count < total_count:
    print('\n❌ Some synonym translations are not working correctly.')
    print('This means the narrative needs stronger rules for these terms.')
else:
    print('\n✅ All synonym translations working correctly!')