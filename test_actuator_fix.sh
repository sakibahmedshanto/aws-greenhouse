#!/bin/bash

echo "🧪 Testing Actuator Control Fix..."
echo ""

API_URL="https://m0tdyp9dia.execute-api.us-east-1.amazonaws.com/prod"

echo "1️⃣ Current Sensor Values:"
echo "================================"
curl -s "${API_URL}/latest?greenhouse_id=greenhouse-01" | \
  jq -r '"Soil: \(.sensors.soil_moisture.value)% | Temp: \(.sensors.temperature.value)°C"'

echo ""
echo "2️⃣ Current Thresholds:"
echo "================================"
curl -s "${API_URL}/actuators/thresholds" | \
  jq -r '.thresholds | "Soil: ON<\(.soil_moisture.turn_on)%, OFF>\(.soil_moisture.turn_off)% | Temp: LOW>\(.temperature.turn_on_low)°C, HIGH>\(.temperature.turn_on_high)°C, OFF<\(.temperature.turn_off)°C"'

echo ""
echo "3️⃣ Triggering Control Logic (Manual Test):"
echo "================================"
curl -s -X POST "${API_URL}/actuators/control?greenhouse_id=greenhouse-01" | \
  jq '{decisions: .decisions, commands_sent: .commands_sent}'

echo ""
echo "4️⃣ Wait 5 seconds and trigger again (should show 0 commands if nothing changed):"
echo "================================"
sleep 5
curl -s -X POST "${API_URL}/actuators/control?greenhouse_id=greenhouse-01" | \
  jq '{decisions: .decisions, commands_sent: .commands_sent}'

echo ""
echo "5️⃣ Recent Command History:"
echo "================================"
curl -s "${API_URL}/actuators/history?greenhouse_id=greenhouse-01&hours=1" | \
  jq -r '.commands[] | "\(.timestamp) | \(.actuator) -> \(.state) \(.speed // \"\") | \(.reason)"' | tail -10

echo ""
echo "✅ Test Complete!"
echo ""
echo "Expected behavior:"
echo "  - First control call: May send commands if state/speed needs to change"
echo "  - Second control call: Should send 0 commands (no duplicate fan commands!)"
