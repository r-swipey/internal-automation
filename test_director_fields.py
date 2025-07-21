#!/usr/bin/env python3
"""
Test Director Fields Integration
Tests updating Director Name and Director Email custom fields in ClickUp
"""

import sys
import os
sys.path.append('.')

from dotenv import load_dotenv
load_dotenv('.env', override=True)

from services.clickup_service import update_clickup_director_fields

def test_director_fields():
    """Test updating Director Name and Director Email fields"""
    
    task_id = "86czpny8a"
    
    # Sample director data (like what comes from OCR)
    directors_data = [
        {
            'name': 'LEE KIAN SENG',
            'email': 'lee@aingineer.io',
            'id_type': 'NRIC',
            'id_number': '920209016081'
        },
        {
            'name': 'JANE SMITH',  # Second director (should be ignored)
            'email': 'jane@example.com',
            'id_type': 'NRIC', 
            'id_number': '850315025639'
        }
    ]
    
    print("=" * 80)
    print("TESTING CLICKUP DIRECTOR FIELDS UPDATE")
    print("=" * 80)
    print(f"Task ID: {task_id}")
    print(f"First Director Name: {directors_data[0]['name']}")
    print(f"First Director Email: {directors_data[0]['email']}")
    print()
    
    # Test director fields update
    print("Step 1: Updating Director Name and Director Email fields...")
    
    try:
        result = update_clickup_director_fields(task_id, directors_data)
        
        if result.get('success'):
            print(f"[OK] Director fields update completed!")
            print(f"   Director Name updated: {result.get('name_updated')}")
            print(f"   Director Email updated: {result.get('email_updated')}")
            
            print()
            print("=" * 80)
            print("DIRECTOR FIELDS TEST COMPLETED!")
            print("=" * 80)
            print("Check your ClickUp task to verify:")
            print(f"   1. Director Name field: {directors_data[0]['name']}")
            print(f"   2. Director Email field: {directors_data[0]['email']}")
            print(f"   3. Task URL: https://app.clickup.com/t/{task_id}")
            print("=" * 80)
            
            return True
            
        else:
            print(f"[ERROR] Director fields update failed: {result.get('error')}")
            return False
            
    except Exception as e:
        print(f"[ERROR] Exception during director fields test: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    test_director_fields()