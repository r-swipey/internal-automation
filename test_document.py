#!/usr/bin/env python3
"""
Comprehensive test suite for the internal automation system
Includes tests for:
- Zapier webhook payload processing
- OCR document processing
- File upload functionality
"""

import requests
import json
import os
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
import io
import unittest
from datetime import datetime
import time
from supabase import create_client, Client
from dotenv import load_dotenv
import uuid

# Load environment variables for database testing
load_dotenv('.env', override=True)

def create_test_pdf():
    """Create a test PDF with company information"""
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    
    # Write test company information
    c.drawString(100, 750, "COMPANY REGISTRATION FORM")
    c.drawString(100, 730, "="*50)
    c.drawString(100, 700, "Company Name: MOHAN NOMAND 123 SDN. BHD.")
    c.drawString(100, 680, "Registration Number: 202501001234 (1234567-A)")
    c.drawString(100, 660, "Incorporation Date: 17/01/2025")
    c.drawString(100, 640, "Company Type: SDN. BHD.")
    c.drawString(100, 620, "Business Address: NO. 123, JALAN TEST 1/2")
    c.drawString(100, 600, "                  TAMAN TEST")
    c.drawString(100, 580, "                  47000 PETALING JAYA")
    c.drawString(100, 560, "                  SELANGOR")
    c.drawString(100, 540, "Business Phone: +60123655555")
    c.drawString(100, 520, "")
    c.drawString(100, 500, "DIRECTORS:")
    c.drawString(100, 480, "1. MOHAN KUMAR A/L SURESH")
    c.drawString(100, 460, "   NRIC: 800123145678")
    c.drawString(100, 440, "   Email: mohan@testcompany.com")
    
    c.save()
    buffer.seek(0)
    return buffer.getvalue()

def upload_test_document():
    """Upload the test PDF document"""
    
    # The upload token from the previous response
    upload_token = "eyJ0YXNrSWQiOiAidGFza19tbjEyM18wMDEiLCAiZW1haWwiOiAiYWRtaW5Ac3dpcGV5LmNvIiwgInRpbWVzdGFtcCI6ICIyMDI1LTA3LTE3VDIzOjI4OjMyLjYxOTE0MSJ9"
    
    # Create test PDF
    pdf_content = create_test_pdf()
    print(f"Created test PDF with {len(pdf_content)} bytes")
    
    # Upload using the async endpoint
    files = {'document': ('test_company_registration.pdf', pdf_content, 'application/pdf')}
    
    try:
        print("Uploading document...")
        response = requests.post(
            f'http://localhost:5000/upload-file-async/{upload_token}',
            files=files
        )
        
        print(f"Upload Response Status: {response.status_code}")
        print(f"Upload Response: {json.dumps(response.json(), indent=2)}")
        
        return response.json()
        
    except Exception as e:
        print(f"Upload error: {e}")
        return None

class TestZapierWebhook(unittest.TestCase):
    """Test cases for Zapier webhook functionality"""
    
    def setUp(self):
        self.base_url = "http://localhost:5000"
        self.test_payload = {
            "customer_name": "Test Customer Auto",
            "customer_email": "admin@swipey.co",
            "company_name": "AutoTest Solutions Bhd",
            "phone": "+601234567890",
            "business_type": "Technology",
            "typeform_response_id": "auto_test_123",
            "submission_timestamp": datetime.now().isoformat(),
            "clickup_task_id": "task_autotest_001",
            "clickup_task_url": "https://app.clickup.com/t/task_autotest_001"
        }
    
    def test_zapier_webhook_valid_payload(self):
        """Test Zapier webhook with valid payload"""
        response = requests.post(
            f"{self.base_url}/zapier-webhook",
            json=self.test_payload,
            headers={'Content-Type': 'application/json'}
        )
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data.get('success'))
        self.assertEqual(data.get('task_id'), self.test_payload['clickup_task_id'])
        self.assertIsNotNone(data.get('upload_link'))
        self.assertIsNotNone(data.get('customer_token'))
        
        print(f"✅ Zapier webhook test passed: {data.get('message')}")
        print(f"Upload link: {data.get('upload_link')}")
        return data.get('customer_token')
    
    def test_zapier_webhook_missing_required_fields(self):
        """Test Zapier webhook with missing required fields"""
        incomplete_payload = self.test_payload.copy()
        del incomplete_payload['customer_name']
        
        response = requests.post(
            f"{self.base_url}/zapier-webhook",
            json=incomplete_payload,
            headers={'Content-Type': 'application/json'}
        )
        
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertFalse(data.get('success'))
        self.assertIn('Missing required field', data.get('error', ''))
        
        print(f"✅ Missing field validation test passed: {data.get('error')}")
    
    def test_zapier_webhook_invalid_email(self):
        """Test Zapier webhook with invalid email format"""
        invalid_payload = self.test_payload.copy()
        invalid_payload['customer_email'] = 'invalid-email'
        
        response = requests.post(
            f"{self.base_url}/zapier-webhook",
            json=invalid_payload,
            headers={'Content-Type': 'application/json'}
        )
        
        # Should still process but might have email validation issues
        data = response.json()
        print(f"✅ Invalid email test completed: Status {response.status_code}")
        print(f"Response: {data}")


