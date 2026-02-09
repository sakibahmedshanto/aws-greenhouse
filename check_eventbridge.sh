#!/bin/bash

# EventBridge Automation Checker
# Run this script to verify if EventBridge is triggering your Lambda

echo "🔍 Checking EventBridge Automation Status..."
echo ""

API_URL="https://m0tdyp9dia.execute-api.us-east-1.amazonaws.com/prod"

echo "📊 Recent Actuator Commands (Last hour):"
echo "========================================"
curl -s "${API_URL}/actuators/history?greenhouse_id=greenhouse-01&hours=1" | \
  jq -r '.commands[] | "\(.timestamp) | \(.actuator) -> \(.state) | Controller: \(.controller)"' | \
  tail -10

echo ""
echo "🤖 EventBridge Automated Commands:"
echo "========================================"
EVENTBRIDGE_COUNT=$(curl -s "${API_URL}/actuators/history?greenhouse_id=greenhouse-01&hours=1" | \
  jq '[.commands[] | select(.controller == "eventbridge-auto")] | length')

echo "Count: $EVENTBRIDGE_COUNT commands in the last hour"

if [ "$EVENTBRIDGE_COUNT" -gt 0 ]; then
  echo "✅ EventBridge IS working!"
  curl -s "${API_URL}/actuators/history?greenhouse_id=greenhouse-01&hours=1" | \
    jq -r '.commands[] | select(.controller == "eventbridge-auto") | "  → \(.timestamp) | \(.actuator) -> \(.state)"'
else
  echo "❌ EventBridge NOT triggering!"
  echo ""
  echo "Troubleshooting steps:"
  echo "1. Check AWS Console → EventBridge → Rules"
  echo "2. Verify rule is ENABLED"
  echo "3. Check CloudWatch Logs: /aws/lambda/<YOUR_LAMBDA_NAME>"
  echo "4. Read EVENTBRIDGE_DEBUG_GUIDE.md for full debugging steps"
fi

echo ""
echo "📈 Current Sensor Values:"
echo "========================================"
curl -s "${API_URL}/latest?greenhouse_id=greenhouse-01" | \
  jq -r '"\(.greenhouse_id) | Soil: \(.sensors.soil_moisture.value)% | Temp: \(.sensors.temperature.value)°C | Updated: \(.timestamp)"'

echo ""
echo "🎯 Current Actuator States:"
echo "========================================"
curl -s "${API_URL}/actuators/status?greenhouse_id=greenhouse-01" | \
  jq -r '.actuators[] | "\(.name): \(.state) (Last: \(.last_updated))"'
