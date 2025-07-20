#!/usr/bin/env python3
"""
Manual Documenso Test
Test the Documenso integration with our existing data
"""

import sys
import os
sys.path.append('.')

from dotenv import load_dotenv
load_dotenv('.env', override=True)

from supabase import create_client
from services.documenso_service import send_signature_request_to_directors

def test_documenso_manual():
    """Manually test Documenso integration with blacksheep2025 data"""
    
    print("=== MANUAL DOCUMENSO TEST ===")
    
    # Initialize Supabase
    supabase_url = os.getenv('SUPABASE_URL')
    supabase_key = os.getenv('SUPABASE_ANON_KEY')
    supabase = create_client(supabase_url, supabase_key)
    
    # Test data
    clickup_task_id = "86czpxnf4"
    
    print(f"1. Getting company data for task: {clickup_task_id}")
    
    # Get company info
    company_result = supabase.table('companies').select('*').eq('clickup_task_id', clickup_task_id).execute()
    if not company_result.data:
        print("[ERROR] Company not found")
        return
    
    company = company_result.data[0]
    company_name = company.get('company_name', 'Unknown Company')
    print(f"   Company: {company_name}")
    
    # Get latest OCR document
    doc_result = supabase.table('documents').select('*').eq('clickup_task_id', clickup_task_id).eq('ocr_status', 'completed').order('created_at', desc=True).limit(1).execute()
    
    if not doc_result.data:
        print("[ERROR] No completed OCR documents found")
        return
    
    document = doc_result.data[0]
    directors_data = document.get('extracted_directors', [])
    
    print(f"   Directors found: {len(directors_data)}")
    
    # Filter directors with emails
    valid_directors = [d for d in directors_data if d.get('email')]
    print(f"   Directors with emails: {len(valid_directors)}")
    
    if not valid_directors:
        print("[ERROR] No directors with valid emails")
        return
    
    for i, director in enumerate(valid_directors):
        print(f"   {i+1}. {director.get('name')} - {director.get('email')}")
    
    print(f"\\n2. Testing Documenso integration...")
    
    # Test the Documenso service
    try:
        result = send_signature_request_to_directors(
            directors_data=valid_directors,
            clickup_task_id=clickup_task_id,
            company_name=company_name
        )
        
        if result.get('success'):
            print(f"[SUCCESS] Documenso signature request created!")
            print(f"   Document ID: {result.get('document_id')}")
            print(f"   Recipients: {len(result.get('recipients', []))}")
            print(f"   Signing URL: {result.get('signing_url')}")
            
            # List recipients
            for recipient in result.get('recipients', []):
                print(f"   - {recipient.get('name')} ({recipient.get('email')})")
                
        else:
            print(f"[ERROR] Documenso request failed: {result.get('error')}")
            
    except Exception as e:
        print(f"[ERROR] Exception during test: {e}")
        import traceback
        traceback.print_exc()
    
    print("\\n3. Next steps:")
    print("   - Check your Documenso dashboard for the created document")
    print("   - Directors should receive email notifications")
    print("   - ClickUp task should show signature status comment")
    print("   - Monitor webhook events for status updates")
    
    print("\\n=== TEST COMPLETED ===")

if __name__ == "__main__":
    test_documenso_manual()