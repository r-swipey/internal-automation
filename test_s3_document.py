#!/usr/bin/env python3
"""
Test OCR extraction with actual SSM documents to debug lodger filtering
"""

import sys
import os
sys.path.append('.')

from services.ocr_service import OCRService
import requests
import json
from dotenv import load_dotenv
from supabase import create_client, Client
import time
import glob

# Load environment variables
load_dotenv('.env', override=True)

def get_ssm_documents():
    """Get list of actual SSM documents from local folder"""
    ssm_folder = r"C:\Users\kalya\Documents\SSM documents"
    # Focus on Aurum Paradise document first
    aurum_doc = os.path.join(ssm_folder, "Aurum Paradise_SSM format 2.pdf")
    if os.path.exists(aurum_doc):
        return [aurum_doc]
    
    # Fallback to all PDFs if Aurum document not found
    pdf_files = glob.glob(os.path.join(ssm_folder, "*.pdf"))
    return pdf_files

def test_ssm_documents_via_route():
    """Test OCR extraction with actual SSM documents to debug lodger filtering"""
    
    print("Testing OCR extraction with actual SSM documents...")
    print("=" * 80)
    
    # Get list of SSM documents
    ssm_documents = get_ssm_documents()
    if not ssm_documents:
        print("No SSM documents found in C:\\Users\\kalya\\Documents\\SSM documents")
        return
    
    print(f"Found {len(ssm_documents)} SSM documents to test")
    
    # Setup Supabase client
    supabase_url = os.getenv('SUPABASE_URL')
    supabase_key = os.getenv('SUPABASE_ANON_KEY')
    supabase = create_client(supabase_url, supabase_key)
    
    # Test results summary
    all_results = []
    
    for i, pdf_path in enumerate(ssm_documents[:1]):  # Test first document (Aurum Paradise)
        filename = os.path.basename(pdf_path)
        print(f"\n{'='*80}")
        print(f"TESTING DOCUMENT {i+1}/{min(3, len(ssm_documents))}: {filename}")
        print(f"{'='*80}")
        
        try:
            # Step 1: Create a test customer for this document
            print("Step 1: Creating test customer...")
            
            webhook_payload = {
                "customer_name": f"Test Customer {i+1}",
                "customer_email": "admin@swipey.co",
                "company_name": f"Test Company {i+1}",
                "phone": "+60123456789",
                "business_type": "Technology",
                "typeform_response_id": f"debug_test_{i+1}",
                "submission_timestamp": "2025-07-19T15:00:00Z",
                "clickup_task_id": f"debug_task_{i+1}",
                "clickup_task_url": f"https://app.clickup.com/t/debug_task_{i+1}"
            }
            
            webhook_response = requests.post(
                "http://localhost:5000/zapier-webhook",
                json=webhook_payload,
                headers={'Content-Type': 'application/json'}
            )
            
            if webhook_response.status_code != 200:
                print(f"Webhook failed: {webhook_response.status_code}")
                continue
            
            webhook_data = webhook_response.json()
            customer_token = webhook_data.get('customer_token')
            
            print(f"[OK] Customer created with token: {customer_token[:20]}...")
            
            # Step 2: Read the actual PDF document
            print(f"Step 2: Reading PDF document: {filename}")
            
            with open(pdf_path, 'rb') as f:
                pdf_content = f.read()
            
            # Step 3: Upload the document via the application route
            print("Step 3: Uploading document via application route...")
            
            files = {'document': (filename, pdf_content, 'application/pdf')}
            
            upload_response = requests.post(
                f"http://localhost:5000/upload-file-async/{customer_token}",
                files=files
            )
            
            if upload_response.status_code != 200:
                print(f"Upload failed: {upload_response.status_code}")
                print(f"Response: {upload_response.text}")
                continue
            
            upload_data = upload_response.json()
            document_id = upload_data.get('documentId')
            
            print(f"[OK] Document uploaded successfully: {document_id}")
            
            # Step 4: Wait for OCR processing to complete
            print("Step 4: Waiting for OCR processing...")
            
            extracted_data = None
            max_attempts = 30
            for attempt in range(max_attempts):
                time.sleep(2)
                print(f"Checking OCR status... (attempt {attempt + 1}/{max_attempts})")
                
                doc_response = supabase.table('documents').select('*').eq('id', document_id).execute()
                if doc_response.data:
                    doc_record = doc_response.data[0]
                    ocr_status = doc_record.get('ocr_status')
                    
                    if ocr_status == 'completed':
                        print(f"[OK] OCR processing completed!")
                        
                        extracted_data = {
                            'company_name': doc_record.get('extracted_company_name'),
                            'registration_number': doc_record.get('extracted_registration_number'),
                            'directors': doc_record.get('extracted_directors', [])
                        }
                        break
                        
                    elif ocr_status == 'failed':
                        print(f"[ERROR] OCR processing failed!")
                        break
            
            else:
                print(f"[TIMEOUT] OCR processing timeout after {max_attempts * 2} seconds")
                continue
            
            # Step 5: Analyze the extracted data
            if extracted_data:
                
                print("\nEXTRACTED DATA:")
                print("=" * 60)
                for field, value in extracted_data.items():
                    if value:
                        if field == 'directors' and isinstance(value, list):
                            print(f"{field}:")
                            for i, director in enumerate(value, 1):
                                print(f"  {i}. {director}")
                        else:
                            print(f"{field}: {value}")
                
                print("\nDIRECTOR VERIFICATION:")
                print("=" * 60)
                directors = extracted_data.get('directors', [])
                
                if directors:
                    print(f"Found {len(directors)} directors:")
                    for i, director in enumerate(directors, 1):
                        director_name = director.get('name', 'Unknown')
                        print(f"  {i}. {director_name}")
                        
                        # Check if this looks like a lodger name (should not be here)
                        if any(name in director_name for name in ['AQILAH', 'YAHINDAH', 'SULAIMAN']):
                            print(f"     WARNING: This looks like a lodger name and should be filtered out!")
                        else:
                            print(f"     This appears to be a valid director name")
                else:
                    print("No directors found")
                
                print("\nTEST RESULTS:")
                print("=" * 60)
                
                # Check if the problematic lodger name was filtered out
                lodger_names_found = []
                for director in directors:
                    director_name = director.get('name', '')
                    if any(name in director_name for name in ['AQILAH', 'YAHINDAH', 'SULAIMAN']):
                        lodger_names_found.append(director_name)
                
                if lodger_names_found:
                    print(f"TEST FAILED: Found lodger names in directors: {lodger_names_found}")
                    print("   The OCR extraction is still including lodger information")
                else:
                    print("TEST PASSED: No lodger names found in directors list")
                    print("   The OCR extraction properly filtered out lodger information")
                
                # Verify database was updated
                print("\nDATABASE VERIFICATION:")
                print("=" * 60)
                
                # Check the document record was updated
                updated_record = supabase.table('documents').select('*').eq('id', document_id).execute()
                if updated_record.data:
                    doc = updated_record.data[0]
                    print(f"OCR Status: {doc.get('ocr_status')}")
                    print(f"Company Name: {doc.get('extracted_company_name')}")
                    print(f"Registration Number: {doc.get('extracted_registration_number')}")
                    print(f"Business Address: {doc.get('extracted_business_address')}")
                    
                    # Check if directors were saved correctly
                    directors_in_db = doc.get('extracted_directors', [])
                    if directors_in_db:
                        print(f"Directors in DB: {len(directors_in_db)}")
                        for i, director in enumerate(directors_in_db, 1):
                            print(f"  {i}. {director}")
                
                return extracted_data
                
            else:
                print("No extracted data available")
                return None
            
        except Exception as e:
            print(f"Error during OCR extraction: {e}")
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
    test_ssm_documents_via_route()