"""
Test script to simulate webhook calls and measure performance
This helps identify timeout issues before deploying fixes
"""

import requests
import json
import time
from datetime import datetime

# Railway base URL - update this with your actual Railway URL
RAILWAY_BASE_URL = "https://internal-automation-production.up.railway.app"

# Test payloads
def test_documenso_webhook():
    """Test Documenso webhook with a realistic payload"""
    print("=" * 60)
    print("TESTING DOCUMENSO WEBHOOK")
    print("=" * 60)

    # Sample Documenso webhook payload (based on logs)
    payload = {
        "event": "DOCUMENT_COMPLETED",
        "payload": {
            "id": 696673,  # Document ID
            "externalId": "swipey_onboardingv1",  # ClickUp task ID
            "title": "Swipey Account Setup Consent_TEST COMPANY SDN. BHD.",
            "status": "COMPLETED",
            "completedAt": datetime.now().isoformat(),
            "createdAt": "2026-01-12T09:00:17.642Z",
            "formValues": None,
            "recipients": [
                {
                    "id": 954123,
                    "name": "Kalyan Amo",
                    "email": "kalyanamo@gmail.com",
                    "role": "SIGNER",
                    "signingStatus": "SIGNED",
                    "signedAt": datetime.now().isoformat()
                }
            ],
            "teamId": 20582,
            "templateId": 5442,
            "userId": 21992
        },
        "createdAt": datetime.now().isoformat(),
        "webhookEndpoint": f"{RAILWAY_BASE_URL}/documenso-webhook"
    }

    print(f"\n[TEST] Sending POST to: {RAILWAY_BASE_URL}/documenso-webhook")
    print(f"[TEST] Payload: {json.dumps(payload, indent=2)}")

    start_time = time.time()

    try:
        response = requests.post(
            f"{RAILWAY_BASE_URL}/documenso-webhook",
            json=payload,
            timeout=60  # 60 second timeout for testing
        )

        elapsed_time = time.time() - start_time

        print(f"\n[RESULT] Response Status: {response.status_code}")
        print(f"[RESULT] Response Time: {elapsed_time:.2f}s")
        print(f"[RESULT] Response Body: {response.text}")

        if elapsed_time > 30:
            print(f"\n[WARNING] Response took longer than 30s - WOULD TIMEOUT IN PRODUCTION!")
        elif elapsed_time > 20:
            print(f"\n[WARNING] Response took longer than 20s - getting close to timeout threshold")
        else:
            print(f"\n[OK] Response time is acceptable")

        return {
            'success': response.status_code == 200,
            'elapsed_time': elapsed_time,
            'status_code': response.status_code,
            'response': response.text
        }

    except requests.exceptions.Timeout:
        elapsed_time = time.time() - start_time
        print(f"\n[ERROR] REQUEST TIMED OUT after {elapsed_time:.2f}s")
        return {'success': False, 'error': 'timeout', 'elapsed_time': elapsed_time}
    except Exception as e:
        elapsed_time = time.time() - start_time
        print(f"\n[ERROR] Request failed: {e}")
        return {'success': False, 'error': str(e), 'elapsed_time': elapsed_time}


def test_typeform_webhook():
    """Test Typeform/Zapier webhook with a realistic payload"""
    print("\n" + "=" * 60)
    print("TESTING TYPEFORM/ZAPIER WEBHOOK")
    print("=" * 60)

    # Sample Zapier webhook payload
    payload = {
        "customer_name": "Kalyan Amo",
        "customer_email": "kalyanamo@gmail.com",
        "company_name": "Test Company Sdn Bhd",
        "phone": "+60123456789",
        "business_type": "Technology",
        "typeform_response_id": "test_response_001",
        "submission_timestamp": datetime.now().isoformat(),
        "clickup_task_id": "test_task_webhook_001",
        "clickup_task_url": "https://app.clickup.com/t/test_task_webhook_001"
    }

    print(f"\n[TEST] Sending POST to: {RAILWAY_BASE_URL}/zapier-webhook")
    print(f"[TEST] Payload: {json.dumps(payload, indent=2)}")

    start_time = time.time()

    try:
        response = requests.post(
            f"{RAILWAY_BASE_URL}/zapier-webhook",
            json=payload,
            timeout=60  # 60 second timeout for testing
        )

        elapsed_time = time.time() - start_time

        print(f"\n[RESULT] Response Status: {response.status_code}")
        print(f"[RESULT] Response Time: {elapsed_time:.2f}s")
        print(f"[RESULT] Response Body: {response.text[:500]}")  # First 500 chars

        if elapsed_time > 30:
            print(f"\n[WARNING] Response took longer than 30s - WOULD TIMEOUT IN PRODUCTION!")
        elif elapsed_time > 20:
            print(f"\n[WARNING] Response took longer than 20s - getting close to timeout threshold")
        else:
            print(f"\n[OK] Response time is acceptable")

        return {
            'success': response.status_code == 200,
            'elapsed_time': elapsed_time,
            'status_code': response.status_code,
            'response': response.text
        }

    except requests.exceptions.Timeout:
        elapsed_time = time.time() - start_time
        print(f"\n[ERROR] REQUEST TIMED OUT after {elapsed_time:.2f}s")
        return {'success': False, 'error': 'timeout', 'elapsed_time': elapsed_time}
    except Exception as e:
        elapsed_time = time.time() - start_time
        print(f"\n[ERROR] Request failed: {e}")
        return {'success': False, 'error': str(e), 'elapsed_time': elapsed_time}


def run_all_tests():
    """Run all webhook tests"""
    print("\n" + "=" * 60)
    print("WEBHOOK PERFORMANCE TEST SUITE")
    print("=" * 60)
    print(f"Target: {RAILWAY_BASE_URL}")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    results = {}

    # Test 1: Documenso webhook
    print("\n[1/2] Testing Documenso webhook...")
    results['documenso'] = test_documenso_webhook()
    time.sleep(2)  # Brief pause between tests

    # Test 2: Typeform webhook
    print("\n[2/2] Testing Typeform/Zapier webhook...")
    results['typeform'] = test_typeform_webhook()

    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)

    for test_name, result in results.items():
        status = "✓ PASSED" if result.get('success') else "✗ FAILED"
        elapsed = result.get('elapsed_time', 0)
        timeout_risk = "⚠ HIGH RISK" if elapsed > 25 else "✓ OK" if elapsed < 20 else "⚠ MODERATE"

        print(f"\n{test_name.upper()}:")
        print(f"  Status: {status}")
        print(f"  Time: {elapsed:.2f}s")
        print(f"  Timeout Risk: {timeout_risk}")
        if result.get('error'):
            print(f"  Error: {result['error']}")

    print("\n" + "=" * 60)
    print("After reviewing the logs from Railway, check for [TIMING] markers")
    print("to identify which operations are taking the most time.")
    print("=" * 60)


if __name__ == "__main__":
    # Allow user to override the base URL
    import sys
    if len(sys.argv) > 1:
        RAILWAY_BASE_URL = sys.argv[1]
        print(f"Using custom base URL: {RAILWAY_BASE_URL}")

    run_all_tests()
