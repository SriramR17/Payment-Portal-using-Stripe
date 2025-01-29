from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import mysql.connector
import stripe
from datetime import datetime
import os
import hashlib
import secrets

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
        
        # Users table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INT AUTO_INCREMENT PRIMARY KEY,
                email VARCHAR(120) UNIQUE NOT NULL,
                password VARCHAR(255) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
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
    return render_template('base.html')

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

if __name__ == '__main__':
    init_db()
    app.run(debug=True)