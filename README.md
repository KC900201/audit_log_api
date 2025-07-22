# Resola code challenge - Audit Log API

This is a code challenge project for creating an Audit Log API. The project uses [FastAPI](https://fastapi.tiangolo.com/) for framework structure

## Tech Stack
- **Framework:** FastAPI
- **API Gateway:** AWS API Gateway
- **Database:** PostgreSQL + TimeScaleDB
- **Message Queue:** AWS SQS
- **Search:** OpenSearch

## Features
- CRUD functions for audit logs (Create, Read, Update, Delete)
- Export feature for audit logs into .csv file
- Real time log streaming for audit logs
- Read and create tenants

## API Endpoints
```commandline
POST   /api/v1/logs                   # Create log entry (with tenant ID)
GET    /api/v1/logs                   # Search/filter logs (tenant-scoped)
GET    /api/v1/logs/{id}              # Get specific log entry (tenant-scoped)
GET    /api/v1/logs/export            # Export logs (tenant-scoped)
GET    /api/v1/logs/stats             # Get log statistics (tenant-scoped)
POST   /api/v1/logs/bulk              # Bulk log creation (with tenant ID)
DELETE /api/v1/logs/cleanup           # Cleanup old logs (tenant-scoped)
WS     /api/v1/logs/stream            # Real-time log streaming (tenant-scoped)
GET    /api/v1/tenants                # List accessible tenants (admin only)
POST   /api/v1/tenants                # Create new tenant (admin only)
```

## Architecture Diagram

### System Architecture (WIP)
```mermaid
graph TB
    subgraph "Client Applications"
        App1[Application 1<br/>Tenant A]
        App2[Application 2<br/>Tenant B]
        App3[Application 3<br/>Tenant C]
    end
    
    subgraph "API Gateway Layer"
        APIGateway[AWS API Gateway]
        ALB[Application Load Balancer]
    end
    
    subgraph "Audit Log API"
        Auth[Authentication]
        TenantAuth[Tenant Authorization]
        RateLimit[Rate Limiting]
    end
    
    subgraph "Core Services"
        LogService[Log Service<br/>Multi-tenant]
        SearchService[Search Service<br/>Tenant-scoped]
        ExportService[Export Service<br/>Tenant-scoped]
        StreamService[Stream Service<br/>Tenant-scoped]
    end
    
    subgraph "Data Layer"
        PostgreSQL[(PostgreSQL + TimescaleDB<br/>Tenant-partitioned)]
        MongoDB[(MongoDB<br/>Tenant-collections)]
        DynamoDB[(DynamoDB<br/>Tenant-partitioned)]
        OpenSearch[(OpenSearch<br/>Tenant-indices)]
    end
    
    subgraph "Message Queue"
        SQS[AWS SQS<br/>Tenant-queues]
    end
    
    subgraph "Background Services"
        Workers[SQS Workers<br/>Tenant-aware]
        Cleanup[Data Cleanup<br/>Tenant-scoped]
        Archive[Data Archival<br/>Tenant-scoped]
    end
    
    App1 --> APIGateway
    App1 --> ALB
    App2 --> APIGateway
    App2 --> ALB
    App3 --> APIGateway
    App3 --> ALB
    
    APIGateway --> Auth
    ALB --> Auth
    Auth --> TenantAuth
    TenantAuth --> RateLimit
    RateLimit --> LogService
    RateLimit --> SearchService
    RateLimit --> ExportService
    RateLimit --> StreamService
    
    LogService --> PostgreSQL
    LogService --> MongoDB
    LogService --> DynamoDB
    SearchService --> OpenSearch
    ExportService --> PostgreSQL
    ExportService --> MongoDB
    ExportService --> DynamoDB
    
    LogService --> SQS
    Workers --> SQS
    Cleanup --> SQS
    Archive --> SQS
```

### Audit Log Flow (TBD)
```mermaid
sequenceDiagram
    participant Client as Client App<br/>(Tenant A)
    participant Gateway as API Gateway/ALB
    participant Auth as Auth Service
    participant TenantAuth as Tenant Auth
    participant Log as Log Service
    participant DB as Database (Tenant A)
    participant SQS as AWS SQS
    participant Search as OpenSearch
    participant Worker as SQS Worker
    
    Client->>Gateway: POST /api/v1/logs<br/>(tenant_id: A)
    Gateway->>Auth: Validate JWT Token
    Auth-->>Gateway: Token Valid
    Gateway->>TenantAuth: Validate Tenant Access
    TenantAuth-->>Gateway: Tenant Access Granted
    Gateway->>Log: Create Log Entry (Tenant A)
    Log->>DB: Store Log Entry (Tenant A)
    Log->>SQS: Queue Background Tasks (Tenant A)
    Log-->>Gateway: Log Created
    Gateway-->>Client: 201 Created
    
    Note over SQS,Worker: Background Processing (Tenant A)
    SQS->>Worker: Process Background Tasks
    Worker->>Search: Index for Search (Tenant A)
    Worker->>DB: Data Cleanup/Archival (Tenant A)
    
    Note over Client,Search: Real-time Streaming (Tenant A)
    Client->>Gateway: WS /api/v1/logs/stream<br/>(tenant_id: A)
    Gateway->>Log: Subscribe to Stream (Tenant A)
    Log->>Client: Real-time Log Updates (Tenant A)
```

## Postman Collection (WIP)


## Project Structure
```
├── .aws/               # Amazon AWS credentials (access key, secret access key)
├── routers/            # Sub-routine files
│   ├── audit_logs.py   # API endpoints for audit_logs class 
│   └── tenants.py      # API endpoints for tenants class
├── venv/               # Virtual environment setup
├── .gitignore          # Git ignore rules
├── auth.py             # Authentication configuration
├── db.py               # Database connection
├── schemas.py          # Class declaration
├── test_main.py        # Test suite
└── README.md           # Project documentation
```

## Local Development Setup (WIP)

### Prerequsites (WIP)

### Install dependencies
```bash
pip install
```

### Initiate virtual environment
```bash
./venv/Scripts/activate
```

### Run local development server
```bash
uvicorn main:app --reload
```

## Learn More

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Postman Documentation](https://www.postman.com/product/what-is-postman/)