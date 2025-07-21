"""
Documenso E-Signature Service - Manages e-signature workflows
This module handles document creation, signing, and status tracking for KYB workflows.
"""

import os
import requests
import json
from datetime import datetime
from typing import Dict, List, Optional


class DocumensoService:
    """Dropbox Sign API service for e-signature workflows"""
    
    def __init__(self, api_key=None, supabase_client=None):
        self.api_key = api_key or os.getenv('DROPBOX_SIGN_API_KEY')
        self.supabase = supabase_client
        self.base_url = "https://api.hellosign.com/v3"
        self.headers = {
            'Authorization': f'Basic {self.api_key}',
            'Content-Type': 'application/json'
        }
    
    def send_signature_request_from_template(self, template_id: str, directors_data: List[Dict], 
                                           clickup_task_id: str, company_name: str) -> Dict:
        """
        Send e-signature request using template with director information
        
        Args:
            template_id (str): Dropbox Sign template ID
            directors_data (list): List of director dictionaries with name and email
            clickup_task_id (str): ClickUp task ID for tracking
            company_name (str): Company name for the signature request
        
        Returns:
            dict: Result of signature request operation
        """
        try:
            if not self.api_key:
                print("Warning: Dropbox Sign API key not configured")
                return {'success': False, 'error': 'No API key configured'}
            
            if not directors_data or len(directors_data) == 0:
                print("Warning: No directors data available for signature request")
                return {'success': False, 'error': 'No directors data'}
            
            # Prepare signers from directors data
            signers = []
            for i, director in enumerate(directors_data):
                director_name = director.get('name', f'Director {i+1}')
                director_email = director.get('email')
                
                if not director_email:
                    print(f"Warning: No email for director {director_name}, skipping")
                    continue
                
                signers.append({
                    'name': director_name,
                    'email_address': director_email,
                    'role': f'Director_{i+1}'  # Map to template roles
                })
            
            if not signers:
                return {'success': False, 'error': 'No valid director emails found'}
            
            # Prepare signature request payload
            payload = {
                'template_id': template_id,
                'subject': f'KYB Signature Request - {company_name}',
                'message': f'Please review and sign the KYB documents for {company_name}.',
                'signers': signers,
                'custom_fields': [
                    {
                        'name': 'company_name',
                        'value': company_name
                    },
                    {
                        'name': 'clickup_task_id', 
                        'value': clickup_task_id
                    }
                ],
                'metadata': {
                    'clickup_task_id': clickup_task_id,
                    'company_name': company_name,
                    'source': 'kyb_automation'
                }
            }
            
            print(f"Sending signature request for {company_name} to {len(signers)} directors...")
            print(f"Template ID: {template_id}")
            print(f"ClickUp Task: {clickup_task_id}")
            
            # Send request to Dropbox Sign API
            url = f"{self.base_url}/signature_request/send_with_template"
            response = requests.post(url, headers=self.headers, json=payload, timeout=30)
            
            if response.status_code == 200:
                response_data = response.json()
                signature_request_id = response_data.get('signature_request', {}).get('signature_request_id')
                
                print(f"[OK] Signature request sent successfully!")
                print(f"   Signature Request ID: {signature_request_id}")
                print(f"   Signers: {[s['name'] for s in signers]}")
                
                # Store signature request in database for tracking
                self._store_signature_request(signature_request_id, clickup_task_id, 
                                            company_name, signers, template_id)
                
                # Update ClickUp with signature request sent status
                self._update_clickup_signature_status(clickup_task_id, 'sent', {
                    'signature_request_id': signature_request_id,
                    'signers_count': len(signers),
                    'template_id': template_id
                })
                
                return {
                    'success': True,
                    'signature_request_id': signature_request_id,
                    'signers_count': len(signers),
                    'signers': [{'name': s['name'], 'email': s['email_address']} for s in signers]
                }
            else:
                error_msg = f"Dropbox Sign API error: {response.status_code} - {response.text}"
                print(f"[ERROR] {error_msg}")
                return {'success': False, 'error': error_msg}
                
        except Exception as e:
            print(f"Signature request error: {e}")
            return {'success': False, 'error': str(e)}
    
    def handle_signature_webhook(self, webhook_data: Dict) -> Dict:
        """
        Handle Dropbox Sign webhook events for signature status updates
        
        Args:
            webhook_data (dict): Webhook payload from Dropbox Sign
            
        Returns:
            dict: Result of webhook processing
        """
        try:
            event_type = webhook_data.get('event', {}).get('event_type')
            signature_request = webhook_data.get('signature_request', {})
            signature_request_id = signature_request.get('signature_request_id')
            
            if not signature_request_id:
                print("Warning: No signature_request_id in webhook data")
                return {'success': False, 'error': 'No signature_request_id'}
            
            print(f"Processing Dropbox Sign webhook: {event_type} for {signature_request_id}")
            
            # Get stored signature request info
            stored_request = self._get_signature_request(signature_request_id)
            if not stored_request:
                print(f"Warning: Signature request {signature_request_id} not found in database")
                return {'success': False, 'error': 'Signature request not found'}
            
            clickup_task_id = stored_request.get('clickup_task_id')
            company_name = stored_request.get('company_name')
            
            # Map webhook events to our status system
            status_mapping = {
                'signature_request_sent': 'sent',
                'signature_request_viewed': 'opened', 
                'signature_request_signed': 'partially_completed',
                'signature_request_all_signed': 'completed',
                'signature_request_declined': 'declined',
                'signature_request_canceled': 'canceled'
            }
            
            mapped_status = status_mapping.get(event_type, event_type)
            
            # Update database with new status
            self._update_signature_request_status(signature_request_id, mapped_status, webhook_data)
            
            # Update ClickUp with signature status
            additional_info = {
                'signature_request_id': signature_request_id,
                'company_name': company_name,
                'event_type': event_type,
                'webhook_data': webhook_data
            }
            
            self._update_clickup_signature_status(clickup_task_id, mapped_status, additional_info)
            
            print(f"[OK] Webhook processed: {event_type} -> {mapped_status} for task {clickup_task_id}")
            
            return {
                'success': True,
                'event_type': event_type,
                'mapped_status': mapped_status,
                'signature_request_id': signature_request_id,
                'clickup_task_id': clickup_task_id
            }
            
        except Exception as e:
            print(f"Webhook processing error: {e}")
            return {'success': False, 'error': str(e)}
    
    def _store_signature_request(self, signature_request_id: str, clickup_task_id: str, 
                                company_name: str, signers: List[Dict], template_id: str):
        """Store signature request in database for tracking"""
        try:
            if not self.supabase:
                print("Warning: Supabase not configured, skipping signature request storage")
                return
            
            request_data = {
                'signature_request_id': signature_request_id,
                'clickup_task_id': clickup_task_id,
                'company_name': company_name,
                'template_id': template_id,
                'signers': signers,  # JSONB array
                'status': 'sent',
                'created_at': datetime.now().isoformat(),
                'updated_at': datetime.now().isoformat()
            }
            
            response = self.supabase.table('signature_requests').insert(request_data).execute()
            print(f"[OK] Signature request stored in database: {signature_request_id}")
            
        except Exception as e:
            print(f"Failed to store signature request: {e}")
    
    def _get_signature_request(self, signature_request_id: str) -> Optional[Dict]:
        """Get signature request from database"""
        try:
            if not self.supabase:
                return None
            
            response = self.supabase.table('signature_requests').select('*').eq('signature_request_id', signature_request_id).execute()
            return response.data[0] if response.data else None
            
        except Exception as e:
            print(f"Failed to get signature request: {e}")
            return None
    
    def _update_signature_request_status(self, signature_request_id: str, status: str, webhook_data: Dict):
        """Update signature request status in database"""
        try:
            if not self.supabase:
                return
            
            update_data = {
                'status': status,
                'updated_at': datetime.now().isoformat(),
                'last_webhook_data': webhook_data  # Store latest webhook data
            }
            
            response = self.supabase.table('signature_requests').update(update_data).eq('signature_request_id', signature_request_id).execute()
            print(f"[OK] Updated signature request status: {signature_request_id} -> {status}")
            
        except Exception as e:
            print(f"Failed to update signature request status: {e}")
    
    def _update_clickup_signature_status(self, clickup_task_id: str, status: str, additional_info: Dict):
        """Update ClickUp task with signature status"""
        try:
            from .clickup_service import update_clickup_task_status
            
            # Create status comment for ClickUp
            status_messages = {
                'sent': 'E-signature request has been sent to directors',
                'opened': 'E-signature document has been opened by a director', 
                'partially_completed': 'Some directors have signed the document',
                'completed': 'All directors have completed the e-signature process',
                'declined': 'E-signature request was declined',
                'canceled': 'E-signature request was canceled'
            }
            
            message = status_messages.get(status, f'E-signature status updated: {status}')
            
            print(f"Updating ClickUp task {clickup_task_id} with signature status: {status}")
            
            result = update_clickup_task_status(
                task_id=clickup_task_id,
                status_type='signature_status',
                status_value=status,
                additional_info={
                    'message': message,
                    'signature_request_id': additional_info.get('signature_request_id'),
                    'company_name': additional_info.get('company_name'),
                    'signers_count': additional_info.get('signers_count')
                }
            )
            
            if result.get('success'):
                print(f"[OK] ClickUp updated with signature status: {status}")
            else:
                print(f"[WARNING] ClickUp signature status update failed: {result.get('error')}")
                
        except Exception as e:
            print(f"ClickUp signature status update error (non-critical): {e}")
    
    def get_signature_request_status(self, signature_request_id: str) -> Dict:
        """Get current status of signature request"""
        try:
            if not self.api_key:
                return {'success': False, 'error': 'No API key configured'}
            
            url = f"{self.base_url}/signature_request/{signature_request_id}"
            response = requests.get(url, headers=self.headers, timeout=10)
            
            if response.status_code == 200:
                return {'success': True, 'data': response.json()}
            else:
                return {'success': False, 'error': f"API error: {response.status_code}"}
                
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def list_templates(self) -> Dict:
        """List available Dropbox Sign templates"""
        try:
            if not self.api_key:
                return {'success': False, 'error': 'No API key configured'}
            
            url = f"{self.base_url}/template/list"
            response = requests.get(url, headers=self.headers, timeout=10)
            
            if response.status_code == 200:
                templates_data = response.json()
                templates = templates_data.get('templates', [])
                
                print(f"Found {len(templates)} Dropbox Sign templates:")
                for template in templates:
                    print(f"  - {template.get('title')} (ID: {template.get('template_id')})")
                
                return {'success': True, 'templates': templates}
            else:
                return {'success': False, 'error': f"API error: {response.status_code}"}
                
        except Exception as e:
            return {'success': False, 'error': str(e)}


# Convenience functions for easy import
def send_signature_request_to_directors(template_id: str, directors_data: List[Dict], 
                                      clickup_task_id: str, company_name: str) -> Dict:
    """
    Convenience function to send e-signature request to directors
    
    Args:
        template_id (str): Dropbox Sign template ID
        directors_data (list): List of director dictionaries
        clickup_task_id (str): ClickUp task ID
        company_name (str): Company name
    
    Returns:
        dict: Result of signature request
    """
    service = DropboxSignService()
    return service.send_signature_request_from_template(
        template_id, directors_data, clickup_task_id, company_name
    )


def handle_dropbox_sign_webhook(webhook_data: Dict) -> Dict:
    """
    Convenience function to handle Dropbox Sign webhooks
    
    Args:
        webhook_data (dict): Webhook payload
        
    Returns:
        dict: Result of webhook processing
    """
    service = DropboxSignService()
    return service.handle_signature_webhook(webhook_data)