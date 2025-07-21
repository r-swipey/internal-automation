#!/usr/bin/env python3
"""
Debug the consent field specifically
"""

import sys
import os
import json
sys.path.append('.')

from dotenv import load_dotenv
load_dotenv('.env', override=True)

from services.clickup_service import ClickUpService

def debug_consent_field():
    """Find and debug the consent field"""
    
    task_id = "86czq4a5a"
    
    clickup_service = ClickUpService()
    
    # Get task with custom fields
    task_with_fields = clickup_service._get_task_with_custom_fields(task_id)
    
    if not task_with_fields.get('success'):
        print(f"Failed to get task fields: {task_with_fields.get('error')}")
        return
    
    custom_fields = task_with_fields.get('custom_fields', [])
    
    print("Looking for consent/authorization field...")
    
    for i, field in enumerate(custom_fields):
        field_name = field.get('name', '')
        field_type = field.get('type', '')
        
        # Check for Unicode or consent-related fields
        if (field_type == 'drop_down' and 
            ('consent' in field_name.lower() or 
             'authorisation' in field_name.lower() or 
             'authorization' in field_name.lower() or
             '✍️' in field_name)):
            
            print(f"\n=== FOUND CONSENT FIELD [{i}] ===")
            
            # Save to file to avoid Unicode issues
            with open('consent_field_data.json', 'w', encoding='utf-8') as f:
                json.dump(field, f, indent=2, ensure_ascii=False)
            
            print(f"Field data saved to consent_field_data.json")
            print(f"Field ID: {field.get('id')}")
            print(f"Field Type: {field.get('type')}")
            print(f"Current Value: {field.get('value')}")
            
            # Check dropdown options
            if 'type_config' in field and 'options' in field['type_config']:
                options = field['type_config']['options']
                print(f"Dropdown options ({len(options)} total):")
                for j, option in enumerate(options):
                    print(f"  [{j}] {option.get('name', 'No Name')}")
            
if __name__ == "__main__":
    debug_consent_field()