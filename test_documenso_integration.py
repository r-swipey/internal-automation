#!/usr/bin/env python3
"""
Test Documenso Integration
Simple test script to validate the Documenso e-signature service
"""

import sys
import os
sys.path.append('.')

from dotenv import load_dotenv
load_dotenv('.env', override=True)

import requests

def test_documenso_endpoints():
    """Test Documenso endpoints without making actual API calls"""
    
    print("=== DOCUMENSO INTEGRATION TEST ===")
    base_url = "http://localhost:5000"
    test_task_id = "86czpxnf4"  # Our test task
    
    # Test 1: Check test endpoint
    print("\\n1. Testing Documenso trigger info endpoint...")
    try:
        response = requests.get(f"{base_url}/test-documenso-trigger?task_id={test_task_id}", timeout=10)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Test endpoint working!")
            print(f"   Company: {data.get('company_name')}")
            print(f"   Directors with emails: {data.get('directors_with_emails')}")
            print(f"   Ready for e-signature: {data.get('ready_for_esignature')}")
            print(f"   Trigger URL: {data.get('trigger_url')}")
            print(f"   Webhook URL: {data.get('webhook_url')}")
        else:
            print(f"❌ Test endpoint failed: {response.status_code}")
            print(f"   Response: {response.text}")
    except Exception as e:
        print(f"❌ Test endpoint error: {e}")
    
    # Test 2: Show curl command for manual testing
    print("\\n2. Manual testing commands:")
    print("\\n   🔍 Check readiness:")
    print(f"   curl {base_url}/test-documenso-trigger?task_id={test_task_id}")
    
    print("\\n   📝 Trigger e-signature (requires DOCUMENSO_API_KEY):")
    print(f"   curl -X POST {base_url}/trigger-documenso/{test_task_id} -H 'Content-Type: application/json'")
    
    print("\\n   🔗 Test webhook (simulate webhook):")
    print(f"""   curl -X POST {base_url}/documenso-webhook -H 'Content-Type: application/json' -d '{{
  "event": "document.created",
  "data": {{
    "id": "test_doc_123",
    "title": "Test Document",
    "status": "PENDING"
  }}
}}'""")
    
    # Test 3: Environment check
    print("\\n3. Environment check:")
    documenso_key = os.getenv('DOCUMENSO_API_KEY')
    if documenso_key:
        print(f"✅ DOCUMENSO_API_KEY configured: {documenso_key[:20]}...")
    else:
        print("⚠️  DOCUMENSO_API_KEY not configured")
        print("   Add DOCUMENSO_API_KEY=your_api_key to .env file")
    
    print("\\n4. Next steps:")
    print("   1. Get Documenso API key from https://app.documenso.com/settings/tokens")
    print("   2. Add DOCUMENSO_API_KEY to your .env file")
    print("   3. Use the curl commands above to test the integration")
    print("   4. Configure webhook URL in Documenso: http://your-domain.com/documenso-webhook")
    
    print("\\n=== TEST COMPLETED ===")

if __name__ == "__main__":
    # Check if Flask app is running
    try:
        response = requests.get("http://localhost:5000/health", timeout=5)
        if response.status_code == 200:
            print("✅ Flask app is running")
            test_documenso_endpoints()
        else:
            print("❌ Flask app not responding correctly")
    except:
        print("❌ Flask app is not running")
        print("Please start Flask app: python app.py")
        print("Then run this test again")