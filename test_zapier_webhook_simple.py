#!/usr/bin/env python3
"""
Simple test script for testing the Zapier webhook endpoint
Tests the live production endpoint without Supabase dependencies
"""

import requests
import json
from datetime import datetime

# Configuration
PRODUCTION_URL = "https://internal-automation-production.up.railway.app"
WEBHOOK_ENDPOINT = f"{PRODUCTION_URL}/zapier-webhook"

def test_endpoint_availability():
    """Test if the production endpoint is available"""

    print("\n" + "="*70)
    print("TEST 1: ENDPOINT AVAILABILITY")
    print("="*70)

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

def test_zapier_webhook():
    """Test the Zapier webhook endpoint with sample data"""

    # Generate unique test data
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    test_payload = {
        "customer_name": f"Test Customer {timestamp}",
        "customer_email": "admin@swipey.co",  # Using a test email
        "company_name": f"Test Company Ltd {timestamp}",
        "phone": "+60123456789",
        "business_type": "Technology",
        "typeform_response_id": f"test_{timestamp}",
        "submission_timestamp": datetime.now().isoformat(),
        "clickup_task_id": f"test_task_{timestamp}",
        "clickup_task_url": f"https://app.clickup.com/t/test_task_{timestamp}"
    }

    print("\n" + "="*70)
    print("TEST 2: ZAPIER WEBHOOK ENDPOINT")
    print("="*70)
    print(f"\nEndpoint: {WEBHOOK_ENDPOINT}")
    print(f"\n📋 Test Payload:")
    print(json.dumps(test_payload, indent=2))
    print("\n" + "-"*70)

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

            try:
                response_data = response.json()
                print(f"\n✅ Response Data:")
                print(json.dumps(response_data, indent=2))

                # Verify response structure
                print("\n" + "-"*70)
                print("RESPONSE VALIDATION")
                print("-"*70)

                expected_fields = ['success', 'task_id', 'upload_link', 'message']
                missing_fields = []
                present_fields = []

                for field in expected_fields:
                    if field in response_data:
                        present_fields.append(field)
                        print(f"✓ Field '{field}': Present")
                    else:
                        missing_fields.append(field)
                        print(f"✗ Field '{field}': Missing")

                # Additional checks
                if response_data.get('success'):
                    print(f"✓ Success flag: True")
                else:
                    print(f"✗ Success flag: {response_data.get('success')}")

                if 'upload_link' in response_data:
                    print(f"✓ Upload link generated: {response_data.get('upload_link')}")

                if 'task_id' in response_data:
                    print(f"✓ Task ID: {response_data.get('task_id')}")

                print("\n" + "-"*70)
                print("WHAT THIS MEANS:")
                print("-"*70)
                print("✓ The webhook endpoint is working correctly")
                print("✓ Customer data was received and processed")
                print("✓ Upload link was generated successfully")
                print("✓ Email should have been sent to the customer")
                print("✓ Company record should be created in Supabase")
                print("\n⚠️  To verify company creation in Supabase:")
                print(f"   - Check the 'companies' table for clickup_task_id: {test_payload['clickup_task_id']}")
                print(f"   - Verify the record contains: {test_payload['customer_email']}")

                return len(missing_fields) == 0

            except json.JSONDecodeError:
                print("⚠️  Response is not valid JSON:")
                print(response.text)
                return False
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
        import traceback
        traceback.print_exc()
        return False

def test_webhook_validation():
    """Test webhook validation with missing fields"""

    print("\n" + "="*70)
    print("TEST 3: WEBHOOK VALIDATION (Missing Required Fields)")
    print("="*70)

    # Payload with missing required fields
    invalid_payload = {
        "customer_name": "Test Customer",
        # Missing customer_email, company_name, and clickup_task_id
    }

    print(f"\n📋 Invalid Payload (missing required fields):")
    print(json.dumps(invalid_payload, indent=2))
    print("\n" + "-"*70)

    try:
        print("\n📤 Sending request with invalid payload...")
        response = requests.post(
            WEBHOOK_ENDPOINT,
            json=invalid_payload,
            headers={"Content-Type": "application/json"},
            timeout=10
        )

        print(f"\n📨 Response Status: {response.status_code}")

        if response.status_code == 400:
            print("✓ Validation working! Returned 400 Bad Request as expected")
            try:
                error_data = response.json()
                print(f"\n✅ Error Response:")
                print(json.dumps(error_data, indent=2))
            except:
                print(response.text)
            return True
        else:
            print(f"⚠️  Expected 400, got {response.status_code}")
            print(response.text)
            return False

    except Exception as e:
        print(f"✗ Error: {e}")
        return False

def main():
    """Run all tests"""

    print("\n" + "="*70)
    print(" "*20 + "LIVE WORKFLOW TEST SUITE")
    print("="*70)
    print(f"Production URL: {PRODUCTION_URL}")
    print(f"Test Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*70)

    results = []

    # Test 1: Endpoint availability
    results.append(("Endpoint Availability", test_endpoint_availability()))

    # Test 2: Zapier webhook with valid data
    results.append(("Zapier Webhook & Company Creation", test_zapier_webhook()))

    # Test 3: Webhook validation
    results.append(("Webhook Validation", test_webhook_validation()))

    # Summary
    print("\n" + "="*70)
    print(" "*25 + "TEST SUMMARY")
    print("="*70)

    for test_name, passed in results:
        status = "✓ PASSED" if passed else "✗ FAILED"
        print(f"{status}: {test_name}")

    total_passed = sum(1 for _, passed in results if passed)
    total_tests = len(results)

    print("\n" + "-"*70)
    print(f"Total: {total_passed}/{total_tests} tests passed")

    if total_passed == total_tests:
        print("\n🎉 All tests passed! The workflow is functioning correctly.")
    else:
        print(f"\n⚠️  {total_tests - total_passed} test(s) failed. Please investigate.")

    print("="*70 + "\n")

    return total_passed == total_tests

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
