#!/usr/bin/env python3
"""
Process a specific AWS Textract JSON file through the OCR extraction logic
"""

import json
import sys
import os

# Add the current directory to the path to import the OCR service
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from services.ocr_service import OCRService
except ImportError:
    print("❌ Could not import OCRService. Make sure services/ocr_service.py exists.")
    sys.exit(1)

def load_textract_json(file_path):
    """Load the Textract JSON response file"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"❌ File not found: {file_path}")
        return None
    except json.JSONDecodeError as e:
        print(f"❌ Invalid JSON file: {e}")
        return None
    except Exception as e:
        print(f"❌ Error loading file: {e}")
        return None

def main():
    # Specify the file path
    file_path = r"C:\Users\kalya\Downloads\AWS TextTract\Super Form - Section 14-warptech\analyzeDocResponse.json"
    
    print("Processing AWS Textract JSON file through OCR extraction logic")
    print("=" * 70)
    print(f"File: {file_path}")
    print("=" * 70)
    
    # Load the JSON file
    textract_response = load_textract_json(file_path)
    if not textract_response:
        print("❌ Failed to load Textract response file")
        return
    
    print(f"Loaded Textract response successfully")
    print(f"   Document Pages: {textract_response.get('DocumentMetadata', {}).get('Pages', 'Unknown')}")
    print(f"   Job Status: {textract_response.get('JobStatus', 'Unknown')}")
    print(f"   Total Blocks: {len(textract_response.get('Blocks', []))}")
    
    # Initialize OCR service
    ocr_service = OCRService()
    
    # Extract key information using the OCR service logic
    print("\\nExtracting key information...")
    try:
        extracted_data = ocr_service._extract_key_information(textract_response)
        
        print("\\n" + "=" * 70)
        print("EXTRACTED DATA RESULTS")
        print("=" * 70)
        
        # Display extracted fields
        fields = [
            ('Company Name', 'company_name'),
            ('Registration Number', 'registration_number'),
            ('Incorporation Date', 'incorporation_date'),
            ('Company Type', 'company_type'),
            ('Business Address', 'business_address'),
            ('Business Phone', 'business_phone'),
            ('Directors', 'directors')
        ]
        
        for field_name, field_key in fields:
            value = extracted_data.get(field_key)
            if value:
                if field_key == 'directors' and isinstance(value, list):
                    print(f"[FOUND] {field_name}:")
                    for i, director in enumerate(value, 1):
                        print(f"   {i}. {director}")
                else:
                    print(f"[FOUND] {field_name}: {value}")
            else:
                print(f"[NOT FOUND] {field_name}: Not found")
        
        # Show confidence scores if available
        if extracted_data.get('confidence_scores'):
            print("\\nCONFIDENCE SCORES:")
            for field, score in extracted_data['confidence_scores'].items():
                print(f"   {field}: {score:.1f}%")
        
        # Show additional extracted text if available
        if extracted_data.get('all_text'):
            print("\\nSAMPLE EXTRACTED TEXT (first 500 chars):")
            print(extracted_data['all_text'][:500] + "..." if len(extracted_data['all_text']) > 500 else extracted_data['all_text'])
        
        print("\\n" + "=" * 70)
        print("EXTRACTION SUMMARY")
        print("=" * 70)
        
        # Count successful extractions
        successful_fields = sum(1 for _, key in fields if extracted_data.get(key))
        total_fields = len(fields)
        
        print(f"Fields extracted: {successful_fields}/{total_fields}")
        print(f"Success rate: {(successful_fields/total_fields)*100:.1f}%")
        
        # Show extraction quality
        if successful_fields >= 5:
            print("Extraction quality: EXCELLENT")
        elif successful_fields >= 3:
            print("Extraction quality: GOOD")
        else:
            print("Extraction quality: POOR")
        
        # Return the extracted data as JSON for further processing
        print("\\nRAW EXTRACTED DATA (JSON):")
        print(json.dumps(extracted_data, indent=2, ensure_ascii=False))
        
    except Exception as e:
        print(f"❌ Error during extraction: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()