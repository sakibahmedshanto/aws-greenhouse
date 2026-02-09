#!/bin/bash

API_URL="https://m0tdyp9dia.execute-api.us-east-1.amazonaws.com/prod"

echo "🧪 COMPLETE ACTUATOR SYSTEM TEST"
echo "=================================="
echo ""

# Step 1: Check DB thresholds
echo "1️⃣ Database Thresholds:"
echo "------------------------"
curl -s "${API_URL}/actuators/thresholds" | jq '.thresholds'
echo ""

# Step 2: Check current sensor values
echo "2️⃣ Current Sensor Values:"
echo "------------------------"
SENSOR_DATA=$(curl -s "${API_URL}/latest?greenhouse_id=greenhouse-01")
echo "$SENSOR_DATA" | jq '{
  greenhouse: .greenhouse_id,
  soil_moisture: .sensors.soil_moisture.value,
  temperature: .sensors.temperature.value,
  timestamp: .timestamp
}'
echo ""

# Step 3: Check actuator status
echo "3️⃣ Current Actuator States:"
echo "------------------------"
curl -s "${API_URL}/actuators/status?greenhouse_id=greenhouse-01" | jq '.actuators[] | {
  name: .name,
  state: .state,
  speed: .speed // "N/A",
  last_updated: .last_updated,
  reason: .reason
}'
echo ""

# Step 4: Manually trigger control logic
echo "4️⃣ Testing Control Logic (Manual Trigger):"
echo "------------------------"
CONTROL_RESULT=$(curl -s -X POST "${API_URL}/actuators/control?greenhouse_id=greenhouse-01")
echo "$CONTROL_RESULT" | jq '{
  sensor_values: .sensor_values,
  water_pump_decision: .decisions.water_pump,
  cooling_fan_decision: .decisions.cooling_fan,
  commands_sent: .commands_sent
}'
echo ""

# Step 5: Check recent commands
echo "5️⃣ Recent Actuator Commands (Last 5):"
echo "------------------------"
curl -s "${API_URL}/actuators/history?greenhouse_id=greenhouse-01&hours=1" | \
  jq -r '.commands | sort_by(.timestamp) | reverse | .[0:5] | .[] | 
  "\(.timestamp) | \(.actuator) → \(.state) \(.speed // "") | controller:\(.controller) | \(.reason)"'
echo ""

# Step 6: Check EventBridge automation
echo "6️⃣ EventBridge Automation Check:"
echo "------------------------"
EVENTBRIDGE_COUNT=$(curl -s "${API_URL}/actuators/history?greenhouse_id=greenhouse-01&hours=24" | \
  jq '[.commands[] | select(.controller == "eventbridge-auto")] | length')
echo "Automated commands (last 24h): ${EVENTBRIDGE_COUNT}"

if [ "$EVENTBRIDGE_COUNT" -eq 0 ]; then
    echo "❌ EventBridge NOT triggering!"
    echo "   → Check AWS Console → EventBridge → Rules"
    echo "   → Ensure rule is ENABLED"
    echo "   → Check Lambda permissions"
else
    echo "✅ EventBridge is working! (${EVENTBRIDGE_COUNT} automated commands)"
fi
echo ""

# Step 7: Test logic analysis
echo "7️⃣ Logic Analysis:"
echo "------------------------"
SOIL=$(echo "$SENSOR_DATA" | jq -r '.sensors.soil_moisture.value')
TEMP=$(echo "$SENSOR_DATA" | jq -r '.sensors.temperature.value')
THRESHOLDS=$(curl -s "${API_URL}/actuators/thresholds")
SOIL_ON=$(echo "$THRESHOLDS" | jq -r '.thresholds.soil_moisture.turn_on')
SOIL_OFF=$(echo "$THRESHOLDS" | jq -r '.thresholds.soil_moisture.turn_off')
TEMP_LOW=$(echo "$THRESHOLDS" | jq -r '.thresholds.temperature.turn_on_low')
TEMP_HIGH=$(echo "$THRESHOLDS" | jq -r '.thresholds.temperature.turn_on_high')
TEMP_OFF=$(echo "$THRESHOLDS" | jq -r '.thresholds.temperature.turn_off')

echo "Water Pump:"
echo "  Current soil: ${SOIL}%"
echo "  Thresholds: ON < ${SOIL_ON}%, OFF > ${SOIL_OFF}%"

# Convert to integers for comparison
SOIL_INT=${SOIL%.*}
SOIL_ON_INT=${SOIL_ON%.*}
SOIL_OFF_INT=${SOIL_OFF%.*}

if [ "$SOIL_INT" -lt "$SOIL_ON_INT" ]; then
    echo "  ✅ Should turn ON (soil < ${SOIL_ON}%)"
elif [ "$SOIL_INT" -gt "$SOIL_OFF_INT" ]; then
    echo "  ✅ Should turn OFF (soil > ${SOIL_OFF}%)"
else
    echo "  ⏸️  Maintenance range - keeps current state"
fi
echo ""

echo "Cooling Fan:"
echo "  Current temp: ${TEMP}°C"
echo "  Thresholds: LOW > ${TEMP_LOW}°C, HIGH > ${TEMP_HIGH}°C, OFF < ${TEMP_OFF}°C"

TEMP_INT=${TEMP%.*}
TEMP_LOW_INT=${TEMP_LOW%.*}
TEMP_HIGH_INT=${TEMP_HIGH%.*}
TEMP_OFF_INT=${TEMP_OFF%.*}

if [ "$TEMP_INT" -ge "$TEMP_HIGH_INT" ]; then
    echo "  ✅ Should be ON (HIGH)"
elif [ "$TEMP_INT" -ge "$TEMP_LOW_INT" ]; then
    echo "  ✅ Should be ON (LOW)"
elif [ "$TEMP_INT" -lt "$TEMP_OFF_INT" ]; then
    echo "  ✅ Should be OFF"
else
    echo "  ⏸️  Maintenance range - keeps current state"
fi
echo ""

echo "=================================="
echo "✅ Test Complete!"
echo ""
echo "Next steps:"
echo "1. Deploy updated Lambda (greenhouse-api/function.zip)"
echo "2. Enable EventBridge rule in AWS Console"
echo "3. Wait 5 minutes and re-run this test"
echo "4. Check CloudWatch Logs: /aws/lambda/YOUR_LAMBDA_NAME"
