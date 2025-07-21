#!/usr/bin/env python3
"""
Test ClickUp Document Attachment
Tests the document attachment functionality with ClickUp task
"""

import sys
import os
sys.path.append('.')

from dotenv import load_dotenv
load_dotenv('.env', override=True)

from services.clickup_service import attach_document_to_clickup_task

def test_clickup_document_attachment():
    """Test attaching a document to ClickUp task"""
    
    task_id = "86czpny8a"
    
    # Use a sample PDF file for testing
    test_file_path = r"C:\Users\kalya\Documents\SSM documents\S14 Company Registration_aiengineer.pdf"
    test_filename = "S14_Company_Registration_aiengineer_TEST.pdf"
    
    print("=" * 80)
    print("TESTING CLICKUP DOCUMENT ATTACHMENT")
    print("=" * 80)
    print(f"Task ID: {task_id}")
    print(f"Test File: {test_file_path}")
    print(f"Filename: {test_filename}")
    print()
    
    # Check if test file exists
    if not os.path.exists(test_file_path):
        print(f"[ERROR] Test file not found: {test_file_path}")
        print("Please ensure the test file exists or update the path")
        return False
    
    # Test document attachment
    print("Step 1: Attaching document to ClickUp task...")
    
    try:
        result = attach_document_to_clickup_task(
            task_id=task_id,
            file_path=test_file_path,
            filename=test_filename
        )
        
        if result.get('success'):
            print(f"[OK] Document attachment successful!")
            print(f"   Attachment URL: {result.get('attachment_url', 'N/A')}")
            print(f"   SSM Field Updated: {result.get('ssm_field_updated', False)}")
            
            print()
            print("=" * 80)
            print("ATTACHMENT TEST COMPLETED SUCCESSFULLY!")
            print("=" * 80)
            print("Check your ClickUp task to verify:")
            print(f"   1. Document attached: {test_filename}")
            print(f"   2. SSM document field updated with attachment URL")
            print(f"   3. Task URL: https://app.clickup.com/t/{task_id}")
            print("=" * 80)
            
            return True
            
        else:
            print(f"[ERROR] Document attachment failed: {result.get('error')}")
            return False
            
    except Exception as e:
        print(f"[ERROR] Exception during attachment test: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    test_clickup_document_attachment()