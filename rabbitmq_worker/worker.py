import pika
import sys
import os
import time

import json

# Configuration
RABBITMQ_HOST = os.environ.get('RABBITMQ_HOST', 'rabbitmq')

# Load config
try:
    with open('config.json', 'r') as f:
        config = json.load(f)
    QUEUE_NAME = config.get('rabbitmqQueue', 'fastapi_to_test_website_requests')
except FileNotFoundError:
    print("Warning: config.json not found, using default queue name")
    QUEUE_NAME = 'fastapi_to_test_website_requests'

def main():
    print(f"Connecting to RabbitMQ at {RABBITMQ_HOST}...")
    
    # Retry logic for connection
    while True:
        try:
            connection = pika.BlockingConnection(
                pika.ConnectionParameters(host=RABBITMQ_HOST)
            )
            break
        except pika.exceptions.AMQPConnectionError:
            print("RabbitMQ not ready yet, retrying in 5 seconds...")
            time.sleep(5)

    channel = connection.channel()

    channel.queue_declare(queue=QUEUE_NAME, durable=True)

    def callback(ch, method, properties, body):
        print(f" [x] Received {body.decode()}")
        # Here you would add logic to process the message
        # For now, we just acknowledge it
        ch.basic_ack(delivery_tag=method.delivery_tag)

    channel.basic_qos(prefetch_count=1)
    channel.basic_consume(queue=QUEUE_NAME, on_message_callback=callback)

    print(' [*] Waiting for messages. To exit press CTRL+C')
    channel.start_consuming()

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('Interrupted')
        try:
            sys.exit(0)
        except SystemExit:
            os._exit(0)
