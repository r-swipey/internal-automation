#!/usr/bin/env python3
"""
Simple ClickUp API Test
"""

import os
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv('.env', override=True)

def test_clickup_auth():
    """Test ClickUp authentication and basic API access"""
    
    api_token = os.getenv('CLICKUP_API_TOKEN')
    print("=" * 60)
    print("CLICKUP API AUTHENTICATION TEST")
    print("=" * 60)
    print(f"API Token: {api_token[:20]}... (truncated)")
    
    # Test 1: Get user info (basic auth test)
    print("\nStep 1: Testing authentication with /user endpoint...")
    
    # Try different authorization header formats
    headers_formats = [
        {'Authorization': api_token, 'Content-Type': 'application/json'},
        {'Authorization': f'Bearer {api_token}', 'Content-Type': 'application/json'},
        {'Authorization': f'Token {api_token}', 'Content-Type': 'application/json'}
    ]
    
    print(f"Testing different authorization formats...")
    
    for i, headers in enumerate(headers_formats):
        print(f"\nFormat {i+1}: {list(headers['Authorization'].split())[0] if ' ' in headers['Authorization'] else 'Direct token'}")
        
        try:
            response = requests.get('https://api.clickup.com/api/v2/user', headers=headers, timeout=10)
            print(f"Response Status: {response.status_code}")
            
            if response.status_code == 200:
                user_data = response.json()
                print(f"[OK] Authentication successful with format {i+1}!")
                print(f"User: {user_data.get('user', {}).get('username', 'Unknown')}")
                
                # Use this format for the rest of the test
                working_headers = headers
                break
            else:
                print(f"[FAILED] {response.text}")
                
        except Exception as e:
            print(f"[ERROR] Request failed: {e}")
            
    else:
        print(f"\n[ERROR] All authorization formats failed!")
        return False
    
    # Test 2: Test task access with the specific task ID
    task_id = "86czpny8a"
    print(f"\nStep 2: Testing access to task {task_id}...")
    
    try:
        response = requests.get(f'https://api.clickup.com/api/v2/task/{task_id}', headers=working_headers, timeout=10)
        print(f"Response Status: {response.status_code}")
        
        if response.status_code == 200:
            task_data = response.json()
            print(f"[OK] Task access successful!")
            print(f"Task Name: {task_data.get('name', 'Unknown')}")
            print(f"Task ID: {task_data.get('id', 'Unknown')}")
            
            # Check custom fields
            custom_fields = task_data.get('custom_fields', [])
            print(f"Custom Fields Found: {len(custom_fields)}")
            
            for field in custom_fields:
                field_name = field.get('name', 'Unknown')
                field_id = field.get('id', 'Unknown')
                field_value = field.get('value', 'Not set')
                print(f"  - {field_name} (ID: {field_id}) = {field_value}")
                
            return True
            
        elif response.status_code == 401:
            print(f"[ERROR] Unauthorized access. Check API token permissions.")
            print(f"Response: {response.text}")
            return False
        elif response.status_code == 404:
            print(f"[ERROR] Task not found. Check task ID or access permissions.")
            print(f"Response: {response.text}")
            return False
        else:
            print(f"[ERROR] Unexpected response: {response.text}")
            return False
            
    except Exception as e:
        print(f"[ERROR] Request failed: {e}")
        return False

if __name__ == "__main__":
    test_clickup_auth()