"""
OCR Service - AWS Textract Implementation
This module contains all OCR-related functionality for document processing.
Replace this service with your preferred OCR provider.
"""

import os
import boto3
import time
from datetime import datetime
from supabase import create_client


class OCRService:
    """OCR Service using AWS Textract"""
    
    def __init__(self, supabase_client=None):
        self.supabase = supabase_client
        self.textract_client = boto3.client(
            'textract',
            aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
            aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
            region_name=os.getenv('AWS_REGION', 'ap-south-1')
        )
        self.s3_bucket = os.getenv('AWS_S3_BUCKET')
    
    def process_document_sync(self, s3_key, document_id):
        """Process document with synchronous Textract OCR"""
        try:
            print(f"=== SYNC OCR PROCESSING START ===")
            print(f"Document ID: {document_id}")
            print(f"S3 Key: {s3_key}")
            
            # Call Textract analyze_document
            response = self.textract_client.analyze_document(
                Document={
                    'S3Object': {
                        'Bucket': self.s3_bucket,
                        'Name': s3_key
                    }
                },
                FeatureTypes=['FORMS', 'TABLES']
            )
            
            print(f"Textract response received! Found {len(response['Blocks'])} blocks")
            
            # Extract key information
            extracted_data = self._extract_key_information(response)
            print(f"Extracted data: {extracted_data}")
            
            # Update database
            self._update_database(document_id, extracted_data, 'completed')
            
            print(f"=== SYNC OCR PROCESSING COMPLETE ===")
            
            return {
                'success': True,
                'extracted_data': extracted_data,
                'ocr_status': 'completed',
                'method': 'sync_textract'
            }
            
        except Exception as e:
            print(f"=== SYNC OCR PROCESSING ERROR ===")
            print(f"Error: {e}")
            
            # Update database with error
            self._update_database(document_id, {}, 'failed')
            
            return {
                'success': False,
                'error': str(e),
                'ocr_status': 'failed'
            }
    
    def process_document_async(self, s3_key, document_id):
        """Process document with asynchronous Textract OCR"""
        try:
            print(f"=== ASYNC OCR PROCESSING START ===")
            
            # Step 1: Start async job
            job_result = self._start_async_job(s3_key)
            
            if not job_result['success']:
                raise Exception(f"Failed to start job: {job_result['error']}")
            
            job_id = job_result['job_id']
            
            # Step 2: Update database with job ID
            if self.supabase:
                self.supabase.table('documents').update({
                    'ocr_status': 'processing',
                    'textract_job_id': job_id,
                    'ocr_started_at': datetime.now().isoformat()
                }).eq('id', document_id).execute()
            
            # Step 3: Poll for completion
            max_attempts = 30  # 5 minutes max
            attempt = 0
            
            while attempt < max_attempts:
                print(f"Polling attempt {attempt + 1}/{max_attempts}")
                
                status_result = self._check_job_status(job_id)
                
                if not status_result['success']:
                    raise Exception(f"Error checking status: {status_result['error']}")
                
                if status_result['status'] == 'COMPLETED':
                    extracted_data = status_result['extracted_data']
                    self._update_database(document_id, extracted_data, 'completed')
                    
                    print(f"ASYNC OCR COMPLETED! Extracted: {extracted_data}")
                    
                    return {
                        'success': True,
                        'extracted_data': extracted_data,
                        'ocr_status': 'completed',
                        'job_id': job_id,
                        'method': 'async_textract'
                    }
                    
                elif status_result['status'] == 'FAILED':
                    raise Exception(f"Textract job failed: {status_result['error']}")
                
                elif status_result['status'] == 'IN_PROGRESS':
                    time.sleep(10)
                    attempt += 1
                else:
                    time.sleep(5)
                    attempt += 1
            
            raise Exception(f"Textract job timed out after {max_attempts * 10} seconds")
            
        except Exception as e:
            print(f"=== ASYNC OCR ERROR ===")
            print(f"Error: {e}")
            
            self._update_database(document_id, {}, 'failed')
            
            return {
                'success': False,
                'error': str(e),
                'ocr_status': 'failed'
            }
    
    def _start_async_job(self, s3_key):
        """Start asynchronous Textract job"""
        try:
            response = self.textract_client.start_document_analysis(
                DocumentLocation={
                    'S3Object': {
                        'Bucket': self.s3_bucket,
                        'Name': s3_key
                    }
                },
                FeatureTypes=['FORMS', 'TABLES']
            )
            
            job_id = response['JobId']
            print(f"Started async job with ID: {job_id}")
            
            return {
                'success': True,
                'job_id': job_id
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def _check_job_status(self, job_id):
        """Check status of async Textract job"""
        try:
            response = self.textract_client.get_document_analysis(JobId=job_id)
            
            job_status = response['JobStatus']
            print(f"Job {job_id} status: {job_status}")
            
            if job_status == 'SUCCEEDED':
                # Extract data from completed job
                extracted_data = self._extract_key_information(response)
                return {
                    'success': True,
                    'status': 'COMPLETED',
                    'extracted_data': extracted_data
                }
            elif job_status == 'FAILED':
                return {
                    'success': True,
                    'status': 'FAILED',
                    'error': response.get('StatusMessage', 'Unknown error')
                }
            elif job_status == 'IN_PROGRESS':
                return {
                    'success': True,
                    'status': 'IN_PROGRESS'
                }
            else:
                return {
                    'success': True,
                    'status': job_status
                }
                
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def _extract_key_information(self, textract_response):
        """Extract specific fields from Textract response"""
        extracted_data = {
            'company_name': None,
            'registration_number': None,
            'incorporation_date': None,
            'company_type': None,
            'business_address': None,
            'business_phone': None,
            'directors': []  # List of directors
        }
        
        blocks = textract_response['Blocks']
        
        # Build block maps
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
        
        # Extract text content for pattern matching
        text_content = self._extract_all_text(blocks)
        
        # Extract company information using pattern matching
        extracted_data.update(self._extract_company_info(text_content))
        
        # Extract director information
        extracted_data['directors'] = self._extract_director_info(text_content)
        
        # Extract from key-value pairs (fallback method)
        for key_id, key_block in key_map.items():
            if 'Relationships' in key_block:
                for relationship in key_block['Relationships']:
                    if relationship['Type'] == 'CHILD':
                        key_text = self._get_text_from_blocks(relationship['Ids'], block_map)
                        
                        # Find corresponding value
                        for rel in key_block.get('Relationships', []):
                            if rel['Type'] == 'VALUE':
                                for value_id in rel['Ids']:
                                    if value_id in value_map:
                                        value_block = value_map[value_id]
                                        if 'Relationships' in value_block:
                                            for value_rel in value_block['Relationships']:
                                                if value_rel['Type'] == 'CHILD':
                                                    value_text = self._get_text_from_blocks(value_rel['Ids'], block_map)
                                                    
                                                    # Field matching patterns (fallback)
                                                    key_lower = key_text.lower()
                                                    if 'proposed name' in key_lower and not extracted_data['company_name']:
                                                        extracted_data['company_name'] = value_text
                                                    elif 'incorporation date' in key_lower and not extracted_data['incorporation_date']:
                                                        extracted_data['incorporation_date'] = value_text
                                                    elif 'business address' in key_lower and not extracted_data['business_address']:
                                                        extracted_data['business_address'] = value_text
        
        return extracted_data
    
    def _extract_all_text(self, blocks):
        """Extract all text from blocks for pattern matching"""
        text_lines = []
        for block in blocks:
            if block['BlockType'] == 'LINE':
                text_lines.append(block.get('Text', ''))
        return '\n'.join(text_lines)
    
    def _extract_company_info(self, text_content):
        """Extract company information using pattern matching"""
        import re
        
        company_info = {
            'company_name': None,
            'registration_number': None,
            'incorporation_date': None,
            'company_type': None,
            'business_address': None,
            'business_phone': None
        }
        
        lines = text_content.split('\n')
        
        for i, line in enumerate(lines):
            line = line.strip()
            
            # Extract company name from "Proposed name" section
            if 'Proposed name' in line and i + 1 < len(lines):
                next_line = lines[i + 1].strip()
                if next_line and 'SDN' in next_line.upper():
                    company_info['company_name'] = next_line
                    # Extract company type
                    if 'SDN. BHD.' in next_line:
                        company_info['company_type'] = 'SDN. BHD.'
            
            # Extract registration number
            if re.match(r'\d{12}\s*\(\d{7}-[A-Z]\)', line):
                company_info['registration_number'] = line
            
            # Extract incorporation date
            if 'Incorporation Date' in line and i + 1 < len(lines):
                next_line = lines[i + 1].strip()
                if re.match(r'\d{2}/\d{2}/\d{4}', next_line):
                    company_info['incorporation_date'] = next_line
            
            # Extract business address - improved logic
            if 'Business Address' in line:
                address_lines = []
                j = i + 1
                while j < len(lines) and lines[j].strip():
                    current_line = lines[j].strip()
                    # Stop if we hit other sections or "Office No NIL"
                    if any(keyword in current_line for keyword in ['Business Phone', 'Fax', 'Email', 'Office No NIL']):
                        break
                    # Skip lines that are just "NIL"
                    if current_line != 'NIL':
                        address_lines.append(current_line)
                    j += 1
                
                if address_lines:
                    company_info['business_address'] = ' '.join(address_lines)
            
            # Extract registered address as fallback
            if 'Registered Address' in line:
                address_lines = []
                j = i + 1
                while j < len(lines) and lines[j].strip():
                    current_line = lines[j].strip()
                    # Stop if we hit other sections
                    if any(keyword in current_line for keyword in ['Business Phone', 'Fax', 'Email', 'Office No']):
                        break
                    # Skip lines that are just "NIL"
                    if current_line != 'NIL':
                        address_lines.append(current_line)
                    j += 1
                
                if address_lines and not company_info['business_address']:
                    company_info['business_address'] = ' '.join(address_lines)
        
        # If business address is still not found or looks incomplete, search for address patterns
        if not company_info['business_address'] or 'NIL' in company_info['business_address'] or company_info['business_address'] == 'Office No':
            # Generic multi-line address extraction logic
            company_info['business_address'] = self._extract_multi_line_address(lines)
            
            # Extract business phone
            if 'Business Phone' in line:
                # Look for phone number in next few lines
                for j in range(i + 1, min(i + 4, len(lines))):
                    phone_line = lines[j].strip()
                    phone_match = re.search(r'\b\d{8,12}\b', phone_line)
                    if phone_match:
                        company_info['business_phone'] = phone_match.group()
                        break
            elif '+60' in line and re.search(r'\d{2}-\d{4}\s*\d{4}', line):
                # Extract phone number from +60 format
                phone_match = re.search(r'\+60\s*([\d-\s]+)', line)
                if phone_match:
                    phone_clean = re.sub(r'[\s-]', '', phone_match.group(1))
                    company_info['business_phone'] = phone_clean
            elif line.strip().isdigit() and len(line.strip()) >= 8:
                # Look for phone number pattern
                phone_match = re.search(r'\b\d{8,12}\b', line)
                if phone_match:
                    company_info['business_phone'] = phone_match.group()
        
        return company_info
    
    def _extract_multi_line_address(self, lines):
        """Generic multi-line address extraction logic"""
        import re
        
        # Common Malaysian address patterns and indicators
        address_indicators = [
            # Building/unit patterns
            r'[A-Z]?\d{1,3}-?\d{1,3}-?\d{1,3}[A-Z]?',  # B12-03, A-3-4, etc.
            r'[A-Z]\d{4}',  # B1203, A1234, etc.
            r'LOT\s+\w+',  # LOT W17A2
            r'UNIT\s+\d+',  # UNIT 123
            r'NO\.?\s*\d+',  # NO. 123, NO 123
            # Street patterns
            r'JALAN\s+\w+',  # JALAN AMPANG
            r'PERSIARAN\s+\w+',  # PERSIARAN DR GEORGE
            r'LORONG\s+\w+',  # LORONG 123
            # Area patterns
            r'TAMAN\s+\w+',  # TAMAN EQUINE
            r'BANDAR\s+\w+',  # BANDAR UTAMA
            r'KEPONG\s+\w+',  # KEPONG BARU
            # Building names
            r'WISMA\s+\w+',  # WISMA GOLDEN EAGLE
            r'MENARA\s+\w+',  # MENARA KUALA LUMPUR
            r'PLAZA\s+\w+',  # PLAZA MONT KIARA
            r'RESIDENCE\s*',  # SPRINGVILLE RESIDENCE
            r'CONDOMINIUM\s*',  # Various condominiums
            # Postal codes
            r'\d{5}\s+\w+',  # 43300 SERI KEMBANGAN
            # States
            r'KUALA\s+LUMPUR',
            r'SELANGOR',
            r'JOHOR',
            r'PENANG',
            r'PERAK',
            r'SABAH',
            r'SARAWAK',
            r'KEDAH',
            r'KELANTAN',
            r'TERENGGANU',
            r'PAHANG',
            r'NEGERI\s+SEMBILAN',
            r'MELAKA',
            r'PERLIS',
            r'PUTRAJAYA',
            r'LABUAN'
        ]
        
        # Find potential address lines
        address_candidates = []
        
        for i, line in enumerate(lines):
            line = line.strip()
            
            # Skip empty lines and obvious non-address content
            if not line or line in ['Business Address', 'Registered Address', 'NIL']:
                continue
            
            # Skip lines that are clearly not addresses
            if any(keyword in line for keyword in ['Business Phone', 'Fax', 'Email', 'Office No NIL', 'PARTICULARS', 'DIRECTOR', 'MEMBER']):
                continue
            
            # Check if line contains address indicators
            address_score = 0
            for pattern in address_indicators:
                if re.search(pattern, line, re.IGNORECASE):
                    address_score += 1
            
            # Add lines with postal codes (strong indicator)
            if re.search(r'\d{5}', line):
                address_score += 2
            
            # Add lines with MALAYSIA (strong indicator)
            if 'MALAYSIA' in line:
                address_score += 2
            
            # Store potential address lines with scores
            if address_score > 0:
                address_candidates.append((i, line, address_score))
        
        if not address_candidates:
            return None
        
        # Sort by score (highest first) and group consecutive lines
        address_candidates.sort(key=lambda x: x[2], reverse=True)
        
        # Find the best address group (consecutive lines with highest combined score)
        best_address_group = []
        best_score = 0
        
        # Sort by line index to process in order
        address_candidates.sort(key=lambda x: x[0])
        
        # Look for consecutive high-scoring lines
        for i, (start_idx, start_line, start_score) in enumerate(address_candidates):
            current_group = [start_line]
            current_score = start_score
            
            # Look for the next consecutive line(s)
            for j in range(i + 1, len(address_candidates)):
                next_idx, next_line, next_score = address_candidates[j]
                
                # Check if this line is consecutive (within 2 lines) and has good score
                if (next_idx <= start_idx + 2 and next_score >= 3 and 
                    not any(keyword in next_line for keyword in ['Business Phone', 'Fax', 'Email', 'Office No'])):
                    current_group.append(next_line)
                    current_score += next_score
                    start_idx = next_idx  # Update for next iteration
                else:
                    break  # Stop if not consecutive
            
            # Update best group if this one is better
            if current_score > best_score:
                best_score = current_score
                best_address_group = current_group
        
        if not best_address_group:
            return None
        
        # Clean up and format the address
        formatted_address = ', '.join(best_address_group)
        
        # Clean up common formatting issues
        formatted_address = re.sub(r'B-(\d{1,2})-(\d{2})', r'B\1\2', formatted_address)  # B-12-03 -> B1203
        formatted_address = re.sub(r'\s+', ' ', formatted_address)  # Multiple spaces -> single space
        formatted_address = re.sub(r',\s*,', ',', formatted_address)  # Remove double commas
        formatted_address = formatted_address.strip(', ')  # Remove leading/trailing commas
        
        return formatted_address if formatted_address else None
    
    def _extract_director_info(self, text_content):
        """Extract director information from text content"""
        import re
        
        directors = []
        lines = text_content.split('\n')
        
        # Find director sections (exclude member sections and lodger sections)
        director_sections = []
        for i, line in enumerate(lines):
            if 'PARTICULARS OF DIRECTOR' in line:
                director_sections.append(i)
            # Do NOT include 'PARTICULARS OF MEMBER' as it's for members, not directors
            # Do NOT include 'LODGER' sections as they are not directors
        
        # Process each director section
        for section_start in director_sections:
            current_directors = []
            
            # Look for director information in the next 30 lines (increased range)
            # Stop if we hit a member section or lodger section
            section_end = section_start + 31
            for k in range(section_start + 1, min(len(lines), section_start + 50)):
                if ('PARTICULARS OF MEMBER' in lines[k] or 
                    'LODGER' in lines[k] or 
                    'PARTICULARS OF LODGER' in lines[k]):
                    section_end = k
                    break
            
            for i in range(section_start + 1, min(section_end, len(lines))):
                line = lines[i].strip()
                
                # Extract director name (looks for names with A/L pattern or common Malaysian names)
                # Exclude certain keywords that are not names
                excluded_keywords = ['OTHER RACE', 'NATIONALITY', 'DESIGNATION', 'PARTICULARS', 
                                   'DIRECTOR', 'MEMBER', 'NAME', 'NRIC', 'PASSPORT', 'EMAIL',
                                   'COMPANY REGISTRATION', 'REGISTRATION', 'CHINESE', 'MALAY', 'INDIAN',
                                   'CERTIFI ED COPY', 'CERTIFIED COPY', 'COMPAN SECRETARY', 
                                   'COMPANY SECRETARY', 'COPY', 'SECRETARY', 'LODGER', 'PARTICULARS OF LODGER']
                
                if ('A/L' in line or 'A/P' in line or 'BIN' in line or 
                    (re.search(r'^[A-Z][A-Z\s]+$', line) and len(line.split()) >= 2 and 
                     not re.search(r'\d', line) and 
                     not any(keyword in line for keyword in excluded_keywords))):
                    
                    # This looks like a director name
                    director = {
                        'name': line,
                        'id_type': 'NRIC',  # Default to NRIC
                        'id_number': None,
                        'email': None
                    }
                    
                    # Look for ID number and email in the next few lines (within director section)
                    for j in range(i + 1, min(i + 15, section_end)):
                        next_line = lines[j].strip()
                        
                        # Extract ID number (12 digits)
                        if re.match(r'^\d{12}$', next_line) and not director['id_number']:
                            director['id_number'] = next_line
                        
                        # Extract email (look for lines containing @ and common TLDs)
                        if '@' in next_line and ('.com' in next_line or '.io' in next_line or '.my' in next_line) and not director['email']:
                            director['email'] = next_line
                    
                    # Look backwards for email (in case it appears before the name)
                    for j in range(max(section_start, i - 8), i):
                        prev_line = lines[j].strip()
                        if '@' in prev_line and ('.com' in prev_line or '.io' in prev_line or '.my' in prev_line) and not director['email']:
                            director['email'] = prev_line
                    
                    # Add director if we have at least a name
                    if director['name']:
                        current_directors.append(director)
            
            # Add all found directors (will deduplicate later)
            directors.extend(current_directors)
        
        # Remove duplicates based on name and ID number
        seen = set()
        unique_directors = []
        for director in directors:
            director_key = (director['name'], director['id_number'])
            if director_key not in seen:
                seen.add(director_key)
                unique_directors.append(director)
        
        directors = unique_directors
        
        # Post-process to match emails with directors more intelligently
        all_emails = []
        for line in lines:
            if '@' in line and ('.com' in line or '.io' in line or '.my' in line):
                all_emails.append(line.strip())
        
        # Create a mapping of directors to emails based on context
        director_emails = {}
        
        # First, try to match emails that appear near director names within director sections
        for director in directors:
            if director['email']:  # Already has email
                continue
                
            director_name = director['name']
            # Find the director name in the text
            for i, line in enumerate(lines):
                if director_name in line:
                    # Check if this director name is in a director section (not member section)
                    is_in_director_section = False
                    
                    # Look backwards to find the section type
                    for k in range(i, max(0, i-20), -1):
                        if 'PARTICULARS OF DIRECTOR' in lines[k]:
                            is_in_director_section = True
                            break
                        elif 'PARTICULARS OF MEMBER' in lines[k]:
                            is_in_director_section = False
                            break
                    
                    # Only process if in director section
                    if is_in_director_section:
                        # Look for emails in surrounding lines (prioritize nearby emails)
                        # Check within 15 lines after the director name
                        for j in range(i + 1, min(len(lines), i + 16)):
                            if '@' in lines[j] and ('.com' in lines[j] or '.io' in lines[j] or '.my' in lines[j]):
                                email = lines[j].strip()
                                # Skip already assigned emails
                                if email not in director_emails.values():
                                    director_emails[director_name] = email
                                    break
                        
                        # If not found after, check before (within 5 lines)
                        if director_name not in director_emails:
                            for j in range(max(0, i-5), i):
                                if '@' in lines[j] and ('.com' in lines[j] or '.io' in lines[j] or '.my' in lines[j]):
                                    email = lines[j].strip()
                                    if email not in director_emails.values():
                                        director_emails[director_name] = email
                                        break
                    break
        
        # Apply matched emails to directors
        for director in directors:
            if not director['email'] and director['name'] in director_emails:
                director['email'] = director_emails[director['name']]
        
        # For remaining directors without emails, assign remaining emails intelligently
        remaining_emails = [email for email in all_emails if email not in director_emails.values()]
        
        # Try to match remaining emails by finding them near director sections only
        for director in directors:
            if not director['email'] and remaining_emails:
                # Look for emails that appear in the same director section
                director_name = director['name']
                for i, line in enumerate(lines):
                    if director_name in line:
                        # Check if this is in a director section
                        is_in_director_section = False
                        for k in range(i, max(0, i-20), -1):
                            if 'PARTICULARS OF DIRECTOR' in lines[k]:
                                is_in_director_section = True
                                break
                            elif 'PARTICULARS OF MEMBER' in lines[k]:
                                is_in_director_section = False
                                break
                        
                        # Only assign emails if in director section
                        if is_in_director_section:
                            # Check if any remaining email appears in nearby lines within director section
                            for j in range(max(0, i-5), min(len(lines), i+15)):
                                # Make sure we're still in director section
                                still_in_director_section = True
                                for m in range(j, min(len(lines), j+10)):
                                    if 'PARTICULARS OF MEMBER' in lines[m]:
                                        still_in_director_section = False
                                        break
                                
                                if still_in_director_section:
                                    for email in remaining_emails:
                                        if email in lines[j]:
                                            director['email'] = email
                                            remaining_emails.remove(email)
                                            break
                                    if director['email']:
                                        break
                        break
        
        return directors
    
    def _get_text_from_blocks(self, block_ids, block_map):
        """Helper function to extract text from block IDs"""
        text = ""
        for block_id in block_ids:
            if block_id in block_map:
                block = block_map[block_id]
                if block['BlockType'] == 'WORD':
                    text += block.get('Text', '') + " "
        return text.strip()
    
    def _update_database(self, document_id, extracted_data, status):
        """Update database with OCR results"""
        if not self.supabase:
            print("Warning: Supabase client not available, skipping database update")
            return
        
        try:
            update_data = {
                'ocr_status': status,
                'ocr_completed_at': datetime.now().isoformat(),
            }
            
            if extracted_data:
                update_data.update({
                    'extracted_company_name': extracted_data.get('company_name'),
                    'extracted_registration_number': extracted_data.get('registration_number'),
                    'extracted_incorporation_date': extracted_data.get('incorporation_date'),
                    'extracted_company_type': extracted_data.get('company_type'),
                    'extracted_business_address': extracted_data.get('business_address'),
                    'extracted_business_phone': extracted_data.get('business_phone'),
                    'extracted_directors': extracted_data.get('directors', [])
                })
            
            print(f"Updating database for document {document_id} with status {status}")
            print(f"Update data: {update_data}")
            
            result = self.supabase.table('documents').update(update_data).eq('id', document_id).execute()
            print(f"Database update result: {result}")
            print("Database updated successfully!")
            
        except Exception as e:
            print(f"Failed to update database: {e}")
            import traceback
            print(f"Traceback: {traceback.format_exc()}")


# Legacy wrapper functions for backward compatibility
def process_document_ocr(s3_key, document_id, supabase_client=None):
    """Legacy wrapper for sync OCR processing"""
    ocr_service = OCRService(supabase_client)
    return ocr_service.process_document_sync(s3_key, document_id)


def process_document_ocr_async(s3_key, document_id, supabase_client=None):
    """Legacy wrapper for async OCR processing"""
    ocr_service = OCRService(supabase_client)
    return ocr_service.process_document_async(s3_key, document_id)


def extract_key_information(textract_response):
    """Legacy wrapper for key extraction"""
    ocr_service = OCRService()
    return ocr_service._extract_key_information(textract_response)