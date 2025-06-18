

from flask_app import app
import base64

import os
import sys
from flask import Flask, request, jsonify, send_file, session
from io import BytesIO
import uuid
import torch
from diffusers import StableDiffusionPipeline
import pyodbc
import smtplib
from email.message import EmailMessage

from peft import LoraConfig, get_peft_model
from PIL import Image
from gradio_client import Client
import os, uuid
import requests
import base64
from io import BytesIO
from flask import request, session, jsonify, send_file
from PIL import Image
from gradio_client import Client
import os, uuid, base64, requests
from io import BytesIO
from flask import request, session, jsonify, send_file




# 1. FORCE ALL CACHE TO D: DRIVE ---------------------------------------------------
cache_base = "D:/ai_cache"  # Base directory for all AI-related files
base_image_path = "E:/GP/Images/Generation"

# 3. DATABASE CONFIGURATION (UNCHANGED) --------------------------------------------
server = 'DESKTOP-M13HNO9\\MSSQLSERVER01'
database = 'GP'
connection_string = f'DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={server};DATABASE={database};Trusted_Connection=yes;'
lora_weights_path = "E:/GP/lora_weights_last.pth"
local_model_path = f"{cache_base}/stable-diffusion-v1-5"

def connect_to_db():
    try:
        return pyodbc.connect(connection_string)
    except pyodbc.Error as e:
        print(f"Database connection error: {e}")
        return None



def send_image_email(user_email, description, image_path):
    try:
        msg = EmailMessage()
        msg['Subject'] = 'Your Generated Image'
        msg['From'] = 'thanaamater@gmail.com' 
        msg['To'] = user_email

        msg.set_content(f"Hello,\n\nHere is your generated image:\nDescription: {description}\nEnjoy!")

        with open(image_path, 'rb') as img:
            img_data = img.read()
            img_name = os.path.basename(image_path)
            msg.add_attachment(img_data, maintype='image', subtype='png', filename=img_name)

        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login('thanaamater@gmail.com', 'gjmhkfdg')  # ✏️ غيّريهم
            smtp.send_message(msg)

    except Exception as e:
        raise Exception(f"Error sending email: {str(e)}")




client = None

def get_gradio_client():
    global client
    if client is None:
        client = Client("abdelrhman145/SD1.5_realistic_faces")
    return client

@app.route('/generate-image', methods=['POST'])
def generate_image():
    if 'user_id' not in session:
        return jsonify({"error": "Unauthorized"}), 401

    data = request.get_json(force=True)
    if not data or 'description' not in data:
        return jsonify({"error": "Description required"}), 400

    conn = connect_to_db()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500

    try:
        description = data['description']
        user_id = session['user_id']
        user_folder = os.path.join(f"{base_image_path}/generated_images", f"user_{user_id}")
        os.makedirs(user_folder, exist_ok=True)

        # الاتصال بالعميل
        client_instance = get_gradio_client()
        result = client_instance.predict(description, api_name="/predict")

        print("🌐 Full result object:", result)
        print("📦 Type of result:", type(result))

        output = result  

        if not os.path.exists(output):
            return jsonify({"error": "Output file does not exist"}), 500

       
        with Image.open(output) as img:
            img = img.convert("RGB")  
            filename = f"{uuid.uuid4()}.png"
            filepath = os.path.join(user_folder, filename)
            img.save(filepath, "PNG")

        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO [Images_generation] (description, image_path, user_id) VALUES (?, ?, ?)",
            (description, filepath, user_id)
        )
        conn.commit()

        img_io = BytesIO()
        with open(filepath, "rb") as f:
            img_io.write(f.read())
        img_io.seek(0)

        return send_file(img_io, mimetype='image/png')

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()




# # ---------------------- 4. MODEL LOADING WITH LoRA ----------------------
# print("\n⏳ Loading base model and applying LoRA weights...")
# pipe = None

# try:
#     if os.path.exists(local_model_path):
#         print(f"📦 Loading model from local cache: {local_model_path}")
#         model_source = local_model_path
#         use_local_only = True
#     else:
#         print("🌐 Local model not found. Downloading from Hugging Face...")
#         model_source = "runwayml/stable-diffusion-v1-5"
#         use_local_only = False

#     pipe = StableDiffusionPipeline.from_pretrained(
#         model_source,
#         torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
#         safety_checker=None,
#         requires_safety_checker=False,
#         local_files_only=use_local_only
#     )

#     if torch.cuda.is_available():
#         pipe = pipe.to("cuda")
#         pipe.enable_attention_slicing()
#         try:
#             import xformers
#             pipe.enable_xformers_memory_efficient_attention()
#         except:
#             print("Xformers not available")

#     # Apply LoRA
#     lora_config = LoraConfig(
#         r=16,
#         lora_alpha=32,
#         target_modules=[
#             "to_q", "to_k", "to_v", "to_out.0",
#             "proj_in", "proj_out",
#             "conv1", "conv2", "conv_shortcut"
#         ],
#         lora_dropout=0.1,
#         bias="none",
#     )
#     pipe.unet = get_peft_model(pipe.unet, lora_config)

#     if os.path.exists(lora_weights_path):
#         print(f"🔄 Loading LoRA weights from: {lora_weights_path}")
#         lora_state = torch.load(lora_weights_path, map_location="cuda" if torch.cuda.is_available() else "cpu")
#         pipe.unet.load_state_dict(lora_state, strict=False)
#         print("✅ LoRA weights applied successfully.")
#     else:
#         raise Exception(f"LoRA weights not found at {lora_weights_path}")

