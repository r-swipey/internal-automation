#!/usr/bin/env python3
"""
Test Template Information
Get details about the Documenso template to understand its structure
"""

import sys
import os
sys.path.append('.')

from dotenv import load_dotenv
load_dotenv('.env', override=True)

from services.documenso_service import DocumensoService
import json

def test_template_info():
    """Get template information from Documenso"""
    
    print("=== DOCUMENSO TEMPLATE INFO TEST ===")
    
    # Initialize Documenso service
    service = DocumensoService()
    template_id = '5442'  # New template ID after plan upgrade
    
    print(f"Getting template info for template ID: {template_id}")
    
    # First get list of all available templates
    print("Getting list of all templates...")
    templates_result = service.get_templates_list()
    
    if templates_result.get('success'):
        templates_data = templates_result.get('data', {})
        templates = templates_data.get('templates', [])
        print(f"[OK] Found {len(templates)} templates:")
        
        for template in templates:
            t_id = template.get('id')
            external_id = template.get('externalId')
            title = template.get('title')
            print(f"   Template ID: {t_id} | External ID: {external_id} | Title: {title}")
    
    print(f"\nNow getting specific template info for: {template_id}")
    
    # Get template information to retrieve recipient IDs
    result = service.get_template_info(template_id)
    
    if result.get('success'):
        template_data = result.get('data')
        print(f"[OK] Template found!")
        print(f"   Template ID: {template_data.get('id')}")
        print(f"   Title: {template_data.get('title')}")
        print(f"   Status: {template_data.get('status')}")
        
        # Show recipients
        recipients = template_data.get('recipients', [])
        print(f"   Recipients: {len(recipients)}")
        for i, recipient in enumerate(recipients):
            print(f"     {i}. ID: {recipient.get('id')} - Role: {recipient.get('role')} - Name: {recipient.get('name', 'Not set')}")
        
        # Show fields that can be prefilled
        fields = template_data.get('fields', [])
        print(f"   Fields: {len(fields)}")
        for i, field in enumerate(fields):
            print(f"     {i}. Type: {field.get('type')} - Page: {field.get('page')} - Inserted: {field.get('inserted')}")
        
        print(f"\n[DEBUG] Full template data:")
        print(json.dumps(template_data, indent=2))
        
    else:
        print(f"[ERROR] Failed to get template info: {result.get('error')}")
        if result.get('response'):
            print(f"   Response: {result.get('response')}")
    
    print("\n=== TEST COMPLETED ===")

if __name__ == "__main__":
    test_template_info()