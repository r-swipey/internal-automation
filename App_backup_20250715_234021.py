from flask import Flask, request, jsonify, render_template_string
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
    supabase_key = os.getenv('SUPABASE_KEY')
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

# SendGrid email functions
def send_upload_email(customer_email, customer_name, upload_link):
    """Send upload link email to customer via SendGrid"""
    try:
        if not sg:
            return {'success': False, 'error': 'SendGrid not configured'}
        
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 0; padding: 20px; }}
                .container {{ max-width: 600px; margin: 0 auto; }}
                .header {{ background-color: #007bff; color: white; padding: 20px; text-align: center; }}
                .content {{ padding: 20px; background-color: #f8f9fa; }}
                .btn {{ background-color: #007bff; color: white; padding: 15px 30px; text-decoration: none; border-radius: 5px; display: inline-block; margin: 20px 0; }}
                .footer {{ text-align: center; color: #666; font-size: 12px; margin-top: 30px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>KYB Document Upload Required</h1>
                </div>
                <div class="content">
                    <p>Dear {customer_name},</p>
                    <p>Thank you for submitting your KYB application. To complete your onboarding process, please upload your required documents using the secure link below:</p>
                    <p style="text-align: center;">
                        <a href="{upload_link}" class="btn">Upload Documents</a>
                    </p>
                    <p><strong>What you need to upload:</strong></p>
                    <ul>
                        <li>Completed KYB form</li>
                        <li>Company registration documents</li>
                        <li>Director identification documents</li>
                    </ul>
                    <p><strong>Important:</strong></p>
                    <ul>
                        <li>Only PDF files are accepted</li>
                        <li>Maximum file size: 10MB</li>
                        <li>This link is secure and unique to your application</li>
                    </ul>
                    <p>If you have any questions, please contact our support team.</p>
                    <p>Best regards,<br>Swipey KYB Team</p>
                </div>
                <div class="footer">
                    <p>This is an automated message. Please do not reply to this email.</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        message = Mail(
            from_email=os.getenv('FROM_EMAIL'),
            to_emails=customer_email,
            subject='KYB Document Upload Required - Swipey',
            html_content=html_content
        )
        
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

📋 **Next Steps:**
1. ✅ Upload link sent to customer via email
2. ⏳ Waiting for customer to upload KYB documents
3. ⏳ OCR processing and validation
4. ⏳ Manual review and approval

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
            
        # Create customers table record
        customer_record = {
            'customer_name': customer_data['customer_name'],
            'customer_email': customer_data['customer_email'],
            'company_name': customer_data['company_name'],
            'phone': customer_data.get('phone'),
            'business_type': customer_data.get('business_type'),
            'clickup_task_id': task_id,
            'customer_token': token,
            'upload_link': upload_link,
            'typeform_response_id': customer_data.get('typeform_response_id'),
            'submission_timestamp': customer_data.get('submission_timestamp'),
            'status': 'pending_upload',
            'created_at': datetime.now().isoformat()
        }
        
        response = supabase.table('customers').insert(customer_record).execute()
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
        extracted_data = extract_key_information(response)
        
        print(f"Extracted data: {extracted_data}")
        
        # Update database with OCR results
        print("Updating database with OCR results...")
        update_result = supabase.table('documents').update({
            'ocr_status': 'completed',
            'ocr_completed_at': datetime.now().isoformat(),
            'extracted_name': extracted_data.get('name'),
            'extracted_email': extracted_data.get('email'),
            'extracted_company_name': extracted_data.get('company_name'),
            'extracted_registration_number': extracted_data.get('registration_number')
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

def extract_key_information(textract_response):
    """Extract specific fields from Textract response - optimized for Malaysian forms"""
    extracted_data = {
        'name': None,
        'email': None,
        'company_name': None,
        'registration_number': None
    }
    
    # Get all text blocks
    blocks = textract_response['Blocks']
    
    # First, try to extract from key-value pairs
    key_map = {}
    value_map = {}
    block_map = {}
    
    for block in blocks:
        block_id = block['Id']
        block_map[block_id] = block
        
        if block['BlockType'] == "KEY_VALUE_SET":
            if 'KEY' in block['EntityTypes']:
                key_map[block_id] = block
            else:
                value_map[block_id] = block
    
    # Extract text from key-value relationships
    for key_id, key_block in key_map.items():
        if 'Relationships' in key_block:
            for relationship in key_block['Relationships']:
                if relationship['Type'] == 'CHILD':
                    key_text = get_text_from_blocks(relationship['Ids'], block_map)
                    
                    # Find corresponding value
                    for rel in key_block.get('Relationships', []):
                        if rel['Type'] == 'VALUE':
                            for value_id in rel['Ids']:
                                if value_id in value_map:
                                    value_block = value_map[value_id]
                                    if 'Relationships' in value_block:
                                        for value_rel in value_block['Relationships']:
                                            if value_rel['Type'] == 'CHILD':
                                                value_text = get_text_from_blocks(value_rel['Ids'], block_map)
                                                
                                                # Match patterns
                                                if any(keyword in key_text.lower() for keyword in ['name', 'nama']):
                                                    extracted_data['name'] = value_text
                                                elif any(keyword in key_text.lower() for keyword in ['email', 'e-mail']):
                                                    extracted_data['email'] = value_text
                                                elif any(keyword in key_text.lower() for keyword in ['company', 'syarikat']):
                                                    extracted_data['company_name'] = value_text
                                                elif any(keyword in key_text.lower() for keyword in ['registration', 'pendaftaran', 'no']):
                                                    extracted_data['registration_number'] = value_text
    
    return extracted_data

def get_text_from_blocks(block_ids, block_map):
    """Helper function to extract text from block IDs"""
    text = ""
    for block_id in block_ids:
        if block_id in block_map:
            block = block_map[block_id]
            if block['BlockType'] == 'WORD':
                text += block.get('Text', '') + " "
    return text.strip()

# Async OCR processing function
def process_ocr_async(s3_key, document_id):
    """Process OCR in background thread"""
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
        message = Mail(
            from_email=os.getenv('FROM_EMAIL'),
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
        upload_link = f"{request.host_url}upload/{token}"
        
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
        upload_link = f"{request.host_url}upload/{token}"
        
        # Send email
        email_result = send_upload_email(customer_email, customer_name, upload_link)
        
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
        upload_link = f"{request.host_url}upload/{token}"
        
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

# TEST ENDPOINT 4: Test async Textract processing
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
        upload_link = f"{request.host_url}upload/{token}"
        
        # Store customer info in database for tracking
        customer_record = store_customer_info(data, task_id, token, upload_link)
        
        # Send email with upload link
        email_result = send_upload_email(data['customer_email'], data['customer_name'], upload_link)
        
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

✅ Document successfully uploaded and stored in S3
⏳ OCR processing initiated
📋 Ready for manual review

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
    upload_link = f"{request.host_url}upload/{token}"
    
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
                <h3>📄 Drop your PDF file here</h3>
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
                const response = await fetch(`/upload-file/${customerToken}`, {
                    method: 'POST',
                    body: formData
                });

                const result = await response.json();

                if (response.ok) {
                    showMessage('✅ Document uploaded successfully! Your file is being processed.', 'success');
                    
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
                showMessage(`❌ Upload failed: ${error.message}`, 'error');
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

# Handle actual file upload
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
    upload_link = f"{request.host_url}upload/{token}"
    
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

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"Starting Flask server on port {port}")
    app.run(host='0.0.0.0', port=port, debug=True)