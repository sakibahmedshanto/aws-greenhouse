# EventBridge Debugging Guide 🔍

## Changes Made to Lambda Function

I've updated your Lambda function with:
1. **Enhanced logging** - Now logs every invocation with event details
2. **Controller tracking** - Commands now tagged as:
   - `eventbridge-auto` = EventBridge triggered (automated)
   - `api-auto` = API triggered (manual)
3. **Relaxed event matching** - Now checks for `source == 'aws.events'` (removed strict detail-type check)

## 🚨 Current Issue

**EventBridge is NOT triggering your Lambda!** All actuator commands show `controller: "api-auto"` (manual), none show `controller: "eventbridge-auto"` (automated).

---

## ✅ Step-by-Step Debugging

### **STEP 1: Deploy Updated Lambda**

```bash
cd /Users/sakibahmed/Downloads/s3\ 2/greenhouse-api
zip -r function.zip lambda.py
aws lambda update-function-code --function-name <YOUR_LAMBDA_NAME> --zip-file fileb://function.zip
```

Replace `<YOUR_LAMBDA_NAME>` with your actual Lambda function name (e.g., `greenhouse-api` or `GreenhouseAPI`).

---

### **STEP 2: Check CloudWatch Logs**

1. **Go to AWS Console** → **CloudWatch** → **Log groups**
2. **Find your Lambda log group**: `/aws/lambda/YOUR_LAMBDA_NAME`
3. **Click on the latest log stream**
4. **Look for these debug logs:**

```
============================================================
🔍 Lambda invoked!
Event Source: aws.events
Detail Type: Scheduled Event
HTTP Method: NOT SET
Full Event Keys: ['version', 'id', 'detail-type', 'source', 'account', 'time', 'region', 'resources', 'detail']
============================================================
🤖 EventBridge scheduled actuator processing triggered
```

**If you see these logs:**
✅ EventBridge IS triggering! Lambda is working!

**If you DON'T see these logs every 5 minutes:**
❌ EventBridge is NOT triggering. Proceed to STEP 3.

---

### **STEP 3: Verify EventBridge Rule**

1. **Go to AWS Console** → **EventBridge** → **Rules**
2. **Find your rule** (probably named `greenhouse-actuator-schedule` or similar)
3. **Check these settings:**

#### ✅ Rule Status
- **MUST be ENABLED** (green checkmark)
- If disabled → Click "Enable"

#### ✅ Schedule Expression
- Should be: `rate(5 minutes)` or `cron(0/5 * * * ? *)`

#### ✅ Target Configuration
- **Target Type:** AWS Lambda function
- **Function Name:** Your Lambda function (e.g., `greenhouse-api`)
- **Payload:** Empty or `{}`

#### ✅ Permissions
- EventBridge needs permission to invoke your Lambda
- Check under "Targets" → "Additional settings" → Should show a resource-based policy

---

### **STEP 4: Check Lambda Permissions**

1. **Go to AWS Console** → **Lambda** → **Your Function** → **Configuration** → **Permissions**
2. **Click on "Resource-based policy statements"**
3. **You should see a policy like:**

```json
{
  "Sid": "EventBridge-Invoke-Permission",
  "Effect": "Allow",
  "Principal": {
    "Service": "events.amazonaws.com"
  },
  "Action": "lambda:InvokeFunction",
  "Resource": "arn:aws:lambda:us-east-1:...:function:YOUR_FUNCTION",
  "Condition": {
    "ArnLike": {
      "AWS:SourceArn": "arn:aws:events:us-east-1:...:rule/YOUR_RULE"
    }
  }
}
```

**If this is missing:**
```bash
aws lambda add-permission \
  --function-name YOUR_LAMBDA_NAME \
  --statement-id EventBridge-Invoke \
  --action lambda:InvokeFunction \
  --principal events.amazonaws.com \
  --source-arn arn:aws:events:us-east-1:YOUR_ACCOUNT:rule/YOUR_RULE_NAME
```

---

### **STEP 5: Manually Test EventBridge Trigger**

Test if Lambda responds to EventBridge-style events:

