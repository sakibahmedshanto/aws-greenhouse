# Smart Greenhouse System Architecture - Mermaid Diagram

## Copy and paste this code into any Mermaid editor or GitHub markdown file

```mermaid
graph TB
    subgraph "User Interface"
        A[S3 Static Website<br/>greenhouse-dashboard-sakibshanto]
        style A fill:#FF9900,stroke:#232F3E,stroke-width:2px,color:#000
    end

    subgraph "API Layer"
        B[API Gateway<br/>m0tdyp9dia.execute-api.us-east-1.amazonaws.com/prod]
        style B fill:#FF4F8B,stroke:#232F3E,stroke-width:2px,color:#fff
    end

    subgraph "Compute Services"
        C[Lambda #2<br/>API & Actuator Control<br/>- Serves dashboard APIs<br/>- Makes actuator decisions<br/>- Manages thresholds]
        D[Lambda #1<br/>Data Processing<br/>- Validates sensor data<br/>- Stores in DynamoDB<br/>- Generates alerts]
        style C fill:#FF9900,stroke:#232F3E,stroke-width:2px,color:#000
        style D fill:#FF9900,stroke:#232F3E,stroke-width:2px,color:#000
    end

    subgraph "Database"
        E[(DynamoDB<br/>greenhouse-sensor-data<br/>PK: greenhouse_id, SK: timestamp)]
        F[(DynamoDB<br/>greenhouse-actuator-commands<br/>PK: greenhouse_id, SK: timestamp)]
        style E fill:#4053D6,stroke:#232F3E,stroke-width:2px,color:#fff
        style F fill:#4053D6,stroke:#232F3E,stroke-width:2px,color:#fff
    end

    subgraph "Messaging Services"
        G[SNS Topic<br/>greenhouse-sensor-data]
        H[SQS Queue<br/>sensor-data-queue]
        I[SNS Topic<br/>greenhouse-alerts]
        style G fill:#FF4F8B,stroke:#232F3E,stroke-width:2px,color:#fff
        style H fill:#FF4F8B,stroke:#232F3E,stroke-width:2px,color:#fff
        style I fill:#FF4F8B,stroke:#232F3E,stroke-width:2px,color:#fff
    end

    subgraph "Automation"
        J[EventBridge<br/>Schedule: rate 5 minutes<br/>greenhouse-actuator-schedule]
        style J fill:#FF9900,stroke:#232F3E,stroke-width:2px,color:#000
    end

    subgraph "IoT Simulation"
        K[EC2 Instance<br/>IoT Sensor Simulator<br/>greenhouse-01<br/>greenhouse-02]
        style K fill:#FF9900,stroke:#232F3E,stroke-width:2px,color:#000
    end

    subgraph "End Users"
        L[👤 User Email<br/>Alert Notifications]
        M[👤 Dashboard User<br/>Web Browser]
        style L fill:#3F8624,stroke:#232F3E,stroke-width:2px,color:#fff
        style M fill:#3F8624,stroke:#232F3E,stroke-width:2px,color:#fff
    end

    %% Data Flow Connections
    K -->|"1. Publish sensor readings<br/>(every 5 sec)"| G
    G -->|"2. Fan-out messages"| H
    H -->|"3. Poll messages"| D
    D -->|"4. Write sensor data"| E
    D -->|"5. Publish alerts"| I
    I -->|"6. Email notifications"| L

    J -->|"7. Trigger (every 5 min)"| C
    C -->|"8. Read sensor data"| E
    C -->|"9. Write commands"| F

    M -->|"10. HTTPS requests"| A
    A -->|"11. API calls"| B
    B -->|"12. Invoke Lambda"| C

    C -.->|"Response"| B
    B -.->|"JSON data"| A
    A -.->|"Render UI"| M

    %% Styling
    classDef aws fill:#FF9900,stroke:#232F3E,stroke-width:2px,color:#000
    classDef database fill:#4053D6,stroke:#232F3E,stroke-width:2px,color:#fff
    classDef messaging fill:#FF4F8B,stroke:#232F3E,stroke-width:2px,color:#fff
    classDef user fill:#3F8624,stroke:#232F3E,stroke-width:2px,color:#fff
```

## Service Names

### Compute & Processing
- **EC2 Instance**: `greenhouse-iot-simulator-instance` (simulates 2 greenhouses)
- **Lambda #1**: `greenhouse-data-processor` (SQS → DynamoDB)
- **Lambda #2**: `greenhouse-api-handler` (API Gateway + EventBridge → DynamoDB)

### Storage
- **DynamoDB Table 1**: `greenhouse-sensor-data` (sensor readings)
- **DynamoDB Table 2**: `greenhouse-actuator-commands` (actuator commands + config)
- **S3 Bucket**: `greenhouse-dashboard-sakibshanto` (static website)

### Messaging
- **SNS Topic 1**: `greenhouse-sensor-data-topic` (sensor data distribution)
- **SNS Topic 2**: `greenhouse-alerts-topic` (alert notifications)
- **SQS Queue**: `greenhouse-sensor-data-queue` (buffer for Lambda #1)

### API & Automation
- **API Gateway**: `greenhouse-api` (REST API)
  - Base URL: `https://m0tdyp9dia.execute-api.us-east-1.amazonaws.com/prod`
- **EventBridge Rule**: `greenhouse-actuator-schedule` (rate: 5 minutes)

### Greenhouses
- **greenhouse-01**: Temperature, Humidity, Soil Moisture, Light Intensity sensors
- **greenhouse-02**: Temperature, Humidity, Soil Moisture, Light Intensity sensors

## Data Flow Sequence

1. **EC2** generates sensor readings → publishes to **SNS**
2. **SNS** fans out messages → **SQS** queue
3. **Lambda #1** polls **SQS** → validates → writes to **DynamoDB** (sensor-data)
4. **Lambda #1** detects alerts → publishes to **SNS** → emails user
5. **EventBridge** triggers **Lambda #2** every 5 minutes
6. **Lambda #2** reads sensor data from **DynamoDB**
7. **Lambda #2** makes actuator decisions based on thresholds
8. **Lambda #2** writes commands to **DynamoDB** (actuator-commands)
9. **Dashboard** calls **API Gateway** → **Lambda #2** → returns data
10. **User** views real-time data and controls actuators via dashboard
