# Water Pump Issue - Root Cause Analysis 🔍

## Executive Summary
Water pump IS working correctly, but **EventBridge automation is broken**. All actuator commands are manual, not automatic.

---

## Current Status

### ✅ What's Working:
- Water pump logic is CORRECT
- API endpoints responding properly
- Thresholds persisting in DynamoDB
- Manual control works fine

### ❌ What's Broken:
- **EventBridge NOT triggering** (0 automated commands in 24h)
- Only manual commands being sent
- Automatic control completely disabled

---

## Why Water Pump "Never Being Called"

**Current Situation:**
- Soil moisture: **52.76%**  
- Turn ON threshold: **< 30%**
- Turn OFF threshold: **> 31%**
- Current state: **OFF**

**Logic Decision:** Keep pump OFF (soil is above 31% threshold) ✅

### The pump WILL trigger when:
1. Soil drops **below 30%** → Pump turns ON
2. OR you enable EventBridge (currently disabled)

---

## 🚨 Critical Issues to Fix

### Issue #1: EventBridge Not Running
**Evidence:** 0 commands with `controller: "eventbridge-auto"` in 24 hours

**How to Fix:**
1. Go to AWS Console → **EventBridge** → **Rules**
2. Find your rule (e.g., `greenhouse-actuator-schedule`)
3. Check if it's **ENABLED** (must have green checkmark)
4. If disabled → Click "Enable"
5. Check **Targets** → Should point to your Lambda function
6. Wait 5 minutes, then run: `./check_eventbridge.sh`

**Expected Result:** Should see commands with `controller: "eventbridge-auto"`

---

### Issue #2: Narrow Threshold Range (30-31%)
**Problem:** Only 1% difference between turn_on and turn_off creates:
- Rapid on/off cycling
- No maintenance range
- Unnecessary actuator commands

**Recommended Fix:**
Update thresholds to wider range:
```json
{
  "soil_moisture": {
    "turn_on": 30,
    "turn_off": 60
  }
}
```

**How to Update:**
```bash
curl -X POST "https://m0tdyp9dia.execute-api.us-east-1.amazonaws.com/prod/actuators/thresholds" \
  -H "Content-Type: application/json" \
  -d '{
    "soil_moisture": {
      "turn_on": 30,
      "turn_off": 60
    }
  }'
```

Or use the dashboard UI to update thresholds.

---

## Testing the Fix

### Step 1: Deploy Updated Lambda
```bash
# Upload greenhouse-api/function.zip to AWS Lambda
# This version has enhanced logging
```

### Step 2: Enable EventBridge
Follow instructions in **EVENTBRIDGE_DEBUG_GUIDE.md**

### Step 3: Run Debug Script
```bash
./debug_water_pump.sh
```

### Step 4: Wait and Verify
```bash
# Wait 5-10 minutes for EventBridge to trigger
./check_eventbridge.sh
```

**Success Criteria:**
- Should see `eventbridge-auto` commands
- Water pump triggers when soil crosses thresholds
- CloudWatch logs show: "🤖 EventBridge scheduled actuator processing triggered"

---

## Understanding Water Pump Behavior

### Current Logic:
```
IF soil < turn_on threshold:
    → Turn pump ON
    
ELIF soil > turn_off threshold:
    → Turn pump OFF
    
ELSE:
    → Maintain current state (no command sent)
```

### Why "No Command Sent" is Correct:
When soil is between thresholds, the pump maintains its current state. This prevents:
- Excessive actuator wear
- Unnecessary database writes
- Rapid on/off cycles

### Example Scenario:
- Thresholds: Turn ON < 30%, Turn OFF > 60%
- Soil: 52% → In maintenance range (30-60%)
- Current state: OFF
- **Decision:** Keep OFF ✅ (correct!)

---

## CloudWatch Logs (After Deploying)

After deploying the updated Lambda, you'll see detailed logs:

```
💧 Water Pump Decision: soil=52%, current_state=OFF
   Thresholds: turn_on<30%, turn_off>60%
   → Decision: Maintain OFF (soil in maintenance range)
   ⏸️  No state change - no command stored
```

This helps debug exactly why decisions are made.

---

## Quick Commands

### Check if water pump should trigger:
```bash
./debug_water_pump.sh
```

### Check EventBridge status:
```bash
./check_eventbridge.sh
```

### Manually trigger control (for testing):
```bash
curl -X POST "https://m0tdyp9dia.execute-api.us-east-1.amazonaws.com/prod/actuators/control?greenhouse_id=greenhouse-01"
```

### View CloudWatch Logs:
AWS Console → CloudWatch → Log groups → `/aws/lambda/YOUR_LAMBDA_NAME`

---

## Summary

**The water pump IS working correctly!** It's not triggering because:
1. ✅ Soil moisture (52%) is above turn_off threshold (31%)
2. ❌ EventBridge is disabled (no automatic triggers)
3. ⚠️  Threshold range is too narrow (30-31%)

**To fix:**
1. Enable EventBridge in AWS Console
2. Widen threshold range (30-60% recommended)
3. Deploy updated Lambda for better logging
4. Wait 5 minutes and verify with `./check_eventbridge.sh`

**After fixing, the system will:**
- Automatically check sensors every 5 minutes
- Turn pump ON when soil < 30%
- Turn pump OFF when soil > 60%
- Maintain state when soil is 30-60%
