#!/usr/bin/env python3
"""
Test ClickUp Custom Field Integration
Tests our ClickUp service with the actual custom fields created in ClickUp
"""

import sys
import os
sys.path.append('.')

from dotenv import load_dotenv
load_dotenv('.env', override=True)  # Force reload environment variables

from services.clickup_service import update_clickup_task_status, ClickUpService
import time

def test_clickup_custom_fields():
    """Test ClickUp custom field updates with real task"""
    
    # Task ID from the provided URL: https://app.clickup.com/t/86czpny8a
    test_task_id = "86czpny8a"
    
    print("=" * 80)
    print("TESTING CLICKUP CUSTOM FIELD INTEGRATION")
    print("=" * 80)
    print(f"Task ID: {test_task_id}")
    print(f"Task URL: https://app.clickup.com/t/{test_task_id}")
    print()
    
    # Initialize ClickUp service
    clickup_service = ClickUpService()
    
    # Test 1: Get task info to verify connection
    print("Step 1: Testing ClickUp API connection...")
    task_info = clickup_service.get_task_info(test_task_id)
    
    if task_info.get('success'):
        task_data = task_info.get('task', {})
        print(f"[OK] Successfully connected to ClickUp!")
        print(f"   Task Name: {task_data.get('name')}")
        print(f"   Task URL: {task_data.get('url')}")
        print()
    else:
        print(f"[ERROR] Failed to connect to ClickUp: {task_info.get('error')}")
        return False
    
    # Test 2: OCR Status Updates
    print("Step 2: Testing OCR Status custom field updates...")
    
    ocr_statuses = ['pending', 'processing', 'completed']
    for i, status in enumerate(ocr_statuses):
        print(f"   Updating OCR Status to: {status}")
        
        # Prepare additional info for completed status
        additional_info = {}
        if status == 'completed':
            additional_info = {
                'extracted_data': {
                    'company_name': 'Test Company Sdn Bhd',
                    'registration_number': '202401042728 (1588573-M)',
                    'directors': [
                        {'name': 'John Doe', 'id_number': '920209016081'},
                        {'name': 'Jane Smith', 'id_number': '850315025639'}
                    ]
                }
            }
        
        result = update_clickup_task_status(
            task_id=test_task_id,
            status_type='ocr_status',
            status_value=status,
            additional_info=additional_info
        )
        
        if result.get('success'):
            print(f"   [OK] OCR Status updated to '{status}' successfully!")
        else:
            print(f"   [ERROR] Failed to update OCR Status: {result.get('error')}")
        
        # Wait between updates to see the changes clearly
        if i < len(ocr_statuses) - 1:
            print("   Waiting 3 seconds...")
            time.sleep(3)
    
    print()
    
    # Test 3: KYB Status Updates  
    print("Step 3: Testing KYB Status custom field updates...")
    
    kyb_statuses = ['pending_documents', 'documents_pending_review', 'kyb_completed']
    for i, status in enumerate(kyb_statuses):
        print(f"   Updating KYB Status to: {status}")
        
        # Prepare additional info
        additional_info = {
            'customer_email': 'test@example.com',
            'company_name': 'Test Company Sdn Bhd'
        }
        
        if status == 'documents_pending_review':
            additional_info['document_count'] = 2
        
        result = update_clickup_task_status(
            task_id=test_task_id,
            status_type='kyb_status', 
            status_value=status,
            additional_info=additional_info
        )
        
        if result.get('success'):
            print(f"   [OK] KYB Status updated to '{status}' successfully!")
        else:
            print(f"   [ERROR] Failed to update KYB Status: {result.get('error')}")
        
        # Wait between updates
        if i < len(kyb_statuses) - 1:
            print("   Waiting 3 seconds...")
            time.sleep(3)
    
    print()
    
    # Test 4: Check custom fields directly
    print("Step 4: Testing custom field discovery...")
    task_with_fields = clickup_service._get_task_with_custom_fields(test_task_id)
    
    if task_with_fields.get('success'):
        custom_fields = task_with_fields.get('custom_fields', [])
        print(f"[OK] Found {len(custom_fields)} custom fields:")
        
        for field in custom_fields:
            field_name = field.get('name', 'Unknown')
            field_id = field.get('id', 'Unknown')
            field_value = field.get('value', 'Not set')
            print(f"   {field_name} (ID: {field_id}) = {field_value}")
    else:
        print(f"[ERROR] Failed to get custom fields: {task_with_fields.get('error')}")
    
    print()
    print("=" * 80)
    print("CLICKUP INTEGRATION TEST COMPLETED!")
    print("=" * 80)
    print("Check your ClickUp task to see the updates:")
    print(f"   https://app.clickup.com/t/{test_task_id}")
    print()
    print("Expected results:")
    print("   OCR Status custom field should show: completed")
    print("   KYB Status custom field should show: kyb_completed") 
    print("   Task should have several new comments with status updates")
    print("=" * 80)
    
    return True

if __name__ == "__main__":
    test_clickup_custom_fields()