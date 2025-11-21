Orders service

This folder contains the Orders application. The services implemented here aim to provide a robust, decoupled order lifecycle suitable for extraction into a microservice.

Quick start (development):

- Ensure project dependencies are installed (use `requirements.txt`).
- Run Django as usual: `python manage.py runserver`.

Microservice notes:

- The included `Dockerfile` is a minimal scaffold. Customize the base image and build steps as needed.
- The Orders app uses signals to communicate with Payments, Warehouse and Delivery apps. When extracted, replace Django signals with an event bus (Kafka/RabbitMQ) for cross-process communication.
