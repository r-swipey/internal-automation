#!/usr/bin/env python3
"""
Inspect ClickUp dropdown field structure
"""

import sys
import os
sys.path.append('.')

from dotenv import load_dotenv
load_dotenv('.env', override=True)

from services.clickup_service import ClickUpService

def inspect_dropdown_fields():
    """Inspect the dropdown structure of our custom fields"""
    
    task_id = "86czq4a5a"
    print("=" * 80)
    print("INSPECTING CLICKUP DROPDOWN FIELDS")
    print("=" * 80)
    
    clickup_service = ClickUpService()
    
    # Get task with custom fields
    task_with_fields = clickup_service._get_task_with_custom_fields(task_id)
    
    if not task_with_fields.get('success'):
        print(f"Failed to get task fields: {task_with_fields.get('error')}")
        return
    
    custom_fields = task_with_fields.get('custom_fields', [])
    
    # Show ALL custom fields first
    print("\n=== ALL CUSTOM FIELDS ===")
    for i, field in enumerate(custom_fields):
        field_name = field.get('name', '')
        field_type = field.get('type', '')
        current_value = field.get('value', 'No Value')
        try:
            print(f"[{i}] Name: '{field_name}' | Type: {field_type} | Value: {current_value}")
        except UnicodeEncodeError:
            print(f"[{i}] Name: [Unicode field] | Type: {field_type} | Value: {current_value}")
            # Also check if this contains consent/authorization keywords
            if 'consent' in field_name.lower() or 'authorisation' in field_name.lower() or 'authorization' in field_name.lower():
                print(f"    *** FOUND CONSENT FIELD: {repr(field_name)} ***")
    
    print("\n" + "="*80)
    
    # Find our target fields
    target_fields = ['OCR Status', 'KYB Status', 'SSM document', '✍️ Consent & Authorisation']
    
    for field in custom_fields:
        field_name = field.get('name', '')
        if field_name in target_fields:
            print(f"\n=== {field_name} ===")
            print(f"Field ID: {field.get('id')}")
            print(f"Field Type: {field.get('type')}")
            print(f"Current Value: {field.get('value')}")
            
            # Check if it's a dropdown with options
            if 'type_config' in field:
                type_config = field['type_config']
                print(f"Type Config: {type_config}")
                
                if 'options' in type_config:
                    options = type_config['options']
                    print(f"Dropdown Options ({len(options)} total):")
                    
                    for i, option in enumerate(options):
                        option_id = option.get('id', 'No ID')
                        option_name = option.get('name', 'No Name')
                        option_value = option.get('value', 'No Value')
                        print(f"  [{i}] ID: {option_id} | Name: {option_name} | Value: {option_value}")
            
            print("-" * 60)

if __name__ == "__main__":
    inspect_dropdown_fields()