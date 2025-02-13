from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import mysql.connector
import stripe
from datetime import datetime
import os
import hashlib
import secrets
import re

app = Flask(__name__)
app.config['SECRET_KEY'] = secrets.token_hex(16)

# MySQL Configuration
db_config = {
    'host': 'localhost',
    'user': 'root',
    'password': 'root',
    'database': 'payment_portal'
}

# Stripe Configuration
stripe.api_key = 'sk_test_51QlohYJfvPkj146a1jbdEzlGhkeotkzlYH4IDgSevIucqYRFZycryre8yYEoPMJB8iM7eRcJbMXlqb8lMTyvhuN200RTsJf98C'

# Database connection helper
def get_db_connection():
    try:
        conn = mysql.connector.connect(**db_config)
        return conn
    except mysql.connector.Error as err:
        print(f"Error connecting to MySQL: {err}")
        return None

# Create database tables
def init_db():
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        try:
            cursor.execute('''
                ALTER TABLE payments 
                ADD COLUMN payment_method VARCHAR(50) DEFAULT 'card'
            ''')
            conn.commit()
        except mysql.connector.Error as err:
            # Error 1060 means column already exists, which is fine
            if err.errno != 1060:
                print(f"Error adding payment_method column: {err}")


        cursor.execute('''
            CREATE TABLE IF NOT EXISTS upi_ids (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                upi_id VARCHAR(255) NOT NULL,
                verified BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id),
                UNIQUE KEY unique_user_upi (user_id, upi_id)
            )
        ''')
        
        # UPI Payments table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS upi_payments (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                upi_id VARCHAR(255) NOT NULL,
                amount DECIMAL(10, 2) NOT NULL,
                description TEXT,
                status VARCHAR(20) DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        ''')
        
        # Users table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INT AUTO_INCREMENT PRIMARY KEY,
                email VARCHAR(120) UNIQUE NOT NULL,
                password VARCHAR(255) NOT NULL,
                stripe_customer_id VARCHAR(255) UNIQUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Check if stripe_customer_id column exists
        try:
            cursor.execute('''
                ALTER TABLE users 
                ADD COLUMN stripe_customer_id VARCHAR(255) UNIQUE
            ''')
            conn.commit()
        except mysql.connector.Error as err:
            # Error 1060 means column already exists, which is fine
            if err.errno != 1060:
                print(f"Error adding stripe_customer_id column: {err}")
        
        # Payments table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS payments (
                id INT AUTO_INCREMENT PRIMARY KEY,
                stripe_payment_id VARCHAR(100) UNIQUE,
                user_id INT NOT NULL,
                amount DECIMAL(10, 2) NOT NULL,
                currency VARCHAR(3) DEFAULT 'USD',
                status VARCHAR(20) NOT NULL,
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        ''')
        
        conn.commit()
        cursor.close()
        conn.close()

# Hash password
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

