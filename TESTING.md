# Testing Strategy for Internal Automation System

## Overview
This document outlines how to use the test cases and when to run them for optimal development and deployment practices.

## Test Files Structure

### 1. `test_document.py` - Basic Tests
- **Purpose**: Quick functionality tests for development
- **Coverage**: Basic API endpoints, file uploads, simple validation
- **Runtime**: ~30 seconds
- **Use case**: Daily development, quick validation

### 2. `test_comprehensive.py` - Full Verification
- **Purpose**: Complete system verification with database and email checks
- **Coverage**: All system components, database verification, email sending, OCR processing
- **Runtime**: ~2-3 minutes
- **Use case**: Pre-deployment, thorough testing

### 3. `test_runner.py` - Test Orchestration
- **Purpose**: Unified test execution with different strategies
- **Features**: Environment checks, organized test runs, deployment verification

## When to Run Tests

### ✅ **REQUIRED: Before Every Deployment**
```bash
# Pre-deployment verification
python test_runner.py pre-deploy
```
**This is mandatory** - prevents broken deployments.

### 🔄 **Daily Development**
```bash
# Quick tests during development
python test_runner.py quick

# Test specific components
python test_runner.py zapier    # After webhook changes
python test_runner.py ocr       # After OCR modifications
```

### 🎯 **Feature Development**
```bash
# Full verification after major changes
python test_runner.py comprehensive
```

### 📡 **Post-Deployment**
```bash
# Verify production deployment
python test_runner.py post-deploy
```

## Test Environment Setup

### Prerequisites
1. **Flask App Running**: `python app.py`
2. **Environment Variables**: Ensure `.env` file is configured
3. **Database Access**: Supabase credentials available
4. **External Services**: SendGrid, AWS credentials

### Environment Variables Required
```bash
# Database
SUPABASE_URL=your_supabase_url
SUPABASE_ANON_KEY=your_supabase_key

# AWS Services
AWS_ACCESS_KEY_ID=your_aws_key
AWS_SECRET_ACCESS_KEY=your_aws_secret
AWS_S3_BUCKET=your_s3_bucket
AWS_REGION=us-east-1

# Email Service
SENDGRID_API_KEY=your_sendgrid_key

# Optional: ClickUp Integration
CLICKUP_API_TOKEN=your_clickup_token
```

## CI/CD Integration

### GitHub Actions Workflow
The included `.github/workflows/test-and-deploy.yml` automatically:
1. Runs tests on every push/PR
2. Blocks deployment if tests fail
3. Runs post-deployment verification

### Manual CI/CD Integration
```bash
# In your deployment script
python test_runner.py pre-deploy
if [ $? -eq 0 ]; then
    echo "✅ Tests passed - deploying..."
    # Your deployment commands here
    python test_runner.py post-deploy
else
    echo "❌ Tests failed - aborting deployment"
    exit 1
fi
```

## Test Coverage

### What Gets Tested
- ✅ **Zapier Webhook Processing**
  - Payload validation
  - Customer token generation
  - Database customer record creation
  - Email sending via SendGrid
  - Upload link generation

- ✅ **Document Upload & Processing**
  - File upload validation
  - S3 storage verification
  - OCR processing initiation
  - Database document record creation

- ✅ **OCR Processing**
  - AWS Textract integration
  - Data extraction accuracy
  - Database updates with extracted data
  - Processing status tracking

- ✅ **Database Operations**
  - Customer record insertion
  - Document metadata storage
  - OCR results storage
  - Status updates

- ✅ **Email Integration**
  - SendGrid email sending
  - Template processing
  - Delivery verification

- ✅ **Complete Workflow**
  - End-to-end process verification
  - Integration between all components
  - Error handling

### What's NOT Tested
- ClickUp API integration (optional component)
- File system operations (handled by Flask/S3)
- AWS infrastructure (assumed working)

## Test Data

### Zapier Payload (Used in Tests)
```json
{
  "customer_name": "Test Customer Auto",
  "customer_email": "admin@swipey.co",
  "company_name": "AutoTest Solutions Bhd",
  "phone": "+601234567890",
  "business_type": "Technology",
  "typeform_response_id": "auto_test_123",
  "submission_timestamp": "2025-01-18T10:30:00",
  "clickup_task_id": "task_autotest_001",
  "clickup_task_url": "https://app.clickup.com/t/task_autotest_001"
}
```

### OCR Test Document
Tests create a PDF with:
- Company Name: AutoTest Solutions Bhd
- Registration Number: 202501001234
- Director information
- Business address

## Troubleshooting

### Common Issues

1. **"Server not running" Error**
   ```bash
   # Start Flask app first
   python app.py
   # Then run tests in another terminal
   python test_runner.py quick
   ```

2. **Database Connection Failed**
   - Check `.env` file has correct Supabase credentials
   - Verify Supabase project is active
   - Check network connectivity

3. **Email Verification Failed**
   - Verify SendGrid API key is valid
   - Check SendGrid account status
   - Confirm sender email is verified

4. **OCR Processing Timeout**
   - AWS Textract may be slow
   - Increase timeout in `wait_for_ocr_completion()`
   - Check AWS credentials and permissions

### Debug Mode
```bash
# Enable verbose output
export PYTHONUNBUFFERED=1
python test_runner.py comprehensive
```

## Best Practices

### 1. **Test-Driven Development**
- Write tests before implementing features
- Run quick tests frequently during development
- Use comprehensive tests before committing

### 2. **Deployment Safety**
- **Always** run `pre-deploy` tests
- Never deploy if tests fail
- Run `post-deploy` tests to verify production

### 3. **Test Maintenance**
- Update test data when system changes
- Add new tests for new features
- Remove obsolete tests

### 4. **Environment Management**
- Use separate test environment when possible
- Don't run tests against production data
- Clean up test data after runs

## Quick Reference

```bash
# Development workflow
python test_runner.py quick              # Quick validation
python test_runner.py zapier             # Test webhooks
python test_runner.py ocr                # Test OCR
python test_runner.py workflow           # Test complete flow

# Deployment workflow
python test_runner.py pre-deploy         # Before deployment
python test_runner.py post-deploy        # After deployment

# Comprehensive testing
python test_runner.py comprehensive      # Full verification
```

## Success Criteria

### Tests Pass When:
- All API endpoints return expected responses
- Database records are created correctly
- Email sending is successful
- OCR processing completes without errors
- Complete workflow executes successfully

### Tests Fail When:
- API returns error responses
- Database operations fail
- Email sending fails
- OCR processing times out or fails
- Any component integration breaks

**Remember**: Failed tests indicate real issues that would affect users. Always investigate and fix failures before deployment.