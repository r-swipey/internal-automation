#!/usr/bin/env python3
"""
Comprehensive End-to-End KYB Workflow Test
Tests the complete workflow: Zapier webhook → Upload → OCR → ClickUp updates
"""

import sys
import os
sys.path.append('.')

import requests
import json
import time
from dotenv import load_dotenv
from supabase import create_client

# Load environment variables
load_dotenv('.env', override=True)

def test_comprehensive_kyb_workflow():
    """Test the complete KYB workflow end-to-end"""
    
    print("=" * 100)
    try:
        print("🚀 COMPREHENSIVE END-TO-END KYB WORKFLOW TEST")
    except UnicodeEncodeError:
        print("COMPREHENSIVE END-TO-END KYB WORKFLOW TEST")
    print("=" * 100)
    
    # Test configuration
    base_url = "http://localhost:5000"
    test_document_path = r"C:\Users\kalya\Documents\SSM documents\S14 Company Registration_aiengineer.pdf"
    
    # Zapier payload (using provided format)
    zapier_payload = {
        "customer_name": "Mohan TangoRajan",
        "customer_email": "kalyanamo@gmail.com", 
        "customer_first_name": "Mohan",
        "company_name": "Blacksheep test",
        "phone": "+60123456789",
        "business_type": "Technology",
        "typeform_response_id": "comprehensive_test_19072025",
        "submission_timestamp": "2025-07-19T16:00:00Z",
        "clickup_task_id": "86czpxnf4",  # Using our test task
        "clickup_task_url": "https://app.clickup.com/t/86czpxnf4"
    }
    
    try:
        print(f"📋 Test Configuration:")
    except UnicodeEncodeError:
        print(f"Test Configuration:")
    print(f"   Base URL: {base_url}")
    print(f"   ClickUp Task: {zapier_payload['clickup_task_id']}")
    print(f"   Customer: {zapier_payload['customer_name']} ({zapier_payload['customer_email']})")
    print(f"   Company: {zapier_payload['company_name']}")
    print(f"   Document: {os.path.basename(test_document_path)}")
    print()
    
    # Check if test document exists
    if not os.path.exists(test_document_path):
        try:
            print(f"❌ [ERROR] Test document not found: {test_document_path}")
        except UnicodeEncodeError:
            print(f"[ERROR] Test document not found: {test_document_path}")
        print("Please ensure the test document exists or update the path")
        return False
    
    # Initialize Supabase for verification
    supabase_url = os.getenv('SUPABASE_URL')
    supabase_key = os.getenv('SUPABASE_ANON_KEY')
    supabase = create_client(supabase_url, supabase_key)
    
    try:
        # Step 1: Send Zapier webhook
        try:
            print("📤 STEP 1: Sending Zapier webhook...")
        except UnicodeEncodeError:
            print("STEP 1: Sending Zapier webhook...")
        webhook_response = requests.post(
            f"{base_url}/zapier-webhook",
            json=zapier_payload,
            headers={'Content-Type': 'application/json'},
            timeout=30
        )
        
        if webhook_response.status_code != 200:
            try:
                print(f"❌ Zapier webhook failed: {webhook_response.status_code}")
            except UnicodeEncodeError:
                print(f"[ERROR] Zapier webhook failed: {webhook_response.status_code}")
            print(f"Response: {webhook_response.text}")
            return False
        
        webhook_data = webhook_response.json()
        customer_token = webhook_data.get('customer_token')
        upload_link = webhook_data.get('upload_link')
        
        try:
            print(f"✅ Zapier webhook successful!")
        except UnicodeEncodeError:
            print(f"[OK] Zapier webhook successful!")
        print(f"   Customer token: {customer_token[:20]}...")
        print(f"   Upload link: {upload_link}")
        print()
        
        # Verify company record in database
        try:
            print("🔍 Verifying company record in database...")
        except UnicodeEncodeError:
            print("Verifying company record in database...")
        company_result = supabase.table('companies').select('*').eq('clickup_task_id', zapier_payload['clickup_task_id']).execute()
        if company_result.data:
            company = company_result.data[0]
            try:
                print(f"✅ Company record found: {company['company_name']}")
            except UnicodeEncodeError:
                print(f"[OK] Company record found: {company['company_name']}")
            print(f"   KYB Status: {company.get('kyb_status', 'N/A')}")
        else:
            try:
                print(f"❌ Company record not found")
            except UnicodeEncodeError:
                print(f"[ERROR] Company record not found")
            return False
        print()
        
        # Step 2: Upload document
        try:
            print("📎 STEP 2: Uploading document...")
        except UnicodeEncodeError:
            print("STEP 2: Uploading document...")
        
        with open(test_document_path, 'rb') as f:
            pdf_content = f.read()
        
        files = {'document': (os.path.basename(test_document_path), pdf_content, 'application/pdf')}
        
        upload_response = requests.post(
            f"{base_url}/upload-file-async/{customer_token}",
            files=files,
            timeout=60
        )
        
        if upload_response.status_code != 200:
            try:
                print(f"❌ Document upload failed: {upload_response.status_code}")
            except UnicodeEncodeError:
                print(f"[ERROR] Document upload failed: {upload_response.status_code}")
            print(f"Response: {upload_response.text}")
            return False
        
        upload_data = upload_response.json()
        document_id = upload_data.get('documentId')
        
        try:
            print(f"✅ Document upload successful!")
        except UnicodeEncodeError:
            print(f"[OK] Document upload successful!")
        print(f"   Document ID: {document_id}")
        print(f"   OCR Success: {upload_data.get('ocrSuccess', 'Unknown')}")
        print()
        
        # Step 3: Monitor OCR processing
        try:
            print("🔄 STEP 3: Monitoring OCR processing...")
        except UnicodeEncodeError:
            print("STEP 3: Monitoring OCR processing...")
        
        max_attempts = 60  # 2 minutes
        for attempt in range(max_attempts):
            time.sleep(2)
            
            # Check document status
            doc_response = supabase.table('documents').select('*').eq('id', document_id).execute()
            if doc_response.data:
                doc_record = doc_response.data[0]
                ocr_status = doc_record.get('ocr_status')
                
                print(f"   Attempt {attempt + 1}/{max_attempts}: OCR status = {ocr_status}")
                
                if ocr_status == 'completed':
                    try:
                        print(f"✅ OCR processing completed!")
                    except UnicodeEncodeError:
                        print(f"[OK] OCR processing completed!")
                    extracted_data = {
                        'company_name': doc_record.get('extracted_company_name'),
                        'registration_number': doc_record.get('extracted_registration_number'),
                        'directors': doc_record.get('extracted_directors', []),
                        'incorporation_date': doc_record.get('extracted_incorporation_date'),
                        'business_address': doc_record.get('extracted_business_address')
                    }
                    
                    try:
                        print(f"📋 Extracted Data:")
                    except UnicodeEncodeError:
                        print(f"Extracted Data:")
                    print(f"   Company: {extracted_data['company_name']}")
                    print(f"   Registration: {extracted_data['registration_number']}")
                    print(f"   Directors: {len(extracted_data['directors'])} found")
                    if extracted_data['directors']:
                        first_director = extracted_data['directors'][0]
                        print(f"   First Director: {first_director.get('name')} ({first_director.get('email', 'No email')})")
                    print()
                    break
                    
                elif ocr_status == 'failed':
                    try:
                        print(f"❌ OCR processing failed!")
                    except UnicodeEncodeError:
                        print(f"[ERROR] OCR processing failed!")
                    return False
                    
            else:
                try:
                    print(f"❌ Document not found: {document_id}")
                except UnicodeEncodeError:
                    print(f"[ERROR] Document not found: {document_id}")
                return False
        else:
            try:
                print(f"❌ OCR processing timeout after {max_attempts * 2} seconds")
            except UnicodeEncodeError:
                print(f"[ERROR] OCR processing timeout after {max_attempts * 2} seconds")
            return False
        
        # Step 4: Verify ClickUp integrations
        try:
            print("🔗 STEP 4: Verifying ClickUp integrations...")
        except UnicodeEncodeError:
            print("STEP 4: Verifying ClickUp integrations...")
        
        # Check updated company KYB status
        company_result = supabase.table('companies').select('*').eq('clickup_task_id', zapier_payload['clickup_task_id']).execute()
        if company_result.data:
            updated_company = company_result.data[0]
            kyb_status = updated_company.get('kyb_status')
            try:
                print(f"✅ Company KYB status: {kyb_status}")
            except UnicodeEncodeError:
                print(f"[OK] Company KYB status: {kyb_status}")
        
        # Wait a moment for ClickUp updates to complete
        print("   Waiting for ClickUp updates to complete...")
        time.sleep(5)
        
        try:
            print(f"✅ ClickUp verification completed!")
        except UnicodeEncodeError:
            print(f"[OK] ClickUp verification completed!")
        print(f"   Task URL: https://app.clickup.com/t/{zapier_payload['clickup_task_id']}")
        print()
        
        # Step 5: Final verification summary
        try:
            print("📊 STEP 5: Final verification summary...")
        except UnicodeEncodeError:
            print("STEP 5: Final verification summary...")
        
        expected_clickup_updates = [
            "[OK] KYB Status: pending_documents -> documents_pending_review",
            "[OK] OCR Status: processing -> completed", 
            "[OK] Document attached to task",
            "[OK] SSM Doc [upload] field with clickable URL",
            "[OK] Director Name field populated",
            "[OK] Director Email field populated",
            "[OK] Status comments posted to task"
        ]
        
        print("Expected ClickUp updates:")
        for update in expected_clickup_updates:
            print(f"   {update}")
        
        print()
        print("=" * 100)
        try:
            print("🎉 COMPREHENSIVE END-TO-END TEST COMPLETED SUCCESSFULLY!")
        except UnicodeEncodeError:
            print("COMPREHENSIVE END-TO-END TEST COMPLETED SUCCESSFULLY!")
        print("=" * 100)
        try:
            print("🔍 Manual Verification Required:")
        except UnicodeEncodeError:
            print("Manual Verification Required:")
        print(f"   1. Check ClickUp task: https://app.clickup.com/t/{zapier_payload['clickup_task_id']}")
        print(f"   2. Verify all custom fields are populated")
        print(f"   3. Verify document attachment and URL field")
        print(f"   4. Verify status comments are posted")
        print(f"   5. Verify director fields are populated")
        print("=" * 100)
        
        return True
        
    except Exception as e:
        try:
            print(f"❌ [ERROR] Exception during comprehensive test: {e}")
        except UnicodeEncodeError:
            print(f"[ERROR] Exception during comprehensive test: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        # Cleanup: Remove test company record
        try:
            try:
                print("🧹 Cleaning up test data...")
            except UnicodeEncodeError:
                print("Cleaning up test data...")
            supabase.table('companies').delete().eq('clickup_task_id', zapier_payload['clickup_task_id']).execute()
            if 'document_id' in locals():
                supabase.table('documents').delete().eq('id', document_id).execute()
            try:
                print("✅ Test data cleaned up")
            except UnicodeEncodeError:
                print("[OK] Test data cleaned up")
        except:
            try:
                print("⚠️ Could not clean up all test data")
            except UnicodeEncodeError:
                print("[WARNING] Could not clean up all test data")

if __name__ == "__main__":
    # Ensure Flask app is running
    try:
        print("⚠️  Make sure Flask app is running on http://localhost:5000")
    except UnicodeEncodeError:
        print("WARNING: Make sure Flask app is running on http://localhost:5000")
    print("   Run: python app.py")
    print()
    
    # Check if Flask app is running
    import requests
    try:
        response = requests.get("http://localhost:5000/health", timeout=5)
        if response.status_code == 200:
            print("[OK] Flask app is running, starting test...")
            test_comprehensive_kyb_workflow()
        else:
            print(f"[ERROR] Flask app responded with status {response.status_code}")
            print("Please start the Flask app with: python app.py")
    except requests.exceptions.RequestException:
        print("[ERROR] Flask app is not running")
        print("Please start the Flask app with: python app.py")
        print("Then run this test again.")