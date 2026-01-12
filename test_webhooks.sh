#!/bin/bash
# Test script for webhook endpoints
# Usage: ./test_webhooks.sh [base_url]

BASE_URL="${1:-https://internal-automation-production.up.railway.app}"

echo "=========================================="
echo "WEBHOOK TEST SCRIPT"
echo "=========================================="
echo "Target: $BASE_URL"
echo "Time: $(date)"
echo "=========================================="
echo ""

# Test 1: Documenso Webhook
echo "TEST 1: Documenso Webhook (DOCUMENT_COMPLETED)"
echo "------------------------------------------"

DOCUMENSO_PAYLOAD='{
  "event": "DOCUMENT_COMPLETED",
  "payload": {
    "id": 696673,
    "externalId": "swipey_onboardingv1",
    "title": "Swipey Account Setup Consent_TEST COMPANY",
    "status": "COMPLETED",
    "completedAt": "'$(date -u +%Y-%m-%dT%H:%M:%S.000Z)'",
    "createdAt": "2026-01-12T09:00:17.642Z",
    "formValues": null,
    "recipients": [
      {
        "id": 954123,
        "name": "Kalyan Amo",
        "email": "kalyanamo@gmail.com",
        "role": "SIGNER",
        "signingStatus": "SIGNED",
        "signedAt": "'$(date -u +%Y-%m-%dT%H:%M:%S.000Z)'"
      }
    ],
    "teamId": 20582,
    "templateId": 5442
  }
}'

echo "Sending request..."
TIME_START=$(date +%s.%N)

curl -X POST "$BASE_URL/documenso-webhook" \
  -H "Content-Type: application/json" \
  -d "$DOCUMENSO_PAYLOAD" \
  -w "\nHTTP Status: %{http_code}\nTime: %{time_total}s\n" \
  -s -o /tmp/documenso_response.txt

TIME_END=$(date +%s.%N)
ELAPSED=$(echo "$TIME_END - $TIME_START" | bc)

echo "Response saved to: /tmp/documenso_response.txt"
cat /tmp/documenso_response.txt
echo ""
echo "Total time: ${ELAPSED}s"

if (( $(echo "$ELAPSED > 30" | bc -l) )); then
  echo "⚠ WARNING: Response took longer than 30s - WOULD TIMEOUT!"
elif (( $(echo "$ELAPSED > 20" | bc -l) )); then
  echo "⚠ WARNING: Response took longer than 20s - getting close to timeout"
else
  echo "✓ OK: Response time is acceptable"
fi

echo ""
echo "=========================================="
echo ""

# Test 2: Typeform/Zapier Webhook
echo "TEST 2: Typeform/Zapier Webhook"
echo "------------------------------------------"

ZAPIER_PAYLOAD='{
  "customer_name": "Kalyan Amo",
  "customer_email": "kalyanamo@gmail.com",
  "company_name": "Test Company Sdn Bhd",
  "phone": "+60123456789",
  "business_type": "Technology",
  "typeform_response_id": "test_response_001",
  "submission_timestamp": "'$(date -u +%Y-%m-%dT%H:%M:%S)Z'",
  "clickup_task_id": "test_task_webhook_001",
  "clickup_task_url": "https://app.clickup.com/t/test_task_webhook_001"
}'

echo "Sending request..."
TIME_START=$(date +%s.%N)

curl -X POST "$BASE_URL/zapier-webhook" \
  -H "Content-Type: application/json" \
  -d "$ZAPIER_PAYLOAD" \
  -w "\nHTTP Status: %{http_code}\nTime: %{time_total}s\n" \
  -s -o /tmp/zapier_response.txt

TIME_END=$(date +%s.%N)
ELAPSED=$(echo "$TIME_END - $TIME_START" | bc)

echo "Response saved to: /tmp/zapier_response.txt"
cat /tmp/zapier_response.txt
echo ""
echo "Total time: ${ELAPSED}s"

if (( $(echo "$ELAPSED > 30" | bc -l) )); then
  echo "⚠ WARNING: Response took longer than 30s - WOULD TIMEOUT!"
elif (( $(echo "$ELAPSED > 20" | bc -l) )); then
  echo "⚠ WARNING: Response took longer than 20s - getting close to timeout"
else
  echo "✓ OK: Response time is acceptable"
fi

echo ""
echo "=========================================="
echo "TESTS COMPLETED"
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. Check Railway logs for [TIMING] markers"
echo "2. Identify slow operations"
echo "3. Apply background threading fixes if needed"
