#!/usr/bin/env python3
"""
Test Document Sending
Try to send the DRAFT document 277574
"""

import sys
import os
sys.path.append('.')

from dotenv import load_dotenv
load_dotenv('.env', override=True)

from services.documenso_service import DocumensoService

def test_send_document():
    """Test sending a specific document"""
    
    print("=== DOCUMENSO SEND DOCUMENT TEST ===")
    
    # Initialize Documenso service
    service = DocumensoService()
    document_id = '277574'  # The DRAFT document
    
    print(f"Attempting to send document: {document_id}")
    
    # First check current status
    print("1. Checking current document status...")
    status_result = service.get_document_status(document_id)
    
    if status_result.get('success'):
        doc_data = status_result.get('data')
        current_status = doc_data.get('status')
        print(f"   Current status: {current_status}")
        print(f"   Title: {doc_data.get('title')}")
        
        recipients = doc_data.get('recipients', [])
        print(f"   Recipients: {len(recipients)}")
        for recipient in recipients:
            print(f"     - {recipient.get('name')} ({recipient.get('email')}) - Send Status: {recipient.get('sendStatus')}")
    else:
        print(f"   [ERROR] Failed to get status: {status_result.get('error')}")
        return
    
    # Try to send the document
    print(f"\n2. Attempting to send document...")
    send_result = service.send_document(document_id)
    
    if send_result.get('success'):
        print(f"   [SUCCESS] Document sent!")
        print(f"   Used endpoint: {send_result.get('endpoint')}")
        
        # Check status again
        print(f"\n3. Checking status after sending...")
        new_status_result = service.get_document_status(document_id)
        if new_status_result.get('success'):
            new_doc_data = new_status_result.get('data')
            new_status = new_doc_data.get('status')
            print(f"   New status: {new_status}")
        
    else:
        print(f"   [ERROR] Failed to send: {send_result.get('error')}")
    
    print("\n=== TEST COMPLETED ===")

if __name__ == "__main__":
    test_send_document()