#     print(f"✅ Model ready with LoRA on {'GPU' if torch.cuda.is_available() else 'CPU'}.")

# except Exception as e:
#     print(f"❌ Error loading model or weights: {e}")
#     pipe = None


# # ---------------------- 5. IMAGE GENERATION ENDPOINT ----------------------
# @app.route('/generate-image', methods=['POST'])
# def generate_image():
#     if 'user_id' not in session:
#         return jsonify({"error": "Unauthorized"}), 401

#     data = request.json
#     if not data or 'description' not in data:
#         return jsonify({"error": "Description required"}), 400

#     if not pipe:
#         return jsonify({"error": "Model not available"}), 503

#     conn = connect_to_db()
#     if not conn:
#         return jsonify({"error": "Database connection failed"}), 500

#     try:
#         description = data['description']
#         user_id = session['user_id']
#         user_folder = os.path.join(f"{base_image_path}/generated_images", f"user_{user_id}")
#         os.makedirs(user_folder, exist_ok=True)

       
#         generator = torch.manual_seed(42)

#         image = pipe(
#             description,
#             num_inference_steps=50,
#             guidance_scale=9,
#             generator=generator  
#         ).images[0]

#         filename = f"{uuid.uuid4()}.png"
#         filepath = os.path.join(user_folder, filename)
#         image.save(filepath)

#         cursor = conn.cursor()
#         cursor.execute(
#             "INSERT INTO [Images_generation] (description, image_path, user_id) VALUES (?, ?, ?)",
#             (description, filepath, user_id)
#         )
#         conn.commit()

#         img_io = BytesIO()
#         image.save(img_io, 'PNG')
#         img_io.seek(0)
#         return send_file(img_io, mimetype='image/png')

#     except Exception as e:
#         return jsonify({"error": str(e)}), 500

#     finally:
#         if conn:
#             conn.close()


 

#---------------------------------------------------------------------------------------NEW-------------------------------------------------------------------------------
#---------------------------------------------------------------------------------------NEW-------------------------------------------------------------------------------
#---------------------------------------------------------------------------------------NEW-------------------------------------------------------------------------------
#---------------------------------------------------------------------------------------NEW-------------------------------------------------------------------------------



@app.route('/send-last-generated-image', methods=['POST'])
def send_last_generated_image():
    if 'user_id' not in session:
        return jsonify({"error": "Unauthorized"}), 401

    user_id = session['user_id']
    conn = connect_to_db()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500

    try:
        cursor = conn.cursor()

        cursor.execute("""
            SELECT TOP 1 description, image_path 
            FROM [Images_generation] 
            WHERE user_id = ? 
            ORDER BY image_id DESC
        """, (user_id,))
        result = cursor.fetchone()

        if not result:
            return jsonify({"error": "No generated image found"}), 404

        description, image_path = result

        cursor.execute("SELECT email FROM [User] WHERE user_id = ?", (user_id,))
        email_row = cursor.fetchone()
        if not email_row:
            return jsonify({"error": "User email not found"}), 404

        user_email = email_row[0]

        send_image_email(user_email, description, image_path)

        return jsonify({"message": "Image sent to email successfully."}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

    finally:
        conn.close()



@app.route('/user-generated-images', methods=['GET'])
def get_user_images_base64():
    if 'user_id' not in session:
        return jsonify({"error": "Unauthorized"}), 401

    user_id = session['user_id']
    conn = connect_to_db()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500

    try:
        cursor = conn.cursor()

        cursor.execute(
            "SELECT image_id, description, image_path FROM [Images_generation] WHERE user_id = ?",
            (user_id,)
        )
        rows = cursor.fetchall()

        images = []
        for img_id, desc, path in rows:
            if os.path.exists(path):
                with open(path, "rb") as img_file:
                    encoded = base64.b64encode(img_file.read()).decode("utf-8")
                    images.append({
                        "image_id": img_id,  
                        "description": desc,
                        "image": f"data:image/png;base64,{encoded}"
                    })

        return jsonify(images), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()




@app.route('/delete-generation-image', methods=['DELETE'])
def delete_generation_image():
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
            "SELECT image_path FROM [Images_generation] WHERE image_id = ? AND user_id = ?",
            (image_id, session['user_id'])
        )
        row = cursor.fetchone()
        if not row:
            return jsonify({"error": "Image not found or does not belong to user"}), 404

        image_path = row[0]
        if os.path.exists(image_path):
            os.remove(image_path)

        cursor.execute("DELETE FROM [Images_generation] WHERE image_id = ? AND user_id = ?", (image_id, session['user_id']))
        conn.commit()

        return jsonify({"message": "Image deleted successfully"}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()


@app.route('/delete-all-generation-images', methods=['DELETE'])
def delete_all_generation_images():
    if 'user_id' not in session:
        return jsonify({"error": "Unauthorized"}), 401

    user_id = session['user_id']
    conn = connect_to_db()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500

    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT image_path FROM [Images_generation] WHERE user_id = ?",
            (user_id,)
        )
        rows = cursor.fetchall()

        for row in rows:
            image_path = row[0]
            if os.path.exists(image_path):
                os.remove(image_path)

        cursor.execute(
            "DELETE FROM [Images_generation] WHERE user_id = ?",
            (user_id,)
        )
        conn.commit()

        return jsonify({"message": "All generation images deleted successfully"}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()