class TestOCRProcessing(unittest.TestCase):
    """Test cases for OCR document processing"""
    
    def setUp(self):
        self.base_url = "http://localhost:5000"
        # Mock OCR response data based on the provided JSON
        self.mock_ocr_response = {
            "DocumentMetadata": {"Pages": 4},
            "JobStatus": "SUCCEEDED",
            "Blocks": [
                {
                    "BlockType": "LINE",
                    "Confidence": 99.76,
                    "Text": "COMPANY REGISTRATION",
                    "Geometry": {
                        "BoundingBox": {
                            "Width": 0.8,
                            "Height": 0.05,
                            "Left": 0.1,
                            "Top": 0.1
                        }
                    }
                },
                {
                    "BlockType": "LINE",
                    "Confidence": 98.45,
                    "Text": "Company Name: AutoTest Solutions Bhd",
                    "Geometry": {
                        "BoundingBox": {
                            "Width": 0.7,
                            "Height": 0.04,
                            "Left": 0.1,
                            "Top": 0.2
                        }
                    }
                },
                {
                    "BlockType": "LINE",
                    "Confidence": 97.89,
                    "Text": "Registration Number: 202501001234",
                    "Geometry": {
                        "BoundingBox": {
                            "Width": 0.6,
                            "Height": 0.04,
                            "Left": 0.1,
                            "Top": 0.25
                        }
                    }
                }
            ]
        }
    
    def test_document_upload_with_valid_token(self):
        """Test document upload with valid token and OCR processing"""
        # First create a customer token via Zapier webhook
        webhook_test = TestZapierWebhook()
        webhook_test.setUp()
        token = webhook_test.test_zapier_webhook_valid_payload()
        
        # Create test PDF
        pdf_content = create_test_pdf()
        files = {'document': ('test_company_registration.pdf', pdf_content, 'application/pdf')}
        
        # Upload document
        response = requests.post(
            f"{self.base_url}/upload-file-async/{token}",
            files=files
        )
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data.get('success'))
        self.assertIsNotNone(data.get('documentId'))
        
        print(f"✅ Document upload test passed: {data.get('message')}")
        print(f"Document ID: {data.get('documentId')}")
        print(f"OCR Status: {data.get('ocr_status')}")
        
        # Wait for OCR processing if it's async
        if data.get('ocr_status') == 'processing':
            time.sleep(5)
            print("Waiting for OCR processing...")
        
        return data.get('documentId')
    
    def test_document_upload_invalid_token(self):
        """Test document upload with invalid token"""
        invalid_token = "invalid_token_123"
        pdf_content = create_test_pdf()
        files = {'document': ('test_company_registration.pdf', pdf_content, 'application/pdf')}
        
        response = requests.post(
            f"{self.base_url}/upload-file-async/{invalid_token}",
            files=files
        )
        
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertFalse(data.get('success'))
        self.assertIn('Invalid or expired token', data.get('error', ''))
        
        print(f"✅ Invalid token test passed: {data.get('error')}")
    
    def test_document_upload_no_file(self):
        """Test document upload endpoint with no file"""
        # First create a customer token
        webhook_test = TestZapierWebhook()
        webhook_test.setUp()
        token = webhook_test.test_zapier_webhook_valid_payload()
        
        # Try to upload without file
        response = requests.post(
            f"{self.base_url}/upload-file-async/{token}"
        )
        
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertFalse(data.get('success'))
        self.assertIn('No file provided', data.get('error', ''))
        
        print(f"✅ No file test passed: {data.get('error')}")


class TestSystemIntegration(unittest.TestCase):
    """Integration tests for the complete workflow"""
    
    def test_complete_workflow(self):
        """Test the complete workflow from Zapier webhook to document upload"""
        print("\n🔄 Testing complete workflow...")
        
        # Step 1: Process Zapier webhook
        zapier_test = TestZapierWebhook()
        zapier_test.setUp()
        token = zapier_test.test_zapier_webhook_valid_payload()
        
        # Step 2: Upload document
        ocr_test = TestOCRProcessing()
        ocr_test.setUp()
        document_id = ocr_test.test_document_upload_with_valid_token()
        
        # Step 3: Verify the complete process
        self.assertIsNotNone(token)
        self.assertIsNotNone(document_id)
        
        print("\n✅ Complete workflow test passed!")
        print(f"Customer token: {token}")
        print(f"Document ID: {document_id}")


if __name__ == "__main__":
    # Run specific tests or all tests
    import sys
    
    if len(sys.argv) > 1:
        test_type = sys.argv[1]
        if test_type == "zapier":
            unittest.main(argv=[''], defaultTest='TestZapierWebhook', exit=False)
        elif test_type == "ocr":
            unittest.main(argv=[''], defaultTest='TestOCRProcessing', exit=False)
        elif test_type == "workflow":
            unittest.main(argv=[''], defaultTest='TestSystemIntegration', exit=False)
        else:
            print("Available test types: zapier, ocr, workflow")
    else:
        # Run all tests
        unittest.main(argv=[''], exit=False)
        
        print("\n" + "="*50)
        print("TEST SUMMARY")
        print("="*50)
        print("✅ All tests completed!")
        print("\nTo run specific test suites:")
        print("  python test_document.py zapier    # Test Zapier webhook only")
        print("  python test_document.py ocr       # Test OCR processing only")
        print("  python test_document.py workflow  # Test complete workflow")