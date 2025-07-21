#!/usr/bin/env python3
"""
Debug ClickUp integration for the manual test
"""

import sys
import os
sys.path.append('.')

from dotenv import load_dotenv
load_dotenv('.env', override=True)

from supabase import create_client

def debug_clickup_integration():
    """Debug why ClickUp integrations didn't trigger"""
    
    supabase_url = os.getenv('SUPABASE_URL')
    supabase_key = os.getenv('SUPABASE_ANON_KEY')
    supabase = create_client(supabase_url, supabase_key)
    
    print("=== DEBUG CLICKUP INTEGRATION ===")
    
    # Find the company record for blacksheep2025
    print("1. Looking for company record with blacksheep2025...")
    company_result = supabase.table('companies').select('*').eq('company_name', 'blacksheep2025').execute()
    
    if not company_result.data:
        print("[ERROR] No company record found for blacksheep2025")
        return
    
    company = company_result.data[0]
    clickup_task_id = company['clickup_task_id']
    customer_token = company.get('customer_token')
    
    print(f"[OK] Company found:")
    print(f"   Task ID: {clickup_task_id}")
    print(f"   Customer Token: {customer_token[:20] if customer_token else 'None'}...")
    print(f"   Customer First Name: {company.get('customer_first_name')}")
    print()
    
    # Find related documents
    print("2. Looking for related documents...")
    if customer_token:
        # Try finding by customer_token (what OCR service uses)
        doc_result = supabase.table('documents').select('*').eq('customer_token', customer_token).execute()
        print(f"   Documents found by customer_token: {len(doc_result.data)}")
    else:
        doc_result = supabase.table('documents').select('*').eq('clickup_task_id', clickup_task_id).execute()
        print(f"   Documents found by clickup_task_id: {len(doc_result.data)}")
    
    if not doc_result.data:
        print("[ERROR] No documents found!")
        return
    
    for doc in doc_result.data:
        print(f"   Document ID: {doc['id']}")
        print(f"   OCR Status: {doc.get('ocr_status')}")
        print(f"   Customer Token: {doc.get('customer_token', 'None')}")
        print(f"   Directors: {len(doc.get('extracted_directors', []))} found")
        if doc.get('extracted_directors'):
            first_director = doc['extracted_directors'][0]
            print(f"   First Director: {first_director.get('name')} ({first_director.get('email', 'No email')})")
        print()
    
    # Check if ClickUp API token is configured
    clickup_token = os.getenv('CLICKUP_API_TOKEN')
    if clickup_token:
        print("[OK] ClickUp API token is configured")
    else:
        print("[ERROR] ClickUp API token NOT configured!")
    
    print("=== END DEBUG ===")

if __name__ == "__main__":
    debug_clickup_integration()