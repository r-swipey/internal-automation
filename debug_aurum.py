#!/usr/bin/env python3
"""
Debug Aurum Paradise document with sync OCR
"""

import sys
import os
sys.path.append('.')

import requests
import json
from dotenv import load_dotenv
from supabase import create_client, Client

# Load environment variables
load_dotenv('.env', override=True)

def debug_aurum_sync():
    """Debug the Aurum Paradise document with sync OCR"""
    
    doc_path = r"C:\Users\kalya\Documents\SSM documents\Aurum Paradise_SSM format 2.pdf"
    filename = "Aurum Paradise_SSM format 2.pdf"
    
    print(f"Testing document: {filename}")
    print("=" * 80)
    
    try:
        # Step 1: Create test customer
        print("Step 1: Creating test customer...")
        
        webhook_payload = {
            "customer_name": "Aurum Debug Test",
            "customer_email": "admin@swipey.co", 
            "company_name": "Aurum Debug Company",
            "phone": "+60123456789",
            "business_type": "Technology",
            "typeform_response_id": "aurum_debug_1",
            "submission_timestamp": "2025-07-19T15:00:00Z",
            "clickup_task_id": "aurum_debug_task",
            "clickup_task_url": "https://app.clickup.com/t/aurum_debug_task"
        }
        
        webhook_response = requests.post(
            "http://localhost:5000/zapier-webhook",
            json=webhook_payload,
            headers={'Content-Type': 'application/json'}
        )
        
        if webhook_response.status_code != 200:
            print(f"Webhook failed: {webhook_response.status_code}")
            print(f"Response: {webhook_response.text}")
            return
        
        webhook_data = webhook_response.json()
        customer_token = webhook_data.get('customer_token')
        
        print(f"[OK] Customer created with token: {customer_token[:20]}...")
        
        # Step 2: Upload document with sync processing
        print(f"Step 2: Uploading document with sync OCR: {filename}")
        
        with open(doc_path, 'rb') as f:
            pdf_content = f.read()
        
        files = {'document': (filename, pdf_content, 'application/pdf')}
        
        # Use sync upload endpoint 
        upload_response = requests.post(
            f"http://localhost:5000/upload-file/{customer_token}",
            files=files
        )
        
        if upload_response.status_code != 200:
            print(f"Upload failed: {upload_response.status_code}")
            print(f"Response: {upload_response.text}")
            return
        
        upload_data = upload_response.json()
        print(f"Upload response: {upload_data}")
        
        # The sync endpoint should return extracted data immediately
        extracted_data = upload_data.get('extracted_data', {})
        
        print("\n" + "="*80)
        print("EXTRACTED DATA FROM SYNC OCR:")
        print("="*80)
        print(f"Company Name: {extracted_data.get('company_name')}")
        print(f"Registration Number: {extracted_data.get('registration_number')}")
        print(f"Incorporation Date: {extracted_data.get('incorporation_date')}")
        print(f"Business Address: {extracted_data.get('business_address')}")
        print(f"Directors: {extracted_data.get('directors', [])}")
        
        return extracted_data
        
    except Exception as e:
        print(f"Error during debug test: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    debug_aurum_sync()