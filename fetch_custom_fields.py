#!/usr/bin/env python3
"""
Simple script to fetch and display ClickUp custom field names for task 86czq4a5a
This helps us see exactly what custom field names exist in ClickUp for proper mapping.
"""

import os
import sys
from dotenv import load_dotenv
from services.clickup_service import ClickUpService

# Load environment variables from .env file
load_dotenv()

def main():
    """Fetch and display custom fields for the specified ClickUp task"""
    
    task_id = "86czq4a5a"
    
    print(f"Fetching custom fields for ClickUp task: {task_id}")
    print("=" * 60)
    
    # Initialize ClickUp service
    try:
        clickup_service = ClickUpService()
        
        if not clickup_service.api_token:
            print("ERROR: ClickUp API token not found in environment variables")
            print("Please set CLICKUP_API_TOKEN environment variable")
            return 1
            
    except Exception as e:
        print(f"ERROR: Failed to initialize ClickUp service: {e}")
        return 1
    
    # Fetch task with custom fields
    try:
        print("Fetching task information...")
        task_info = clickup_service._get_task_with_custom_fields(task_id)
        
        if not task_info.get('success'):
            print(f"ERROR: Failed to fetch task: {task_info.get('error')}")
            return 1
            
    except Exception as e:
        print(f"ERROR: Exception while fetching task: {e}")
        return 1
    
    # Display custom fields
    custom_fields = task_info.get('custom_fields', [])
    
    if not custom_fields:
        print("No custom fields found for this task.")
        return 0
    
    print(f"\nFound {len(custom_fields)} custom fields:")
    print("-" * 60)
    
    for i, field in enumerate(custom_fields, 1):
        field_id = field.get('id', 'No ID')
        field_name = field.get('name', 'No Name')
        field_type = field.get('type', 'No Type')
        
        print(f"{i:2}. Field Name: {repr(field_name)}")
        print(f"    Field ID:   {field_id}")
        print(f"    Field Type: {field_type}")
        
        # Show dropdown options if it's a dropdown field
        if field_type == 'drop_down':
            type_config = field.get('type_config', {})
            options = type_config.get('options', [])
            if options:
                print(f"    Options:    {[opt.get('name') for opt in options]}")
        
        # Show current value if available
        value = field.get('value')
        if value is not None:
            print(f"    Value:      {repr(value)}")
        
        print()
    
    print("=" * 60)
    print("Custom field names extraction complete!")
    
    return 0

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)