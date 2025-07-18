#!/usr/bin/env python3
"""
Script to process AWS Textract JSON files using existing OCR logic
"""

import json
import sys
import os
from services.ocr_service import OCRService

def load_json_file(file_path):
    """Load JSON file and return content"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading {file_path}: {e}")
        return None

def main():
    # File paths
    json_files = [
        r"C:\Users\kalya\Downloads\AWS TextTract\Company SSM UNI-20250218174711051322-905590-uniROC-ipayob_en - LATEST\analyzeDocResponse(1).json",
        r"C:\Users\kalya\Downloads\AWS TextTract\SuperFormANSB ansb finance\analyzeDocResponse.json"
    ]
    
    # Create OCR service instance
    ocr_service = OCRService()
    
    for i, file_path in enumerate(json_files, 1):
        print(f"\n{'='*60}")
        print(f"PROCESSING FILE {i}: {os.path.basename(file_path)}")
        print(f"{'='*60}")
        
        # Load JSON file
        textract_response = load_json_file(file_path)
        if not textract_response:
            print(f"Failed to load file: {file_path}")
            continue
        
        # Extract key information using existing OCR logic
        try:
            extracted_data = ocr_service._extract_key_information(textract_response)
            
            print(f"\nEXTRACTED FIELDS:")
            print(f"Company Name: {extracted_data.get('company_name', 'N/A')}")
            print(f"Registration Number: {extracted_data.get('registration_number', 'N/A')}")
            print(f"Incorporation Date: {extracted_data.get('incorporation_date', 'N/A')}")
            print(f"Company Type: {extracted_data.get('company_type', 'N/A')}")
            print(f"Business Address: {extracted_data.get('business_address', 'N/A')}")
            print(f"Business Phone: {extracted_data.get('business_phone', 'N/A')}")
            
            directors = extracted_data.get('directors', [])
            if directors:
                print(f"\nDIRECTORS ({len(directors)} found):")
                for j, director in enumerate(directors, 1):
                    print(f"  {j}. Name: {director.get('name', 'N/A')}")
                    print(f"     ID Type: {director.get('id_type', 'N/A')}")
                    print(f"     ID Number: {director.get('id_number', 'N/A')}")
                    print(f"     Email: {director.get('email', 'N/A')}")
                    print()
            else:
                print(f"\nDIRECTORS: None found")
                
        except Exception as e:
            print(f"Error processing file {file_path}: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    main()