# Backup created on 2025-07-16 - Companies table schema fixed and tested successfully
# Test passed with payload: K mohan 1829, VKK mohan 1829, kalyanamo@gmail.com, +6012365086
# Customer record ID: 3f3fe1d3-e0ea-42e4-a60d-5a044274630d

from flask import Flask, request, jsonify, render_template_string, render_template
import os
from dotenv import load_dotenv
import boto3
from supabase import create_client, Client
import base64
import json
from datetime import datetime
import secrets
import string
from werkzeug.utils import secure_filename
import requests
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
import threading
import io
try:
    from PyPDF2 import PdfReader, PdfWriter
    PDF_CONVERSION_AVAILABLE = True
except ImportError:
    PDF_CONVERSION_AVAILABLE = False
    print("PyPDF2 not available - PDF conversion disabled")

# Load environment variables from .env file
load_dotenv('.env', override=True)

print("=== DEBUG INFO ===")
print(f"AWS_ACCESS_KEY_ID: {os.getenv('AWS_ACCESS_KEY_ID')}")
print(f"AWS_SECRET_ACCESS_KEY: {'*' * len(os.getenv('AWS_SECRET_ACCESS_KEY', '')) if os.getenv('AWS_SECRET_ACCESS_KEY') else 'NOT FOUND'}")
print(f"AWS_S3_BUCKET: {os.getenv('AWS_S3_BUCKET')}")
print(f"AWS_REGION: {os.getenv('AWS_REGION')}")
print("==================")

app = Flask(__name__)

# ClickUp Configuration (optional - only for adding comments to existing tasks)
CLICKUP_API_TOKEN = os.getenv('CLICKUP_API_TOKEN')

# AWS S3 Configuration
try:
    s3_client = boto3.client(
        's3',
        aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
        aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
        region_name=os.getenv('AWS_REGION', 'us-east-1')
    )
    print("S3 client created successfully!")
except Exception as e:
    print(f"AWS S3 setup warning: {e}")
    s3_client = None

# Supabase Configuration
try:
    supabase_url = os.getenv('SUPABASE_URL')
    supabase_key = os.getenv('SUPABASE_ANON_KEY')
    if supabase_url and supabase_key and 'your_' not in supabase_url:
        supabase = create_client(supabase_url, supabase_key)
        print("Supabase client created successfully!")
    else:
        supabase = None
except Exception as e:
    print(f"Supabase setup warning: {e}")
    supabase = None

# SendGrid Configuration
try:
    sendgrid_api_key = os.getenv('SENDGRID_API_KEY')
    if sendgrid_api_key and 'your_' not in sendgrid_api_key:
        sg = SendGridAPIClient(api_key=sendgrid_api_key)
        print("SendGrid client created successfully!")
    else:
        sg = None
        print("SendGrid API key not configured")
except Exception as e:
    print(f"SendGrid setup warning: {e}")
    sg = None

# UPLOAD HELPER FUNCTIONS (after s3_client and supabase are defined)

# Helper function to generate customer token
def generate_customer_token(task_id, customer_email):
    data = {
        'taskId': task_id,
        'email': customer_email,
        'timestamp': datetime.now().isoformat()
    }
    return base64.b64encode(json.dumps(data).encode()).decode()

# Decode customer token
def decode_customer_token(token):
    try:
        decoded = base64.b64decode(token).decode()
        return json.loads(decoded)
    except Exception as e:
        raise ValueError('Invalid token')

# Upload to S3 function
def upload_to_s3(file_content, customer_id, filename):
    key = f"documents/customer-{customer_id}/{filename}"
    
    try:
        s3_client.put_object(
            Bucket=os.getenv('AWS_S3_BUCKET'),
            Key=key,
            Body=file_content,
            ContentType='application/pdf',
            ServerSideEncryption='AES256'
        )
        return {
            'success': True,
            'key': key,
            'bucket': os.getenv('AWS_S3_BUCKET')
        }
    except Exception as e:
        print(f'S3 Upload Error: {e}')
        raise e

# Save document metadata to database
def save_document_metadata(customer_data, s3_data, file_info):
    try:
        data = {
            'customer_token': customer_data['originalToken'],
            'clickup_task_id': customer_data['taskId'],
            'customer_email': customer_data['email'],
            's3_key': s3_data['key'],
            'filename': file_info['filename'],
            'file_size': file_info['size']
        }
        
        response = supabase.table('documents').insert(data).execute()
        return response.data[0] if response.data else None
    except Exception as e:
        print(f'Database save error: {e}')
        raise e

def update_company_kyb_status(clickup_task_id, status):
    """Update kyb_status in Companies table and notify ClickUp"""
    try:
        if not supabase:
            print("Warning: Supabase not configured, skipping status update")
            return None
        
        response = supabase.table('companies').update({
            'kyb_status': status
        }).eq('clickup_task_id', clickup_task_id).execute()
        
        print(f"Updated company kyb_status to {status} for task {clickup_task_id}")
        
        # Notify ClickUp of KYB status change
        try:
            from services.clickup_service import update_clickup_task_status
            
            # Get additional info for context
            additional_info = {}
            if response.data and len(response.data) > 0:
                company_data = response.data[0]
                additional_info = {
                    'customer_email': company_data.get('email'),
                    'company_name': company_data.get('company_name')
                }
            
            clickup_result = update_clickup_task_status(clickup_task_id, 'kyb_status', status, additional_info)
            
            if clickup_result.get('success'):
                print(f"✅ ClickUp task {clickup_task_id} updated with KYB status: {status}")
            else:
                print(f"⚠️ ClickUp KYB update failed: {clickup_result.get('error')}")
                
        except Exception as clickup_error:
            print(f"⚠️ ClickUp KYB notification failed (non-critical): {clickup_error}")
        
        return response.data[0] if response.data else None
    except Exception as e:
        print(f'Company status update error: {e}')
        return None

# SendGrid email functions
def send_upload_email(customer_email, customer_name, upload_link, company_name=None):
    """Send upload link email to customer via SendGrid dynamic template"""
    try:
        if not sg:
            return {'success': False, 'error': 'SendGrid not configured'}
        
        # Use dynamic template with template data
        from_email_address = os.getenv('FROM_EMAIL')
        from_name = os.getenv('FROM_NAME', 'Swipey Team')  # Default fallback
        
        message = Mail(
            from_email=(from_email_address, from_name),  # (email, name) tuple
            to_emails=customer_email
        )
        
        # Set the dynamic template ID
        message.template_id = 'd-6d0f3e46d206423a9b52508631eceeb7'
        
        # Set dynamic template data
        message.dynamic_template_data = {
            'customer_name': customer_name,
            'upload_link': upload_link,
            'Company_name': company_name or 'your company'  # Add Company_name for template
        }
        
        response = sg.send(message)
        
        return {
            'success': True,
            'status_code': response.status_code,
            'message': 'Email sent successfully'
        }
        
    except Exception as e:
        print(f"Email sending error: {e}")
        return {
            'success': False,
            'error': str(e)
        }

# ZAPIER WEBHOOK FUNCTIONS

def update_clickup_with_upload_link(task_id, upload_link, customer_data):
    """Add upload link to existing ClickUp task (optional)"""
    try:
        if not CLICKUP_API_TOKEN:
            print("ClickUp API token not configured, skipping task update")
            return {'success': False, 'reason': 'No API token'}
            
        headers = {
            'Authorization': CLICKUP_API_TOKEN,
            'Content-Type': 'application/json'
        }
        
        # Add comment with upload link
        comment_data = {
            'comment_text': f"""
🔗 **Upload Link Generated**

Customer: {customer_data['customer_name']} ({customer_data['customer_email']})
Company: {customer_data['company_name']}

**Secure Upload Link:** {upload_link}

**Next Steps:**
1. Upload link sent to customer via email
2. Waiting for customer to upload KYB documents
3. OCR processing and validation
4. Manual review and approval

*This link has been automatically generated and sent to the customer.*
            """,
            'notify_all': False  # Don't spam everyone
        }
        
        # Add comment to task
        url = f"https://api.clickup.com/api/v2/task/{task_id}/comment"
        response = requests.post(url, headers=headers, json=comment_data, timeout=30)
        
        if response.status_code == 200:
            print(f"Successfully added upload link to ClickUp task {task_id}")
            return {'success': True}
        else:
            print(f"Failed to update ClickUp task: {response.status_code} - {response.text}")
            return {'success': False, 'error': response.text}
            
    except Exception as e:
        print(f"ClickUp task update error: {e}")
        return {'success': False, 'error': str(e)}

def store_customer_info(customer_data, task_id, token, upload_link):
    """Store customer information in database for tracking"""
    try:
        if not supabase:
            print("Warning: Supabase not configured, skipping customer storage")
            return None
            
        # Create companies table record matching the schema
        company_record = {
            'email': customer_data['customer_email'],
            'customer_name': customer_data['customer_name'],
            'customer_first_name': customer_data.get('customer_first_name'),
            'phone': customer_data.get('phone'),
            'clickup_task_id': task_id,
            'company_name': customer_data['company_name'],
            'typeform_submission_id': customer_data.get('typeform_response_id'),
            'kyb_status': 'pending_documents',
            'kyb_failure_reason': None,
            'first_upload_at': None,
            'kyb_completed_at': None
        }
        
        print(f"Inserting company record: {company_record}")
        response = supabase.table('companies').insert(company_record).execute()
        print(f"Supabase response: {response}")
        return response.data[0] if response.data else None
        
    except Exception as e:
        print(f"Customer storage error: {e}")
        return None

