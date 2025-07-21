#!/usr/bin/env python3
"""
Test webhook endpoint with secret
"""

import requests
import json

def test_webhook_with_secret():
    """Test the webhook endpoint with secret verification"""
    
    webhook_url = "http://localhost:5000/documenso-webhook"
    
    # Test without secret (should fail if secret is configured)
    print("=== Testing webhook without secret ===")
    payload = {
        "event": "document.completed",
        "data": {
            "id": "test-doc-123"
        }
    }
    
    response = requests.post(webhook_url, json=payload)
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
    
    # Test with secret (should work if secret is configured)
    print("\n=== Testing webhook with secret ===")
    headers = {
        "Content-Type": "application/json",
        "X-Documenso-Signature": "WuJ62MT7^36T!P70"
    }
    
    response = requests.post(webhook_url, json=payload, headers=headers)
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")

if __name__ == "__main__":
    test_webhook_with_secret()