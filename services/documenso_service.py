"""
Documenso E-Signature Service - Manages e-signature workflows
This module handles document creation, signing, and status tracking for KYB workflows.
"""

import os
import requests
import json
import base64
from datetime import datetime
from typing import Dict, List, Optional


class DocumensoService:
    """Documenso API service for e-signature workflows"""
    
    def __init__(self, api_key=None, supabase_client=None):
        self.api_key = api_key or os.getenv('DOCUMENSO_API_KEY')
        self.supabase = supabase_client
        self.base_url = "https://app.documenso.com/api/v1"
        self.headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }
    
    def get_template_fields_and_recipients(self, template_id: str) -> Dict:
        """Get template field IDs and recipient IDs for proper prefilling"""
        try:
            if not self.api_key:
                return {'success': False, 'error': 'No API key configured'}
            
            url = f"{self.base_url}/templates/{template_id}"
            response = requests.get(url, headers=self.headers, timeout=15)
            
            if response.status_code == 200:
                template_data = response.json()
                
                # Map field labels to field IDs - handle None fieldMeta
                label_to_field = {}
                for field in template_data.get('Field', []):
                    field_meta = field.get('fieldMeta') or {}  # Handle None fieldMeta
                    label = field_meta.get('label', '')
                    if label:
                        # If we already have this label, keep the first one unless it's a duplicate
                        if label not in label_to_field:
                            label_to_field[label] = {
                                'id': field['id'],
                                'type': field_meta.get('type', 'text')
                            }
                
                # Get recipient IDs
                recipient_ids = [r['id'] for r in template_data.get('recipients', [])]
                
                return {
                    'success': True,
                    'label_to_field': label_to_field,
                    'recipient_ids': recipient_ids,
                    'template_data': template_data
                }
            else:
                return {'success': False, 'error': f'Template fetch failed: {response.status_code}'}
                
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def create_signature_request(self, directors_data: List[Dict], clickup_task_id: str, 
                               company_name: str, registration_number: str = None, document_content: bytes = None) -> Dict:
        """
        Create e-signature request with director information
        
        Args:
            directors_data (list): List of director dictionaries with name and email
            clickup_task_id (str): ClickUp task ID for tracking
            company_name (str): Company name for the signature request
            document_content (bytes): PDF document content to sign
        
        Returns:
            dict: Result of signature request operation
        """
        
        # Fixed template 5442 - hardcode known field IDs for efficiency
        template_id = '5442'
        
        # Known field IDs from template 5442 analysis
        COMPANY_NAME_FIELD_IDS = [1332978, 1454718]  # Both Company_Name fields
        REGISTRATION_NUMBER_FIELD_ID = 1454719
        RECIPIENT_ID = 373233
        
        try:
            if not self.api_key:
                print("Warning: Documenso API key not configured")
                return {'success': False, 'error': 'No API key configured'}
            
            if not directors_data or len(directors_data) == 0:
                print("Warning: No directors data available for signature request")
                return {'success': False, 'error': 'No directors data'}
            
            # Prepare recipients from directors data using template recipient IDs
            recipients = []
            for i, director in enumerate(directors_data):
                director_name = director.get('name', f'Director {i+1}')
                director_email = director.get('email')
                
                if not director_email:
                    print(f"Warning: No email for director {director_name}, skipping")
                    continue
                
                recipients.append({
                    'id': RECIPIENT_ID,  # Use hardcoded recipient ID
                    'name': director_name,
                    'email': director_email,
                    'signingOrder': 1
                })
            
            if not recipients:
                return {'success': False, 'error': 'No valid director emails found'}
            
            # Create document payload with proper structure from API docs
            payload = {
                'title': f'KYB Signature Request - {company_name}',
                'recipients': recipients,
                'externalId': clickup_task_id,
                'meta': {
                    'subject': 'Swipey Account Setup | Signature Required to Activate Account',
                    'message': f'Hi {{signer.name}},\n\nWe\'re setting up your Swipey account and need your digital signature to complete the process.\n\nPlease review and sign the account setup documents for {company_name}.\nThis will only take a minute and helps us verify your identity for account security.\n\nBest regards,\nThe Swipey Onboarding Team',
                    'redirectUrl': 'https://app.documenso.com/documents',
                    'timezone': 'Asia/Kuala_Lumpur',
                    'dateFormat': 'dd/MM/yyyy hh:mm a',
                    'signingOrder': 'PARALLEL',
                    'distributionMethod': 'EMAIL',
                    'language': 'en',
                    'emailSettings': {
                        'recipientSigned': True,
                        'recipientSigningRequest': True,
                        'recipientRemoved': True,
                        'documentPending': True,
                        'documentCompleted': True,
                        'documentDeleted': True,
                        'ownerDocumentCompleted': True
                    },
                    'webhookUrl': os.getenv('WEBHOOK_BASE_URL', 'https://internal-automation-production.up.railway.app') + '/documenso-webhook'
                },
                'prefillFields': self._build_prefill_fields_fixed(
                    company_name, 
                    registration_number, 
                    COMPANY_NAME_FIELD_IDS, 
                    REGISTRATION_NUMBER_FIELD_ID
                )
            }
            
            
            # If document content is provided, include it
            if document_content:
                # Convert document to base64
                document_base64 = base64.b64encode(document_content).decode('utf-8')
                payload['document'] = {
                    'name': f'{company_name}_KYB_Document.pdf',
                    'content': document_base64,
                    'contentType': 'application/pdf'
                }
            
            print(f"Creating signature request for {company_name} with {len(recipients)} recipients...")
            print(f"ClickUp Task: {clickup_task_id}")
            
            # Send request to Documenso API using the correct generate-document endpoint
            url = f"{self.base_url}/templates/{template_id}/generate-document"
            
            print(f"Using template endpoint: {url}")
            response = requests.post(url, headers=self.headers, json=payload, timeout=30)
            
            
            if response.status_code in [200, 201]:
                response_data = response.json()
                document_id = response_data.get('documentId')  # Correct field name
                api_recipients = response_data.get('recipients', [])
                
                print(f"[OK] Document created successfully!")
                print(f"   Document ID: {document_id}")
                print(f"   Recipients: {[r['name'] for r in recipients]}")
                
                # Now try to send the document via /send endpoint
                if document_id:
                    print(f"[INFO] Attempting to send document via API...")
                    send_url = f"{self.base_url}/documents/{document_id}/send"
                    print(f"[INFO] Sending via: {send_url}")
                    
                    # Use correct send parameters from API documentation
                    send_payload = {
                        'sendEmail': True,
                        'sendCompletionEmails': True
                    }
                    
                    send_response = requests.post(send_url, headers=self.headers, json=send_payload, timeout=30)
                    
                    if send_response.status_code in [200, 201, 204]:
                        print(f"[OK] Document sent successfully!")
                        doc_status = 'SENT'  # Update status for return value
                    else:
                        print(f"[WARNING] Failed to send document: {send_response.status_code} - {send_response.text}")
                        print(f"[INFO] Check Documenso dashboard to manually send: https://app.documenso.com/documents/{document_id}")
                        doc_status = 'DRAFT'  # Assume DRAFT if send failed
                else:
                    print(f"[ERROR] No document ID received")
                    doc_status = 'ERROR'
                
                # Store signature request in database for tracking
                self._store_signature_request(document_id, clickup_task_id, 
                                            company_name, recipients)
                
                # Update ClickUp with signature request sent status
                self._update_clickup_signature_status(clickup_task_id, 'sent', {
                    'document_id': document_id,
                    'recipients_count': len(recipients),
                    'company_name': company_name
                })
                
                return {
                    'success': True,
                    'document_id': document_id,
                    'recipients_count': len(recipients),
                    'recipients': [{'name': r['name'], 'email': r['email']} for r in recipients],
                    'signing_url': response_data.get('signingUrl')
                }
            else:
                error_msg = f"Documenso API error: {response.status_code} - {response.text}"
                print(f"[ERROR] {error_msg}")
                return {'success': False, 'error': error_msg}
                
        except Exception as e:
            print(f"Signature request error: {e}")
            return {'success': False, 'error': str(e)}
    
    def handle_signature_webhook(self, webhook_data: Dict) -> Dict:
        """
        Handle Documenso webhook events for signature status updates
        
        Args:
            webhook_data (dict): Webhook payload from Documenso
            
        Returns:
            dict: Result of webhook processing
        """
        try:
            event_type = webhook_data.get('event')
            payload_data = webhook_data.get('payload', {})
            
            # Documenso uses payload.id for document ID according to official docs
            document_id = payload_data.get('id')
            external_id = payload_data.get('externalId')  # This is our ClickUp task ID
            
            if not document_id:
                print("Warning: No document ID found in webhook payload")
                return {'success': False, 'error': 'No document ID'}
            
            print(f"Processing Documenso webhook: {event_type} for document {document_id}")
            print(f"[DEBUG] External ID (ClickUp Task): {external_id}")
            print(f"[DEBUG] Payload keys: {list(payload_data.keys())}")
            
            # Use external_id from Documenso payload (this is the ClickUp task ID)
            clickup_task_id = external_id
            
            # Critical check: If no external_id, we can't update ClickUp
            if not clickup_task_id:
                print(f"[ERROR] No externalId in webhook payload for event {event_type}")
                print(f"[ERROR] Cannot update ClickUp without task ID - webhook payload: {payload_data}")
                return {'success': False, 'error': 'No ClickUp task ID (externalId) in webhook payload'}
            # Try to get company name from multiple possible sources in webhook
            company_name = 'Unknown Company'
            
            # Check formValues (but ensure it's not None)
            form_values = payload_data.get('formValues')
            if form_values and isinstance(form_values, dict):
                company_name = form_values.get('Company_Name', 'Unknown Company')
            
            # Check prefillFields (but ensure it's not None)  
            elif 'prefillFields' in payload_data and payload_data['prefillFields']:
                for field in payload_data['prefillFields']:
                    if field and field.get('label') == 'Company_Name' or 'company' in field.get('label', '').lower():
                        company_name = field.get('value', 'Unknown Company')
                        break
            
            # Try to extract from document title as fallback
            elif 'title' in payload_data:
                title = payload_data.get('title', '')
                if 'KYB Signature Request -' in title:
                    company_name = title.replace('KYB Signature Request -', '').strip()
                    if company_name:
                        company_name = company_name
                    else:
                        company_name = 'Unknown Company'
            
            # Try to get from database for additional info, but don't fail if not found
            stored_request = self._get_signature_request(str(document_id)) if document_id else None
            
            # Map webhook events to our status system (Documenso uses UPPERCASE format)
            status_mapping = {
                'DOCUMENT_CREATED': 'created',
                'DOCUMENT_SENT': 'sent', 
                'DOCUMENT_OPENED': 'opened',
                'DOCUMENT_SIGNED': 'partially_completed',
                'DOCUMENT_COMPLETED': 'completed',
                'DOCUMENT_REJECTED': 'declined',
                'DOCUMENT_CANCELLED': 'canceled',
                # Keep old lowercase format for backwards compatibility
                'document.created': 'created',
                'document.sent': 'sent',
                'document.opened': 'opened',
                'document.signed': 'partially_completed',
                'document.completed': 'completed',
                'document.rejected': 'declined',
                'document.cancelled': 'canceled'
            }
            
            mapped_status = status_mapping.get(event_type, event_type)
            
            # Debug event mapping
            if event_type in status_mapping:
                print(f"[DEBUG] Mapped event '{event_type}' -> status '{mapped_status}'")
            else:
                print(f"[WARNING] Unknown Documenso event type: '{event_type}' - using as-is: '{mapped_status}'")
                print(f"[DEBUG] Available mappings: {list(status_mapping.keys())}")
            
            # Update database with new status
            self._update_signature_request_status(document_id, mapped_status, webhook_data)
            
            # Update ClickUp with signature status
            additional_info = {
                'document_id': document_id,
                'company_name': company_name,
                'event_type': event_type,
                'webhook_data': webhook_data
            }
            
            self._update_clickup_signature_status(clickup_task_id, mapped_status, additional_info)
            
            # Update Consent & Authorisation custom field for relevant Documenso states
            if mapped_status in ['sent', 'opened', 'completed', 'declined']:
                print(f"Updating Consent & Authorisation field to: {mapped_status}")
                self._update_consent_field(clickup_task_id, mapped_status, additional_info)
            
            # Download and attach signed document to ClickUp when completed
            if mapped_status == 'completed':
                print(f"Document completed! Downloading signed document {document_id}...")
                self._download_and_attach_signed_document(document_id, clickup_task_id, company_name)
            
            print(f"[OK] Webhook processed: {event_type} -> {mapped_status} for task {clickup_task_id}")
            
            return {
                'success': True,
                'event_type': event_type,
                'mapped_status': mapped_status,
                'document_id': document_id,
                'clickup_task_id': clickup_task_id
            }
            
        except Exception as e:
            print(f"Webhook processing error: {e}")
            return {'success': False, 'error': str(e)}
    
    def get_templates_list(self) -> Dict:
        """Get list of available templates"""
        try:
            if not self.api_key:
                return {'success': False, 'error': 'No API key configured'}
            
            url = f"{self.base_url}/templates"
            response = requests.get(url, headers=self.headers, timeout=10)
            
            if response.status_code == 200:
                return {'success': True, 'data': response.json()}
            else:
                return {'success': False, 'error': f"API error: {response.status_code}", 'response': response.text}
                
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def get_template_info(self, template_id: str) -> Dict:
        """Get template information including recipients and fields"""
        try:
            if not self.api_key:
                return {'success': False, 'error': 'No API key configured'}
            
            url = f"{self.base_url}/templates/{template_id}"
            response = requests.get(url, headers=self.headers, timeout=10)
            
            if response.status_code == 200:
                return {'success': True, 'data': response.json()}
            else:
                return {'success': False, 'error': f"API error: {response.status_code}", 'response': response.text}
                
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def send_document(self, document_id: str) -> Dict:
        """Send document to recipients (move from DRAFT to SENT)"""
        try:
            if not self.api_key:
                return {'success': False, 'error': 'No API key configured'}
            
            # Try common send endpoints
            possible_endpoints = [
                f"{self.base_url}/documents/{document_id}/send",
                f"{self.base_url}/documents/{document_id}/publish",
                f"{self.base_url}/documents/{document_id}/trigger"
            ]
            
            for endpoint in possible_endpoints:
                print(f"Trying send endpoint: {endpoint}")
                response = requests.post(endpoint, headers=self.headers, timeout=10)
                
                if response.status_code in [200, 201, 204]:
                    print(f"[OK] Document sent via: {endpoint}")
                    return {'success': True, 'endpoint': endpoint, 'response': response.json() if response.text else {}}
                else:
                    print(f"[FAILED] {endpoint}: {response.status_code} - {response.text}")
            
            return {'success': False, 'error': 'No working send endpoint found'}
                
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def get_document_status(self, document_id: str) -> Dict:
        """Get current status of signature document"""
        try:
            if not self.api_key:
                return {'success': False, 'error': 'No API key configured'}
            
            url = f"{self.base_url}/documents/{document_id}"
            response = requests.get(url, headers=self.headers, timeout=10)
            
            if response.status_code == 200:
                return {'success': True, 'data': response.json()}
            else:
                return {'success': False, 'error': f"API error: {response.status_code}"}
                
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def download_completed_document(self, document_id: str) -> Dict:
        """Download completed signed document from Documenso"""
        try:
            if not self.api_key:
                return {'success': False, 'error': 'No API key configured'}
            
            # Try common download endpoints for Documenso
            possible_endpoints = [
                f"{self.base_url}/documents/{document_id}/download",
                f"{self.base_url}/documents/{document_id}/download/completed",
                f"{self.base_url}/documents/{document_id}/pdf",
                f"{self.base_url}/documents/{document_id}/certificate"
            ]
            
            for endpoint in possible_endpoints:
                print(f"[DEBUG] Trying download endpoint: {endpoint}")
                response = requests.get(endpoint, headers=self.headers, timeout=30)
                
                print(f"[DEBUG] Response status: {response.status_code}")
                print(f"[DEBUG] Response headers: {dict(response.headers)}")
                print(f"[DEBUG] Response content size: {len(response.content)}")
                print(f"[DEBUG] Response content preview: {response.content[:200]}")
                
                if response.status_code == 200:
                    # Check if we got actual PDF content
                    if response.content.startswith(b'%PDF'):
                        return {
                            'success': True, 
                            'content': response.content,
                            'content_type': response.headers.get('content-type', 'application/pdf'),
                            'filename': f'signed_document_{document_id}.pdf',
                            'endpoint_used': endpoint
                        }
                    # Check if we got a JSON response with downloadUrl (Documenso format)
                    elif response.headers.get('content-type') == 'application/json':
                        try:
                            import json
                            json_response = json.loads(response.content.decode())
                            download_url = json_response.get('downloadUrl')
                            
                            if download_url:
                                print(f"[INFO] Got pre-signed download URL, fetching actual PDF...")
                                # Download from the pre-signed URL
                                pdf_response = requests.get(download_url, timeout=30)
                                
                                if pdf_response.status_code == 200 and pdf_response.content.startswith(b'%PDF'):
                                    return {
                                        'success': True, 
                                        'content': pdf_response.content,
                                        'content_type': pdf_response.headers.get('content-type', 'application/pdf'),
                                        'filename': f'signed_document_{document_id}.pdf',
                                        'endpoint_used': endpoint,
                                        'download_url': download_url
                                    }
                                else:
                                    print(f"[WARNING] Failed to download PDF from pre-signed URL: {pdf_response.status_code}")
                            
                        except (json.JSONDecodeError, Exception) as e:
                            print(f"[WARNING] Failed to parse JSON response: {e}")
                        
                        print(f"[WARNING] Got JSON response without valid downloadUrl from {endpoint}")
                        continue
                    else:
                        print(f"[WARNING] Got unexpected content type from {endpoint}: {response.headers.get('content-type')}")
                        continue
                else:
                    print(f"[WARNING] {endpoint} failed: {response.status_code} - {response.text[:200]}")
            
            return {'success': False, 'error': 'No working download endpoint found'}
                
        except Exception as e:
            print(f"Document download error: {e}")
            return {'success': False, 'error': str(e)}
    
    def _store_signature_request(self, document_id: str, clickup_task_id: str, 
                                company_name: str, recipients: List[Dict]):
        """Store signature request in database for tracking"""
        try:
            if not self.supabase:
                print("Warning: Supabase not configured, skipping signature request storage")
                return
            
            request_data = {
                'signature_request_id': document_id,  # Using document_id as the main identifier
                'clickup_task_id': clickup_task_id,
                'company_name': company_name,
                'recipients': recipients,  # JSONB array
                'status': 'sent',
                'created_at': datetime.now().isoformat(),
                'updated_at': datetime.now().isoformat(),
                'service_provider': 'documenso'
            }
            
            response = self.supabase.table('signature_requests').insert(request_data).execute()
            print(f"[OK] Signature request stored in database: {document_id}")
            
        except Exception as e:
            print(f"Failed to store signature request: {e}")
    
    def _get_signature_request(self, document_id: str) -> Optional[Dict]:
        """Get signature request from database"""
        try:
            if not self.supabase:
                return None
            
            response = self.supabase.table('signature_requests').select('*').eq('signature_request_id', document_id).execute()
            return response.data[0] if response.data else None
            
        except Exception as e:
            print(f"Failed to get signature request: {e}")
            return None
    
    def _update_signature_request_status(self, document_id: str, status: str, webhook_data: Dict):
        """Update signature request status in database"""
        try:
            if not self.supabase:
                return
            
            update_data = {
                'status': status,
                'updated_at': datetime.now().isoformat(),
                'last_webhook_data': webhook_data  # Store latest webhook data
            }
            
            response = self.supabase.table('signature_requests').update(update_data).eq('signature_request_id', document_id).execute()
            print(f"[OK] Updated signature request status: {document_id} -> {status}")
            
        except Exception as e:
            print(f"Failed to update signature request status: {e}")
    
    def _update_clickup_signature_status(self, clickup_task_id: str, status: str, additional_info: Dict):
        """Update ClickUp task with signature status"""
        try:
            from .clickup_service import update_clickup_task_status
            
            # Create status comment for ClickUp
            status_messages = {
                'created': 'E-signature document has been created',
                'sent': 'E-signature request has been sent to directors',
                'opened': 'E-signature document has been opened by a director', 
                'partially_completed': 'Some directors have signed the document',
                'completed': 'All directors have completed the e-signature process',
                'declined': 'E-signature request was declined/rejected',
                'canceled': 'E-signature request was canceled'
            }
            
            message = status_messages.get(status, f'E-signature status updated: {status}')
            
            print(f"Updating ClickUp task {clickup_task_id} with signature status: {status}")
            
            result = update_clickup_task_status(
                task_id=clickup_task_id,
                status_type='consent_status',
                status_value=status,
                additional_info={
                    'message': message,
                    'document_id': additional_info.get('document_id'),
                    'company_name': additional_info.get('company_name'),
                    'recipients_count': additional_info.get('recipients_count')
                }
            )
            
            if result.get('success'):
                print(f"[OK] ClickUp updated with signature status: {status}")
            else:
                print(f"[WARNING] ClickUp signature status update failed: {result.get('error')}")
                
        except Exception as e:
            print(f"ClickUp signature status update error (non-critical): {e}")
    
    def _update_consent_field(self, clickup_task_id: str, consent_status: str, additional_info: Dict):
        """Update the Consent & Authorisation custom field based on Documenso webhook state"""
        try:
            from .clickup_service import update_clickup_task_status
            
            print(f"Updating Consent & Authorisation field to '{consent_status}' for task {clickup_task_id}")
            
            result = update_clickup_task_status(
                task_id=clickup_task_id,
                status_type='consent_status',
                status_value=consent_status,
                additional_info={
                    'company_name': additional_info.get('company_name'),
                    'document_id': additional_info.get('document_id'),
                    'event_type': additional_info.get('event_type')
                }
            )
            
            if result.get('success'):
                print(f"[OK] Consent & Authorisation field updated to '{consent_status}' for task {clickup_task_id}")
            else:
                print(f"[WARNING] Consent field update failed: {result.get('error')}")
                
        except Exception as e:
            print(f"Consent field update error (non-critical): {e}")
    
    def _download_and_attach_signed_document(self, document_id: str, clickup_task_id: str, company_name: str):
        """Download signed document and attach it to ClickUp task"""
        try:
            print(f"[INFO] Downloading signed document {document_id} for task {clickup_task_id}")
            
            # Download the completed document
            download_result = self.download_completed_document(document_id)
            
            if not download_result.get('success'):
                print(f"[ERROR] Failed to download document: {download_result.get('error')}")
                return
            
            # Import ClickUp service for signed document attachment
            from .clickup_service import attach_signed_document_content_to_task
            
            # Prepare file info for ClickUp attachment
            file_content = download_result['content']
            filename = f"Signed_Consent_Authorization_{company_name}_{document_id}.pdf"
            
            print(f"[INFO] Attaching signed document to ClickUp task: {filename}")
            
            # Attach to ClickUp task with Signed Consent Form field update
            attachment_result = attach_signed_document_content_to_task(
                clickup_task_id, 
                file_content, 
                filename,
                comment=f"✅ Signed consent and authorization documents from {company_name} (Documenso Document ID: {document_id})"
            )
            
            if attachment_result.get('success'):
                print(f"[OK] Signed document attached to ClickUp task {clickup_task_id}")
            else:
                print(f"[WARNING] Failed to attach signed document: {attachment_result.get('error')}")
                
        except Exception as e:
            print(f"Signed document attachment error (non-critical): {e}")
    
    def _build_prefill_fields_fixed(self, company_name: str, registration_number: str, 
                                   company_name_field_ids: List[int], registration_number_field_id: int) -> List[Dict]:
        """Build prefillFields array using fixed field IDs for template 5442"""
        prefill_fields = []
        
        # Fill ALL Company_Name fields if value exists
        if company_name:
            for field_id in company_name_field_ids:
                prefill_fields.append({
                    'id': field_id,
                    'type': 'text',
                    'value': str(company_name)
                })
                print(f"[DEBUG] Filled Company_Name field ID {field_id} = '{company_name}'")
        else:
            print(f"[DEBUG] Company name is empty, skipping Company_Name fields")
        
        # Fill Registration_Number field if value exists
        if registration_number:
            prefill_fields.append({
                'id': registration_number_field_id,
                'type': 'text',
                'value': str(registration_number)
            })
            print(f"[DEBUG] Filled Registration_Number field ID {registration_number_field_id} = '{registration_number}'")
        else:
            print(f"[DEBUG] Registration number is empty, skipping Registration_Number field")
        
        print(f"[DEBUG] Total prefill fields created: {len(prefill_fields)}")
        return prefill_fields
    
    def _build_prefill_fields(self, label_to_field: Dict, company_name: str, registration_number: str = None) -> List[Dict]:
        """Build prefillFields array using correct field IDs and types - LEGACY METHOD"""
        prefill_fields = []
        
        # Map our data to template fields
        field_mappings = {
            'Company_Name': company_name,
            'Registration_Number': registration_number or ''
        }
        
        for label, value in field_mappings.items():
            if label in label_to_field and value:  # Only add if field exists and value is not empty
                field_info = label_to_field[label]
                prefill_fields.append({
                    'id': field_info['id'],
                    'type': field_info['type'],
                    'value': str(value)
                })
                print(f"[DEBUG] Mapped {label} -> field ID {field_info['id']} (type: {field_info['type']}) = '{value}'")
            else:
                print(f"[WARNING] Field '{label}' not found in template or value is empty")
        
        return prefill_fields


# Convenience functions for easy import
def send_signature_request_to_directors(directors_data: List[Dict], clickup_task_id: str, 
                                      company_name: str, registration_number: str = None, document_content: bytes = None) -> Dict:
    """
    Convenience function to send e-signature request to directors
    
    Args:
        directors_data (list): List of director dictionaries
        clickup_task_id (str): ClickUp task ID
        company_name (str): Company name
        document_content (bytes): PDF document content
    
    Returns:
        dict: Result of signature request
    """
    service = DocumensoService()
    return service.create_signature_request(
        directors_data, clickup_task_id, company_name, registration_number, document_content
    )


def handle_documenso_webhook(webhook_data: Dict) -> Dict:
    """
    Convenience function to handle Documenso webhooks
    
    Args:
        webhook_data (dict): Webhook payload
        
    Returns:
        dict: Result of webhook processing
    """
    service = DocumensoService()
    return service.handle_signature_webhook(webhook_data)