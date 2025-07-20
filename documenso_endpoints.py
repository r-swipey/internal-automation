"""
Documenso E-Signature Endpoints
Add these to your app.py file or import this module
"""

from flask import request, jsonify
import os
from supabase import create_client

# Initialize Supabase (assuming it's available globally in your app)
supabase_url = os.getenv('SUPABASE_URL')
supabase_key = os.getenv('SUPABASE_ANON_KEY')
supabase = create_client(supabase_url, supabase_key) if supabase_url and supabase_key else None


def trigger_documenso_signature(clickup_task_id):
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


def handle_documenso_webhook():
    """Handle Documenso webhook events for signature status updates"""
    try:
        # Get webhook data
        webhook_data = request.get_json()
        
        if not webhook_data:
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
        print(f"Documenso webhook error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


def test_documenso_trigger(task_id='86czpxnf4'):
    """Test endpoint to show Documenso e-signature trigger information"""
    try:
        clickup_task_id = request.args.get('task_id', task_id)
        
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


# Flask route definitions (add these to your app.py)
"""
@app.route('/trigger-documenso/<clickup_task_id>', methods=['POST'])
def trigger_documenso_signature_route(clickup_task_id):
    return trigger_documenso_signature(clickup_task_id)

@app.route('/documenso-webhook', methods=['POST'])
def documenso_webhook_route():
    return handle_documenso_webhook()

@app.route('/test-documenso-trigger')
def test_documenso_trigger_route():
    return test_documenso_trigger()
"""