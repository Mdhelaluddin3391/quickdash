# QuickDash API

QuickDash is a comprehensive backend solution for an e-commerce and delivery platform. It includes functionalities for user management, product catalog, inventory, orders, payments, delivery, and notifications. The project is built with Django and Django REST Framework, featuring a modular architecture with various Django apps for different services.

## Features

-   **User Authentication:** JWT-based authentication for secure access.
-   **Role-Based Access Control:** Differentiated permissions for various user roles.
-   **Product Catalog:** Management of products and categories.
-   **Inventory Management:** Tracking stock levels and warehouse information.
-   **Order Processing:** Complete order flow from creation to completion.
-   **Payment Integration:** Support for payment gateways like Razorpay.
-   **Real-time Delivery Tracking:** Real-time location updates for deliveries using WebSockets.
-   **Notifications:** Push notifications and SMS alerts (via Twilio).
-   **Analytics:** Tracking and reporting of key metrics.
-   **Background Tasks:** Asynchronous task processing with Celery and Redis.

## Technologies Used

-   **Backend:** Django, Django REST Framework
-   **Database:** PostgreSQL
-   **Asynchronous Tasks:** Celery, Redis
-   **Real-time Communication:** Django Channels, WebSockets
-   **Authentication:** djangorestframework-simplejwt
-   **Payments:** Razorpay
-   **SMS/Notifications:** Twilio
-   **Deployment:** Docker, Gunicorn, Daphne

## Project Structure

The project is organized into several Django apps, each responsible for a specific domain:

```
/
├── apps/
│   ├── accounts/       # User management, authentication, and roles
│   ├── analytics/      # Data tracking and analytics
│   ├── catalog/        # Product and category management
│   ├── delivery/       # Delivery tracking and logistics
│   ├── inventory/      # Inventory and stock management
│   ├── notifications/  # Manages notifications (FCM, SMS)
│   ├── orders/         # Order processing and management
│   ├── payments/       # Payment processing and integration
│   ├── utils/          # Shared utilities, middleware, and helpers
│   └── warehouse/      # Warehouse management
├── config/             # Django project configuration, settings, and URLs
├── manage.py           # Django's command-line utility
├── requirements.txt    # Python dependencies
├── Dockerfile          # Docker configuration for the application
└── docker-compose.yml  # Docker Compose for multi-container setup
```

### App Descriptions

-   **`accounts`**: Handles user registration, login, profile management, and role-based access control.
-   **`analytics`**: Provides services for tracking events and generating analytics reports.
-   **`catalog`**: Manages the product catalog, including categories, products, and variations.
-   **`delivery`**: Deals with delivery personnel, real-time location tracking, and delivery status updates.
-   **`inventory`**: Manages stock levels, suppliers, and inventory records.
-   **`notifications`**: Responsible for sending notifications to users, such as push notifications (FCM) and SMS (Twilio).
-   **`orders`**: Implements the entire order lifecycle, from cart to checkout and fulfillment.
-   **`payments`**: Integrates with payment gateways like Razorpay to handle transactions.
-   **`utils`**: Contains common utilities, custom middleware, exception handlers, and other shared components.
-   **`warehouse`**: Manages warehouse information, stock transfers, and warehouse-specific operations.

## Setup and Installation

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/Mdhelaluddin3391/quickdash
    cd quickdash
    ```

2.  **Create a virtual environment and install dependencies:**
    ```bash
    python -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt
    ```

3.  **Set up environment variables:**
    Create a `.env` file in the root directory and add the necessary environment variables. You can use `.env.example` as a template.
    ```
    SECRET_KEY=your-secret-key
    DEBUG=True
    DATABASE_URL=postgres://user:password@host:port/dbname
    REDIS_URL=redis://localhost:6379/0
    # ... other variables
    ```

4.  **Run database migrations:**
    ```bash
    python manage.py migrate
    ```

## Running the Application

-   **Development Server:**
    ```bash
    python manage.py runserver
    ```

-   **Using Docker Compose:**
    ```bash
    docker-compose up --build
    ```

## API Documentation

API endpoints are not yet documented in this README. You can explore the `urls.py` file in each app to see the available endpoints. Consider adding a dedicated API documentation using tools like Swagger or Redoc.

## Contributing

Contributions are welcome! Please follow these steps:

1.  Fork the repository.
2.  Create a new branch (`git checkout -b feature/your-feature`).
3.  Make your changes.
4.  Commit your changes (`git commit -m 'Add some feature'`).
5.  Push to the branch (`git push origin feature/your-feature`).
6.  Open a pull request.

## License

This project is licensed under the MIT License. See the `LICENSE` file for details.