```bash
aws lambda invoke \
  --function-name YOUR_LAMBDA_NAME \
  --payload '{"source":"aws.events","detail-type":"Scheduled Event","detail":{}}' \
  response.json
cat response.json
```

**Expected Output:**
```json
{
  "statusCode": 200,
  "body": "{\"processed\": 2, \"timestamp\": \"2026-02-09T...\", \"results\": [...]}"
}
```

Then check actuator history:
```bash
curl -s "https://m0tdyp9dia.execute-api.us-east-1.amazonaws.com/prod/actuators/history?greenhouse_id=greenhouse-01&hours=1" | jq '.commands | .[] | select(.controller == "eventbridge-auto")'
```

**If you see commands with `"controller": "eventbridge-auto"`:**
✅ Lambda is working! Issue is with EventBridge configuration.

---

### **STEP 6: Verify EventBridge Metrics**

1. **Go to AWS Console** → **EventBridge** → **Rules** → **Your Rule**
2. **Click "Monitoring" tab**
3. **Check these metrics:**
   - **Invocations** - Should increase every 5 minutes
   - **Failed Invocations** - Should be 0
   - **Throttled Rules** - Should be 0

**If "Invocations" is stuck at 0:**
- Rule is not firing → Check if rule is ENABLED
- Check schedule expression syntax

**If "Failed Invocations" > 0:**
- Lambda is rejecting EventBridge → Check Lambda permissions (STEP 4)

---

## 🎯 Quick Verification Commands

### Check if EventBridge is triggering (run every 5 minutes):
```bash
curl -s "https://m0tdyp9dia.execute-api.us-east-1.amazonaws.com/prod/actuators/history?greenhouse_id=greenhouse-01&hours=1" | jq '.commands | .[] | {timestamp, actuator, controller}'
```

Look for `"controller": "eventbridge-auto"` entries!

### Check latest sensor data:
```bash
curl -s "https://m0tdyp9dia.execute-api.us-east-1.amazonaws.com/prod/latest?greenhouse_id=greenhouse-01" | jq '.sensors | {soil_moisture: .soil_moisture.value, temperature: .temperature.value}'
```

---

## 🐛 Common Issues & Fixes

### Issue 1: "EventBridge rule exists but never triggers"
**Fix:** Rule might be DISABLED
- Go to EventBridge → Rules → Enable your rule

### Issue 2: "Lambda shows InvocationErrors"
**Fix:** Check CloudWatch Logs for Python errors
- Common: Missing DynamoDB permissions

### Issue 3: "EventBridge metrics show invocations, but no actuator commands"
**Fix:** Lambda event detection failed
- Check CloudWatch Logs for the debug output
- Event structure might be different than expected

### Issue 4: "Commands sent but not changing actuators"
**Fix:** Thresholds might prevent changes
- Check current sensor values vs thresholds
- Water pump: turns ON if soil < 25%, turns OFF if soil > 70%
- Cooling fan: turns ON if temp > 28°C, turns OFF if temp < 25°C

---

## 📊 Success Indicators

✅ **EventBridge is working when:**
1. CloudWatch Logs show `🤖 EventBridge scheduled actuator processing triggered` every 5 minutes
2. Actuator history shows commands with `"controller": "eventbridge-auto"`
3. EventBridge metrics show increasing "Invocations" count
4. Actuator states change automatically based on sensor readings

---

## 🚀 Next Steps After Fixing

Once EventBridge is triggering:

1. **Monitor for 15 minutes** - Should see 3 automatic triggers
2. **Check actuator history** - Should see `eventbridge-auto` entries
3. **Verify sensor-based decisions** - Commands should match threshold logic
4. **Update your README** - Document that automation is working

---

## 💡 Pro Tip

Add this query to your dashboard to show automation status:

```javascript
fetch(`${API_BASE_URL}/actuators/history?greenhouse_id=greenhouse-01&hours=1`)
  .then(res => res.json())
  .then(data => {
    const eventBridgeCommands = data.commands.filter(c => c.controller === 'eventbridge-auto');
    console.log(`🤖 EventBridge triggered ${eventBridgeCommands.length} times in last hour`);
  });
```

---

Good luck! 🍀 After deploying the updated Lambda, start with CloudWatch Logs (STEP 2).
