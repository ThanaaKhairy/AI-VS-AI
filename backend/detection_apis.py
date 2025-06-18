from flask_app import app

import re
from flask import Flask, request, jsonify, session, redirect
import bcrypt
import random
import smtplib
import base64
import numpy as np
from tensorflow.keras.applications.xception import preprocess_input
from PIL import Image
from io import BytesIO
import types
import sys
import os
import uuid
import torch
import pyodbc
import requests
import torchvision.transforms as transforms
from datetime import datetime



server = 'DESKTOP-M13HNO9\\MSSQLSERVER01'
database = 'GP'
connection_string = f'DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={server};DATABASE={database};Trusted_Connection=yes;'

base_image_path = "E:/GP/Images/Detection"

def connect_to_db():
    try:
        conn = pyodbc.connect(connection_string)
        return conn
    except pyodbc.Error:
        return None

import torch
from transformers.models.efficientnet.modeling_efficientnet import EfficientNetModel

from transformers.models.efficientnet.modeling_efficientnet import EfficientNetModel
torch.serialization.add_safe_globals([EfficientNetModel])
model = torch.load("E:/GP/EfficientNet-B6 Final.pth", map_location=torch.device('cpu'), weights_only=False)
model.eval()

label_map = {0: "Fake", 1: "Real"}

def preprocess_image(image: Image.Image):
    image = image.resize((299, 299))
    img_array = np.array(image).astype(np.float32)
    img_array = np.expand_dims(img_array, axis=0)
    img_array = preprocess_input(img_array)
    return torch.from_numpy(img_array).permute(0, 3, 1, 2)  # (B, C, H, W)

@app.route('/upload-URL-image', methods=['POST'])
def save_image_from_url():
    if 'user_id' not in session:
        return jsonify({"error": "Please log in first."}), 401

    data = request.json
    image_url = data.get('image_url')
    if not image_url:
        return jsonify({"error": "Please provide an image URL."}), 400

    user_id = session['user_id']
    conn = connect_to_db()
    if conn is None:
        return jsonify({"error": "Database connection error."}), 500

    try:
        response = requests.get(image_url, stream=True, timeout=30)
        response.raise_for_status()
        image_data = response.content
        img = Image.open(BytesIO(image_data))

        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")

        image_tensor = preprocess_image(img)

        with torch.no_grad():
            output = model(image_tensor)
            logits = output.logits
            probabilities = torch.softmax(logits, dim=-1)
            predicted_class_idx = probabilities.argmax(-1).item()
            confidence = probabilities[0][predicted_class_idx].item() * 100
            predicted_label = label_map[predicted_class_idx]

        user_folder = os.path.join(base_image_path, f"user_{user_id}")
        os.makedirs(user_folder, exist_ok=True)
        image_name = f"{uuid.uuid4()}.jpg"
        image_full_path = os.path.join(user_folder, image_name)
        img.save(image_full_path, format="JPEG")

        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO Images_detection (image_path, detection_result, user_id) VALUES (?, ?, ?)",
            (image_full_path, predicted_label, user_id)
        )
        conn.commit()

        return jsonify({
            "message": "Image uploaded and detected successfully!",
            "predicted_class": predicted_label,
            "confidence": f"{confidence:.2f}%"
        }), 201

    except requests.exceptions.RequestException as req_error:
        return jsonify({"error": f"Failed to download image: {str(req_error)}"}), 400

    except Exception as e:
        return jsonify({"error": f"Error processing image: {str(e)}"}), 500
    finally:
        conn.close()


@app.route('/upload-image-local', methods=['POST'])
def upload_image_local():
    if 'user_id' not in session:
        return jsonify({"error": "Please log in first."}), 401

    if 'image' not in request.files:
        return jsonify({"error": "No image file provided."}), 400

    image = request.files['image']
    if image.filename == '':
        return jsonify({"error": "No selected file."}), 400

    user_id = session['user_id']
    conn = connect_to_db()
    if conn is None:
        return jsonify({"error": "Database connection error."}), 500

    try:
        img = Image.open(image)
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")

        image_tensor = preprocess_image(img)

        with torch.no_grad():
            output = model(image_tensor)
            logits = output.logits
            probabilities = torch.softmax(logits, dim=-1)
            predicted_class_idx = probabilities.argmax(-1).item()
            confidence = probabilities[0][predicted_class_idx].item() * 100
            predicted_label = label_map[predicted_class_idx]

        user_folder = os.path.join(base_image_path, f"user_{user_id}")
        os.makedirs(user_folder, exist_ok=True)
        image_name = f"{uuid.uuid4()}.jpg"
        image_full_path = os.path.join(user_folder, image_name)
        img.save(image_full_path, format="JPEG")

        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO Images_detection (image_path, detection_result, user_id) VALUES (?, ?, ?)",
            (image_full_path, predicted_label, user_id)
        )
        conn.commit()

        return jsonify({
            "message": "Image uploaded and detected successfully!",
            "predicted_class": predicted_label,
            "confidence": f"{confidence:.2f}%"
        }), 201

    except Exception as e:
        return jsonify({"error": f"Error processing image: {str(e)}"}), 500
    finally:
        conn.close()
        
        
        
@app.route('/user-detection-images', methods=['GET'])
def get_user_detection_images():
    if 'user_id' not in session:
        return jsonify({"error": "Unauthorized"}), 401

    user_id = session['user_id']
    conn = connect_to_db()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500

    try:
        cursor = conn.cursor()

        cursor.execute(
            "SELECT image_id, detection_result, image_path FROM [Images_detection] WHERE user_id = ?",
            (user_id,)
        )
        rows = cursor.fetchall()

        images = []
        for img_id, result, path in rows:
            if os.path.exists(path):
                with open(path, "rb") as img_file:
                    encoded = base64.b64encode(img_file.read()).decode("utf-8")
                    images.append({
                        "image_id": img_id,  
                        "detection_result": result,
                        "image": f"data:image/png;base64,{encoded}"
                    })

        return jsonify(images), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()


@app.route('/delete-detection-image', methods=['DELETE'])
def delete_detection_image():
    if 'user_id' not in session:
        return jsonify({"error": "Unauthorized"}), 401

    data = request.get_json(force=True)
    image_id = data.get("image_id")
    if not image_id:
        return jsonify({"error": "Image ID is required"}), 400

    conn = connect_to_db()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500

    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT image_path FROM [Images_detection] WHERE image_id = ? AND user_id = ?",
            (image_id, session['user_id'])
        )
        row = cursor.fetchone()
        if not row:
            return jsonify({"error": "Image not found or does not belong to user"}), 404

        image_path = row[0]
        if os.path.exists(image_path):
            os.remove(image_path)

        cursor.execute("DELETE FROM [Images_detection] WHERE image_id = ? AND user_id = ?", (image_id, session['user_id']))
        conn.commit()

        return jsonify({"message": "Image deleted successfully"}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()


@app.route('/delete-all-detection-images', methods=['DELETE'])
def delete_all_detection_images():
    if 'user_id' not in session:
        return jsonify({"error": "Unauthorized"}), 401

    user_id = session['user_id']
    conn = connect_to_db()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500

    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT image_path FROM [Images_detection] WHERE user_id = ?",
            (user_id,)
        )
        rows = cursor.fetchall()

        for row in rows:
            image_path = row[0]
            if os.path.exists(image_path):
                os.remove(image_path)

        cursor.execute(
            "DELETE FROM [Images_detection] WHERE user_id = ?",
            (user_id,)
        )
        conn.commit()

        return jsonify({"message": "All detection images deleted successfully"}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()
