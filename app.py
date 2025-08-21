from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import openai
import os
from dotenv import load_dotenv
import logging
import time
import json
from datetime import datetime
import uuid

# انوائرمنٹ ویری ایبلز لوڈ کریں
load_dotenv()

# ایپلیکیشن سیٹ اپ
app = Flask(__name__, static_folder='../frontend', static_url_path='')
CORS(app, origins=["http://localhost:8000", "http://127.0.0.1:8000", "https://your-vercel-app.vercel.app"])

# لوگنگ سیٹ اپ
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# OpenAI API کنفیگریشن
openai.api_key = os.getenv("OPENAI_API_KEY")
if not openai.api_key:
    logger.warning("OpenAI API key not found! Please set OPENAI_API_KEY in .env file")

# API کی درخواستوں کی حد بندی کے لیے
class RateLimiter:
    def __init__(self, max_requests, time_window):
        self.max_requests = max_requests
        self.time_window = time_window
        self.requests = {}

    def is_allowed(self, ip_address):
        now = time.time()
        if ip_address not in self.requests:
            self.requests[ip_address] = []
        
        # پرانی درخواستیں صاف کریں
        self.requests[ip_address] = [req_time for req_time in self.requests[ip_address] 
                                   if now - req_time < self.time_window]
        
        if len(self.requests[ip_address]) < self.max_requests:
            self.requests[ip_address].append(now)
            return True
        return False

# فی منٹ 30 درخواستوں کی حد
rate_limiter = RateLimiter(max_requests=30, time_window=60)

# چیٹ ہسٹری سٹور کرنے کے لیے (production کے لیے database استعمال کریں)
chat_sessions = {}

# روٹس
@app.route('/')
def serve_frontend():
    """فرنٹ ایند سرو کرنے کے لیے"""
    return send_from_directory(app.static_folder, 'index.html')

@app.route('/<path:path>')
def serve_static_files(path):
    """سٹیٹک فائلیں سرو کرنے کے لیے"""
    return send_from_directory(app.static_folder, path)

@app.route('/api/chat', methods=['POST'])
def chat():
    """AI کے ساتھ چیٹ کے لیے مرکزی API"""
    try:
        # درخواست کی حد بندی چیک کریں
        client_ip = request.remote_addr
        if not rate_limiter.is_allowed(client_ip):
            return jsonify({
                "error": "درخواست کی حد سے تجاوز۔ براہ کرم ایک منٹ بعد دوبارہ کوشش کریں۔"
            }), 429

        # ڈیٹا ویلیڈیٹ کریں
        data = request.get_json()
        if not data or 'message' not in data:
            return jsonify({
                "error": "غلط درخواست۔ 'message' فیلڈ ضروری ہے۔"
            }), 400

        user_message = data['message'].strip()
        session_id = data.get('session_id', str(uuid.uuid4()))
        
        # میسج کی لمبائی چیک کریں
        if len(user_message) > 1000:
            return jsonify({
                "error": "پیغام بہت طویل ہے۔ زیادہ سے زیادہ 1000 حروف allowed ہیں۔"
            }), 400

        if not user_message:
            return jsonify({
                "error": "خالی پیغام نہیں بھیجا جا سکتا۔"
            }), 400

        # سیشن مینجمنٹ
        if session_id not in chat_sessions:
            chat_sessions[session_id] = {
                'messages': [],
                'created_at': datetime.now(),
                'last_activity': datetime.now()
            }

        # پرانی سیشنز صاف کریں (24 گھنٹے سے پرانی)
        cleanup_old_sessions()

        # OpenAI API کو کال کریں
        start_time = time.time()
        
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "آپ ایک مفید AI معاون ہیں۔ اردو میں جواب دیں اور صارف کی مدد کے لیے تیار رہیں۔"},
                *chat_sessions[session_id]['messages'],
                {"role": "user", "content": user_message}
            ],
            max_tokens=500,
            temperature=0.7,
            timeout=30  # 30 سیکنڈ میں ٹائم آؤٹ
        )

        processing_time = time.time() - start_time

        ai_response = response.choices[0].message['content']
        
        # چیٹ ہسٹری اپ ڈیٹ کریں
        chat_sessions[session_id]['messages'].extend([
            {"role": "user", "content": user_message},
            {"role": "assistant", "content": ai_response}
        ])
        chat_sessions[session_id]['last_activity'] = datetime.now()

        # ہسٹری لمبائی محدود کریں
        if len(chat_sessions[session_id]['messages']) > 20:
            chat_sessions[session_id]['messages'] = chat_sessions[session_id]['messages'][-20:]

        logger.info(f"Chat processed - Session: {session_id}, Time: {processing_time:.2f}s")

        return jsonify({
            "reply": ai_response,
            "session_id": session_id,
            "processing_time": processing_time
        })

    except openai.error.AuthenticationError:
        logger.error("OpenAI authentication failed")
        return jsonify({
            "error": "API key غلط ہے۔ براہ کرم درست API key سیٹ کریں۔"
        }), 401

    except openai.error.RateLimitError:
        logger.error("OpenAI rate limit exceeded")
        return jsonify({
            "error": "API استعمال کی حد سے تجاوز۔ براہ کرم تھوڑی دیر بعد دوبارہ کوشش کریں۔"
        }), 429

    except openai.error.Timeout:
        logger.error("OpenAI request timeout")
        return jsonify({
            "error": "درخواست ٹائم آؤٹ ہو گئی۔ براہ کرم دوبارہ کوشش کریں۔"
        }), 408

    except openai.error.APIError as e:
        logger.error(f"OpenAI API error: {str(e)}")
        return jsonify({
            "error": "API میں عارضی مسئلہ ہے۔ براہ کرم دوبارہ کوشش کریں۔"
        }), 500

    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return jsonify({
            "error": "سرور میں عارضی مسئلہ ہے۔ براہ کرم دوبارہ کوشش کریں۔"
        }), 500

