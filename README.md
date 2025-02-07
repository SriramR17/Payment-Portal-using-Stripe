
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
