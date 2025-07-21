#!/usr/bin/env python3
"""
Manual test to trigger ClickUp integrations for existing document
"""

import sys
import os
sys.path.append('.')

from dotenv import load_dotenv
load_dotenv('.env', override=True)

from services.ocr_service import OCRService
from supabase import create_client

def test_clickup_manual_trigger():
    """Manually trigger ClickUp integrations for the blacksheep2025 document"""
    
    print("=== MANUAL CLICKUP INTEGRATION TEST ===")
    
    # Initialize services
    supabase_url = os.getenv('SUPABASE_URL')
    supabase_key = os.getenv('SUPABASE_ANON_KEY')
    supabase = create_client(supabase_url, supabase_key)
    
    # Initialize OCR service with Supabase client
    ocr_service = OCRService(supabase)
    
    # Find the completed document
    doc_result = supabase.table('documents').select('*').eq('clickup_task_id', '86czpxnf4').eq('ocr_status', 'completed').execute()
    
    if not doc_result.data:
        print("[ERROR] No completed document found for task 86czpxnf4")
        return
    
    document = doc_result.data[0]
    document_id = document['id']
    directors_data = document.get('extracted_directors', [])
    
    print(f"Found document: {document_id}")
    print(f"OCR Status: {document.get('ocr_status')}")
    print(f"Directors: {len(directors_data)} found")
    
    if directors_data:
        first_director = directors_data[0]
        print(f"First Director: {first_director.get('name')} ({first_director.get('email', 'No email')})")
    
    print()
    
    # Test 1: Send OCR notification
    print("Test 1: Sending OCR completion notification to ClickUp...")
    try:
        extracted_data = {
            'company_name': document.get('extracted_company_name'),
            'registration_number': document.get('extracted_registration_number'),
            'directors': directors_data,
            'incorporation_date': document.get('extracted_incorporation_date'),
            'business_address': document.get('extracted_business_address')
        }
        
        ocr_service._send_clickup_ocr_notification(document_id, 'completed', extracted_data)
        print("[OK] OCR notification sent")
    except Exception as e:
        print(f"[ERROR] OCR notification failed: {e}")
        import traceback
        traceback.print_exc()
    
    print()
    
    # Test 2: Update director fields
    print("Test 2: Updating ClickUp director fields...")
    try:
        ocr_service._update_clickup_director_fields(document_id, directors_data)
        print("[OK] Director fields updated")
    except Exception as e:
        print(f"[ERROR] Director fields update failed: {e}")
        import traceback
        traceback.print_exc()
    
    print()
    print("=== TEST COMPLETED ===")
    print("Check ClickUp task: https://app.clickup.com/t/86czpxnf4")
    print("Verify:")
    print("1. OCR status comment posted")
    print("2. Director Name field populated") 
    print("3. Director Email field populated")

if __name__ == "__main__":
    test_clickup_manual_trigger()