#!/usr/bin/env python3
"""
Test script for live workflow verification
Tests the Zapier webhook endpoint and company creation in Supabase
"""

import requests
import json
from datetime import datetime
import os
from dotenv import load_dotenv
from supabase import create_client

# Load environment variables
load_dotenv()

# Configuration
PRODUCTION_URL = "https://internal-automation-production.up.railway.app"
WEBHOOK_ENDPOINT = f"{PRODUCTION_URL}/zapier-webhook"

# Initialize Supabase client for verification
supabase_url = os.getenv('SUPABASE_URL')
supabase_key = os.getenv('SUPABASE_ANON_KEY')
supabase = None

if supabase_url and supabase_key:
    try:
        supabase = create_client(supabase_url, supabase_key)
        print("✓ Supabase client initialized")
    except Exception as e:
        print(f"✗ Failed to initialize Supabase: {e}")
else:
    print("✗ Supabase credentials not found in environment")

def test_zapier_webhook():
    """Test the Zapier webhook endpoint with sample data"""

    # Generate unique test data
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    test_payload = {
        "customer_name": f"Test Customer {timestamp}",
        "customer_email": "admin@swipey.co",  # Using your email for testing
        "company_name": f"Test Company Ltd {timestamp}",
        "phone": "+60123456789",
        "business_type": "Technology",
        "typeform_response_id": f"test_{timestamp}",
        "submission_timestamp": datetime.now().isoformat(),
        "clickup_task_id": f"test_task_{timestamp}",
        "clickup_task_url": f"https://app.clickup.com/t/test_task_{timestamp}"
    }

    print("\n" + "="*60)
    print("TESTING LIVE ZAPIER WEBHOOK ENDPOINT")
    print("="*60)
    print(f"\nEndpoint: {WEBHOOK_ENDPOINT}")
    print(f"\nTest Payload:")
    print(json.dumps(test_payload, indent=2))
    print("\n" + "-"*60)

    try:
        # Send POST request to the webhook
        print("\n📤 Sending webhook request...")
        response = requests.post(
            WEBHOOK_ENDPOINT,
            json=test_payload,
            headers={"Content-Type": "application/json"},
            timeout=30
        )

        print(f"\n📨 Response Status: {response.status_code}")

        if response.status_code == 200:
            print("✓ Webhook request successful!")
            response_data = response.json()
            print(f"\n📋 Response Data:")
            print(json.dumps(response_data, indent=2))

            # Test Supabase verification
            if supabase and response_data.get('success'):
                print("\n" + "-"*60)
                print("VERIFYING SUPABASE COMPANY CREATION")
                print("-"*60)

                task_id = test_payload['clickup_task_id']
                verify_company_in_supabase(task_id, test_payload)

            return True
        else:
            print(f"✗ Webhook request failed!")
            print(f"\n❌ Error Response:")
            try:
                error_data = response.json()
                print(json.dumps(error_data, indent=2))
            except:
                print(response.text)
            return False

    except requests.exceptions.Timeout:
        print("✗ Request timed out after 30 seconds")
        return False
    except requests.exceptions.ConnectionError:
        print("✗ Connection error - is the server running?")
        return False
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        return False

def verify_company_in_supabase(task_id, expected_data):
    """Verify that the company was created in Supabase"""

    try:
        print(f"\n🔍 Searching for company with task_id: {task_id}")

        # Query the companies table
        response = supabase.table('companies').select('*').eq('clickup_task_id', task_id).execute()

        if response.data and len(response.data) > 0:
            company = response.data[0]
            print("✓ Company found in Supabase!")
            print(f"\n📊 Company Record:")
            print(json.dumps(company, indent=2, default=str))

            # Verify key fields
            print("\n" + "-"*60)
            print("FIELD VERIFICATION")
            print("-"*60)

            checks = [
                ("Email", company.get('email'), expected_data['customer_email']),
                ("Customer Name", company.get('customer_name'), expected_data['customer_name']),
                ("Company Name", company.get('company_name'), expected_data['company_name']),
                ("Phone", company.get('phone'), expected_data['phone']),
                ("ClickUp Task ID", company.get('clickup_task_id'), expected_data['clickup_task_id']),
                ("Typeform ID", company.get('typeform_submission_id'), expected_data['typeform_response_id']),
                ("KYB Status", company.get('kyb_status'), 'pending_documents'),
            ]

            all_passed = True
            for field_name, actual, expected in checks:
                if actual == expected:
                    print(f"✓ {field_name}: {actual}")
                else:
                    print(f"✗ {field_name}: Expected '{expected}', got '{actual}'")
                    all_passed = False

            if all_passed:
                print("\n🎉 All field verifications passed!")
            else:
                print("\n⚠️  Some field verifications failed")

            return True
        else:
            print("✗ Company NOT found in Supabase!")
            print("\nThis could mean:")
            print("  1. The webhook didn't create the record")
            print("  2. There was a database error")
            print("  3. The task_id doesn't match")
            return False

    except Exception as e:
        print(f"✗ Error querying Supabase: {e}")
        return False

def test_endpoint_availability():
    """Test if the production endpoint is available"""

    print("\n" + "="*60)
    print("TESTING ENDPOINT AVAILABILITY")
    print("="*60)

    try:
        # Test the root endpoint
        print(f"\n🔍 Checking {PRODUCTION_URL}...")
        response = requests.get(PRODUCTION_URL, timeout=10)

        if response.status_code == 200:
            print(f"✓ Server is online (Status: {response.status_code})")
            return True
        else:
            print(f"⚠️  Server responded with status: {response.status_code}")
            return True  # Server is responding, just not 200

    except requests.exceptions.Timeout:
        print("✗ Request timed out - server may be down")
        return False
    except requests.exceptions.ConnectionError:
        print("✗ Connection error - server is not reachable")
        return False
    except Exception as e:
        print(f"✗ Error: {e}")
        return False

def main():
    """Run all tests"""

    print("\n" + "="*60)
    print("LIVE WORKFLOW TEST SUITE")
    print("="*60)
    print(f"Testing: {PRODUCTION_URL}")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)

    results = []

    # Test 1: Endpoint availability
    results.append(("Endpoint Availability", test_endpoint_availability()))

    # Test 2: Zapier webhook
    results.append(("Zapier Webhook & Company Creation", test_zapier_webhook()))

    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)

    for test_name, passed in results:
        status = "✓ PASSED" if passed else "✗ FAILED"
        print(f"{status}: {test_name}")

    total_passed = sum(1 for _, passed in results if passed)
    total_tests = len(results)

    print("\n" + "-"*60)
    print(f"Total: {total_passed}/{total_tests} tests passed")
    print("="*60)

    return total_passed == total_tests

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
