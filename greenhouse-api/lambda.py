"""
Smart GreenHouse - API Handler & Actuator Control Lambda

ARCHITECTURE:
-------------
1. EC2 Instance: Simulates 2 greenhouses, generates sensor data
2. SNS Topic: Receives sensor readings from EC2
3. SQS Queue: Subscribed to SNS, buffers sensor messages
4. Data Processing Lambda: Reads from SQS → Writes to DynamoDB sensor-data table
5. THIS LAMBDA (API Handler): 
   - Serves all API endpoints for the dashboard
   - Reads from sensor-data table
   - Makes actuator decisions based on thresholds
   - Writes actuator commands to actuator-commands table
   - Triggered by:
     * API Gateway (for dashboard requests)
     * EventBridge (every 5 minutes for automatic control)
6. DynamoDB Tables:
   - greenhouse-sensor-data: Stores sensor readings
   - greenhouse-actuator-commands: Stores actuator commands and config
7. S3: Hosts static dashboard website

This Lambda provides:
- Sensor data API endpoints (latest, history, stats, alerts)
- Actuator control API endpoints (status, history, manual, thresholds)
- Automatic actuator decision-making based on sensor readings
- Threshold management with DynamoDB persistence
"""

import json
import boto3
from boto3.dynamodb.conditions import Key
from datetime import datetime, timedelta
from decimal import Decimal

# Initialize AWS services
dynamodb = boto3.resource('dynamodb')
sensor_table = dynamodb.Table('greenhouse-sensor-data')
actuator_table = dynamodb.Table('greenhouse-actuator-commands')

# CORS headers for browser access
CORS_HEADERS = {
    'Content-Type': 'application/json',
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type'
}

# ============================================
# ACTUATOR CONTROL THRESHOLDS
# ============================================

# Default thresholds - ONLY used for initial database setup
# After first setup, ALL values come from DynamoDB
INITIAL_THRESHOLDS = {
    'soil_moisture': {
        'turn_on': 30,      # Turn ON water pump when below this
        'turn_off': 65,     # Turn OFF water pump when above this
    },
    'temperature': {
        'turn_on_low': 30,  # Turn ON fan (LOW speed) when above this
        'turn_on_high': 35, # Turn ON fan (HIGH speed) when above this
        'turn_off': 25,     # Turn OFF fan when below this
    }
}

def load_thresholds():
    """Load thresholds from DynamoDB. Initialize DB if empty."""
    try:
        response = actuator_table.get_item(
            Key={
                'greenhouse_id': '__CONFIG__',
                'timestamp': 'thresholds'
            }
        )
        
        if 'Item' in response and 'data' in response['Item']:
            # Convert Decimal to float
            thresholds = json.loads(json.dumps(response['Item']['data'], default=decimal_default))
            print(f"✅ Loaded thresholds from DB: soil_on={thresholds['soil_moisture']['turn_on']}%, soil_off={thresholds['soil_moisture']['turn_off']}%")
            return thresholds
        else:
            # First time setup - initialize DB with default values
            print("📋 DB empty - Initializing with default thresholds")
            save_thresholds(INITIAL_THRESHOLDS)
            return INITIAL_THRESHOLDS.copy()
    except Exception as e:
        print(f"⚠️ Error loading thresholds: {e}")
        # Try to initialize DB
        try:
            save_thresholds(INITIAL_THRESHOLDS)
            print("✅ Initialized DB with default thresholds after error")
            return INITIAL_THRESHOLDS.copy()
        except:
            print("❌ Failed to initialize DB, using in-memory defaults")
            return INITIAL_THRESHOLDS.copy()

def save_thresholds(thresholds):
    """Save thresholds to DynamoDB for persistence"""
    try:
        actuator_table.put_item(
            Item={
                'greenhouse_id': '__CONFIG__',
                'timestamp': 'thresholds',
                'data': float_to_decimal(thresholds),
                'updated_at': datetime.utcnow().isoformat() + 'Z'
            }
        )
        print("✅ Saved thresholds to DynamoDB")
        return True
    except Exception as e:
        print(f"❌ Error saving thresholds: {e}")
        return False


# ============================================
# UTILITY FUNCTIONS
# ============================================

def decimal_default(obj):
    """JSON serializer for Decimal types"""
    if isinstance(obj, Decimal):
        return float(obj)
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


