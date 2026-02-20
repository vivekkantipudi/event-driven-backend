import os
import json
import pika
from fastapi import FastAPI, HTTPException, status, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Dict, Any

app = FastAPI(title="Event Producer API")

# --- 1. Strict HTTP 400 for Validation Errors ---
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST, # Requirement: Return 400, not 422
        content={"detail": exc.errors(), "message": "Invalid UserActivityEvent payload"},
    )

# --- Configuration ---
RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "rabbitmq")
RABBITMQ_QUEUE = os.getenv("RABBITMQ_QUEUE", "user_activity_events")
RABBITMQ_USER = os.getenv("RABBITMQ_USER", "guest")
RABBITMQ_PASS = os.getenv("RABBITMQ_PASS", "guest")

# --- Data Models ---
class UserActivityEvent(BaseModel):
    user_id: int = Field(..., gt=0)
    event_type: str = Field(..., min_length=1)
    timestamp: datetime
    metadata: Dict[str, Any] = Field(default_factory=dict)

# --- RabbitMQ Client ---
class RabbitMQClient:
    def __init__(self):
        self.connection = None
        self.channel = None

    def connect(self):
        try:
            credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASS)
            parameters = pika.ConnectionParameters(host=RABBITMQ_HOST, credentials=credentials)
            self.connection = pika.BlockingConnection(parameters)
            self.channel = self.connection.channel()
            self.channel.queue_declare(queue=RABBITMQ_QUEUE, durable=True)
            print("Producer connected to RabbitMQ")
        except Exception as e:
            print(f"Producer failed to connect to RabbitMQ: {e}")

    def publish(self, message: dict):
        if not self.connection or self.connection.is_closed:
            self.connect()
        try:
            self.channel.basic_publish(
                exchange='',
                routing_key=RABBITMQ_QUEUE,
                body=json.dumps(message, default=str),
                properties=pika.BasicProperties(delivery_mode=2)
            )
            return True
        except Exception as e:
            print(f"Publish error: {e}")
            return False

    def close(self):
        if self.connection and not self.connection.is_closed:
            self.connection.close()
            print("Producer connection closed")

mq_client = RabbitMQClient()

@app.on_event("startup")
async def startup():
    mq_client.connect()

@app.on_event("shutdown")
async def shutdown():
    mq_client.close() # Requirement: Graceful Shutdown

# --- Endpoints ---

@app.post("/api/v1/events/track", status_code=status.HTTP_202_ACCEPTED)
async def track_event(event: UserActivityEvent):
    payload = event.model_dump()
    payload['timestamp'] = payload['timestamp'].isoformat()
    
    if mq_client.publish(payload):
        return {"status": "accepted"}
    else:
        raise HTTPException(status_code=500, detail="Internal Broker Error")

@app.get("/health")
async def health_check():
    if mq_client.connection and mq_client.connection.is_open:
        return {"status": "healthy"}
    return JSONResponse(status_code=503, content={"status": "unhealthy"})