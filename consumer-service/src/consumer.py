import os
import json
import time
import pika
import mysql.connector
import signal
import sys
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

# --- Global State for Health Check ---
is_healthy = False

# --- Configuration ---
RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "rabbitmq")
RABBITMQ_QUEUE = os.getenv("RABBITMQ_QUEUE", "user_activity_events")
RABBITMQ_USER = os.getenv("RABBITMQ_USER", "guest")
RABBITMQ_PASS = os.getenv("RABBITMQ_PASS", "guest")

MYSQL_HOST = os.getenv("MYSQL_HOST", "mysql")
MYSQL_USER = os.getenv("MYSQL_USER", "user")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "user_password")
MYSQL_DB = os.getenv("MYSQL_DATABASE", "user_activity_db")

# --- HTTP Health Check Server (Runs in background thread) ---
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/health':
            if is_healthy:
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b'{"status": "healthy"}')
            else:
                self.send_response(503)
                self.end_headers()
                self.wfile.write(b'{"status": "unhealthy"}')
        else:
            self.send_response(404)
            self.end_headers()

def start_health_server():
    server = HTTPServer(('0.0.0.0', 8001), HealthHandler)
    print("🏥 Health check server running on port 8001")
    server.serve_forever()

# --- Database & Logic ---
def get_db_connection():
    return mysql.connector.connect(
        host=MYSQL_HOST, user=MYSQL_USER, password=MYSQL_PASSWORD, database=MYSQL_DB
    )

def save_to_db(data):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        query = "INSERT INTO user_activities (user_id, event_type, timestamp, metadata) VALUES (%s, %s, %s, %s)"
        cursor.execute(query, (data['user_id'], data['event_type'], data['timestamp'], json.dumps(data['metadata'])))
        conn.commit()
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        print(f"DB Error: {e}")
        return False

def callback(ch, method, properties, body):
    try:
        print(f"Processing: {body}")
        data = json.loads(body)
        if save_to_db(data):
            ch.basic_ack(delivery_tag=method.delivery_tag)
        else:
            # Logic: If DB fails, we NACK with requeue=True to try again later
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
            time.sleep(1)
    except json.JSONDecodeError:
        print("Malformed JSON. Dropping.")
        ch.basic_ack(delivery_tag=method.delivery_tag) # Ack to remove bad message

# --- Main ---
def main():
    global is_healthy
    
    # Start Health Check Server in a separate thread
    health_thread = threading.Thread(target=start_health_server, daemon=True)
    health_thread.start()

    # Graceful Shutdown Handler
    def signal_handler(sig, frame):
        print('Graceful shutdown initiated...')
        sys.exit(0)
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    print("🚀 Consumer starting...")
    while True:
        try:
            creds = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASS)
            params = pika.ConnectionParameters(host=RABBITMQ_HOST, credentials=creds, heartbeat=600)
            connection = pika.BlockingConnection(params)
            channel = connection.channel()
            channel.queue_declare(queue=RABBITMQ_QUEUE, durable=True)
            channel.basic_qos(prefetch_count=1)
            channel.basic_consume(queue=RABBITMQ_QUEUE, on_message_callback=callback)
            
            print("Consumer Connected & Waiting")
            is_healthy = True # Mark as healthy once connected
            channel.start_consuming()
        except Exception as e:
            is_healthy = False
            print(f"⚠️ Connection lost: {e}. Retrying in 5s...")
            time.sleep(5)

if __name__ == "__main__":
    main()