def response(status_code, body):
    """Build API response with CORS headers"""
    return {
        'statusCode': status_code,
        'headers': CORS_HEADERS,
        'body': json.dumps(body, default=decimal_default)
    }


def float_to_decimal(obj):
    """Convert floats to Decimal for DynamoDB"""
    if isinstance(obj, float):
        return Decimal(str(round(obj, 4)))
    elif isinstance(obj, dict):
        return {k: float_to_decimal(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [float_to_decimal(i) for i in obj]
    return obj


# ============================================
# SENSOR DATA ENDPOINTS
# ============================================

def get_latest_reading(greenhouse_id):
    """Get most recent sensor reading"""
    result = sensor_table.query(
        KeyConditionExpression=Key('greenhouse_id').eq(greenhouse_id),
        ScanIndexForward=False,
        Limit=1
    )
    
    if result['Items']:
        return result['Items'][0]
    return None


def get_readings_history(greenhouse_id, hours=6):
    """Get sensor readings for time period"""
    end_time = datetime.utcnow()
    start_time = end_time - timedelta(hours=hours)
    
    result = sensor_table.query(
        KeyConditionExpression=
            Key('greenhouse_id').eq(greenhouse_id) &
            Key('timestamp').between(
                start_time.isoformat() + 'Z',
                end_time.isoformat() + 'Z'
            ),
        ScanIndexForward=True
    )
    
    return result['Items']


def get_statistics(greenhouse_id, hours=24):
    """Calculate statistics for time period"""
    readings = get_readings_history(greenhouse_id, hours)
    
    if not readings:
        return None
    
    sensors = ['temperature', 'humidity', 'soil_moisture', 'light_intensity']
    stats = {}
    
    for sensor in sensors:
        values = [float(r['sensors'][sensor]['value']) for r in readings if sensor in r['sensors']]
        
        if values:
            stats[sensor] = {
                'min': round(min(values), 2),
                'max': round(max(values), 2),
                'avg': round(sum(values) / len(values), 2),
                'current': values[-1] if values else None
            }
    
    # Count alerts
    total_alerts = sum(int(r.get('alert_count', 0)) for r in readings)
    
    stats['summary'] = {
        'total_readings': len(readings),
        'total_alerts': total_alerts,
        'period_hours': hours
    }
    
    return stats


def get_recent_alerts(greenhouse_id, limit=10):
    """Get recent alerts"""
    end_time = datetime.utcnow()
    start_time = end_time - timedelta(hours=24)
    
    result = sensor_table.query(
        KeyConditionExpression=
            Key('greenhouse_id').eq(greenhouse_id) &
            Key('timestamp').gte(start_time.isoformat() + 'Z'),
        FilterExpression='alert_count > :zero',
        ExpressionAttributeValues={':zero': 0},
        ScanIndexForward=False
    )
    
    alerts = []
    for item in result['Items'][:limit]:
        for alert in item.get('alerts', []):
            alert['reading_timestamp'] = item['timestamp']
            alerts.append(alert)
    
    return alerts


def list_greenhouses():
    """Get list of all greenhouses with data"""
    result = sensor_table.scan(
        ProjectionExpression='greenhouse_id',
        Select='SPECIFIC_ATTRIBUTES'
    )
    
    greenhouse_ids = list(set(item['greenhouse_id'] for item in result['Items']))
    
    return sorted(greenhouse_ids)


# ============================================
# ACTUATOR CONTROL LOGIC
# ============================================

def get_last_actuator_state(greenhouse_id, actuator_name):
    """Get the last known state and speed of an actuator"""
    try:
        response = actuator_table.query(
            KeyConditionExpression=Key('greenhouse_id').eq(greenhouse_id),
            ScanIndexForward=False,
            Limit=10
        )
        
        for item in response.get('Items', []):
            if item.get('actuator') == actuator_name:
                state = item.get('state', 'OFF')
                speed = item.get('speed', 'OFF')
                return {'state': state, 'speed': speed}
        
        return {'state': 'OFF', 'speed': 'OFF'}
    except Exception as e:
        print(f"Error getting actuator state: {e}")
        return {'state': 'OFF', 'speed': 'OFF'}


def store_actuator_command(greenhouse_id, actuator_name, state, reason, sensor_values=None, speed=None):
    """Store actuator command in DynamoDB"""
    timestamp = datetime.utcnow().isoformat() + 'Z'
    
    command = {
        'greenhouse_id': greenhouse_id,
        'timestamp': timestamp,
        'actuator': actuator_name,
        'state': state,
        'reason': reason,
        'sensor_values': float_to_decimal(sensor_values or {}),
        'controller': 'api-auto'
    }
    
    if speed:
        command['speed'] = speed
    
    try:
        actuator_table.put_item(Item=command)
        print(f"✅ Stored command: {actuator_name} -> {state}")
        return command
    except Exception as e:
        print(f"❌ Error storing command: {e}")
        return None


def make_actuator_decisions(greenhouse_id):
    """
    Get latest sensor reading and make actuator decisions
    Returns: list of commands sent
    """
    # Load current thresholds from DynamoDB (fresh on every call)
    THRESHOLDS = load_thresholds()
    print(f"🔧 Using thresholds from DB: {THRESHOLDS}")
    
    # Get latest sensor reading
    latest = get_latest_reading(greenhouse_id)
    
    if not latest or 'sensors' not in latest:
        return {'error': 'No sensor data available', 'commands': []}
    
    sensors = latest['sensors']
    soil_moisture = float(sensors.get('soil_moisture', {}).get('value', 50))
    temperature = float(sensors.get('temperature', {}).get('value', 25))
    
    commands_sent = []
    
    # ==========================================
    # WATER PUMP CONTROL
    # ==========================================
    pump_status = get_last_actuator_state(greenhouse_id, 'water_pump')
    pump_current_state = pump_status['state']
    pump_new_state = pump_current_state
    pump_reason = ''
    
    print(f"💧 Water Pump Decision: soil={soil_moisture}%, current_state={pump_current_state}")
    print(f"   Thresholds: turn_on<{THRESHOLDS['soil_moisture']['turn_on']}%, turn_off>{THRESHOLDS['soil_moisture']['turn_off']}%")
    
    if soil_moisture < THRESHOLDS['soil_moisture']['turn_on']:
        pump_new_state = 'ON'
        pump_reason = f'Soil moisture low: {soil_moisture}% (threshold: {THRESHOLDS["soil_moisture"]["turn_on"]}%)'
        print(f"   → Decision: Turn ON (soil below turn_on threshold)")
    elif soil_moisture >= THRESHOLDS['soil_moisture']['turn_off']:
        pump_new_state = 'OFF'
        pump_reason = f'Soil moisture sufficient: {soil_moisture}% (threshold: {THRESHOLDS["soil_moisture"]["turn_off"]}%)'
        print(f"   → Decision: Turn OFF (soil above turn_off threshold)")
    else:
        pump_reason = f'Soil moisture in range: {soil_moisture}% - maintaining {pump_current_state}'
        print(f"   → Decision: Maintain {pump_current_state} (soil in maintenance range)")
    
    # Only store command if state changes
    if pump_new_state != pump_current_state:
        print(f"   ✅ State changed! Storing command: {pump_current_state} → {pump_new_state}")
        cmd = store_actuator_command(
            greenhouse_id, 
            'water_pump', 
            pump_new_state, 
            pump_reason,
            {'soil_moisture': soil_moisture}
        )
        if cmd:
            commands_sent.append(cmd)
    else:
        print(f"   ⏸️  No state change - no command stored")
    
    # ==========================================
    # COOLING FAN CONTROL
    # ==========================================
    fan_status = get_last_actuator_state(greenhouse_id, 'cooling_fan')
    fan_current_state = fan_status['state']
    fan_current_speed = fan_status['speed']
    fan_new_state = fan_current_state
    fan_new_speed = fan_current_speed
    fan_reason = ''
    
    print(f"🌡️  Cooling Fan Decision: temp={temperature}°C, current_state={fan_current_state}@{fan_current_speed}")
    print(f"   Thresholds: LOW>{THRESHOLDS['temperature']['turn_on_low']}°C, HIGH>{THRESHOLDS['temperature']['turn_on_high']}°C, OFF<{THRESHOLDS['temperature']['turn_off']}°C")
    
    if temperature >= THRESHOLDS['temperature']['turn_on_high']:
        fan_new_state = 'ON'
        fan_new_speed = 'HIGH'
        fan_reason = f'Temperature critical: {temperature}°C (threshold: {THRESHOLDS["temperature"]["turn_on_high"]}°C)'
    elif temperature >= THRESHOLDS['temperature']['turn_on_low']:
        fan_new_state = 'ON'
        fan_new_speed = 'LOW'
        fan_reason = f'Temperature high: {temperature}°C (threshold: {THRESHOLDS["temperature"]["turn_on_low"]}°C)'
    elif temperature < THRESHOLDS['temperature']['turn_off']:
        fan_new_state = 'OFF'
        fan_new_speed = 'OFF'
        fan_reason = f'Temperature normal: {temperature}°C (threshold: {THRESHOLDS["temperature"]["turn_off"]}°C)'
    else:
        fan_reason = f'Temperature acceptable: {temperature}°C - maintaining {fan_current_state} @ {fan_current_speed}'
    
    # Store command ONLY if state changes OR speed changes
    if fan_new_state != fan_current_state or fan_new_speed != fan_current_speed:
        print(f"   ✅ State/Speed changed! Storing command: {fan_current_state}@{fan_current_speed} → {fan_new_state}@{fan_new_speed}")
        cmd = store_actuator_command(
            greenhouse_id, 
            'cooling_fan', 
            fan_new_state, 
            fan_reason,
            {'temperature': temperature},
            fan_new_speed
        )
        if cmd:
            commands_sent.append(cmd)
    else:
        print(f"   ⏸️  No state/speed change - no command stored")
    
    print(f"📊 Total commands sent: {len(commands_sent)}")
    
    return {
        'greenhouse_id': greenhouse_id,
        'timestamp': latest['timestamp'],
        'sensor_values': {
            'soil_moisture': soil_moisture,
            'temperature': temperature
        },
        'decisions': {
            'water_pump': {
                'previous_state': pump_current_state,
                'new_state': pump_new_state,
                'reason': pump_reason
            },
            'cooling_fan': {
                'previous_state': fan_current_state,
                'previous_speed': fan_current_speed,
                'new_state': fan_new_state,
                'new_speed': fan_new_speed,
                'reason': fan_reason
            }
        },
        'commands_sent': len(commands_sent)
    }


def process_all_greenhouses():
    """
    Process actuator decisions for all greenhouses
    This is called by EventBridge scheduled rule
    """
    greenhouses = list_greenhouses()
    results = []
    
    print(f"🤖 Processing {len(greenhouses)} greenhouses...")
    
    for greenhouse_id in greenhouses:
        try:
            result = make_actuator_decisions(greenhouse_id)
            results.append(result)
            print(f"✅ {greenhouse_id}: {result.get('commands_sent', 0)} commands sent")
        except Exception as e:
            print(f"❌ Error processing {greenhouse_id}: {e}")
            results.append({
                'greenhouse_id': greenhouse_id,
                'error': str(e)
            })
    
    return {
        'processed': len(results),
        'timestamp': datetime.utcnow().isoformat() + 'Z',
        'results': results
    }


# ============================================
# ACTUATOR STATUS & HISTORY
# ============================================

def get_actuator_status(greenhouse_id):
    """Get current status of all actuators"""
    try:
        result = actuator_table.query(
            KeyConditionExpression=Key('greenhouse_id').eq(greenhouse_id),
            ScanIndexForward=False,
            Limit=20
        )
        
        actuators = {}
        
        for item in result.get('Items', []):
            actuator_name = item.get('actuator')
            
            if actuator_name not in actuators:
                actuators[actuator_name] = {
                    'name': actuator_name,
                    'state': item.get('state', 'UNKNOWN'),
                    'last_updated': item.get('timestamp'),
                    'reason': item.get('reason', ''),
                    'sensor_values': item.get('sensor_values', {})
                }
                
                if 'speed' in item:
                    actuators[actuator_name]['speed'] = item.get('speed')
        
        return {
            'greenhouse_id': greenhouse_id,
            'actuators': list(actuators.values()),
            'count': len(actuators),
            'thresholds': load_thresholds()
        }
    
    except Exception as e:
        print(f"Error getting actuator status: {e}")
        return {'error': str(e), 'actuators': []}


def get_actuator_history(greenhouse_id, hours=24):
    """Get history of actuator commands"""
    try:
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=hours)
        
        result = actuator_table.query(
            KeyConditionExpression=
                Key('greenhouse_id').eq(greenhouse_id) &
                Key('timestamp').between(
                    start_time.isoformat() + 'Z',
                    end_time.isoformat() + 'Z'
                ),
            ScanIndexForward=False
        )
        
        return {
            'greenhouse_id': greenhouse_id,
            'commands': result.get('Items', []),
            'count': len(result.get('Items', [])),
            'hours': hours
        }
    
    except Exception as e:
        print(f"Error getting actuator history: {e}")
        return {'error': str(e), 'commands': []}


# ============================================
# MANUAL CONTROL & THRESHOLDS
# ============================================

def manual_control_actuator(greenhouse_id, actuator_name, state, speed=None):
    """Manually control an actuator"""
    valid_actuators = ['water_pump', 'cooling_fan']
    valid_states = ['ON', 'OFF']
    
    if actuator_name not in valid_actuators:
        return {'error': f'Invalid actuator: {actuator_name}. Must be one of {valid_actuators}'}
    
    if state not in valid_states:
        return {'error': f'Invalid state: {state}. Must be one of {valid_states}'}
    
    reason = f'Manual control: {state}'
    
    cmd = store_actuator_command(
        greenhouse_id, 
        actuator_name, 
        state, 
        reason,
        {},
        speed
    )
    
    if cmd:
        return {
            'success': True,
            'message': f'{actuator_name} set to {state}',
            'command': cmd
        }
    else:
        return {'error': 'Failed to store command'}


def get_thresholds():
    """Get current threshold values"""
    return load_thresholds()


def update_thresholds(new_thresholds):
    """Update threshold values and save to DynamoDB"""
    try:
        # Load current thresholds
        current_thresholds = load_thresholds()
        
        # Update with new values
        if 'soil_moisture' in new_thresholds:
            if 'turn_on' in new_thresholds['soil_moisture']:
                current_thresholds['soil_moisture']['turn_on'] = float(new_thresholds['soil_moisture']['turn_on'])
            if 'turn_off' in new_thresholds['soil_moisture']:
                current_thresholds['soil_moisture']['turn_off'] = float(new_thresholds['soil_moisture']['turn_off'])
        
        if 'temperature' in new_thresholds:
            if 'turn_on_low' in new_thresholds['temperature']:
                current_thresholds['temperature']['turn_on_low'] = float(new_thresholds['temperature']['turn_on_low'])
            if 'turn_on_high' in new_thresholds['temperature']:
                current_thresholds['temperature']['turn_on_high'] = float(new_thresholds['temperature']['turn_on_high'])
            if 'turn_off' in new_thresholds['temperature']:
                current_thresholds['temperature']['turn_off'] = float(new_thresholds['temperature']['turn_off'])
        
        # Save to DynamoDB
        if save_thresholds(current_thresholds):
            return {
                'success': True,
                'message': 'Thresholds updated and saved to database',
                'thresholds': current_thresholds
            }
        else:
            return {
                'success': False,
                'error': 'Failed to save thresholds to database',
                'thresholds': current_thresholds
            }
    
    except Exception as e:
        return {'error': f'Failed to update thresholds: {str(e)}'}


# ============================================
# MAIN HANDLER
# ============================================

def lambda_handler(event, context):
    """
    Main handler - processes both API Gateway and EventBridge events
    
    EventBridge invokes this function every 5 minutes to process actuators
    API Gateway invokes it for dashboard requests
    """
    
    # Debug logging for all invocations
    print("=" * 60)
    print(f"🔍 Lambda Invoked at {datetime.utcnow().isoformat()}Z")
    print(f"   Event source: {event.get('source', 'NOT_SET')}")
    print(f"   Detail-type: {event.get('detail-type', 'NOT_SET')}")
    print(f"   HTTP method: {event.get('httpMethod', 'NOT_SET')}")
    print(f"   Path: {event.get('path', 'NOT_SET')}")
    print("=" * 60)
    
    # Check if this is an EventBridge scheduled event
    if event.get('source') == 'aws.events':
        print("🤖 EventBridge scheduled actuator processing triggered")
        print(f"   Event detail-type: {event.get('detail-type')}")
        result = process_all_greenhouses()
        print(f"✅ EventBridge processing complete: {result.get('processed', 0)} greenhouses")
        return {
            'statusCode': 200,
            'body': json.dumps(result, default=decimal_default)
        }
    
    # Handle CORS preflight
    if event.get('httpMethod') == 'OPTIONS':
        return response(200, {'message': 'OK'})
    
    # Parse path and parameters
    path = event.get('path', '/')
    method = event.get('httpMethod', 'GET')
    params = event.get('queryStringParameters') or {}
    
    greenhouse_id = params.get('greenhouse_id', 'greenhouse-01')
    
    try:
        # ==========================================
        # SENSOR DATA ENDPOINTS
        # ==========================================
        
        if path == '/latest' and method == 'GET':
            data = get_latest_reading(greenhouse_id)
            if data:
                return response(200, data)
            return response(404, {'error': 'No data found'})
        
        elif path == '/history' and method == 'GET':
            hours = int(params.get('hours', 6))
            hours = min(hours, 168)
            data = get_readings_history(greenhouse_id, hours)
            return response(200, {'readings': data, 'count': len(data)})
        
        elif path == '/stats' and method == 'GET':
            hours = int(params.get('hours', 24))
            data = get_statistics(greenhouse_id, hours)
            if data:
                return response(200, data)
            return response(404, {'error': 'No data found'})
        
        elif path == '/alerts' and method == 'GET':
            limit = int(params.get('limit', 10))
            data = get_recent_alerts(greenhouse_id, limit)
            return response(200, {'alerts': data, 'count': len(data)})
        
        elif path == '/greenhouses' and method == 'GET':
            data = list_greenhouses()
            return response(200, {'greenhouses': data})
        
        # ==========================================
        # ACTUATOR CONTROL ENDPOINTS
        # ==========================================
        
        elif path == '/actuators/status' and method == 'GET':
            """Get current actuator status"""
            data = get_actuator_status(greenhouse_id)
            return response(200, data)
        
        elif path == '/actuators/history' and method == 'GET':
            """Get actuator command history"""
            hours = int(params.get('hours', 24))
            data = get_actuator_history(greenhouse_id, hours)
            return response(200, data)
        
        elif path == '/actuators/control' and method == 'POST':
            """Manually trigger control logic for one greenhouse"""
            data = make_actuator_decisions(greenhouse_id)
            return response(200, data)
        
        elif path == '/actuators/manual' and method == 'POST':
            """Manual actuator control"""
            try:
                body = json.loads(event.get('body', '{}'))
                actuator = body.get('actuator')
                state = body.get('state')
                speed = body.get('speed')
                
                if not actuator or not state:
                    return response(400, {'error': 'Missing actuator or state'})
                
                data = manual_control_actuator(greenhouse_id, actuator, state, speed)
                return response(200, data)
            except json.JSONDecodeError:
                return response(400, {'error': 'Invalid JSON in request body'})
        
        elif path == '/actuators/thresholds' and method == 'GET':
            """Get current thresholds"""
            data = get_thresholds()
            return response(200, {'thresholds': data})
        
        elif path == '/actuators/thresholds' and method == 'POST':
            """Update thresholds"""
            try:
                body = json.loads(event.get('body', '{}'))
                data = update_thresholds(body)
                return response(200, data)
            except json.JSONDecodeError:
                return response(400, {'error': 'Invalid JSON in request body'})
        
        # ==========================================
        # HEALTH CHECK
        # ==========================================
        
        elif path == '/' and method == 'GET':
            return response(200, {
                'service': 'Smart GreenHouse API',
                'status': 'healthy',
                'version': '2.0-with-automatic-actuators',
                'endpoints': {
                    'sensors': ['/latest', '/history', '/stats', '/alerts', '/greenhouses'],
                    'actuators': [
                        '/actuators/status',
                        '/actuators/history', 
                        '/actuators/control (POST)',
                        '/actuators/manual (POST)',
                        '/actuators/thresholds'
                    ]
                },
                'automation': 'EventBridge scheduled every 5 minutes'
            })
        
        else:
            return response(404, {'error': f'Unknown endpoint: {method} {path}'})
    
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return response(500, {'error': str(e)})