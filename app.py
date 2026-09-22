from flask import Flask, request
import requests
import os

app = Flask(__name__)

# ضع رمز بوت تيليجرام ورقم المحادثة هنا أو استخدم متغيرات البيئة
TELEGRAM_BOT_TOKEN = "TOKEN_HERE"
TELEGRAM_CHAT_ID = "CHAT_ID_HERE"

@app.route('/')
def home():
    return "Bot is running successfully!"

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.get_json()
    if data:
        # استخراج الرسالة القادمة من تنبيه ترادينغ فيو
        message = data.get('message', 'تنبيه جديد من TradingView')
        
        # إرسال الرسالة إلى تيليجرام
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "Markdown"
        }
        response = requests.post(url, json=payload)
        
        if response.status_code == 200:
            return "Sent to Telegram successfully", 200
        else:
            return "Failed to send to Telegram", 500
            
    return "No data received", 400

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
