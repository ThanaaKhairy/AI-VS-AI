
from flask_app import app

import os
import pyodbc
import re
import requests
from flask import Flask, request, jsonify, session, redirect
import bcrypt
import uuid
import random
import smtplib
from email.mime.text import MIMEText
from datetime import datetime, timedelta
from email.message import EmailMessage
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
from google.auth.exceptions import GoogleAuthError
from PIL import Image
from io import BytesIO
import types
import sys


server = 'DESKTOP-M13HNO9\\MSSQLSERVER01'
database = 'GP'
connection_string = f'DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={server};DATABASE={database};Trusted_Connection=yes;'



base_image_path = "E:/GP/Images"

def connect_to_db():
    try:
        conn = pyodbc.connect(connection_string)
        return conn
    except pyodbc.Error:
        return None


def send_verification_email(email, verification_code):
    EMAIL_ADDRESS = 'thanaamater@gmail.com'
    EMAIL_PASSWORD = ''

    msg = EmailMessage()
    msg['Subject'] = 'OTP Verification'
    msg['From'] = EMAIL_ADDRESS
    msg['To'] = email
    msg.set_content(f"Your verification code is: {verification_code}")

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            server.send_message(msg)
    except Exception as e:
        print(f"Failed to send email: {e}")

@app.route('/register', methods=['POST'])
def register_user():
    data = request.json
    name = data.get('name')
    email = data.get('email')
    password = data.get('password')

    if not name or not email or not password:
        return jsonify({"error": "Please fill all fields."}), 400

    email_pattern = r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$'

    if not re.match(email_pattern, email):
      return jsonify({"error": "Invalid email format."}), 400

    if not email.endswith('@gmail.com'):
      return jsonify({"error": "Email must end with @gmail.com."}), 400

    if len(password) < 8:
        return jsonify({"error": "Password must be at least 8 characters long."}), 400

    hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

    verification_code = str(random.randint(100000, 999999))
    verification_code_expiry = datetime.now() + timedelta(minutes=3)

    conn = connect_to_db()
    if conn is None:
        return jsonify({"error": "Error connecting to database."}), 500

    try:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO [User] (name, email, password, verification_code, verification_code_expiry) VALUES (?, ?, ?, ?, ?)",
            (name, email, hashed_password, verification_code, verification_code_expiry)
        )
        conn.commit()
        send_verification_email(email, verification_code)
        return jsonify({"message": "User registered successfully! Verification code sent to email."}), 201
    except pyodbc.IntegrityError:
        return jsonify({"error": "Email already exists."}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()

@app.route('/verify-code', methods=['POST'])
def verify_code():
    data = request.json
    email = data.get('email')
    code = data.get('code')

    if not email or not code:
        return jsonify({"error": "Please provide email and verification code."}), 400

    conn = connect_to_db()
    if conn is None:
        return jsonify({"error": "Error connecting to database."}), 500

    try:
        cursor = conn.cursor()
        cursor.execute("SELECT verification_code, verification_code_expiry FROM [User] WHERE email = ?", (email,))
        user = cursor.fetchone()

        if not user:
            return jsonify({"error": "User not found."}), 404

        stored_code, code_expiry = user

        if datetime.now() > code_expiry:
            return jsonify({"error": "Verification code has expired."}), 400

        if code != stored_code:
            return jsonify({"error": "Invalid verification code."}), 400

        cursor.execute("UPDATE [User] SET is_verified = 1 WHERE email = ?", (email,))
        conn.commit()
        return jsonify({"message": "Email verified successfully!"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()

@app.route('/resend-verification-code', methods=['POST'])
def resend_verification_code_api():
    data = request.json
    email = data.get('email')

    if not email:
        return jsonify({"error": "Please provide an email."}), 400

    conn = connect_to_db()
    if conn is None:
        return jsonify({"error": "Error connecting to database."}), 500

    try:
        cursor = conn.cursor()
        cursor.execute("SELECT is_verified FROM [User] WHERE email = ?", (email,))
        user = cursor.fetchone()

        if not user:
            return jsonify({"error": "User not found."}), 404

        if user[0]:
            return jsonify({"message": "Email is already verified."}), 400

        verification_code = str(random.randint(100000, 999999))
        verification_code_expiry = datetime.now() + timedelta(minutes=3)
        cursor.execute(
            "UPDATE [User] SET verification_code = ?, verification_code_expiry = ? WHERE email = ?",
            (verification_code, verification_code_expiry, email)
        )
        conn.commit()
        send_verification_email(email, verification_code)
        return jsonify({"message": "Verification code resent successfully."}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()

@app.route('/forgot-password', methods=['POST'])
def forgot_password():
    data = request.json
    email = data.get('email')

    if not email:
        return jsonify({"error": "Please provide an email."}), 400

    conn = connect_to_db()
    if conn is None:
        return jsonify({"error": "Error connecting to database."}), 500

    try:
        cursor = conn.cursor()
        cursor.execute("SELECT user_id FROM [User] WHERE email = ?", (email,))
        user = cursor.fetchone()

        if not user:
            return jsonify({"error": "Email not found."}), 404

        verification_code = str(random.randint(100000, 999999))
        verification_code_expiry = datetime.now() + timedelta(minutes=10)
        cursor.execute(
            "UPDATE [User] SET verification_code = ?, verification_code_expiry = ? WHERE email = ?",
            (verification_code, verification_code_expiry, email)
        )
        conn.commit()
        send_verification_email(email, verification_code)
        return jsonify({"message": "Password reset code sent to email."}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()

@app.route('/verify-reset-code', methods=['POST'])
def verify_reset_code():
    data = request.json
    email = data.get('email')
    reset_code = data.get('reset_code')

    if not email or not reset_code:
        return jsonify({"error": "Please provide email and reset code."}), 400

    conn = connect_to_db()
    if conn is None:
        return jsonify({"error": "Error connecting to database."}), 500

    try:
        cursor = conn.cursor()
        cursor.execute("SELECT verification_code, verification_code_expiry FROM [User] WHERE email = ?", (email,))
        user = cursor.fetchone()

        if not user:
            return jsonify({"error": "User not found."}), 404

        stored_code, code_expiry = user

        if datetime.now() > code_expiry:
            return jsonify({"error": "Reset code has expired."}), 400

        if reset_code != stored_code:
            return jsonify({"error": "Invalid reset code."}), 400

        return jsonify({"message": "Reset code verified successfully!"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()

@app.route('/reset-password', methods=['POST'])
def reset_password():
    data = request.json
    email = data.get('email')
    new_password = data.get('new_password')

    if not email or not new_password:
        return jsonify({"error": "Please provide email and new password."}), 400

    if len(new_password) < 8:
        return jsonify({"error": "Password must be at least 8 characters long."}), 400

    hashed_password = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

    conn = connect_to_db()
    if conn is None:
        return jsonify({"error": "Error connecting to database."}), 500

    try:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE [User] SET password = ?, verification_code = NULL, verification_code_expiry = NULL WHERE email = ?",
            (hashed_password, email)
        )
        conn.commit()
        return jsonify({"message": "Password reset successfully!"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()

@app.route('/login', methods=['POST'])
def login_user():
    data = request.json
    email = data.get('email')
    password = data.get('password')

    if not email or not password:
        return jsonify({"error": "Please provide email and password."}), 400

    email_pattern = r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$'

    if not re.match(email_pattern, email):
        return jsonify({"error": "Invalid email format."}), 400

    if not email.endswith('@gmail.com'):
        return jsonify({"error": "Email must end with @gmail.com."}), 400

    conn = connect_to_db()
    if conn is None:
        return jsonify({"error": "Error connecting to database."}), 500

    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT user_id, name, email, password, is_verified, role FROM [User] WHERE email = ?",
            (email,)
        )
        user = cursor.fetchone()

        if not user:
            return jsonify({"error": "There is no account with this email"}), 404

        user_id, name, email, stored_password, is_verified, role = user

        if not bcrypt.checkpw(password.encode('utf-8'), stored_password.encode('utf-8')):
            return jsonify({"error": "Invalid email or password."}), 400

        if not is_verified:
            return jsonify({"error": "Email not verified."}), 400

        session['user_id'] = user_id

        response_data = {
            "message": "Login successful!",
            "redirect_url": "/admin-dashboard" if role == 'Admin' else "/user-dashboard",
            "user_id": user_id,
            "name": name,
            "email": email,
            "role": role
        }

        return jsonify(response_data), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()
        
        
        
@app.route('/logout', methods=['POST'])
def logout_user():
    if 'user_id' in session:
        session.pop('user_id', None)
        return jsonify({"message": "Logout successful."}), 200
    else:
        return jsonify({"error": "User not logged in."}), 400
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
