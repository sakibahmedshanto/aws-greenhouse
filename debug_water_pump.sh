#!/bin/bash

API_URL="https://m0tdyp9dia.execute-api.us-east-1.amazonaws.com/prod"

echo "🔍 WATER PUMP DEBUGGING REPORT"
echo "================================"
echo ""

# Get current sensor values
echo "1️⃣ Current Sensor Values:"
SENSOR_DATA=$(curl -s "${API_URL}/latest?greenhouse_id=greenhouse-01")
SOIL=$(echo $SENSOR_DATA | jq -r '.sensors.soil_moisture.value')
TEMP=$(echo $SENSOR_DATA | jq -r '.sensors.temperature.value')
echo "   Soil Moisture: ${SOIL}%"
echo "   Temperature: ${TEMP}°C"
echo ""

# Get thresholds
echo "2️⃣ Water Pump Thresholds:"
THRESHOLDS=$(curl -s "${API_URL}/actuators/thresholds")
TURN_ON=$(echo $THRESHOLDS | jq -r '.thresholds.soil_moisture.turn_on')
TURN_OFF=$(echo $THRESHOLDS | jq -r '.thresholds.soil_moisture.turn_off')
echo "   Turn ON when soil < ${TURN_ON}%"
echo "   Turn OFF when soil > ${TURN_OFF}%"
echo ""

# Get current pump state
echo "3️⃣ Current Water Pump State:"
PUMP_STATE=$(curl -s "${API_URL}/actuators/status?greenhouse_id=greenhouse-01" | jq -r '.actuators[] | select(.name == "water_pump")')
echo "$PUMP_STATE" | jq -r '"   State: \(.state)\n   Last Updated: \(.last_updated)\n   Reason: \(.reason)"'
echo ""

# Check logic
echo "4️⃣ Water Pump Logic Analysis:"
echo "   Current soil: ${SOIL}%"
echo "   Turn ON threshold: < ${TURN_ON}%"
echo "   Turn OFF threshold: > ${TURN_OFF}%"
echo ""

# Use bc for floating point comparison
SOIL_INT=${SOIL%.*}
TURN_ON_INT=${TURN_ON%.*}
TURN_OFF_INT=${TURN_OFF%.*}

if [ "$SOIL_INT" -lt "$TURN_ON_INT" ]; then
    echo "   ✅ Soil is BELOW turn_on threshold"
    echo "   → Water pump SHOULD turn ON"
elif [ "$SOIL_INT" -gt "$TURN_OFF_INT" ]; then
    echo "   ✅ Soil is ABOVE turn_off threshold"
    echo "   → Water pump SHOULD turn OFF"
else
    echo "   ⚠️  Soil is IN MAINTENANCE RANGE (${TURN_ON}% - ${TURN_OFF}%)"
    echo "   → Water pump will MAINTAIN current state"
    echo "   → No command will be sent (this is correct behavior!)"
fi
echo ""

# Test control logic
echo "5️⃣ Testing Control Logic (Manual Trigger):"
CONTROL_RESULT=$(curl -s -X POST "${API_URL}/actuators/control?greenhouse_id=greenhouse-01")
echo "$CONTROL_RESULT" | jq '{
  soil_moisture: .sensor_values.soil_moisture,
  water_pump: .decisions.water_pump,
  commands_sent: .commands_sent
}'
echo ""

# Check recent water pump commands
echo "6️⃣ Recent Water Pump Commands (Last 24h):"
PUMP_HISTORY=$(curl -s "${API_URL}/actuators/history?greenhouse_id=greenhouse-01&hours=24" | \
  jq -r '.commands[] | select(.actuator == "water_pump") | "\(.timestamp) | \(.state) | \(.reason) | controller:\(.controller)"')

if [ -z "$PUMP_HISTORY" ]; then
    echo "   ⚠️  NO water pump commands in last 24 hours!"
    echo "   This means soil moisture stayed in maintenance range"
else
    echo "$PUMP_HISTORY" | head -10
fi
echo ""

# Check EventBridge
echo "7️⃣ EventBridge Automation Status:"
EVENTBRIDGE_COUNT=$(curl -s "${API_URL}/actuators/history?greenhouse_id=greenhouse-01&hours=24" | \
  jq '[.commands[] | select(.controller == "eventbridge-auto")] | length')
echo "   Automated commands (last 24h): ${EVENTBRIDGE_COUNT}"

if [ "$EVENTBRIDGE_COUNT" -eq 0 ]; then
    echo "   ❌ EventBridge is NOT triggering!"
    echo "   → Automatic control is disabled"
    echo "   → You must manually trigger or fix EventBridge"
else
    echo "   ✅ EventBridge is working"
fi
echo ""

echo "📋 Summary:"
echo "================================"
if [ "$SOIL_INT" -ge "$TURN_ON_INT" ] && [ "$SOIL_INT" -le "$TURN_OFF_INT" ]; then
    echo "Water pump is NOT triggering because:"
    echo "  • Soil moisture (${SOIL}%) is within maintenance range (${TURN_ON}%-${TURN_OFF}%)"
    echo "  • No state change is needed"
    echo "  • This is CORRECT behavior!"
    echo ""
    echo "To trigger water pump:"
    echo "  • Wait for soil to drop below ${TURN_ON}% (pump will turn ON)"
    echo "  • OR wait for soil to rise above ${TURN_OFF}% (pump will turn OFF)"
    echo "  • OR adjust thresholds on dashboard to trigger at different values"
fi

if [ "$EVENTBRIDGE_COUNT" -eq 0 ]; then
    echo ""
    echo "⚠️  CRITICAL: EventBridge automation is NOT working!"
    echo "   Read EVENTBRIDGE_DEBUG_GUIDE.md to fix this issue"
fi
