"""
ClickUp Service - Manages task updates and status notifications
This module handles all ClickUp API interactions for status updates.
"""

import os
import requests
import json
from datetime import datetime


class ClickUpService:
    """ClickUp API service for task updates"""
    
    def __init__(self, api_token=None):
        self.api_token = api_token or os.getenv('CLICKUP_API_TOKEN')
        self.base_url = "https://api.clickup.com/api/v2"
        self.headers = {
            'Authorization': self.api_token,
            'Content-Type': 'application/json'
        }
    
    def update_task_status(self, task_id, status_type, status_value, additional_info=None):
        """
        Update task with OCR or KYB status information
        
        Args:
            task_id (str): ClickUp task ID
            status_type (str): 'ocr_status' or 'kyb_status'
            status_value (str): Status value (e.g., 'completed', 'failed', 'documents_pending_review')
            additional_info (dict): Optional additional information to include
        """
        try:
            if not self.api_token:
                print("Warning: ClickUp API token not configured")
                return {'success': False, 'error': 'No API token'}
            
            # Create status comment based on type
            if status_type == 'ocr_status':
                comment_text = self._create_ocr_status_comment(status_value, additional_info)
            elif status_type == 'kyb_status':
                comment_text = self._create_kyb_status_comment(status_value, additional_info)
            else:
                comment_text = f"**{status_type.upper()}**: {status_value}"
            
            # Add comment to task
            result = self._add_comment_to_task(task_id, comment_text)
            
            # Update task custom fields if available
            self._update_custom_fields(task_id, status_type, status_value)
            
            return result
            
        except Exception as e:
            print(f"ClickUp update error: {e}")
            return {'success': False, 'error': str(e)}
    
    def _create_ocr_status_comment(self, status_value, additional_info):
        """Create OCR status comment"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        if status_value == 'processing':
            emoji = '[PROCESSING]'
            title = 'OCR Processing Started'
            message = 'Document OCR extraction has begun. Please wait for completion.'
        elif status_value == 'completed':
            emoji = '[COMPLETED]'
            title = 'OCR Processing Complete'
            message = 'Document data has been successfully extracted!'
        elif status_value == 'failed':
            emoji = '[FAILED]'
            title = 'OCR Processing Failed'
            message = 'Document OCR extraction encountered an error. Manual review required.'
        else:
            emoji = '[STATUS]'
            title = f'OCR Status: {status_value}'
            message = f'OCR status has been updated to: {status_value}'
        
        comment = f"""
{emoji} **{title}**

**Status:** {status_value.upper()}
**Timestamp:** {timestamp}