@app.route('/api/sessions/<session_id>', methods=['DELETE'])
def clear_session(session_id):
    """سیشن ہسٹری صاف کرنے کے لیے"""
    if session_id in chat_sessions:
        del chat_sessions[session_id]
        logger.info(f"Session cleared: {session_id}")
        return jsonify({"message": "سیشن ہسٹری صاف کر دی گئی ہے۔"})
    return jsonify({"error": "سیشن نہیں ملا۔"}), 404

@app.route('/api/health', methods=['GET'])
def health_check():
    """ہیلتھ چیک API"""
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "active_sessions": len(chat_sessions),
        "openai_configured": bool(openai.api_key)
    })

@app.route('/api/info', methods=['GET'])
def api_info():
    """API معلومات کے لیے"""
    return jsonify({
        "name": "AI Chat API",
        "version": "1.0.0",
        "description": "OpenAI GPT-3.5 Turbo پر مبنی چیٹ API",
        "endpoints": {
            "chat": "POST /api/chat",
            "health": "GET /api/health",
            "clear_session": "DELETE /api/sessions/<session_id>"
        }
    })

def cleanup_old_sessions():
    """24 گھنٹے سے پرانی سیشنز صاف کریں"""
    now = datetime.now()
    sessions_to_delete = []
    
    for session_id, session_data in chat_sessions.items():
        if (now - session_data['last_activity']).total_seconds() > 24 * 3600:  # 24 گھنٹے
            sessions_to_delete.append(session_id)
    
    for session_id in sessions_to_delete:
        del chat_sessions[session_id]
    
    if sessions_to_delete:
        logger.info(f"Cleaned up {len(sessions_to_delete)} old sessions")

# ایرر ہینڈلرز
@app.errorhandler(404)
def not_found_error(error):
    return jsonify({"error": "راستہ نہیں ملا۔"}), 404

@app.errorhandler(500)
def internal_error(error):
    logger.error(f"Server error: {str(error)}")
    return jsonify({"error": "سرور میں عارضی مسئلہ ہے۔"}), 500

# ہر 10 منٹ بعد پرانی سیشنز صاف کریں
@app.before_request
def before_request():
    # ہر 10ویں درخواست پر صفائی چلائیں
    if len(chat_sessions) % 10 == 0:
        cleanup_old_sessions()

if __name__ == '__main__':
    # پروڈکشن کے لیے پورٹ 5000 استعمال کریں
    port = int(os.environ.get('PORT', 5000))
    
    # ڈیبگ موڈ صرف ڈویلپمنٹ میں
    debug = os.environ.get('FLASK_ENV') == 'development'
    
    logger.info(f"Starting Flask server on port {port}")
    app.run(host='0.0.0.0', port=port, debug=debug)