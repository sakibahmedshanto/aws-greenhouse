# Smart Greenhouse System Architecture - Mermaid Diagram

## Copy and paste this code into any Mermaid editor or GitHub markdown file

```mermaid
flowchart TD
    subgraph users["👥 Users"]
        M[Dashboard User]
        L[Email Subscriber]
    end
    
    subgraph frontend["Frontend Layer"]
        A[S3 Static Website<br/>greenhouse-dashboard-sakibshanto]
    end
    
    subgraph api["API Layer"]
        B[API Gateway<br/>REST API Endpoints]
    end
    
    subgraph compute["Compute Services"]
        C[Lambda 2: API Handler<br/>greenhouse-api-handler]
        D[Lambda 1: Data Processor<br/>greenhouse-data-processor]
    end
    
    subgraph storage["Data Storage"]
        E[(DynamoDB<br/>sensor-data table)]
        F[(DynamoDB<br/>actuator-commands table)]
    end
    
    subgraph messaging["Messaging Services"]
        G[SNS Topic: Sensor Data]
        H[SQS Queue: Buffer]
        I[SNS Topic: Alerts]
    end
    
    subgraph automation["Automation"]
        J[EventBridge Schedule<br/>Every 5 minutes]
    end
    
    subgraph iot["IoT Simulation"]
        K[EC2 Instance<br/>Sensor Simulator<br/>greenhouse-01, greenhouse-02]
    end

    %% Data Flow Connections
    K -->|1. Publish readings every 5s| G
    G -->|2. Fan-out to subscribers| H
    H -->|3. Poll messages| D
    D -->|4. Write sensor data| E
    D -->|5. Send alerts| I
    I -->|6. Email notifications| L
    
    J -->|7. Trigger every 5min| C
    C -->|8. Read sensor data| E
    C -->|9. Write actuator commands| F
    
    M -->|10. Browse dashboard| A
    A -->|11. API calls HTTPS| B
    B -->|12. Invoke Lambda| C
    C -.->|Response JSON| B
    B -.->|Data| A
    A -.->|Display UI| M
    
    %% Styling Classes
    classDef compute fill:#FF9900,stroke:#232F3E,stroke-width:2px
    classDef storage fill:#4053D6,stroke:#232F3E,stroke-width:2px,color:#fff
    classDef messaging fill:#FF4F8B,stroke:#232F3E,stroke-width:2px
    classDef user fill:#3F8624,stroke:#232F3E,stroke-width:2px,color:#fff
    
    class C,D,K,J compute
    class E,F storage
    class G,H,I,B messaging
    class M,L user
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
