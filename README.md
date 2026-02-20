# Event-Driven User Activity Tracking System

A robust, decoupled backend service that tracks user activities (e.g., login, logout, page view) using an event-driven architecture. This system handles real-time data streams by separating event ingestion from database persistence using a message queue.



##  Architecture Overview

This system is built using a decoupled **Producer-Consumer** pattern to ensure high availability, fast response times, and resilience against database downtime.

1. **Producer API (FastAPI):** A lightweight REST API that accepts incoming user events, validates the payload, and publishes them to a message broker. It responds to the client immediately (Asynchronous Handoff) without waiting for database operations.
2. **Message Broker (RabbitMQ):** Buffers the events in a durable queue (`user_activity_events`). This guarantees no data is lost even if the downstream consumer or database is temporarily offline.
3. **Consumer Service (Python Worker):** A background service that subscribes to the RabbitMQ queue, processes incoming events one by one, and persists them to the database.
4. **Database (MySQL):** Stores the processed events. It utilizes a JSON column format for highly flexible event metadata.

##  Tech Stack

* **Language:** Python 3.10
* **Framework:** FastAPI (Producer)
* **Message Broker:** RabbitMQ
* **Database:** MySQL 8.0
* **Containerization:** Docker & Docker Compose

---

##  Getting Started

### Prerequisites
* Docker and Docker Compose installed on your machine.

### Setup and Execution

1. **Clone the repository and navigate to the root directory.**
2. **Start the system using Docker Compose:**
   ```bash
   docker-compose up --build
   ```
3. **Verify Health**
  * Check the health status of the services using the following endpoints:
  *Producer API http://localhost:8000/health
  *Consumer Worker http://localhost:8001/health

## API Documentation

###  Track Event

Ingests a new user activity event and queues it for processing.

**URL:** `/api/v1/events/track`  
**Method:** `POST`  
**Content-Type:** `application/json`
**Request Body Parameters
| Parameter   | Type        | Required | Description                                              | Example                         |
|-------------|-------------|----------|----------------------------------------------------------|----------------------------------|
| user_id     | Integer     | Yes      | Unique identifier for the user. Must be > 0.             | 123                              |
| event_type  | String      | Yes      | Categorical name of the event.                           | "page_view"                      |
| timestamp   | String      | Yes      | ISO 8601 formatted datetime string.                      | "2026-02-20T10:00:00Z"           |
| metadata    | JSON Object | No       | Flexible key-value pairs for extra context.              | {"device": "mobile"}             |

## Example Request

### JSON
```json
{
  "user_id": 123,
  "event_type": "page_view",
  "timestamp": "2026-02-20T10:00:00Z",
  "metadata": {
    "page_url": "/products/item-xyz",
    "session_id": "abc123"
  }
}
```
## Responses

### Success (202 Accepted)
Event successfully validated and queued.

```json
{
  "status": "accepted",
  "message": "Event queued for processing"
}
```
### Validation Error (400 Bad Request)
Missing required fields or invalid data types.

```json
{
  "detail": [...],
  "message": "Invalid UserActivityEvent payload"
}
```
### Broker Error (500 Internal Server Error)
The API failed to communicate with RabbitMQ.

## Database Structure

The system uses **MySQL**. The schema is automatically initialized on startup via `db/init.sql`.

**Database:** `user_activity_db`  
**Table:** `user_activities`

| Column Name | Data Type   | Constraints                     | Description                                              |
|-------------|-------------|----------------------------------|----------------------------------------------------------|
| id          | INT         | PRIMARY KEY, AUTO_INCREMENT     | Unique internal record ID.                              |
| user_id     | INT         | NOT NULL                        | ID of the user who triggered the event.                 |
| event_type  | VARCHAR(50) | NOT NULL                        | Type of the activity (e.g., login).                     |
| timestamp   | DATETIME    | NOT NULL                        | When the event originally occurred.                     |
| metadata    | JSON        | —                                | Flexible storage for dynamic event properties.          |
| created_at  | TIMESTAMP   | DEFAULT CURRENT_TIMESTAMP       | When the record was inserted into the DB.               |

## Testing

Automated tests can be executed directly inside the running containers using `docker-compose exec`.

*(Assuming `pytest` is configured in your respective directories.)*

### Test the Producer Service

```bash
docker-compose exec producer-service pytest
```
### Test the Consumer Service

```bash
docker-compose exec consumer-service pytest
```