# OCR Processing Functions
def process_document_ocr(s3_key, document_id):
    """Process document with AWS Textract OCR"""
    try:
        print(f"=== OCR PROCESSING START ===")
        print(f"Document ID: {document_id}")
        print(f"S3 Key: {s3_key}")
        print(f"S3 Bucket: {os.getenv('AWS_S3_BUCKET')}")
        print(f"AWS Region: {os.getenv('AWS_REGION')}")
        
        # Call Textract
        textract_client = boto3.client(
            'textract',
            aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
            aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
            region_name=os.getenv('AWS_REGION', 'ap-south-1')
        )
        
        print("Textract client created successfully")
        print("Calling Textract analyze_document...")
        
        # Start document analysis
        response = textract_client.analyze_document(
            Document={
                'S3Object': {
                    'Bucket': os.getenv('AWS_S3_BUCKET'),
                    'Name': s3_key
                }
            },
            FeatureTypes=['FORMS', 'TABLES']
        )
        
        print(f"Textract response received! Found {len(response['Blocks'])} blocks")
        
        # Extract key-value pairs and text
        from services.ocr_service import OCRService
        ocr_service = OCRService(supabase)
        extracted_data = ocr_service._extract_key_information(response)
        
        print(f"Extracted data: {extracted_data}")
        
        # Update database with OCR results
        print("Updating database with OCR results...")
        update_result = supabase.table('documents').update({
            'ocr_status': 'completed',
            'ocr_completed_at': datetime.now().isoformat(),
            'extracted_company_name': extracted_data.get('company_name'),
            'extracted_registration_number': extracted_data.get('registration_number'),
            'extracted_incorporation_date': extracted_data.get('incorporation_date'),
            'extracted_company_type': extracted_data.get('company_type'),
            'extracted_business_address': extracted_data.get('business_address'),
            'extracted_business_phone': extracted_data.get('business_phone'),
            'extracted_directors': extracted_data.get('directors', [])
        }).eq('id', document_id).execute()
        
        print("Database updated successfully!")
        print(f"=== OCR PROCESSING COMPLETE ===")
        
        return {
            'success': True,
            'extracted_data': extracted_data,
            'ocr_status': 'completed'
        }
        
    except Exception as e:
        print(f"=== OCR PROCESSING ERROR ===")
        print(f"Error: {e}")
        print(f"Error type: {type(e)}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        
        # Update database with error status
        try:
            supabase.table('documents').update({
                'ocr_status': 'failed',
                'ocr_completed_at': datetime.now().isoformat()
            }).eq('id', document_id).execute()
            print("Database updated with failure status")
        except Exception as db_error:
            print(f"Failed to update database: {db_error}")
        
        return {
            'success': False,
            'error': str(e),
            'ocr_status': 'failed'
        }

# Removed old extract_key_information and get_text_from_blocks functions - now using OCR service

# Async OCR processing function
# Asynchronous Textract implementation (like the console uses)
def start_async_textract_job(s3_key):
    """Start asynchronous Textract job (like console does)"""
    try:
        textract_client = boto3.client(
            'textract',
            aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
            aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
            region_name='ap-south-1'
        )
        
        print(f"Starting ASYNC Textract job for: {s3_key}")
        
        # Start document analysis job (async)
        response = textract_client.start_document_analysis(
            DocumentLocation={
                'S3Object': {
                    'Bucket': os.getenv('AWS_S3_BUCKET'),
                    'Name': s3_key
                }
            },
            FeatureTypes=['FORMS', 'TABLES']
        )
        
        job_id = response['JobId']
        print(f"Async job started! Job ID: {job_id}")
        
        return {
            'success': True,
            'job_id': job_id,
            'status': 'IN_PROGRESS'
        }
        
    except Exception as e:
        print(f"Failed to start async job: {e}")
        return {
            'success': False,
            'error': str(e)
        }

def check_textract_job_status(job_id):
    """Check status of async Textract job"""
    try:
        textract_client = boto3.client(
            'textract',
            aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
            aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
            region_name='ap-south-1'
        )
        
        print(f"Checking job status: {job_id}")
        
        response = textract_client.get_document_analysis(JobId=job_id)
        
        job_status = response['JobStatus']
        print(f"Job status: {job_status}")
        
        if job_status == 'SUCCEEDED':
            # Job completed successfully
            from services.ocr_service import OCRService
            ocr_service = OCRService(supabase)
            extracted_data = ocr_service._extract_key_information(response)
            
            return {
                'success': True,
                'status': 'COMPLETED',
                'extracted_data': extracted_data,
                'total_blocks': len(response.get('Blocks', []))
            }
            
        elif job_status == 'IN_PROGRESS':
            return {
                'success': True,
                'status': 'IN_PROGRESS',
                'message': 'Job still processing...'
            }
            
        elif job_status == 'FAILED':
            return {
                'success': False,
                'status': 'FAILED',
                'error': response.get('StatusMessage', 'Job failed')
            }
            
        else:
            return {
                'success': True,
                'status': job_status,
                'message': f'Unexpected status: {job_status}'
            }
        
    except Exception as e:
        print(f"Error checking job status: {e}")
        return {
            'success': False,
            'error': str(e)
        }

# Async OCR processing function (NEW)
def process_document_ocr_async(s3_key, document_id):
    """Process document with async Textract (like console)"""
    try:
        print(f"=== ASYNC OCR PROCESSING START ===")
        
        # Step 1: Start async job
        job_result = start_async_textract_job(s3_key)
        
        if not job_result['success']:
            raise Exception(f"Failed to start job: {job_result['error']}")
        
        job_id = job_result['job_id']
        
        # Step 2: Update database with job ID and pending status
        supabase.table('documents').update({
            'ocr_status': 'processing',
            'textract_job_id': job_id,
            'ocr_started_at': datetime.now().isoformat()
        }).eq('id', document_id).execute()
        
        print(f"Database updated with job ID: {job_id}")
        
        # Step 3: Poll for completion (with timeout)
        max_attempts = 30  # 30 attempts = 5 minutes max
        attempt = 0
        
        while attempt < max_attempts:
            print(f"Polling attempt {attempt + 1}/{max_attempts}")
            
            status_result = check_textract_job_status(job_id)
            
            if not status_result['success']:
                raise Exception(f"Error checking status: {status_result['error']}")
            
            if status_result['status'] == 'COMPLETED':
                # Job completed successfully!
                extracted_data = status_result['extracted_data']
                
                # Update database with results
                supabase.table('documents').update({
                    'ocr_status': 'completed',
                    'ocr_completed_at': datetime.now().isoformat(),
                    'extracted_company_name': extracted_data.get('company_name'),
                    'extracted_registration_number': extracted_data.get('registration_number'),
                    'extracted_incorporation_date': extracted_data.get('incorporation_date'),
                    'extracted_company_type': extracted_data.get('company_type'),
                    'extracted_business_address': extracted_data.get('business_address'),
                    'extracted_business_phone': extracted_data.get('business_phone'),
                    'extracted_directors': extracted_data.get('directors', [])
                }).eq('id', document_id).execute()
                
                print(f"ASYNC OCR COMPLETED! Extracted: {extracted_data}")
                
                return {
                    'success': True,
                    'extracted_data': extracted_data,
                    'ocr_status': 'completed',
                    'job_id': job_id,
                    'method': 'async_api'
                }
                
            elif status_result['status'] == 'FAILED':
                raise Exception(f"Textract job failed: {status_result['error']}")
            
            elif status_result['status'] == 'IN_PROGRESS':
                # Wait 10 seconds before next check (like console timing)
                import time
                time.sleep(10)
                attempt += 1
            
            else:
                print(f"Unexpected status: {status_result['status']}")
                time.sleep(5)
                attempt += 1
        
        # Timeout reached
        raise Exception(f"Textract job timed out after {max_attempts * 10} seconds")
        
    except Exception as e:
        print(f"=== ASYNC OCR ERROR ===")
        print(f"Error: {e}")
        
        # Update database with error
        supabase.table('documents').update({
            'ocr_status': 'failed',
            'ocr_completed_at': datetime.now().isoformat()
        }).eq('id', document_id).execute()
        
        return {
            'success': False,
            'error': str(e),
            'ocr_status': 'failed'
        }

def process_ocr_async(s3_key, document_id):
    """Process OCR in background thread (OLD - for compatibility)"""
    def run_ocr():
        try:
            result = process_document_ocr(s3_key, document_id)
            print(f"Async OCR completed for document {document_id}: {result}")
        except Exception as e:
            print(f"Async OCR failed for document {document_id}: {e}")
    
    thread = threading.Thread(target=run_ocr)
    thread.daemon = True
    thread.start()
    return {"message": "OCR processing started in background"}

# PDF Conversion Functions
def convert_pdf_for_textract(pdf_content):
    """Convert PDF to be compatible with AWS Textract"""
    try:
        if not PDF_CONVERSION_AVAILABLE:
            return {
                'success': True,
                'content': pdf_content,
                'converted': False,
                'message': 'PyPDF2 not available - using original PDF'
            }
        
        print("🔄 Starting PDF conversion for Textract compatibility...")
        
        # Read the original PDF
        pdf_reader = PdfReader(io.BytesIO(pdf_content))
        pdf_writer = PdfWriter()
        
        # Check PDF version
        original_version = getattr(pdf_reader, 'pdf_header', 'Unknown')
        print(f"📖 Original PDF version: {original_version}")
        
        # Copy all pages to new PDF
        page_count = len(pdf_reader.pages)
        print(f"Processing {page_count} pages...")
        
        for page_num in range(page_count):
            page = pdf_reader.pages[page_num]
            pdf_writer.add_page(page)
        
        # Write to new PDF with PDF 1.7 compatibility
        output_buffer = io.BytesIO()
        pdf_writer.write(output_buffer)
        converted_content = output_buffer.getvalue()
        
        print(f"PDF conversion completed:")
        print(f"   - Original size: {len(pdf_content)} bytes")
        print(f"   - Converted size: {len(converted_content)} bytes")
        print(f"   - Size change: {len(converted_content) - len(pdf_content)} bytes")
        
        return {
            'success': True,
            'content': converted_content,
            'converted': True,
            'original_version': original_version,
            'final_version': 'PDF-1.7',
            'size_change': len(converted_content) - len(pdf_content),
            'page_count': page_count
        }
        
    except Exception as e:
        print(f"PDF conversion failed: {e}")
        print("Using original PDF content...")
        return {
            'success': True,
            'content': pdf_content,
            'converted': False,
            'error': str(e),
            'message': 'Conversion failed - using original PDF'
        }

# ROUTES

@app.route('/')
def home():
    return jsonify({
        "message": "Customer Onboarding Automation Server Running!",
        "timestamp": datetime.now().isoformat(),
        "status": "healthy",
        "python_version": "Flask app ready"
    })

@app.route('/health')
def health():
    return jsonify({
        "status": "healthy",
        "services": {
            "s3": "configured" if s3_client else "not configured",
            "database": "configured" if supabase else "not configured",
            "sendgrid": "configured" if sg else "not configured"
        }
    })

@app.route('/test-s3')
def test_s3():
    if not s3_client:
        return jsonify({"error": "S3 not configured"}), 500
    
    try:
        # Test S3 connection
        bucket_name = os.getenv('AWS_S3_BUCKET')
        if not bucket_name:
            return jsonify({"error": "S3 bucket name not configured"}), 500
            
        s3_client.head_bucket(Bucket=bucket_name)
        return jsonify({"message": "S3 connection successful!", "bucket": bucket_name})
    except Exception as e:
        return jsonify({"error": f"S3 connection failed: {str(e)}"}), 500

@app.route('/test-db')
def test_db():
    if not supabase:
        return jsonify({"error": "Database not configured"}), 500
    
    try:
        # Simple test - just try to select from the table
        response = supabase.table('documents').select('id').limit(1).execute()
        return jsonify({
            "message": "Database connection successful!", 
            "table_accessible": True,
            "response": "connected"
        })
    except Exception as e:
        return jsonify({"error": f"Database connection failed: {str(e)}"}), 500

@app.route('/test-sendgrid')
def test_sendgrid():
    if not sg:
        return jsonify({"error": "SendGrid not configured"}), 500
    
    try:
        # Test SendGrid connection by sending a test email
        from_email_address = os.getenv('FROM_EMAIL')
        from_name = os.getenv('FROM_NAME', 'Swipey Team')
        
        message = Mail(
            from_email=(from_email_address, from_name),
            to_emails='kalyanamo@gmail.com',
            subject='SendGrid Test Email',
            html_content='<p>This is a test email from your KYB automation system.</p>'
        )
        
        response = sg.send(message)
        return jsonify({
            "message": "SendGrid test email sent successfully!",
            "status_code": response.status_code
        })
    except Exception as e:
        return jsonify({"error": f"SendGrid test failed: {str(e)}"}), 500

# Test endpoint for ClickUp API
@app.route('/test-clickup')
def test_clickup():
    """Test ClickUp API connection"""
    try:
        if not CLICKUP_API_TOKEN:
            return jsonify({
                'status': 'error',
                'message': 'ClickUp API token not configured'
            }), 400
            
        headers = {
            'Authorization': CLICKUP_API_TOKEN,
            'Content-Type': 'application/json'
        }
        
        # Test with team info
        url = f"https://api.clickup.com/api/v2/team"
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            teams = response.json()
            return jsonify({
                'status': 'success',
                'message': 'ClickUp API connection successful',
                'teams': teams.get('teams', [])
            })
        else:
            return jsonify({
                'status': 'error',
                'message': f'ClickUp API error: {response.status_code}',
                'details': response.text
            }), 500
            
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': 'ClickUp connection failed',
            'error': str(e)
        }), 500

