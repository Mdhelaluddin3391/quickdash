<div align="center">

# ⚡ QuickDash API ⚡

**A robust, scalable, and feature-rich backend for modern e-commerce and delivery platforms.**

</div>

<p align="center">
  <img alt="GitHub language count" src="https://img.shields.io/github/languages/count/Mdhelaluddin3391/quickdash?style=for-the-badge&color=blue">
  <img alt="GitHub top language" src="https://img.shields.io/github/languages/top/Mdhelaluddin3391/quickdash?style=for-the-badge&color=blueviolet">
  <img alt="GitHub" src="https://img.shields.io/github/license/Mdhelaluddin3391/quickdash?style=for-the-badge&color=brightgreen">
  <img alt="GitHub repo size" src="https://img.shields.io/github/repo-size/Mdhelaluddin3391/quickdash?style=for-the-badge&color=orange">
</p>

QuickDash provides a comprehensive and modular backend solution designed to power sophisticated e-commerce and on-demand delivery services. Built with Django and the Django REST Framework, it features a clean, organized architecture that separates concerns into dedicated applications. From user management and payment processing to real-time delivery tracking, QuickDash is engineered for performance, scalability, and developer efficiency.

---

## 📋 Table of Contents

- [Key Features](#-key-features)
- [System Architecture & Tech Stack](#-system-architecture--tech-stack)
- [Getting Started (Docker)](#-getting-started-docker)
- [API Documentation](#-api-documentation)
- [Running Tests](#-running-tests)
- [Project Structure](#-project-structure)
- [Contributing](#-contributing)
- [License](#-license)

---

## ✨ Key Features

- **Authentication & Security:** Secure JWT-based authentication with role-based access control (RBAC) to protect endpoints.
- **Full E-commerce Flow:** Complete management of products, categories, inventory, and the entire order lifecycle.
- **Payment Gateway Integration:** Seamless and secure payment processing via Razorpay.
- **Real-time Delivery Tracking:** Live location updates for deliveries powered by Django Channels and WebSockets.
- **Multi-channel Notifications:** Keep users informed with push notifications via Firebase Cloud Messaging (FCM) and SMS alerts via Twilio.
- **Advanced Analytics:** Built-in hooks for tracking key metrics to drive data-informed decisions.
- **Asynchronous Task Processing:** Efficiently handles long-running and periodic tasks (like sending emails or processing data) using Celery and Redis, preventing API slowdowns.
- **Geospatial Capabilities:** Utilizes PostGIS for location-based queries and mapping features.
- **Automated API Docs:** Comes with auto-generated, interactive API documentation using `drf-spectacular`.

---

## 🏗️ System Architecture & Tech Stack

The project runs as a set of containerized services orchestrated by Docker Compose, ensuring a consistent development and production environment.

| Service        | Technology                                                                                                         | Purpose                                                       |
|----------------|--------------------------------------------------------------------------------------------------------------------|---------------------------------------------------------------|
| **Web Server** | [Nginx](https://www.nginx.com/)                                                                                    | High-performance HTTP reverse proxy and static file server.     |
| **App Server** | [Daphne](https://github.com/django/daphne) / [Django](https://www.djangoproject.com/)                               | Serves the Django application and handles WebSocket connections.  |
| **Database**   | [PostgreSQL](https://www.postgresql.org/) + [PostGIS](https://postgis.net/)                                        | Primary relational database with geospatial capabilities.       |
| **Caching**    | [Redis](https://redis.io/)                                                                                         | In-memory data store for caching and WebSocket channel layers.  |
| **Task Queue** | [Celery](https://docs.celeryq.dev/) / [Redis](https://redis.io/)                                                     | Manages and executes background tasks asynchronously.         |
| **Frameworks** | [Django REST Framework](https://www.django-rest-framework.org/), [Django Channels](https://channels.readthedocs.io/) | Building APIs and handling real-time protocols.               |

---

## 🚀 Getting Started (Docker)

Running the project with Docker is the recommended approach. It handles all dependencies, services, and configurations automatically.

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/)
- [Docker Compose](https://docs.docker.com/compose/install/)

### Installation Steps

1.  **Clone the Repository**
    ```bash
    git clone https://github.com/Mdhelaluddin3391/quickdash
    cd quickdash
    ```

2.  **Configure Environment Variables**
    Create a `.env` file in the project root. You can copy the example file if one is provided, or create it from scratch.
    ```bash
    # .env
    SECRET_KEY='your-strong-secret-key'
    DEBUG=1
    ALLOWED_HOSTS='localhost,127.0.0.1'

    # Database Credentials
    DB_NAME=quickdash
    DB_USER=admin
    DB_PASSWORD=admin
    DB_HOST=db
    DB_PORT=5432

    # Redis URL
    REDIS_URL='redis://redis:6379/1'
    CELERY_BROKER_URL='redis://redis:6379/0'

    # Add other credentials for Razorpay, Twilio, etc.
    ```

3.  **Build and Run the Containers**
    This single command will build the images, start all services, and run the database migrations as defined in `start.sh`.
    ```bash
    docker-compose up --build
    ```

The application will be accessible at `http://localhost:80`.

---

## 📖 API Documentation

Thanks to `drf-spectacular`, interactive API documentation is automatically generated. Once the application is running, you can access:

-   **Swagger UI:** `http://localhost/api/schema/swagger-ui/`
-   **ReDoc:** `http://localhost/api/schema/redoc/`
-   **Schema File:** `http://localhost/api/schema/`

---

## ✅ Running Tests

To run the test suite, execute the following command while the Docker containers are running. This command runs `pytest` inside the `web` container.

```bash
docker-compose exec web python manage.py test
```

---

## 📂 Project Structure

The project follows a modular structure where each Django app is responsible for a specific domain.

```
/
├── apps/
│   ├── accounts/        # User management, auth, and roles
│   ├── analytics/       # Data tracking and analytics
│   ├── catalog/         # Product and category management
│   ├── delivery/        # Delivery tracking and logistics
│   ├── inventory/       # Stock and warehouse management
│   ├── notifications/   # FCM & SMS notifications
│   ├── orders/          # Order processing and lifecycle
│   ├── payments/        # Payment integration
│   ├── utils/           # Shared utilities and helpers
│   └── warehouse/       # Multi-warehouse logic
├── config/              # Django project settings, ASGI/WSGI, and root URLs
├── nginx/               # Nginx configuration
├── start.sh             # Startup script for the Django container
├── docker-compose.yml   # Defines and orchestrates all services
├── Dockerfile           # Defines the application container
└── requirements.txt     # Python dependencies
```

---

## 🤝 Contributing

Contributions are welcome! Please follow these steps to contribute:

1.  Fork the repository.
2.  Create a new feature branch (`git checkout -b feature/your-awesome-feature`).
3.  Make your changes.
4.  Commit your changes (`git commit -m 'Add some awesome feature'`).
5.  Push to the branch (`git push origin feature/your-awesome-feature`).
6.  Open a Pull Request.

---

## 📜 License

This project is licensed under the MIT License. See the `LICENSE` file for more details.
