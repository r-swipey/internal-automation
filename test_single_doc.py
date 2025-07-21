#!/usr/bin/env python3
"""
Test single document to see Textract output structure
"""

import sys
import os
sys.path.append('.')

import requests
import json
from dotenv import load_dotenv
from supabase import create_client, Client
import time

# Load environment variables
load_dotenv('.env', override=True)

def test_aiengineer_document():
    """Test the aiengineer document specifically"""
    
    doc_path = r"C:\Users\kalya\Documents\SSM documents\S14 Company Registration_aiengineer.pdf"
    filename = "S14 Company Registration_aiengineer.pdf"
    
    print(f"Testing document: {filename}")
    print("=" * 80)
    
    # Setup Supabase client
    supabase_url = os.getenv('SUPABASE_URL')
    supabase_key = os.getenv('SUPABASE_ANON_KEY')
    supabase = create_client(supabase_url, supabase_key)
    
    try:
        # Step 1: Create test customer
        print("Step 1: Creating test customer...")
        
        webhook_payload = {
            "customer_name": "Aurum Paradise Test",
            "customer_email": "admin@swipey.co",
            "company_name": "Aurum Paradise Test Company",
            "phone": "+60123456789",
            "business_type": "Technology",
            "typeform_response_id": "aurum_test_1",
            "submission_timestamp": "2025-07-19T15:00:00Z",
            "clickup_task_id": "aurum_test_task",
            "clickup_task_url": "https://app.clickup.com/t/aurum_test_task"
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
        
        # Step 2: Upload document
        print(f"Step 2: Uploading document: {filename}")
        
        with open(doc_path, 'rb') as f:
            pdf_content = f.read()
        
        files = {'document': (filename, pdf_content, 'application/pdf')}
        
        upload_response = requests.post(
            f"http://localhost:5000/upload-file-async/{customer_token}",
            files=files
        )
        
        if upload_response.status_code != 200:
            print(f"Upload failed: {upload_response.status_code}")
            print(f"Response: {upload_response.text}")
            return
        
        upload_data = upload_response.json()
        document_id = upload_data.get('documentId')
        
        print(f"[OK] Document uploaded successfully: {document_id}")
        
        # Step 3: Wait for OCR processing
        print("Step 3: Waiting for OCR processing...")
        
        max_attempts = 60  # 2 minutes
        for attempt in range(max_attempts):
            time.sleep(2)
            print(f"Checking OCR status... (attempt {attempt + 1}/{max_attempts})")
            
            doc_response = supabase.table('documents').select('*').eq('id', document_id).execute()
            if doc_response.data:
                doc_record = doc_response.data[0]
                ocr_status = doc_record.get('ocr_status')
                
                if ocr_status == 'completed':
                    print(f"[OK] OCR processing completed!")
                    
                    print("\n" + "="*80)
                    print("EXTRACTED DATA FROM DATABASE:")
                    print("="*80)
                    print(f"Company Name: {doc_record.get('extracted_company_name')}")
                    print(f"Registration Number: {doc_record.get('extracted_registration_number')}")
                    print(f"Directors: {doc_record.get('extracted_directors', [])}")
                    print(f"OCR Status: {doc_record.get('ocr_status')}")
                    
                    return {
                        'company_name': doc_record.get('extracted_company_name'),
                        'registration_number': doc_record.get('extracted_registration_number'),
                        'directors': doc_record.get('extracted_directors', [])
                    }
                    
                elif ocr_status == 'failed':
                    print(f"[ERROR] OCR processing failed!")
                    return None
        
        print(f"[TIMEOUT] OCR processing timeout after {max_attempts * 2} seconds")
        return None
        
    except Exception as e:
        print(f"Error during test: {e}")
        import traceback
        traceback.print_exc()
        return None
    
    finally:
        # Clean up test record
        try:
            if 'document_id' in locals():
                supabase.table('documents').delete().eq('id', document_id).execute()
                print(f"Cleaned up test document record: {document_id}")
        except:
            pass

if __name__ == "__main__":
    test_aiengineer_document()