# TEST ENDPOINT 1: Mimic typeform submission and update Supabase
@app.route('/test-typeform-submission', methods=['POST'])
def test_typeform_submission():
    """Test endpoint to mimic typeform submission with KMT_150725_10pm and kalyanamo@gmail.com"""
    try:
        # Use test data or override with request data
        test_data = {
            'customer_name': 'Test Customer',
            'customer_email': 'kalyanamo@gmail.com',
            'company_name': 'KMT_150725_10pm',
            'phone': '+601234567890',
            'business_type': 'Technology',
            'typeform_response_id': 'test_response_123',
            'submission_timestamp': datetime.now().isoformat(),
            'clickup_task_id': 'TEST_TASK_001'
        }
        
        # Override with any provided data
        if request.json:
            test_data.update(request.json)
        
        # Generate upload link
        token = generate_customer_token(test_data['clickup_task_id'], test_data['customer_email'])
        upload_link = f"{request.host_url}upload-async/{token}"
        
        # Store in database
        customer_record = store_customer_info(test_data, test_data['clickup_task_id'], token, upload_link)
        
        return jsonify({
            'success': True,
            'message': 'Typeform submission test completed',
            'customer_data': test_data,
            'upload_link': upload_link,
            'customer_record_id': customer_record.get('id') if customer_record else None,
            'token': token
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# TEST ENDPOINT 2: Generate and send email with upload link
@app.route('/test-send-email', methods=['POST'])
def test_send_email():
    """Test endpoint to send email with upload link to kalyanamo@gmail.com"""
    try:
        # Generate test upload link
        task_id = 'TEST_TASK_EMAIL_001'
        customer_email = 'kalyanamo@gmail.com'
        customer_name = 'Test Customer'
        
        token = generate_customer_token(task_id, customer_email)
        upload_link = f"{request.host_url}upload-async/{token}"
        
        # Send email
        email_result = send_upload_email(customer_email, customer_name, upload_link, "Test Company")
        
        return jsonify({
            'success': True,
            'message': 'Email test completed',
            'email_result': email_result,
            'upload_link': upload_link,
            'customer_email': customer_email
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# TEST ENDPOINT 3: Test PDF upload and S3 storage (already exists in upload routes)
@app.route('/test-upload-flow')
def test_upload_flow():
    """Test endpoint to generate upload link for testing PDF upload"""
    try:
        task_id = 'TEST_UPLOAD_001'
        customer_email = 'kalyanamo@gmail.com'
        
        token = generate_customer_token(task_id, customer_email)
        upload_link = f"{request.host_url}upload-async/{token}"
        
        return jsonify({
            'success': True,
            'message': 'Upload flow test ready',
            'upload_link': upload_link,
            'token': token,
            'instructions': 'Visit the upload_link to test PDF upload functionality'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# TEST ENDPOINT 4: Test async Textract processing (NEW VERSION)
@app.route('/test-async-textract/<token>')
def test_async_textract(token):
    """Test async Textract processing on uploaded document"""
    try:
        # Get the document
        response = supabase.table('documents').select('*').eq('customer_token', token).order('upload_timestamp', desc=True).limit(1).execute()
        
        if not response.data:
            return jsonify({"error": "No documents found"})
        
        document = response.data[0]
        s3_key = document['s3_key']
        document_id = document['id']
        
        print(f"Testing ASYNC Textract on: {s3_key}")
        
        # Process with async method
        result = process_document_ocr_async(s3_key, document_id, supabase)
        
        return jsonify({
            "status": "async_test_complete",
            "result": result,
            "message": "Async processing completed (matching console behavior)"
        })
        
    except Exception as e:
        return jsonify({
            "error": "Async test failed",
            "details": str(e)
        })

# TEST ENDPOINT 4: Test async Textract processing (OLD VERSION - for compatibility)
@app.route('/test-async-ocr/<token>')
def test_async_ocr(token):
    """Test endpoint to run async OCR on uploaded document"""
    try:
        # Get the last uploaded document for this token
        response = supabase.table('documents').select('*').eq('customer_token', token).order('upload_timestamp', desc=True).limit(1).execute()
        
        if not response.data:
            return jsonify({"error": "No documents found for this token"})
        
        document = response.data[0]
        s3_key = document['s3_key']
        document_id = document['id']
        
        # Start async OCR processing
        async_result = process_ocr_async(s3_key, document_id)
        
        return jsonify({
            "success": True,
            "message": "Async OCR processing started",
            "document_id": document_id,
            "s3_key": s3_key,
            "async_result": async_result
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

# Database helper route
@app.route('/add-job-id-column')
def add_job_id_column():
    """Add textract_job_id column to documents table"""
    try:
        # This is just for reference - you'll need to run this SQL in Supabase
        sql_command = """
        ALTER TABLE documents 
        ADD COLUMN IF NOT EXISTS textract_job_id TEXT,
        ADD COLUMN IF NOT EXISTS ocr_started_at TIMESTAMP;
        """
        
        return jsonify({
            "message": "Run this SQL in Supabase SQL Editor:",
            "sql": sql_command,
            "note": "This adds columns to track async Textract jobs"
        })
        
    except Exception as e:
        return jsonify({
            "error": str(e)
        })

# Check OCR results
@app.route('/check-ocr-results/<token>')
def check_ocr_results(token):
    """Check OCR processing results for a token"""
    try:
        # Get documents for this token
        response = supabase.table('documents').select('*').eq('customer_token', token).execute()
        
        if not response.data:
            return jsonify({"error": "No documents found for this token"})
        
        documents = response.data
        results = []
        
        for doc in documents:
            results.append({
                'document_id': doc['id'],
                'filename': doc['filename'],
                'ocr_status': doc.get('ocr_status', 'pending'),
                'ocr_completed_at': doc.get('ocr_completed_at'),
                'extracted_data': {
                    'name': doc.get('extracted_name'),
                    'email': doc.get('extracted_email'),
                    'company_name': doc.get('extracted_company_name'),
                    'registration_number': doc.get('extracted_registration_number')
                }
            })
        
        return jsonify({
            "success": True,
            "documents": results,
            "total_documents": len(results)
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

# ZAPIER WEBHOOK ROUTES

# Zapier webhook endpoint - receives Typeform submissions
@app.route('/zapier-webhook', methods=['POST'])
def zapier_webhook():
    """
    Receives customer data from Zapier when Typeform is submitted
    Expected payload from Zapier (with ClickUp task already created):
    {
        "customer_name": "John Doe",
        "customer_email": "john@company.com", 
        "company_name": "ABC Corp",
        "phone": "+1234567890",
        "business_type": "Technology",
        "typeform_response_id": "abc123",
        "submission_timestamp": "2025-01-15T10:30:00Z",
        "clickup_task_id": "task_id_from_zapier",
        "clickup_task_url": "https://app.clickup.com/t/task_id"
    }
    """
    try:
        # Get data from Zapier
        data = request.get_json()
        print(f"Received Zapier webhook data: {data}")
        
        # Validate required fields
        required_fields = ['customer_name', 'customer_email', 'company_name', 'clickup_task_id']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'error': f'Missing required field: {field}'}), 400
        
        # Get ClickUp task info from Zapier (already created)
        task_id = data['clickup_task_id']
        task_url = data.get('clickup_task_url', f"https://app.clickup.com/t/{task_id}")
        
        # Generate upload link
        token = generate_customer_token(task_id, data['customer_email'])
        upload_link = f"{request.host_url}upload-async/{token}"
        
        # Store customer info in database for tracking
        customer_record = store_customer_info(data, task_id, token, upload_link)
        
        # Notify ClickUp of initial KYB status (pending_documents) - only if not already set to a more advanced status
        update_company_kyb_status(task_id, 'pending_documents')
        
        # Send email with upload link
        email_result = send_upload_email(data['customer_email'], data['customer_name'], upload_link, data['company_name'])
        
        # Optionally update ClickUp task with upload link (if you want)
        update_clickup_with_upload_link(task_id, upload_link, data)
        
        # Send response back to Zapier with all the info
        response_data = {
            'success': True,
            'task_id': task_id,
            'task_url': task_url,
            'upload_link': upload_link,
            'customer_token': token,
            'customer_record_id': customer_record.get('id') if customer_record else None,
            'email_sent': email_result.get('success', False),
            'message': f'Upload link generated and emailed to {data["customer_name"]} - {data["company_name"]}'
        }
        
        print(f"Zapier webhook processed successfully: {response_data}")
        return jsonify(response_data)
        
    except Exception as e:
        print(f"Zapier webhook error: {e}")
        import traceback
        print(traceback.format_exc())
        return jsonify({'error': 'Webhook processing failed', 'details': str(e)}), 500

# Debug endpoint for Supabase connection
@app.route('/debug-supabase', methods=['GET'])
def debug_supabase():
    """Debug endpoint to test Supabase connection and table insertion"""
    try:
        if not supabase:
            return jsonify({'error': 'Supabase not configured'}), 500
        
        # Test simple insert with basic fields matching schema
        test_record = {
            'email': 'test@example.com',
            'phone': '+1234567890',
            'clickup_task_id': 'test_task_debug',
            'company_name': 'Test Company',
            'typeform_submission_id': None,
            'kyb_status': 'pending_documents',
            'kyb_failure_reason': None,
            'first_upload_at': None,
            'kyb_completed_at': None
        }
        
        print(f"Attempting to insert: {test_record}")
        response = supabase.table('companies').insert(test_record).execute()
        print(f"Supabase response: {response}")
        
        return jsonify({
            'success': True,
            'message': 'Supabase test successful',
            'response': str(response),
            'data': response.data
        })
        
    except Exception as e:
        print(f"Supabase debug error: {e}")
        return jsonify({'error': str(e)}), 500

# Debug endpoint for Zapier testing
@app.route('/zapier-test', methods=['GET', 'POST'])
def zapier_test():
    """Test endpoint for Zapier integration"""
    if request.method == 'GET':
        return jsonify({
            'status': 'ready',
            'message': 'Zapier webhook endpoint is ready',
            'expected_fields': [
                'customer_name',
                'customer_email', 
                'company_name',
                'phone',
                'business_type',
                'typeform_response_id',
                'submission_timestamp',
                'clickup_task_id',
                'clickup_task_url'
            ]
        })
    
    # POST - simulate webhook with sample data
    sample_data = {
        'customer_name': 'John Doe',
        'customer_email': 'john.doe@testcompany.com',
        'company_name': 'Test Company Ltd',
        'phone': '+1234567890',
        'business_type': 'Technology',
        'typeform_response_id': 'test123',
        'submission_timestamp': datetime.now().isoformat(),
        'clickup_task_id': 'test-task-123',
        'clickup_task_url': 'https://app.clickup.com/t/test-task-123'
    }
    
    # Use provided data or sample data
    request_data = request.get_json() or sample_data
    
    # Simulate zapier webhook call
    return zapier_webhook()

# Webhook to update ClickUp when document is uploaded
@app.route('/update-clickup-task', methods=['POST'])
def update_clickup_task():
    """Update ClickUp task when document is uploaded"""
    try:
        data = request.get_json()
        task_id = data.get('task_id')
        customer_email = data.get('customer_email')
        filename = data.get('filename')
        upload_timestamp = data.get('upload_timestamp')
        
        if not task_id:
            return jsonify({'error': 'task_id required'}), 400
        
        # Update task with comment
        headers = {
            'Authorization': CLICKUP_API_TOKEN,
            'Content-Type': 'application/json'
        }
        
        comment_data = {
            'comment_text': f"""
🎉 **Document Upload Complete**

Customer: {customer_email}
File: {filename}
Uploaded: {upload_timestamp}

Document successfully uploaded and stored in S3
OCR processing initiated
Ready for manual review

Next steps:
1. Review OCR results
2. Validate customer information
3. Approve or request additional documents
            """,
            'notify_all': True
        }
        
        # Add comment to task
        url = f"https://api.clickup.com/api/v2/task/{task_id}/comment"
        response = requests.post(url, headers=headers, json=comment_data, timeout=30)
        
        # Update task status
        status_data = {'status': 'in progress'}  # Adjust based on your statuses
        status_url = f"https://api.clickup.com/api/v2/task/{task_id}"
        status_response = requests.put(status_url, headers=headers, json=status_data, timeout=30)
        
        return jsonify({
            'success': True,
            'comment_added': response.status_code == 200,
            'status_updated': status_response.status_code == 200
        })
        
    except Exception as e:
        print(f"ClickUp update error: {e}")
        return jsonify({'error': str(e)}), 500

# UPLOAD ROUTES

# Generate upload link endpoint (for testing)
@app.route('/generate-link', methods=['POST'])
def generate_link():
    data = request.get_json()
    task_id = data.get('taskId')
    customer_email = data.get('customerEmail')
    
    if not task_id or not customer_email:
        return jsonify({'error': 'Task ID and email are required'}), 400
    
    token = generate_customer_token(task_id, customer_email)
    upload_link = f"{request.host_url}upload-async/{token}"
    
    return jsonify({
        'uploadLink': upload_link,
        'token': token,
        'expiresAt': 'Never'
    })

# Upload page route - serve actual HTML page
@app.route('/upload/<token>')
def upload_page(token):
    try:
        customer_data = decode_customer_token(token)
        
        # HTML template for upload page
        html_template = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Upload Your KYB Document</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            max-width: 600px;
            margin: 50px auto;
            padding: 20px;
            background-color: #f5f5f5;
        }
        .container {
            background: white;
            padding: 40px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        .upload-area {
            border: 2px dashed #ccc;
            border-radius: 10px;
            padding: 40px;
            text-align: center;
            margin: 20px 0;
            cursor: pointer;
            transition: all 0.3s ease;
        }
        .upload-area:hover {
            border-color: #007bff;
            background-color: #f8f9fa;
        }
        .upload-area.dragover {
            border-color: #007bff;
            background-color: #e3f2fd;
        }
        .btn {
            background-color: #007bff;
            color: white;
            padding: 12px 30px;
            border: none;
            border-radius: 5px;
            cursor: pointer;
            font-size: 16px;
            margin: 10px 0;
        }
        .btn:hover {
            background-color: #0056b3;
        }
        .btn:disabled {
            background-color: #ccc;
            cursor: not-allowed;
        }
        .message {
            padding: 15px;
            margin: 15px 0;
            border-radius: 5px;
            display: none;
        }
        .success {
            background-color: #d4edda;
            color: #155724;
            border: 1px solid #c3e6cb;
        }
        .error {
            background-color: #f8d7da;
            color: #721c24;
            border: 1px solid #f5c6cb;
        }
        .file-info {
            background-color: #e9ecef;
            padding: 10px;
            border-radius: 5px;
            margin: 10px 0;
            display: none;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>Upload Your KYB Document</h1>
        <p>Hello <strong>{{ customer_email }}</strong>,</p>
        <p>Please upload your completed KYB form to continue with your onboarding process.</p>
        
        <div class="upload-area" id="uploadArea">
            <div>
                <h3>Drop your PDF file here</h3>
                <p>or</p>
                <button type="button" class="btn" onclick="document.getElementById('fileInput').click()">
                    Choose File
                </button>
                <input type="file" id="fileInput" accept=".pdf" style="display: none;">
                <p><small>Maximum file size: 10MB | PDF files only</small></p>
            </div>
        </div>

        <div class="file-info" id="fileInfo"></div>

        <button type="button" class="btn" id="uploadBtn" onclick="uploadFile()" disabled>
            Upload Document
        </button>

        <div class="message" id="message"></div>
    </div>

    <script>
        const uploadArea = document.getElementById('uploadArea');
        const fileInput = document.getElementById('fileInput');
        const uploadBtn = document.getElementById('uploadBtn');
        const fileInfo = document.getElementById('fileInfo');
        const message = document.getElementById('message');

        let selectedFile = null;
        const customerToken = '{{ token }}';

        // File input change handler
        fileInput.addEventListener('change', handleFileSelect);

        // Drag and drop handlers
        uploadArea.addEventListener('dragover', (e) => {
            e.preventDefault();
            uploadArea.classList.add('dragover');
        });

        uploadArea.addEventListener('dragleave', () => {
            uploadArea.classList.remove('dragover');
        });

        uploadArea.addEventListener('drop', (e) => {
            e.preventDefault();
            uploadArea.classList.remove('dragover');
            const files = e.dataTransfer.files;
            if (files.length > 0) {
                handleFile(files[0]);
            }
        });

        function handleFileSelect(e) {
            handleFile(e.target.files[0]);
        }

        function handleFile(file) {
            if (!file) return;

            if (file.type !== 'application/pdf') {
                showMessage('Please select a PDF file only.', 'error');
                return;
            }

            if (file.size > 10 * 1024 * 1024) {
                showMessage('File size must be less than 10MB.', 'error');
                return;
            }

            selectedFile = file;
            fileInfo.innerHTML = `
                <strong>Selected file:</strong> ${file.name}<br>
                <strong>Size:</strong> ${(file.size / 1024 / 1024).toFixed(2)} MB
            `;
            fileInfo.style.display = 'block';
            uploadBtn.disabled = false;
            message.style.display = 'none';
        }

        async function uploadFile() {
            if (!selectedFile || !customerToken) {
                showMessage('No file selected or invalid upload link.', 'error');
                return;
            }

            const formData = new FormData();
            formData.append('document', selectedFile);

            uploadBtn.disabled = true;
            uploadBtn.textContent = 'Uploading...';
            
            try {
                const response = await fetch(`/upload-file-converted/${customerToken}`, {
                    method: 'POST',
                    body: formData
                });

                const result = await response.json();

                if (response.ok) {
                    showMessage('Document uploaded successfully! Your file is being processed.', 'success');
                    
                    // Reset form
                    selectedFile = null;
                    fileInput.value = '';
                    fileInfo.style.display = 'none';
                    uploadBtn.disabled = true;
                    uploadBtn.textContent = 'Upload Document';
                } else {
                    throw new Error(result.error || 'Upload failed');
                }
            } catch (error) {
                showMessage(`Upload failed: ${error.message}`, 'error');
                uploadBtn.disabled = false;
                uploadBtn.textContent = 'Upload Document';
            }
        }

        function showMessage(text, type) {
            message.textContent = text;
            message.className = `message ${type}`;
            message.style.display = 'block';
        }
    </script>
</body>
</html>
        '''
        
        return render_template_string(html_template, 
                                    customer_email=customer_data['email'], 
                                    token=token)
    except Exception as e:
        return jsonify({'error': 'Invalid upload link'}), 400

# Handle actual file upload with PDF conversion
@app.route('/upload-file-converted/<token>', methods=['POST'])
def upload_file_with_conversion(token):
    """Upload file with automatic PDF conversion for Textract compatibility"""
    try:
        print(f"Starting CONVERTED upload for token: {token[:20]}...")
        
        # Decode customer data
        customer_data = decode_customer_token(token)
        customer_data['originalToken'] = token
        
        # File validation (same as before)
        if 'document' not in request.files:
            return jsonify({'error': 'No file uploaded'}), 400
        
        file = request.files['document']
        if file.filename == '' or not file.filename.lower().endswith('.pdf'):
            return jsonify({'error': 'Please select a valid PDF file'}), 400
        
        # Check file size
        file.seek(0, 2)
        file_size = file.tell()
        file.seek(0)
        
        if file_size > 10 * 1024 * 1024:
            return jsonify({'error': 'File size must be less than 10MB'}), 400
        
        print(f"File validated: {file.filename}, Size: {file_size} bytes")
        
        # Read file content
        original_content = file.read()
        
        # PDF conversion
        conversion_result = convert_pdf_for_textract(original_content)
        
        if conversion_result['success']:
            file_content = conversion_result['content']
            conversion_info = {
                'converted': conversion_result['converted'],
                'original_version': conversion_result.get('original_version', 'Unknown'),
                'final_version': conversion_result.get('final_version', 'Unknown'),
                'size_change': conversion_result.get('size_change', 0)
            }
            print(f"Conversion info: {conversion_info}")
        else:
            file_content = original_content
            conversion_info = {'converted': False, 'error': conversion_result.get('error')}
        
        # Generate unique filename
        existing_docs = supabase.table('documents').select('*').eq('customer_token', token).execute()
        document_count = len(existing_docs.data) + 1
        base_filename = f"SSM_{document_count}.pdf"
        
        # Upload to S3
        s3_result = upload_to_s3(file_content, customer_data['taskId'], base_filename)
        print(f"S3 upload successful: {s3_result['key']}")
        
        # Save to database
        file_info = {
            'filename': base_filename,
            'size': len(file_content)
        }
        db_result = save_document_metadata(customer_data, s3_result, file_info)
        print(f"Database record created: {db_result['id']}")
        
        # Wait for S3 consistency
        import time
        time.sleep(2)
        
        # Process with ASYNC OCR (NEW METHOD)
        print(f"Starting ASYNC OCR processing on converted PDF...")
        try:
            ocr_result = process_document_ocr_async(s3_result['key'], db_result['id'], supabase)
            ocr_success = ocr_result.get('success', False)
            extracted_data = ocr_result.get('extracted_data', {})
            print(f"ASYNC OCR completed. Success: {ocr_success}")
        except Exception as ocr_error:
            print(f"ASYNC OCR processing failed: {ocr_error}")
            ocr_success = False
            extracted_data = {}

        return jsonify({
            'success': True,
            'message': 'Document uploaded, converted, and processed successfully',
            'documentId': db_result['id'],
            'filename': file_info['filename'],
            'uploadedAt': db_result['upload_timestamp'],
            'ocr_status': 'completed' if ocr_success else 'failed',
            'conversion_info': conversion_info,
            'extracted_preview': {
                'company_name': extracted_data.get('company_name'),
                'registration_number': extracted_data.get('registration_number'),
                'incorporation_date': extracted_data.get('incorporation_date'),
                'company_type': extracted_data.get('company_type'),
                'business_address': extracted_data.get('business_address'),
                'business_phone': extracted_data.get('business_phone'),
                'directors': extracted_data.get('directors', [])
            },
            'debug_info': {
                's3_key': s3_result['key'],
                'original_size': file_size,
                'final_size': len(file_content)
            }
        })
        
    except Exception as e:
        print(f"Upload with conversion error: {e}")
        import traceback
        print(traceback.format_exc())
        return jsonify({
            'error': 'Upload with conversion failed',
            'details': str(e)
        }), 500

# Handle actual file upload (original)
@app.route('/upload-file/<token>', methods=['POST'])
def upload_file(token):
    try:
        # Decode customer data
        customer_data = decode_customer_token(token)
        customer_data['originalToken'] = token
        
        # Check if file was uploaded
        if 'document' not in request.files:
            return jsonify({'error': 'No file uploaded'}), 400
        
        file = request.files['document']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        # Validate file type
        if not file.filename.lower().endswith('.pdf'):
            return jsonify({'error': 'Only PDF files are allowed'}), 400
        
        # Check file size (10MB limit)
        file.seek(0, 2)  # Seek to end
        file_size = file.tell()
        file.seek(0)  # Reset to beginning
        
        if file_size > 10 * 1024 * 1024:  # 10MB
            return jsonify({'error': 'File size must be less than 10MB'}), 400
        
        # Check if customer already uploaded (get count for filename)
        existing_docs = supabase.table('documents').select('*').eq('customer_token', token).execute()
        document_count = len(existing_docs.data) + 1
        
        # Generate secure filename
        filename = f"SSM_{document_count}.pdf"
        
        # Read file content
        file_content = file.read()
        
        # Upload to S3
        s3_result = upload_to_s3(file_content, customer_data['taskId'], filename)
        
        # Save metadata to database
        file_info = {
            'filename': filename,
            'size': file_size
        }
        db_result = save_document_metadata(customer_data, s3_result, file_info)

        # Update customer status if customers table exists
        try:
            if supabase:
                supabase.table('customers').update({
                    'status': 'documents_uploaded',
                    'documents_uploaded_at': datetime.now().isoformat()
                }).eq('customer_token', token).execute()
        except Exception as e:
            print(f"Warning: Could not update customer status: {e}")

        # Trigger async OCR processing
        if db_result and db_result.get('id'):
            process_ocr_async(s3_result['key'], db_result['id'])

        return jsonify({
            'success': True,
            'message': 'Document uploaded successfully',
            'documentId': db_result['id'] if db_result else None,
            'filename': filename,
            'uploadedAt': db_result['upload_timestamp'] if db_result else None
        })
        
    except Exception as e:
        print(f"Upload error: {e}")
        return jsonify({
            'error': 'Upload failed',
            'details': str(e)
        }), 500

# Check upload status
@app.route('/status/<token>')
def upload_status(token):
    try:
        customer_data = decode_customer_token(token)
        
        # Get documents for this customer
        response = supabase.table('documents').select('*').eq('customer_token', token).execute()
        documents = response.data
        
        return jsonify({
            'customer': {
                'taskId': customer_data['taskId'],
                'email': customer_data['email']
            },
            'documents': documents,
            'totalUploads': len(documents)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/generate-link-test')
def generate_link_test():
    task_id = request.args.get('taskId', 'test-123')
    customer_email = request.args.get('customerEmail', 'test@example.com')
    
    token = generate_customer_token(task_id, customer_email)
    upload_link = f"{request.host_url}upload-async/{token}"
    
    return jsonify({
        'uploadLink': upload_link,
        'token': token,
        'expiresAt': 'Never'
    })

# OCR Testing Routes
@app.route('/test-ocr')
def test_ocr():
    try:
        # Check if AWS Textract is available in the region
        textract_client = boto3.client(
            'textract',
            aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
            aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
            region_name=os.getenv('AWS_REGION', 'ap-south-1')
        )
        
        # Try to list available operations (this doesn't cost anything)
        return jsonify({
            "status": "success",
            "message": f"Textract available in {os.getenv('AWS_REGION')}",
            "region": os.getenv('AWS_REGION')
        })
        
    except Exception as e:
        error_str = str(e).lower()
        if "not supported" in error_str.lower() or "not supported" in error_str.lower():
            return jsonify({
                "status": "not_available",
                "message": f"Textract not available in {os.getenv('AWS_REGION')}",
                "error": error_str,
                "solution": "Try us-east-1 region"
            })
        else:
            return jsonify({
                "status": "error",
                "message": "Unknown Textract error",
                "error": error_str
            })

@app.route('/test-ocr/<token>')
def test_ocr_simple(token):
    try:
        # Get the last uploaded document for this token
        response = supabase.table('documents').select('*').eq('customer_token', token).order('upload_timestamp', desc=True).limit(1).execute()
        
        if not response.data:
            return jsonify({"error": "No documents found for this token"})
        
        document = response.data[0]
        s3_key = document['s3_key']
        document_id = document['id']
        
        print(f"Testing OCR on document: {document_id}, S3 key: {s3_key}")
        
        # Try a simple Textract call with timeout
        textract_client = boto3.client(
            'textract',
            aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
            aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
            region_name=os.getenv('AWS_REGION', 'ap-south-1')
        )
        
        print("Calling Textract...")
        
        # Simple text detection first (faster than analyze_document)
        response = textract_client.detect_document_text(
            Document={
                'S3Object': {
                    'Bucket': os.getenv('AWS_S3_BUCKET'),
                    'Name': s3_key
                }
            }
        )
        
        print(f"Success! Found {len(response['Blocks'])} text blocks")
        
        # Extract just the text to see if it's working
        text_blocks = []
        for block in response['Blocks']:
            if block['BlockType'] == 'LINE':
                text_blocks.append(block['Text'])
        
        return jsonify({
            "status": "success",
            "textract_blocks": len(response['Blocks']),
            "sample_text": text_blocks[:5],  # First 5 lines
            "document_id": document_id
        })
        
    except Exception as e:
        print(f"OCR test error: {e}")
        import traceback
        print(traceback.format_exc())
        return jsonify({
            "status": "error",
            "error": str(e)
        })

# EmailService class for notifications
class EmailService:
    def __init__(self, api_key=None):
        self.api_key = api_key or os.getenv('SENDGRID_API_KEY')
        if self.api_key and 'your_' not in self.api_key:
            self.sg = SendGridAPIClient(api_key=self.api_key)
        else:
            self.sg = None
    
    def send_processing_notification(self, customer_email, status, document_info):
        """Send processing status notification"""
        try:
            if not self.sg:
                return False
            
            if status == 'started':
                subject = 'Document Processing Started'
                status_text = 'Processing Started'
                status_color = '#17a2b8'
                message_text = f"We've received your document <strong>{document_info['filename']}</strong> and processing has begun."
            else:
                return False
            
            html_content = f'''
            <html>
            <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                <div style="background-color: #f8f9fa; padding: 20px; border-radius: 10px;">
                    <h1 style="color: #007bff; text-align: center;">Swipey Digital Services</h1>
                    <h2 style="color: {status_color}; text-align: center;">{status_text}</h2>
                    
                    <div style="background-color: white; padding: 20px; border-radius: 5px;">
                        <p>{message_text}</p>
                        
                        <div style="background-color: #e8f4f8; padding: 15px; border-radius: 5px; margin: 20px 0;">
                            <h3>Processing Details:</h3>
                            <ul>
                                <li><strong>Filename:</strong> {document_info.get('filename', 'N/A')}</li>
                                <li><strong>Upload Time:</strong> {document_info.get('upload_time', 'N/A')}</li>
                                <li><strong>Method:</strong> AI OCR (AWS Textract)</li>
                                <li><strong>Status:</strong> Processing...</li>
                            </ul>
                        </div>
                        
                        <p>You'll receive another email once processing is complete.</p>
                        <p>Thank you for choosing Swipey Digital Services!</p>
                    </div>
                </div>
            </body>
            </html>
            '''
            
            message = Mail(
                from_email=os.getenv('FROM_EMAIL', 'kalyana.mohan@swipey.co'),
                to_emails=customer_email,
                subject=subject,
                html_content=html_content
            )
            
            response = self.sg.send(message)
            return response.status_code == 202
            
        except Exception as e:
            print(f"Processing notification email failed: {e}")
            return False

# Helper functions for completion and failure emails
def send_completion_email(customer_email, document_info, extracted_data):
    """Send completion email with extracted data"""
    try:
        sendgrid_api_key = os.getenv('SENDGRID_API_KEY')
        if not sendgrid_api_key or 'your_' in sendgrid_api_key:
            return False
        
        sg_client = SendGridAPIClient(api_key=sendgrid_api_key)
        
        # Build extracted data HTML
        extracted_html = ""
        if extracted_data:
            extracted_html = "<h4>Extracted Information:</h4><ul>"
            
            if extracted_data.get('company_name'):
                extracted_html += f"<li><strong>Company Name:</strong> {extracted_data['company_name']}</li>"
            if extracted_data.get('registration_number'):
                extracted_html += f"<li><strong>Registration Number:</strong> {extracted_data['registration_number']}</li>"
            if extracted_data.get('incorporation_date'):
                extracted_html += f"<li><strong>Incorporation Date:</strong> {extracted_data['incorporation_date']}</li>"
            if extracted_data.get('company_type'):
                extracted_html += f"<li><strong>Company Type:</strong> {extracted_data['company_type']}</li>"
            if extracted_data.get('business_address'):
                extracted_html += f"<li><strong>Business Address:</strong> {extracted_data['business_address']}</li>"
            if extracted_data.get('business_phone'):
                extracted_html += f"<li><strong>Business Phone:</strong> {extracted_data['business_phone']}</li>"
            
            # Display directors
            directors = extracted_data.get('directors', [])
            if directors:
                extracted_html += "<li><strong>Directors:</strong><ul>"
                for director in directors:
                    extracted_html += f"<li>{director.get('name', 'Unknown')}"
                    if director.get('id_number'):
                        extracted_html += f" (ID: {director['id_number']})"
                    if director.get('email'):
                        extracted_html += f" - {director['email']}"
                    extracted_html += "</li>"
                extracted_html += "</ul></li>"
            
            extracted_html += "</ul>"
        
        subject = 'Document Processing Complete - Data Extracted Successfully'
        
        html_content = f'''
        <html>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <div style="background-color: #f8f9fa; padding: 20px; border-radius: 10px;">
                <h1 style="color: #007bff; text-align: center;">Swipey Digital Services</h1>
                <h2 style="color: #28a745; text-align: center;">Processing Complete!</h2>
                
                <div style="background-color: white; padding: 20px; border-radius: 5px;">
                    <p><strong>Great news! Your KYB document has been successfully processed.</strong></p>
                    
                    <h3>Processing Summary:</h3>
                    <ul>
                        <li><strong>Filename:</strong> {document_info.get('filename', 'N/A')}</li>
                        <li><strong>Processing Time:</strong> {document_info.get('processing_time', 'N/A')}</li>
                        <li><strong>Method:</strong> Async AI OCR (AWS Textract)</li>
                        <li><strong>Status:</strong> Completed Successfully</li>
                    </ul>
                    
                    <div style="background-color: #e8f5e8; padding: 15px; border-radius: 5px; margin: 20px 0;">
                        {extracted_html}
                    </div>
                    
                    <p>Thank you for choosing Swipey Digital Services!</p>
                </div>
            </div>
        </body>
        </html>
        '''
        
        from_email_address = os.getenv('FROM_EMAIL', 'hi@swipey.co')
        from_name = os.getenv('FROM_NAME', 'Swipey Team')
        
        message = Mail(
            from_email=(from_email_address, from_name),
            to_emails=customer_email,
            subject=subject,
            html_content=html_content
        )
        
        response = sg_client.send(message)
        return response.status_code == 202
        
    except Exception as e:
        print(f"Completion email failed: {e}")
        return False

def send_failure_email(customer_email, document_info):
    """Send failure notification email"""
    try:
        sendgrid_api_key = os.getenv('SENDGRID_API_KEY')
        if not sendgrid_api_key or 'your_' in sendgrid_api_key:
            return False
        
        sg_client = SendGridAPIClient(api_key=sendgrid_api_key)
        
        subject = 'Document Processing Issue - Support Notified'
        
        html_content = f'''
        <html>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <div style="background-color: #f8f9fa; padding: 20px; border-radius: 10px;">
                <h1 style="color: #007bff; text-align: center;">Swipey Digital Services</h1>
                <h2 style="color: #dc3545; text-align: center;">Processing Issue</h2>
                
                <div style="background-color: white; padding: 20px; border-radius: 5px;">
                    <p>We encountered an issue processing your document: <strong>{document_info.get('filename', 'N/A')}</strong></p>
                    
                    <div style="background-color: #f8d7da; padding: 15px; border-radius: 5px; margin: 20px 0;">
                        <p><strong>Don't worry - we're on it!</strong></p>
                        <p>Our technical team has been automatically notified and will review your document manually.</p>
                    </div>
                    
                    <p>Contact us at kalyana.mohan@swipey.co if you have questions.</p>
                </div>
            </div>
        </body>
        </html>
        '''
        
        from_email_address = os.getenv('FROM_EMAIL', 'hi@swipey.co')
        from_name = os.getenv('FROM_NAME', 'Swipey Team')
        
        message = Mail(
            from_email=(from_email_address, from_name),
            to_emails=customer_email,
            subject=subject,
            html_content=html_content
        )
        
        response = sg_client.send(message)
        return response.status_code == 202
        
    except Exception as e:
        print(f"Failure email failed: {e}")
        return False

# Add async upload route (working version from previous implementation)
@app.route('/upload-file-async/<token>', methods=['POST'])
def upload_file_with_async_ocr(token):
    """Upload file with ASYNC OCR processing (like console)"""
    try:
        print(f"Starting ASYNC upload for token: {token[:20]}...")
        
        # Decode customer data
        customer_data = decode_customer_token(token)
        customer_data['originalToken'] = token
        
        # File validation (same as existing)
        if 'document' not in request.files:
            return jsonify({'error': 'No file uploaded'}), 400
        
        file = request.files['document']
        if file.filename == '' or not file.filename.lower().endswith('.pdf'):
            return jsonify({'error': 'Please select a valid PDF file'}), 400
        
        # Check file size
        file.seek(0, 2)
        file_size = file.tell()
        file.seek(0)
        
        if file_size > 10 * 1024 * 1024:
            return jsonify({'error': 'File size must be less than 10MB'}), 400
        
        print(f"File validated: {file.filename}, Size: {file_size} bytes")
        
        # Read and convert PDF
        original_content = file.read()
        conversion_result = convert_pdf_for_textract(original_content)
        
        if conversion_result['success']:
            file_content = conversion_result['content']
            conversion_info = {
                'converted': conversion_result['converted'],
                'original_version': conversion_result.get('original_version', 'Unknown'),
                'final_version': conversion_result.get('final_version', 'Unknown'),
                'size_change': conversion_result.get('size_change', 0)
            }
        else:
            file_content = original_content
            conversion_info = {'converted': False, 'error': conversion_result.get('error')}
        
        # Generate filename
        existing_docs = supabase.table('documents').select('*').eq('customer_token', token).execute()
        document_count = len(existing_docs.data) + 1
        base_filename = f"SSM_{document_count}.pdf"
        
        # Upload to S3
        s3_result = upload_to_s3(file_content, customer_data['taskId'], base_filename)
        print(f"S3 upload successful: {s3_result['key']}")
        
        # Save to database
        file_info = {'filename': base_filename, 'size': len(file_content)}
        db_result = save_document_metadata(customer_data, s3_result, file_info)
        print(f"Database record created: {db_result['id']}")
        
        # Update company kyb_status to indicate document uploaded and pending review
        update_company_kyb_status(customer_data['taskId'], 'documents_pending_review')
        
        # Attach document to ClickUp task and update SSM document field
        try:
            from services.clickup_service import attach_document_to_clickup_task
            
            # Create temporary file path for ClickUp attachment
            import tempfile
            temp_file_path = None
            
            try:
                # Create temporary file with the uploaded content
                with tempfile.NamedTemporaryFile(delete=False, suffix=f"_{base_filename}") as temp_file:
                    temp_file.write(file_content)
                    temp_file_path = temp_file.name
                
                print(f"Attaching document to ClickUp task {customer_data['taskId']}: {base_filename}")
                
                attachment_result = attach_document_to_clickup_task(
                    task_id=customer_data['taskId'],
                    file_path=temp_file_path,
                    filename=base_filename
                )
                
                if attachment_result.get('success'):
                    print(f"[OK] Document attached to ClickUp task successfully")
                    print(f"[OK] SSM document field updated: {attachment_result.get('ssm_field_updated')}")
                else:
                    print(f"[WARNING] ClickUp document attachment failed: {attachment_result.get('error')}")
                    
            finally:
                # Clean up temporary file
                if temp_file_path and os.path.exists(temp_file_path):
                    os.unlink(temp_file_path)
                    
        except Exception as clickup_error:
            print(f"ClickUp document attachment error (non-critical): {clickup_error}")
        
        # NEW: Use ASYNC OCR processing (like console)
        print(f"Starting ASYNC OCR processing (like console)...")
        
        try:
            # Use the OCR service
            from services.ocr_service import OCRService
            ocr_service = OCRService(supabase)
            ocr_result = ocr_service.process_document_async(s3_result['key'], db_result['id'])
            ocr_success = ocr_result.get('success', False)
            extracted_data = ocr_result.get('extracted_data', {})
            
            print(f"ASYNC OCR completed. Success: {ocr_success}")
            
            # Note: OCR status is already updated to 'completed' by OCR service
            # Company kyb_status remains 'documents_pending_review' for manual review
            
        except Exception as ocr_error:
            print(f"ASYNC OCR processing failed: {ocr_error}")
            ocr_success = False
            extracted_data = {}
            # Update companies kyb_status to failed if OCR fails
            update_company_kyb_status(customer_data['taskId'], 'kyb_failed')

        return jsonify({
            'success': True,
            'message': 'Document uploaded and processed with ASYNC OCR (like console)',
            'documentId': db_result['id'],
            'filename': file_info['filename'],
            'uploadedAt': db_result['upload_timestamp'],
            'ocr_status': 'completed' if ocr_success else 'failed',
            'processing_method': 'async_textract',
            'conversion_info': conversion_info,
            'extracted_preview': {
                'company_name': extracted_data.get('company_name'),
                'registration_number': extracted_data.get('registration_number'),
                'incorporation_date': extracted_data.get('incorporation_date'),
                'company_type': extracted_data.get('company_type'),
                'business_address': extracted_data.get('business_address'),
                'business_phone': extracted_data.get('business_phone'),
                'directors': extracted_data.get('directors', [])
            },
            'debug_info': {
                's3_key': s3_result['key'],
                'textract_job_id': ocr_result.get('job_id'),
                'processing_time': '10-15 seconds (async)'
            }
        })
        
    except Exception as e:
        print(f"ASYNC upload error: {e}")
        import traceback
        print(traceback.format_exc())
        return jsonify({
            'error': 'ASYNC upload failed',
            'details': str(e)
        }), 500

# Add async upload page that uses the working async endpoint
@app.route('/upload-async/<token>')
def upload_page_async(token):
    """Upload page that uses ASYNC OCR processing"""
    try:
        customer_data = decode_customer_token(token)
        task_id = customer_data['taskId']
        customer_email = customer_data['email']
        
        # Fetch customer first name from Supabase companies table
        customer_first_name = "Customer"  # Default fallback
        if supabase:
            try:
                response = supabase.table('companies').select('customer_first_name').eq('clickup_task_id', task_id).execute()
                if response.data and response.data[0].get('customer_first_name'):
                    customer_first_name = response.data[0]['customer_first_name']
                else:
                    print(f"No customer_first_name found for task {task_id}")
            except Exception as e:
                print(f"Could not fetch customer_first_name: {e}")
        
        return render_template('upload_async.html', 
                             customer_email=customer_email,
                             customer_name=customer_first_name, 
                             token=token)
    except Exception as e:
        return jsonify({'error': 'Invalid upload link'}), 400

# Add async upload route with email notifications
@app.route('/upload-file-async-with-emails/<token>', methods=['POST'])
def upload_file_async_with_emails(token):
    """Upload with async OCR and automatic email notifications"""
    try:
        print(f"Starting ASYNC upload with EMAIL NOTIFICATIONS...")
        
        # Initialize email service
        email_service = EmailService()
        
        # Decode customer data
        customer_data = decode_customer_token(token)
        customer_data['originalToken'] = token
        customer_email = customer_data['email']
        
        # File validation (same as existing route)
        if 'document' not in request.files:
            return jsonify({'error': 'No file uploaded'}), 400
        
        file = request.files['document']
        if file.filename == '' or not file.filename.lower().endswith('.pdf'):
            return jsonify({'error': 'Please select a valid PDF file'}), 400
        
        file.seek(0, 2)
        file_size = file.tell()
        file.seek(0)
        
        if file_size > 10 * 1024 * 1024:
            return jsonify({'error': 'File size must be less than 10MB'}), 400
        
        print(f"File validated: {file.filename}")
        
        # PDF conversion (use existing function)
        original_content = file.read()
        conversion_result = convert_pdf_for_textract(original_content)
        
        if conversion_result['success']:
            file_content = conversion_result['content']
        else:
            file_content = original_content
        
        # Upload to S3 (use existing functions)
        existing_docs = supabase.table('documents').select('*').eq('customer_token', token).execute()
        document_count = len(existing_docs.data) + 1
        base_filename = f"SSM_{document_count}.pdf"
        
        s3_result = upload_to_s3(file_content, customer_data['taskId'], base_filename)
        file_info = {'filename': base_filename, 'size': len(file_content)}
        db_result = save_document_metadata(customer_data, s3_result, file_info)
        
        print(f"S3 upload successful, Database updated")
        
        # Send "processing started" email
        document_info = {
            'filename': base_filename,
            'upload_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        print(f"Sending processing started email to {customer_email}")
        email_service.send_processing_notification(customer_email, 'started', document_info)
        
        # Start async OCR processing
        print(f"Starting async OCR...")
        
        try:
            import time
            start_time = time.time()
            
            # Use existing OCR function
            ocr_result = process_document_ocr_async(s3_result['key'], db_result['id'], supabase)
            processing_time = f"{time.time() - start_time:.1f} seconds"
            
            if ocr_result.get('success'):
                extracted_data = ocr_result.get('extracted_data', {})
                
                # Send "processing completed" email with extracted data
                document_info['processing_time'] = processing_time
                print(f"Sending completion email with extracted data to {customer_email}")
                
                completion_email_sent = send_completion_email(customer_email, document_info, extracted_data)
                
                print(f"OCR completed, Completion email sent: {completion_email_sent}")
                
                return jsonify({
                    'success': True,
                    'message': 'Document processed successfully with email notifications',
                    'documentId': db_result['id'],
                    'filename': base_filename,
                    'processing_time': processing_time,
                    'emails_sent': ['processing_started', 'processing_completed'],
                    'extracted_preview': {
                        'company_name': extracted_data.get('company_name'),
                        'registration_number': extracted_data.get('registration_number'),
                        'incorporation_date': extracted_data.get('incorporation_date'),
                        'company_type': extracted_data.get('company_type'),
                        'business_address': extracted_data.get('business_address'),
                        'business_phone': extracted_data.get('business_phone'),
                        'directors': extracted_data.get('directors', [])
                    }
                })
            else:
                # Send "processing failed" email
                print(f"Sending failure email to {customer_email}")
                failure_email_sent = send_failure_email(customer_email, document_info)
                
                return jsonify({
                    'success': False,
                    'message': 'OCR processing failed, failure email sent',
                    'documentId': db_result['id'],
                    'emails_sent': ['processing_started', 'processing_failed']
                })
                
        except Exception as ocr_error:
            print(f"OCR error: {ocr_error}")
            
            # Send failure email
            print(f"Sending failure email due to error")
            send_failure_email(customer_email, document_info)
            
            return jsonify({
                'success': False,
                'message': 'OCR processing failed with error',
                'error': str(ocr_error),
                'emails_sent': ['processing_started', 'processing_failed']
            })
        
    except Exception as e:
        print(f"Upload error: {e}")
        return jsonify({'error': 'Upload failed', 'details': str(e)}), 500

# TEST ENDPOINT: Send test email using Supabase company data
@app.route('/test-email-from-supabase/<uuid>')
def test_email_from_supabase(uuid):
    """Test endpoint to send email using company data from Supabase by UUID"""
    try:
        if not supabase:
            # Mock company data for testing when Supabase is not configured
            if uuid == '623c46e0-b5ea-46b7-949f-590fa810f7a0':
                company_data = {
                    'id': uuid,
                    'email': 'kalyanamo@gmail.com',
                    'company_name': 'Test Company Ltd',
                    'clickup_task_id': 'test-task-123',
                    'kyb_status': 'pending_documents',
                    'phone': '+1234567890',
                    'typeform_submission_id': 'test-typeform-123'
                }
            else:
                return jsonify({'error': f'Company with UUID {uuid} not found (Supabase not configured)'}), 404
        else:
            # Fetch company data from Supabase
            response = supabase.table('companies').select('*').eq('id', uuid).execute()
            
            if not response.data:
                return jsonify({'error': f'Company with UUID {uuid} not found'}), 404
            
            company_data = response.data[0]
        
        # Extract required fields for email
        customer_email = company_data.get('email')
        customer_name = company_data.get('company_name', 'Valued Customer')
        task_id = company_data.get('clickup_task_id', 'test-task')
        
        if not customer_email:
            return jsonify({'error': 'Company record missing email address'}), 400
        
        # Generate test upload link (using async route)
        token = generate_customer_token(task_id, customer_email)
        upload_link = f"{request.host_url}upload-async/{token}"
        
        # Send email using dynamic template
        email_result = send_upload_email(customer_email, customer_name, upload_link, "Test Company")
        
        return jsonify({
            'success': True,
            'message': f'Test email sent to {customer_email}',
            'company_data': company_data,
            'upload_link': upload_link,
            'email_result': email_result,
            'note': 'Using mock data' if not supabase else 'Using Supabase data'
        })
        
    except Exception as e:
        print(f"Test email error: {e}")
        return jsonify({'error': 'Test email failed', 'details': str(e)}), 500

# Routes continue below - app.run() moved to end of file

# DOCUMENSO E-SIGNATURE ENDPOINTS

@app.route('/trigger-documenso/<clickup_task_id>', methods=['POST'])
def trigger_documenso_signature_route(clickup_task_id):
    """Trigger Documenso e-signature request for a specific ClickUp task"""
    try:
        print(f"Triggering Documenso e-signature request for ClickUp task: {clickup_task_id}")
        
        # Get company and director information
        if not supabase:
            return jsonify({'error': 'Database not configured'}), 500
        
        # Find company by ClickUp task ID
        company_result = supabase.table('companies').select('*').eq('clickup_task_id', clickup_task_id).execute()
        if not company_result.data:
            return jsonify({'error': f'Company not found for task {clickup_task_id}'}), 404
        
        company = company_result.data[0]
        company_name = company.get('company_name', 'Unknown Company')
        
        # Find latest completed OCR document for this task
        doc_result = supabase.table('documents').select('*').eq('clickup_task_id', clickup_task_id).eq('ocr_status', 'completed').order('created_at', desc=True).limit(1).execute()
        
        if not doc_result.data:
            return jsonify({'error': 'No completed OCR documents found for this task'}), 404
        
        document = doc_result.data[0]
        directors_data = document.get('extracted_directors', [])
        
        if not directors_data:
            return jsonify({'error': 'No directors data found in OCR results'}), 400
        
        # Filter directors with valid emails
        valid_directors = [d for d in directors_data if d.get('email')]
        if not valid_directors:
            return jsonify({'error': 'No directors with valid email addresses found'}), 400
        
        print(f"Found {len(valid_directors)} directors with emails for {company_name}")
        
        # Trigger Documenso signature request
        from services.documenso_service import send_signature_request_to_directors
        
        result = send_signature_request_to_directors(
            directors_data=valid_directors,
            clickup_task_id=clickup_task_id,
            company_name=company_name
        )
        
        if result.get('success'):
            return jsonify({
                'success': True,
                'message': f'Documenso e-signature request sent successfully to {len(valid_directors)} directors',
                'document_id': result.get('document_id'),
                'company_name': company_name,
                'recipients': result.get('recipients'),
                'clickup_task_id': clickup_task_id,
                'signing_url': result.get('signing_url')
            })
        else:
            return jsonify({
                'success': False,
                'error': result.get('error', 'Unknown error occurred')
            }), 500
            
    except Exception as e:
        print(f"Documenso e-signature trigger error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/documenso-webhook', methods=['POST'])
def documenso_webhook_route():
    """Handle Documenso webhook events for signature status updates"""
    print("=== DOCUMENSO WEBHOOK CALLED ===")
    try:
        # Verify webhook secret if configured - TEMPORARILY DISABLED FOR DEBUG
        webhook_secret = os.getenv('DOCUMENSO_WEBHOOK_SECRET')
        print(f"DEBUG: Webhook secret configured: {webhook_secret is not None}")
        
        # Get signature from headers for debugging
        signature = request.headers.get('X-Documenso-Signature') or request.headers.get('X-Signature') or request.headers.get('Authorization')
        print(f"DEBUG: Received signature: {signature}")
        print(f"DEBUG: All headers: {dict(request.headers)}")
        
        # TEMPORARILY SKIP SIGNATURE VALIDATION FOR DEBUGGING
        # if webhook_secret:
        #     if not signature:
        #         print("Warning: No webhook signature found in headers")
        #         return jsonify({'error': 'Webhook signature required'}), 401
        #     if webhook_secret not in signature:
        #         print("Warning: Invalid webhook signature")
        #         return jsonify({'error': 'Invalid webhook signature'}), 401
        
        # Get webhook data
        webhook_data = request.get_json()
        
        if not webhook_data:
            print("ERROR: No webhook data received")
            return jsonify({'error': 'No webhook data received'}), 400
        
        print(f"Received Documenso webhook: {webhook_data.get('event')}")
        
        # Process webhook with Documenso service
        from services.documenso_service import handle_documenso_webhook
        
        result = handle_documenso_webhook(webhook_data)
        
        if result.get('success'):
            return jsonify({
                'success': True,
                'message': 'Webhook processed successfully',
                'event_type': result.get('event_type'),
                'status': result.get('mapped_status')
            })
        else:
            print(f"Webhook processing failed: {result.get('error')}")
            return jsonify({
                'success': False,
                'error': result.get('error', 'Webhook processing failed')
            }), 500
            
    except Exception as e:
        print(f"=== DOCUMENSO WEBHOOK EXCEPTION ===")
        print(f"Exception: {e}")
        print(f"Exception type: {type(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/test-documenso-trigger')
def test_documenso_trigger_route():
    """Test endpoint to show Documenso e-signature trigger information"""
    try:
        clickup_task_id = request.args.get('task_id', '86czpxnf4')
        
        if not supabase:
            return jsonify({'error': 'Database not configured'}), 500
        
        # Get company info
        company_result = supabase.table('companies').select('*').eq('clickup_task_id', clickup_task_id).execute()
        if not company_result.data:
            return jsonify({'error': f'Company not found for task {clickup_task_id}'}), 404
        
        company = company_result.data[0]
        
        # Get latest OCR document
        doc_result = supabase.table('documents').select('*').eq('clickup_task_id', clickup_task_id).eq('ocr_status', 'completed').order('created_at', desc=True).limit(1).execute()
        
        if not doc_result.data:
            return jsonify({'error': 'No completed OCR documents found'}), 404
        
        document = doc_result.data[0]
        directors_data = document.get('extracted_directors', [])
        valid_directors = [d for d in directors_data if d.get('email')]
        
        return jsonify({
            'success': True,
            'service': 'Documenso',
            'company_name': company.get('company_name'),
            'clickup_task_id': clickup_task_id,
            'directors_found': len(directors_data),
            'directors_with_emails': len(valid_directors),
            'directors': valid_directors,
            'ready_for_esignature': len(valid_directors) > 0,
            'trigger_url': f"{request.host_url}trigger-documenso/{clickup_task_id}",
            'test_command': f"curl -X POST {request.host_url}trigger-documenso/{clickup_task_id} -H 'Content-Type: application/json'",
            'webhook_url': f"{request.host_url}documenso-webhook"
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/eSignature_Request/<token>', methods=['POST'])
def esignature_request(token):
    """Handle e-signature request from upload page"""
    try:
        # Decode customer data from token
        customer_data = decode_customer_token(token)
        clickup_task_id = customer_data.get('taskId')
        
        # Get request data
        data = request.get_json()
        selected_director_index = data.get('selectedDirector', 0)
        
        if not clickup_task_id:
            return jsonify({'error': 'Invalid token or missing task ID'}), 400
        
        # Get company data from Supabase
        if not supabase:
            return jsonify({'error': 'Database not configured'}), 500
        
        response = supabase.table('companies').select('*').eq('clickup_task_id', clickup_task_id).execute()
        if not response.data:
            return jsonify({'error': 'Company not found'}), 404
        
        company = response.data[0]
        company_name = company.get('company_name', 'Unknown Company')
        
        # Get directors from documents table and use the selected index from frontend
        doc_response = supabase.table('documents').select('id, extracted_directors').eq('clickup_task_id', clickup_task_id).order('created_at', desc=True).limit(1).execute()
        if not doc_response.data:
            return jsonify({'error': 'No documents found for this task'}), 404
        
        document = doc_response.data[0]
        directors_data = document.get('extracted_directors', [])
        
        if not directors_data or len(directors_data) == 0:
            return jsonify({'error': 'No directors found for this company'}), 400
        
        # Get selected director using the index from frontend
        try:
            selected_director_index = int(selected_director_index)
            if selected_director_index >= len(directors_data):
                selected_director_index = 0
        except (ValueError, TypeError):
            selected_director_index = 0
        
        selected_director = directors_data[selected_director_index]
        
        # Store the selection in the database for audit trail
        updated_directors = directors_data.copy()
        for i, director in enumerate(updated_directors):
            director['selected'] = (i == selected_director_index)
        
        supabase.table('documents').update({
            'extracted_directors': updated_directors
        }).eq('id', document['id']).execute()
        director_email = selected_director.get('email', '')
        director_name = selected_director.get('name', 'Unknown Director')
        
        # 1. Update ClickUp Consent & Authorisation field to "Pending Signature"
        from services.clickup_service import update_clickup_task_status
        
        consent_result = update_clickup_task_status(
            task_id=clickup_task_id,
            status_type='consent_status',
            status_value='pending_signature',
            additional_info={
                'director_name': director_name,
                'director_email': director_email,
                'company_name': company_name
            }
        )
        
        if not consent_result.get('success'):
            print(f"Warning: Failed to update consent status: {consent_result.get('error')}")
        
        # 2. Also send the original comment to ClickUp for additional context
        from services.clickup_service import ClickUpService
        clickup_service = ClickUpService()
        
        comment_text = f"""
[APPROVAL] **E-Signature Request Initiated**

**Company:** {company_name}
**Selected Director:** {director_name}
**Director Email:** {director_email}
**Timestamp:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

E-signature request has been sent to the selected director for account activation approval.

*Automated update from KYB system*
"""
        
        clickup_result = clickup_service._add_comment_to_task(clickup_task_id, comment_text)
        if not clickup_result.get('success'):
            print(f"Warning: Failed to add ClickUp comment: {clickup_result.get('error')}")
        
        # 3. Send request via Documenso
        from services.documenso_service import DocumensoService
        documenso_service = DocumensoService(supabase_client=supabase)
        
        # Create signature request with the selected director
        signature_result = documenso_service.create_signature_request(
            directors_data=[selected_director],  # Only send to selected director
            clickup_task_id=clickup_task_id,
            company_name=company_name
        )
        
        if signature_result.get('success'):
            return jsonify({
                'success': True,
                'message': f'E-signature request sent to {director_name}. Please check your email from Documenso and sign as soon as possible.',
                'director_name': director_name,
                'director_email': director_email,
                'document_id': signature_result.get('document_id')
            })
        else:
            return jsonify({
                'success': False,
                'error': f'Failed to send e-signature request: {signature_result.get("error")}'
            }), 500
        
    except Exception as e:
        print(f"E-signature request error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/sendComment/<token>', methods=['POST'])
def send_comment(token):
    """Handle comment submission from upload page"""
    try:
        # Decode customer data from token
        customer_data = decode_customer_token(token)
        clickup_task_id = customer_data.get('taskId')
        customer_email = customer_data.get('email', 'Unknown Customer')
        
        # Get request data
        data = request.get_json()
        comment = data.get('comment', '').strip()
        
        if not clickup_task_id:
            return jsonify({'error': 'Invalid token or missing task ID'}), 400
        
        if not comment:
            return jsonify({'error': 'Comment cannot be empty'}), 400
        
        # Get company data from Supabase for context
        company_name = 'Unknown Company'
        if supabase:
            try:
                response = supabase.table('companies').select('company_name').eq('clickup_task_id', clickup_task_id).execute()
                if response.data:
                    company_name = response.data[0].get('company_name', 'Unknown Company')
            except Exception as e:
                print(f"Warning: Could not fetch company name: {e}")
        
        # Send comment to ClickUp
        from services.clickup_service import ClickUpService
        clickup_service = ClickUpService()
        
        comment_text = f"""
[CUSTOMER FEEDBACK] **Information Correction Request**

**Company:** {company_name}
**Customer Email:** {customer_email}
**Timestamp:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

**Customer Comment:**
"{comment}"

**Action Required:** Customer has indicated information is incorrect and needs assistance from our team. Please review the extracted data and contact the customer if needed.

*Automated update from KYB system*
"""
        
        clickup_result = clickup_service._add_comment_to_task(clickup_task_id, comment_text)
        
        if clickup_result.get('success'):
            return jsonify({
                'success': True,
                'message': 'Comment sent successfully! Our team will review and get back to you.'
            })
        else:
            print(f"ClickUp comment failed: {clickup_result.get('error')}")
            return jsonify({
                'success': False,
                'error': 'Failed to send comment. Please try again or contact support.'
            }), 500
        
    except Exception as e:
        print(f"Send comment error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/test-new-route')
def test_new_route():
    """Simple test route to verify Flask is loading new routes"""
    return jsonify({'message': 'New route works!', 'success': True})


@app.route('/storeSelectedDirector/<token>', methods=['POST'])
def store_selected_director(token):
    """Store the selected director in documents table"""
    try:
        # Decode customer data from token
        customer_data = decode_customer_token(token)
        clickup_task_id = customer_data.get('taskId')
        
        # Get request data
        data = request.get_json()
        selected_director_index = data.get('selectedDirectorIndex', 0)
        
        if not clickup_task_id:
            return jsonify({'error': 'Invalid token or missing task ID'}), 400
        
        # Get the latest document for this task
        if not supabase:
            return jsonify({'error': 'Database not configured'}), 500
        
        doc_response = supabase.table('documents').select('id, extracted_directors').eq('clickup_task_id', clickup_task_id).order('created_at', desc=True).limit(1).execute()
        if not doc_response.data:
            return jsonify({'error': 'No documents found for this task'}), 404
        
        document = doc_response.data[0]
        directors_data = document.get('extracted_directors', [])
        
        if not directors_data or len(directors_data) == 0:
            return jsonify({'error': 'No directors found in document'}), 400
        
        # Get selected director
        try:
            selected_director_index = int(selected_director_index)
            if selected_director_index >= len(directors_data):
                selected_director_index = 0
        except (ValueError, TypeError):
            selected_director_index = 0
        
        selected_director = directors_data[selected_director_index]
        
        # Store selected director by adding a 'selected' flag to the extracted_directors JSONB
        updated_directors = directors_data.copy()
        for i, director in enumerate(updated_directors):
            director['selected'] = (i == selected_director_index)
        
        update_result = supabase.table('documents').update({
            'extracted_directors': updated_directors
        }).eq('id', document['id']).execute()
        
        if update_result.data:
            return jsonify({
                'success': True,
                'message': 'Selected director stored successfully',
                'selected_director': selected_director
            })
        else:
            return jsonify({'error': 'Failed to store selected director'}), 500
        
    except Exception as e:
        print(f"Store selected director error: {e}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"Starting Flask server on port {port}")
    app.run(host='0.0.0.0', port=port, debug=True)