{message}
"""
        
        # Add extracted data if available
        if additional_info and status_value == 'completed':
            extracted_data = additional_info.get('extracted_data', {})
            if extracted_data:
                comment += "\n**EXTRACTED INFORMATION:**\n"
                if extracted_data.get('company_name'):
                    comment += f"- **Company:** {extracted_data['company_name']}\n"
                if extracted_data.get('registration_number'):
                    comment += f"- **Registration:** {extracted_data['registration_number']}\n"
                if extracted_data.get('incorporation_date'):
                    comment += f"- **Incorporation:** {extracted_data['incorporation_date']}\n"
                if extracted_data.get('directors'):
                    directors = extracted_data['directors']
                    comment += f"- **Directors:** {len(directors)} found\n"
                    for director in directors[:2]:  # Show first 2 directors
                        comment += f"  - {director.get('name', 'Unknown')}\n"
                    if len(directors) > 2:
                        comment += f"  - ... and {len(directors) - 2} more\n"
        
        comment += "\n*Automated update from KYB system*"
        return comment
    
    def _create_kyb_status_comment(self, status_value, additional_info):
        """Create KYB status comment"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        status_config = {
            'pending_documents': {
                'emoji': '[PENDING]',
                'title': 'KYB: Awaiting Documents',
                'message': 'Customer has been notified. Waiting for document upload.'
            },
            'documents_pending_review': {
                'emoji': '[REVIEW]',
                'title': 'KYB: Documents Under Review',
                'message': 'Documents uploaded successfully. Ready for manual review.'
            },
            'kyb_passed': {
                'emoji': '[APPROVED]',
                'title': 'KYB: APPROVED',
                'message': 'Customer KYB verification has been completed successfully!'
            },
            'kyb_completed': {
                'emoji': '[COMPLETED]',
                'title': 'KYB: COMPLETED',
                'message': 'Customer KYB verification has been completed successfully!'
            },
            'kyb_failed': {
                'emoji': '[REJECTED]',
                'title': 'KYB: REJECTED',
                'message': 'KYB verification failed. Customer may need to resubmit documents.'
            },
            'documents_processing': {
                'emoji': '[PROCESSING]',
                'title': 'KYB: Processing Documents',
                'message': 'Documents are being processed and validated.'
            }
        }
        
        config = status_config.get(status_value, {
            'emoji': '[STATUS]',
            'title': f'KYB Status: {status_value}',
            'message': f'KYB status updated to: {status_value}'
        })
        
        comment = f"""
{config['emoji']} **{config['title']}**

**Status:** {status_value.upper()}
**Timestamp:** {timestamp}

{config['message']}
"""
        
        # Add document info if available
        if additional_info:
            if additional_info.get('document_count'):
                comment += f"\n**Documents:** {additional_info['document_count']} uploaded"
            if additional_info.get('customer_email'):
                comment += f"\n**Customer:** {additional_info['customer_email']}"
        
        comment += "\n\n*Automated update from KYB system*"
        return comment
    
    def _add_comment_to_task(self, task_id, comment_text):
        """Add comment to ClickUp task"""
        try:
            url = f"{self.base_url}/task/{task_id}/comment"
            payload = {
                'comment_text': comment_text,
                'notify_all': False  # Don't spam entire team
            }
            
            response = requests.post(url, headers=self.headers, json=payload, timeout=30)
            
            if response.status_code == 200:
                print(f"[OK] Successfully added comment to ClickUp task {task_id}")
                return {'success': True, 'comment_id': response.json().get('id')}
            else:
                error_msg = f"ClickUp API error: {response.status_code} - {response.text}"
                print(f"[ERROR] {error_msg}")
                return {'success': False, 'error': error_msg}
                
        except Exception as e:
            error_msg = f"Failed to add comment: {str(e)}"
            print(f"[ERROR] {error_msg}")
            return {'success': False, 'error': error_msg}
    
    def _update_custom_fields(self, task_id, status_type, status_value):
        """Update custom fields for OCR and KYB status"""
        try:
            # Get task to find custom field IDs
            task_info = self._get_task_with_custom_fields(task_id)
            if not task_info.get('success'):
                print(f"Could not get task info for custom fields: {task_info.get('error')}")
                return
            
            custom_fields = task_info.get('custom_fields', [])
            field_id = None
            
            # Find the correct custom field based on status type
            field_name = "OCR Status" if status_type == 'ocr_status' else "KYB Status"
            
            for field in custom_fields:
                if field.get('name', '').lower() in [field_name.lower(), status_type.lower()]:
                    field_id = field.get('id')
                    break
            
            if not field_id:
                print(f"Custom field '{field_name}' not found in task {task_id}")
                return
            
            # Get the correct value for dropdown fields
            field_value = self._get_dropdown_value(custom_fields, field_id, status_value)
            
            # Update the custom field
            url = f"{self.base_url}/task/{task_id}/field/{field_id}"
            payload = {
                'value': field_value
            }
            
            response = requests.post(url, headers=self.headers, json=payload, timeout=10)
            
            if response.status_code == 200:
                print(f"[OK] Updated ClickUp custom field '{field_name}' to '{status_value}'")
                return {'success': True}
            else:
                print(f"[WARNING] Custom field update failed: {response.status_code} - {response.text}")
                return {'success': False, 'error': response.text}
                
        except Exception as e:
            print(f"Custom field update failed (non-critical): {e}")
            return {'success': False, 'error': str(e)}
    
    def _get_dropdown_value(self, custom_fields, field_id, status_value):
        """Get the correct dropdown value (index or UUID) for a given status"""
        try:
            # Find the field by ID
            target_field = None
            for field in custom_fields:
                if field.get('id') == field_id:
                    target_field = field
                    break
            
            if not target_field:
                print(f"Field {field_id} not found in custom fields")
                return status_value  # Fallback to original value
            
            # Check if it's a dropdown field
            if target_field.get('type') != 'drop_down':
                return status_value  # Not a dropdown, return original value
            
            # Get dropdown options
            type_config = target_field.get('type_config', {})
            options = type_config.get('options', [])
            
            if not options:
                print(f"No dropdown options found for field {field_id}")
                return status_value
            
            # Map our status values to ClickUp dropdown names
            status_mapping = {
                # OCR Status mappings
                'pending': 'pending',
                'processing': 'processing', 
                'completed': 'completed',
                'failed': 'failed',
                
                # KYB Status mappings  
                'pending_documents': 'pending documents',
                'documents_pending_review': 'documents pending review',
                'kyb_completed': 'Completed',
                'kyb_failed': 'Failed'
            }
            
            # Get the ClickUp dropdown name for our status
            clickup_name = status_mapping.get(status_value, status_value)
            
            # Find matching option by name
            for i, option in enumerate(options):
                option_name = option.get('name', '').lower()
                if option_name == clickup_name.lower():
                    # Return the index (ClickUp prefers index over UUID)
                    print(f"Mapping '{status_value}' to dropdown index {i} ('{option.get('name')}')")
                    return i
            
            # If no exact match, try partial matching
            for i, option in enumerate(options):
                option_name = option.get('name', '').lower()
                if clickup_name.lower() in option_name or option_name in clickup_name.lower():
                    print(f"Partial match: '{status_value}' to dropdown index {i} ('{option.get('name')}')")
                    return i
            
            print(f"No matching dropdown option found for '{status_value}' in field {field_id}")
            print(f"Available options: {[opt.get('name') for opt in options]}")
            return 0  # Default to first option
            
        except Exception as e:
            print(f"Error getting dropdown value: {e}")
            return status_value  # Fallback to original value
    
    def _get_task_with_custom_fields(self, task_id):
        """Get task with custom fields information"""
        try:
            url = f"{self.base_url}/task/{task_id}?include_subtasks=false"
            response = requests.get(url, headers=self.headers, timeout=10)
            
            if response.status_code == 200:
                task_data = response.json()
                return {
                    'success': True,
                    'custom_fields': task_data.get('custom_fields', [])
                }
            else:
                return {'success': False, 'error': f"HTTP {response.status_code}"}
                
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def attach_document_to_task(self, task_id, file_path, filename):
        """Attach a document to ClickUp task and update SSM document custom field"""
        try:
            if not self.api_token:
                print("Warning: ClickUp API token not configured")
                return {'success': False, 'error': 'No API token'}
            
            # Step 1: Upload file as attachment
            attachment_result = self._upload_file_attachment(task_id, file_path, filename)
            
            if not attachment_result.get('success'):
                return attachment_result
            
            attachment_data = attachment_result.get('attachment_data')
            attachment_url = attachment_result.get('attachment_url')
            
            # Step 2: Update SSM Doc [upload] custom field with attachment URL
            ssm_field_result = self._update_ssm_doc_url_field(task_id, attachment_url, filename)
            
            return {
                'success': True,
                'attachment_url': attachment_url,
                'ssm_field_updated': ssm_field_result.get('success', False)
            }
            
        except Exception as e:
            print(f"Document attachment error: {e}")
            return {'success': False, 'error': str(e)}
    
    def _upload_file_attachment(self, task_id, file_path, filename):
        """Upload file as attachment to ClickUp task"""
        try:
            url = f"{self.base_url}/task/{task_id}/attachment"
            
            # Prepare file for upload
            with open(file_path, 'rb') as file:
                files = {
                    'attachment': (filename, file, 'application/pdf')
                }
                
                # Use different headers for file upload (no Content-Type)
                headers = {
                    'Authorization': self.api_token
                }
                
                response = requests.post(url, headers=headers, files=files, timeout=60)
            
            if response.status_code == 200:
                response_data = response.json()
                attachment_url = response_data.get('url', '')
                print(f"[OK] Document attached to ClickUp task {task_id}: {filename}")
                print(f"DEBUG: Attachment response data: {response_data}")  # Debug info
                return {
                    'success': True,
                    'attachment_url': attachment_url,
                    'attachment_data': response_data
                }
            else:
                error_msg = f"File upload failed: {response.status_code} - {response.text}"
                print(f"[ERROR] {error_msg}")
                return {'success': False, 'error': error_msg}
                
        except Exception as e:
            error_msg = f"Failed to upload file: {str(e)}"
            print(f"[ERROR] {error_msg}")
            return {'success': False, 'error': error_msg}
    
    def _update_ssm_document_field(self, task_id, attachment_data, filename):
        """Update SSM document custom field with attachment ID"""
        try:
            # Get task with custom fields to find SSM document field
            task_info = self._get_task_with_custom_fields(task_id)
            if not task_info.get('success'):
                print(f"Could not get task info for SSM field update: {task_info.get('error')}")
                return {'success': False, 'error': 'Could not get task info'}
            
            custom_fields = task_info.get('custom_fields', [])
            ssm_field_id = None
            ssm_field = None
            
            # Find SSM document field
            for field in custom_fields:
                field_name = field.get('name', '').lower()
                if 'ssm document' in field_name or 'ssm' in field_name:
                    ssm_field_id = field.get('id')
                    ssm_field = field
                    break
            
            if not ssm_field_id:
                print(f"SSM document custom field not found in task {task_id}")
                return {'success': False, 'error': 'SSM field not found'}
            
            # Check if it's an attachment field
            if ssm_field.get('type') != 'attachment':
                print(f"SSM field is not an attachment field, it's: {ssm_field.get('type')}")
                return {'success': False, 'error': 'SSM field is not attachment type'}
            
            # For attachment fields, we need to use the attachment ID, not URL
            attachment_id = attachment_data.get('id')
            if not attachment_id:
                print(f"No attachment ID found in attachment data")
                return {'success': False, 'error': 'No attachment ID'}
            
            # Try using the full attachment ID (with extension)
            print(f"DEBUG: Using full attachment ID: {attachment_id}")
            
            # Update the SSM document field with attachment ID array
            url = f"{self.base_url}/task/{task_id}/field/{ssm_field_id}"
            payload = {
                'value': {
                    'add': [attachment_id]  # Use full attachment ID
                }
            }
            
            print(f"DEBUG: SSM field update payload: {payload}")
            
            response = requests.post(url, headers=self.headers, json=payload, timeout=10)
            
            if response.status_code == 200:
                print(f"[OK] Updated SSM document field with attachment: {filename}")
                return {'success': True}
            else:
                error_msg = f"SSM field update failed: {response.status_code} - {response.text}"
                print(f"[WARNING] {error_msg}")
                return {'success': False, 'error': error_msg}
                
        except Exception as e:
            print(f"SSM field update failed (non-critical): {e}")
            return {'success': False, 'error': str(e)}
    
    def _update_ssm_doc_url_field(self, task_id, attachment_url, filename):
        """Update SSM Doc [upload] custom field with attachment URL"""
        try:
            # Get task with custom fields to find SSM Doc URL field
            task_info = self._get_task_with_custom_fields(task_id)
            if not task_info.get('success'):
                print(f"Could not get task info for SSM Doc URL field update: {task_info.get('error')}")
                return {'success': False, 'error': 'Could not get task info'}
            
            custom_fields = task_info.get('custom_fields', [])
            ssm_field_id = None
            ssm_field = None
            
            # Find SSM Doc [upload] field (with or without emoji)
            for field in custom_fields:
                field_name = field.get('name', '').lower()
                # Match field that contains "ssm doc" and "upload" (ignoring emojis)
                if 'ssm doc' in field_name and 'upload' in field_name:
                    ssm_field_id = field.get('id')
                    ssm_field = field
                    try:
                        print(f"Found SSM Doc field: {field.get('name')} (ID: {ssm_field_id})")
                    except UnicodeEncodeError:
                        print(f"Found SSM Doc field with emoji (ID: {ssm_field_id})")
                    break
            
            if not ssm_field_id:
                print(f"SSM Doc [upload] custom field not found in task {task_id}")
                try:
                    print(f"Available fields: {[f.get('name') for f in custom_fields]}")
                except UnicodeEncodeError:
                    print(f"Available fields: [contains emoji field names - {len(custom_fields)} total]")
                return {'success': False, 'error': 'SSM Doc [upload] field not found'}
            
            # Check field type
            field_type = ssm_field.get('type')
            print(f"SSM Doc [upload] field type: {field_type}")
            
            # Update the SSM Doc [upload] field with attachment URL
            url = f"{self.base_url}/task/{task_id}/field/{ssm_field_id}"
            payload = {
                'value': attachment_url
            }
            
            print(f"Updating SSM Doc [upload] field with URL: {attachment_url}")
            
            response = requests.post(url, headers=self.headers, json=payload, timeout=10)
            
            if response.status_code == 200:
                try:
                    print(f"[OK] Updated SSM Doc field with document URL: {filename}")
                except UnicodeEncodeError:
                    print(f"[OK] Updated SSM Doc field with document URL (filename contains special chars)")
                return {'success': True}
            else:
                error_msg = f"SSM Doc URL field update failed: {response.status_code} - {response.text}"
                print(f"[WARNING] {error_msg}")
                return {'success': False, 'error': error_msg}
                
        except Exception as e:
            print(f"SSM Doc URL field update failed (non-critical): {e}")
            return {'success': False, 'error': str(e)}
    
    def update_director_fields(self, task_id, directors_data):
        """Update Director Name and Director Email custom fields with first director from OCR"""
        try:
            if not directors_data or len(directors_data) == 0:
                print(f"[INFO] No directors data available for ClickUp fields update")
                return {'success': False, 'error': 'No directors data'}
            
            # Get first director
            first_director = directors_data[0]
            director_name = first_director.get('name', '')
            director_email = first_director.get('email', '')
            
            print(f"Updating ClickUp director fields - Name: {director_name}, Email: {director_email}")
            
            # Get task with custom fields
            task_info = self._get_task_with_custom_fields(task_id)
            if not task_info.get('success'):
                print(f"Could not get task info for director fields update: {task_info.get('error')}")
                return {'success': False, 'error': 'Could not get task info'}
            
            custom_fields = task_info.get('custom_fields', [])
            
            # Find Director Name and Director Email fields
            director_name_field_id = None
            director_email_field_id = None
            
            for field in custom_fields:
                field_name = field.get('name', '').lower()
                if 'director name' in field_name:
                    director_name_field_id = field.get('id')
                    print(f"Found Director Name field (ID: {director_name_field_id})")
                elif 'director email' in field_name:
                    director_email_field_id = field.get('id')
                    print(f"Found Director Email field (ID: {director_email_field_id})")
            
            results = {'name_updated': False, 'email_updated': False}
            
            # Update Director Name field
            if director_name_field_id and director_name:
                name_result = self._update_custom_field_value(task_id, director_name_field_id, director_name, "Director Name")
                results['name_updated'] = name_result.get('success', False)
            else:
                print(f"[WARNING] Director Name field not found or no name data")
            
            # Update Director Email field  
            if director_email_field_id and director_email:
                email_result = self._update_custom_field_value(task_id, director_email_field_id, director_email, "Director Email")
                results['email_updated'] = email_result.get('success', False)
            else:
                print(f"[WARNING] Director Email field not found or no email data")
            
            return {
                'success': True,
                'name_updated': results['name_updated'],
                'email_updated': results['email_updated']
            }
            
        except Exception as e:
            print(f"Director fields update failed (non-critical): {e}")
            return {'success': False, 'error': str(e)}
    
    def _update_custom_field_value(self, task_id, field_id, value, field_name):
        """Helper method to update a custom field value"""
        try:
            url = f"{self.base_url}/task/{task_id}/field/{field_id}"
            payload = {'value': value}
            
            response = requests.post(url, headers=self.headers, json=payload, timeout=10)
            
            if response.status_code == 200:
                print(f"[OK] Updated {field_name} field: {value}")
                return {'success': True}
            else:
                error_msg = f"{field_name} field update failed: {response.status_code} - {response.text}"
                print(f"[WARNING] {error_msg}")
                return {'success': False, 'error': error_msg}
                
        except Exception as e:
            print(f"{field_name} field update failed: {e}")
            return {'success': False, 'error': str(e)}
    
    def get_task_info(self, task_id):
        """Get basic task information"""
        try:
            url = f"{self.base_url}/task/{task_id}"
            response = requests.get(url, headers=self.headers, timeout=10)
            
            if response.status_code == 200:
                task_data = response.json()
                return {
                    'success': True,
                    'task': {
                        'id': task_data.get('id'),
                        'name': task_data.get('name'),
                        'status': task_data.get('status', {}).get('status'),
                        'url': task_data.get('url')
                    }
                }
            else:
                return {'success': False, 'error': f"Task not found: {response.status_code}"}
                
        except Exception as e:
            return {'success': False, 'error': str(e)}


# Convenience functions for easy import
def update_clickup_task_status(task_id, status_type, status_value, additional_info=None):
    """
    Convenience function to update ClickUp task status
    
    Args:
        task_id (str): ClickUp task ID
        status_type (str): 'ocr_status' or 'kyb_status'
        status_value (str): Status value
        additional_info (dict): Optional additional information
    
    Returns:
        dict: Result of the update operation
    """
    service = ClickUpService()
    return service.update_task_status(task_id, status_type, status_value, additional_info)


def attach_document_to_clickup_task(task_id, file_path, filename):
    """
    Convenience function to attach document to ClickUp task
    
    Args:
        task_id (str): ClickUp task ID
        file_path (str): Full path to the document file
        filename (str): Name of the file
    
    Returns:
        dict: Result of the attachment operation
    """
    service = ClickUpService()
    return service.attach_document_to_task(task_id, file_path, filename)


def update_clickup_director_fields(task_id, directors_data):
    """
    Convenience function to update Director Name and Director Email fields
    
    Args:
        task_id (str): ClickUp task ID
        directors_data (list): List of director dictionaries with 'name' and 'email'
    
    Returns:
        dict: Result of the update operation
    """
    service = ClickUpService()
    return service.update_director_fields(task_id, directors_data)