@app.route('/')
def index():
    return render_template('base2.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        data = request.json
        email = data.get('email')
        password = data.get('password')
        
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor(dictionary=True)
            
            # Check if email exists
            cursor.execute('SELECT id FROM users WHERE email = %s', (email,))
            if cursor.fetchone():
                cursor.close()
                conn.close()
                return jsonify({'error': 'Email already exists'}), 400
            
            # Insert new user
            hashed_password = hash_password(password)
            cursor.execute(
                'INSERT INTO users (email, password) VALUES (%s, %s)',
                (email, hashed_password)
            )
            conn.commit()
            cursor.close()
            conn.close()
            
            return jsonify({'message': 'Registration successful'})
        
        return jsonify({'error': 'Database connection error'}), 500
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        data = request.json
        email = data.get('email')
        password = data.get('password')
        
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor(dictionary=True)
            
            hashed_password = hash_password(password)
            cursor.execute(
                'SELECT id FROM users WHERE email = %s AND password = %s',
                (email, hashed_password)
            )
            user = cursor.fetchone()
            cursor.close()
            conn.close()
            
            if user:
                session['user_id'] = user['id']
                return jsonify({'message': 'Login successful'})
            
            return jsonify({'error': 'Invalid credentials'}), 401
        
        return jsonify({'error': 'Database connection error'}), 500
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect(url_for('index'))

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor(dictionary=True)
        
        # Get user's payments
        cursor.execute('''
            SELECT * FROM payments 
            WHERE user_id = %s 
            ORDER BY created_at DESC
        ''', (session['user_id'],))
        
        payments = cursor.fetchall()
        cursor.close()
        conn.close()
        
        return render_template('dashboard.html', payments=payments)
    
    return redirect(url_for('login'))

@app.route('/create-payment-intent', methods=['POST'])
def create_payment_intent():
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    try:
        data = request.json
        intent = stripe.PaymentIntent.create(
            amount=int(float(data['amount']) * 100),
            currency='usd',
            description=data.get('description', ''),
            metadata={'user_id': session['user_id']}
        )
        
        return jsonify({
            'clientSecret': intent.client_secret
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/payment-success', methods=['POST'])
def payment_success():
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    data = request.json
    payment_intent_id = data.get('paymentIntentId')
    
    try:
        # Verify payment with Stripe
        payment_intent = stripe.PaymentIntent.retrieve(payment_intent_id)
        
        if payment_intent.status == 'succeeded':
            conn = get_db_connection()
            if conn:
                cursor = conn.cursor()
                
                # Record payment
                cursor.execute('''
                    INSERT INTO payments 
                    (stripe_payment_id, user_id, amount, currency, status, description)
                    VALUES (%s, %s, %s, %s, %s, %s)
                ''', (
                    payment_intent_id,
                    session['user_id'],
                    payment_intent.amount / 100,
                    payment_intent.currency,
                    'completed',
                    payment_intent.description
                ))
                
                conn.commit()
                cursor.close()
                conn.close()
                
                return jsonify({'message': 'Payment recorded successfully'})
            
            return jsonify({'error': 'Database connection error'}), 500
        
        return jsonify({'error': 'Payment verification failed'}), 400
        
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/payment-history')
def payment_history():
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute('''
            SELECT * FROM payments 
            WHERE user_id = %s 
            ORDER BY created_at DESC
        ''', (session['user_id'],))
        
        payments = cursor.fetchall()
        cursor.close()
        conn.close()
        
        # Convert decimal objects to float for JSON serialization
        for payment in payments:
            payment['amount'] = float(payment['amount'])
            payment['created_at'] = payment['created_at'].strftime('%Y-%m-%d %H:%M:%S')
        
        return jsonify(payments)
    
    return jsonify({'error': 'Database connection error'}), 500




@app.route('/credit-card-payment')
def credit_card_payment():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('credit-card.html')

@app.route('/bank-account-payment')
def bank_account_payment():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('bank-account.html')

@app.route('/upi-payment')
def upi_payment():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('upi.html')



@app.route('/create-setup-intent', methods=['POST'])
def create_setup_intent():
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
        
    try:
        # Get or create customer
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute('SELECT stripe_customer_id FROM users WHERE id = %s', (session['user_id'],))
            user = cursor.fetchone()
            
            if not user or not user.get('stripe_customer_id'):
                # Create new Stripe customer
                customer = stripe.Customer.create()
                cursor.execute(
                    'UPDATE users SET stripe_customer_id = %s WHERE id = %s',
                    (customer.id, session['user_id'])
                )
                conn.commit()
                customer_id = customer.id
            else:
                customer_id = user['stripe_customer_id']
                
            cursor.close()
            conn.close()
            
            # Create SetupIntent
            setup_intent = stripe.SetupIntent.create(
                customer=customer_id,
                payment_method_types=['card'],
            )
            
            return jsonify({
                'clientSecret': setup_intent.client_secret
            })
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/save-card', methods=['POST'])
def save_card():
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
        
    data = request.json
    payment_method_id = data.get('paymentMethodId')
    card_holder_name = data.get('cardHolderName')
    
    try:
        # Get user's stripe customer ID from database
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute('SELECT stripe_customer_id FROM users WHERE id = %s', (session['user_id'],))
            user = cursor.fetchone()
            cursor.close()
            conn.close()
            
            if not user or not user.get('stripe_customer_id'):
                return jsonify({'error': 'Stripe customer not found'}), 400
                
            # Attach the payment method to the customer
            payment_method = stripe.PaymentMethod.attach(
                payment_method_id,
                customer=user['stripe_customer_id'],
            )
            
            # Update the payment method with the cardholder name
            stripe.PaymentMethod.modify(
                payment_method_id,
                billing_details={"name": card_holder_name}
            )
            
            return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/get-saved-cards')
def get_saved_cards():
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
        
    try:
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute('SELECT stripe_customer_id FROM users WHERE id = %s', (session['user_id'],))
            user = cursor.fetchone()
            cursor.close()
            conn.close()
            
            if not user or not user.get('stripe_customer_id'):
                return jsonify({'error': 'Stripe customer not found'}), 400
                
            payment_methods = stripe.PaymentMethod.list(
                customer=user['stripe_customer_id'],
                type="card",
            )
            
            cards = [{
                'id': pm.id,
                'last4': pm.card.last4,
                'expMonth': pm.card.exp_month,
                'expYear': pm.card.exp_year,
                'brand': pm.card.brand,
                'cardHolderName': pm.billing_details.name
            } for pm in payment_methods.data]
            
            return jsonify(cards)
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/link-bank-account', methods=['POST'])
def link_bank_account():
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
        
    data = request.json
    try:
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute('SELECT stripe_customer_id FROM users WHERE id = %s', (session['user_id'],))
            user = cursor.fetchone()
            cursor.close()
            conn.close()
            
            if not user or not user.get('stripe_customer_id'):
                return jsonify({'error': 'Stripe customer not found'}), 400
        
        # Create a bank account token
        bank_account = stripe.Token.create(
            bank_account={
                'country': 'US',
                'currency': 'usd',
                'account_holder_name': data['accountHolderName'],
                'account_holder_type': 'individual',
                'routing_number': data['routingNumber'],
                'account_number': data['accountNumber'],
            },
        )
        
        # Attach the bank account to the customer
        customer = stripe.Customer.modify(
            user['stripe_customer_id'],
            source=bank_account.id
        )
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/add-upi', methods=['POST'])
def add_upi():
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
        
    data = request.json
    upi_id = data.get('upiId')
    
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database connection error'}), 500
            
        cursor = conn.cursor()
        
        # Create upi_ids table if it doesn't exist
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS upi_ids (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                upi_id VARCHAR(255) NOT NULL,
                verified BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id),
                UNIQUE KEY unique_user_upi (user_id, upi_id)
            )
        ''')
        
        # Insert the new UPI ID
        cursor.execute('''
            INSERT INTO upi_ids (user_id, upi_id)
            VALUES (%s, %s)
        ''', (session['user_id'], upi_id))
        
        conn.commit()
        return jsonify({'success': True})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()
    
@app.route('/verify-upi', methods=['POST'])
def verify_upi():
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
        
    data = request.json
    upi_id = data.get('upiId')
    
    # Validate UPI ID format
    upi_pattern = r'^[a-zA-Z0-9\.\-\_]{2,256}@[a-zA-Z][a-zA-Z]{2,64}$'
    if not re.match(upi_pattern, upi_id):
        return jsonify({'error': 'Invalid UPI ID format'}), 400
    
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database connection error'}), 500
            
        cursor = conn.cursor(dictionary=True)
        
        # Check if UPI ID already exists for this user
        cursor.execute('''
            SELECT id FROM upi_ids 
            WHERE user_id = %s AND upi_id = %s
        ''', (session['user_id'], upi_id))
        
        if cursor.fetchone():
            return jsonify({'error': 'UPI ID already exists'}), 400
        
        # In a real application, you would verify the UPI ID with your payment processor here
        # For demo purposes, we'll assume verification is successful
        verified = True
        
        if verified:
            return jsonify({'verified': True})
        else:
            return jsonify({'error': 'UPI verification failed'}), 400
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()

@app.route('/get-saved-upis')
def get_saved_upis():
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
        
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database connection error'}), 500
            
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute('''
            SELECT id, upi_id, verified, created_at 
            FROM upi_ids 
            WHERE user_id = %s 
            ORDER BY created_at DESC
        ''', (session['user_id'],))
        
        upi_ids = cursor.fetchall()
        
        # Convert datetime objects to strings for JSON serialization
        for upi in upi_ids:
            upi['created_at'] = upi['created_at'].strftime('%Y-%m-%d %H:%M:%S')
        
        return jsonify(upi_ids)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()

@app.route('/remove-upi/<int:upi_id>', methods=['DELETE'])
def remove_upi(upi_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
        
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database connection error'}), 500
            
        cursor = conn.cursor()
        
        # Delete UPI ID (only if it belongs to the current user)
        cursor.execute('''
            DELETE FROM upi_ids 
            WHERE id = %s AND user_id = %s
        ''', (upi_id, session['user_id']))
        
        conn.commit()
        return jsonify({'success': True})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()

@app.route('/initiate-upi-payment', methods=['POST'])
def initiate_upi_payment():
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
        
    data = request.json
    upi_id = data.get('upiId')
    amount = data.get('amount')
    description = data.get('description')
    
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database connection error'}), 500
            
        cursor = conn.cursor(dictionary=True)
        
        # Verify UPI ID belongs to user
        cursor.execute('''
            SELECT id FROM upi_ids 
            WHERE user_id = %s AND upi_id = %s AND verified = TRUE
        ''', (session['user_id'], upi_id))
        
        if not cursor.fetchone():
            return jsonify({'error': 'Invalid or unverified UPI ID'}), 400
        
        # Generate a unique payment ID for UPI payments
        payment_id = f"upi_{secrets.token_hex(16)}"
        
        # Insert into the main payments table
        cursor.execute('''
            INSERT INTO payments (
                stripe_payment_id, 
                user_id, 
                amount, 
                currency, 
                status, 
                description,
                payment_method
            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
        ''', (
            payment_id,
            session['user_id'],
            amount,
            'INR',  # Using INR for UPI payments
            'completed',  # You might want to add proper status handling
            description,
            f'UPI ({upi_id})'
        ))
        
        conn.commit()
        return jsonify({
            'success': True,
            'message': 'Payment recorded successfully'
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()

@app.route('/get-payment-methods')
def get_payment_methods():
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
        
    try:
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute('SELECT stripe_customer_id FROM users WHERE id = %s', (session['user_id'],))
            user = cursor.fetchone()
            cursor.close()
            conn.close()
            
            if not user or not user.get('stripe_customer_id'):
                return jsonify({'error': 'Stripe customer not found'}), 400
        
        # Get all payment methods for the customer
        cards = stripe.PaymentMethod.list(
            customer=user['stripe_customer_id'],
            type="card",
        )
        
        # Get bank accounts
        customer = stripe.Customer.retrieve(
            user['stripe_customer_id'],
            expand=['sources']
        )
        bank_accounts = [source for source in customer.sources.data if source.object == 'bank_account']
        
        return jsonify({
            'cards': [{
                'id': pm.id,
                'last4': pm.card.last4,
                'expMonth': pm.card.exp_month,
                'expYear': pm.card.exp_year,
                'brand': pm.card.brand
            } for pm in cards.data],
            'bankAccounts': [{
                'id': ba.id,
                'last4': ba.last4,
                'bankName': ba.bank_name,
                'accountHolderName': ba.account_holder_name
            } for ba in bank_accounts]
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/remove-payment-method/<method_type>/<method_id>', methods=['DELETE'])
def remove_payment_method(method_type, method_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
        
    try:
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute('SELECT stripe_customer_id FROM users WHERE id = %s', (session['user_id'],))
            user = cursor.fetchone()
            cursor.close()
            conn.close()
            
            if not user or not user.get('stripe_customer_id'):
                return jsonify({'error': 'Stripe customer not found'}), 400
                
        if method_type == 'card':
            stripe.PaymentMethod.detach(method_id)
        elif method_type == 'bank_account':
            stripe.Customer.delete_source(
                user['stripe_customer_id'],
                method_id
            )
            
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 400

if __name__ == '__main__':
    init_db()
    app.run(debug=True)