# Payment Integration App with Stripe

This is a web application that provides a seamless payment integration using Stripe. The application is built using Flask for the backend, and HTML, CSS, JavaScript, and Tailwind CSS (via CDN) for the frontend. The app uses MySQL as the database to store user information and payment history.

---

## Features

- **User Registration and Login**: Secure user authentication with hashed passwords.
- **Stripe Payment Gateway Integration**: Create payment intents and handle successful payments.
- **User Dashboard**: Displays payment history for each user.
- **Responsive Frontend**: Designed using HTML, CSS, Tailwind CSS (via Cloudflare CDN), and JavaScript.
- **Database Storage**: MySQL for storing user details and payment records.
- **REST API Endpoints**: AJAX-powered functionality for creating payment intents and recording payment success.

---

## Tech Stack

### Backend:
- **Flask**: Python-based web framework.
- **Stripe API**: Payment processing.
- **MySQL**: Relational database for storing user and payment data.

### Frontend:
- **HTML**: Markup language for structuring the app.
- **CSS**: Styling the application.
- **JavaScript**: Adding interactivity.
- **Tailwind CSS**: Utility-first CSS framework via Cloudflare CDN.
- **Stripe.js**: For secure and dynamic Stripe payment integration.

---

## Installation

### Prerequisites:
- Python 3.8+ installed.
- MySQL installed and configured.
- Stripe account for API keys.

### Steps:
1. Clone this repository:
    ```bash
    git clone https://github.com/your-username/payment-integration-app.git
    cd payment-integration-app
    ```

2. Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```

3. Configure the database:
    - Update `db_config` in `app.py` with your MySQL credentials.
    - Run the app once to initialize the database tables.

4. Configure Stripe:
    - Replace `stripe.api_key` in `app.py` with your **Secret Key** from the Stripe dashboard.

5. Start the application:
    ```bash
    python app.py
    ```

6. Open the app in your browser:
    ```
    http://127.0.0.1:5000/
    ```

---

## Project Structure


├── templates/ │ 
    ├── base.html # Base template │ 
    ├── register.html # User registration page │
    ├── login.html # User login page │ 
    ├── dashboard.html # User dashboard with payment history 
├── static/ │ 
    ├── styles.css # Custom CSS styles (optional) │ 
    ├── script.js # Custom JavaScript (optional) 

── app.py # Main Flask app ├
── requirements.txt # Python dependencies ├
── README.md # Project documentation
---

## Key Endpoints

### 1. `/register`
- **Method**: `GET, POST`
- **Description**: Allows users to register with an email and password.

### 2. `/login`
- **Method**: `GET, POST`
- **Description**: Allows users to log in to their account.

### 3. `/dashboard`
- **Method**: `GET`
- **Description**: Displays the user's payment history.

### 4. `/create-payment-intent`
- **Method**: `POST`
- **Description**: Creates a payment intent using Stripe API.

### 5. `/payment-success`
- **Method**: `POST`
- **Description**: Records a successful payment to the database.

### 6. `/payment-history`
- **Method**: `GET`
- **Description**: Fetches the logged-in user's payment history.

---

## Dependencies

- **Flask**: `pip install flask`
- **MySQL Connector**: `pip install mysql-connector-python`
- **Stripe**: `pip install stripe`

All dependencies are listed in the `requirements.txt` file.

---

## Tailwind CSS Integration

This app uses Tailwind CSS via the Cloudflare CDN. To customize or add styles, include Tailwind classes directly in your HTML files.

Example:
```html
<link href="https://cdn.jsdelivr.net/npm/tailwindcss@2.2.19/dist/tailwind.min.css" rel="stylesheet">
