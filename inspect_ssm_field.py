#!/usr/bin/env python3
"""
Inspect SSM document field structure to understand attachment field format
"""

import sys
import os
sys.path.append('.')

from dotenv import load_dotenv
load_dotenv('.env', override=True)

from services.clickup_service import ClickUpService

def inspect_ssm_field():
    """Inspect the SSM document field structure"""
    
    task_id = "86czpny8a"
    print("=" * 80)
    print("INSPECTING SSM DOCUMENT FIELD")
    print("=" * 80)
    
    clickup_service = ClickUpService()
    
    # Get task with custom fields
    task_with_fields = clickup_service._get_task_with_custom_fields(task_id)
    
    if not task_with_fields.get('success'):
        print(f"Failed to get task fields: {task_with_fields.get('error')}")
        return
    
    custom_fields = task_with_fields.get('custom_fields', [])
    
    # Find SSM document field
    for field in custom_fields:
        field_name = field.get('name', '')
        if 'ssm' in field_name.lower():
            print(f"\n=== {field_name} ===")
            print(f"Field ID: {field.get('id')}")
            print(f"Field Type: {field.get('type')}")
            print(f"Current Value: {field.get('value')}")
            
            # Check type config for attachment fields
            if 'type_config' in field:
                type_config = field['type_config']
                print(f"Type Config: {type_config}")
            
            print("-" * 60)
            
            # Print full field structure for debugging
            print("FULL FIELD STRUCTURE:")
            import json
            print(json.dumps(field, indent=2))
            print("-" * 60)

if __name__ == "__main__":
    inspect_ssm_field()