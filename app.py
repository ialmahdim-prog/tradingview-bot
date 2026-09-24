from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask, request
import requests
import json
import os

app = Flask(__name__)

# ⚙️ إعدادات بوت تيليجرام
TELEGRAM_BOT_TOKEN = "8655072721:AAFlvQZFdR2DOduJcLeOsqBSDNXyGJZlSXA"
TELEGRAM_CHANNEL_ID = "-1004363846255"

# مجموعة لتسجيل الأخبار لمنع التكرار
sent_alerts = set()

def send_to_telegram(message):
    """🤖 دالة إرسال الرسائل إلى قناة تيليجرام"""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHANNEL_ID,
        "text": message,
        "parse_mode": "Markdown",
    }
    try:
        response = requests.post(url, json=payload)
        return response.json()
    except Exception as e:
        print("خطأ في إرسال الرسالة إلى تيليجرام:", e)
        return None

# 1️⃣ استقبال إشارات تريدينج فيو
@app.route("/webhook", endpoint="webhook_receiver", methods=["POST"])
def webhook():
    print("Raw request data received:", request.data)

    data = request.get_json(force=True, silent=True)
    if not data:
        if request.form:
            data = request.form.to_dict()
        else:
            try:
                data = json.loads(request.data.decode('utf-8'))
            except Exception:
                data = {}

    if not data:
        return "Invalid Data", 400

    signal_type = data.get("type", "VIP")
    ticker = data.get("ticker", "XAUUSD")
    interval = data.get("interval", "15m")
    action = data.get("action", "شراء")
    close_price = data.get("close", "0.0")
    sl = data.get("sl", "يُحدد هنا")
    tp1 = data.get("tp1", "يُحدد هنا")
    tp2 = data.get("tp2", "يُحدد هنا")
    tp3 = data.get("tp3", "يُحدد هنا")

    if signal_type == "VIP":
        message = f"""🚨🔥 [صفقة VIP رئيسية] 🔥🚨
━━━━━━━━━━━━━━━━━
📊 مؤشر: EA ALPHA VIP
💱 الأداة / الزوج: {ticker}
⏳ الفريم الزمني: {interval}
🎯 نوع الصفقة: {action}
💰 سعر الدخول: {close_price}
🛑 وقف الخسارة (SL): {sl}
🎯 الهدف الأول (TP1): {tp1}
🎯 الهدف الثاني (TP2): {tp2}
🎯 الهدف الثالث (TP3): {tp3}
━━━━━━━━━━━━━━━━━
#VIP_Signal #EA_ALPHA"""
    elif signal_type == "reversal":
        message = f"""🛑⚠️ [تنبيه انعكاس / خروج مبكر] ⚠️🛑
━━━━━━━━━━━━━━━━━
📊 مؤشر: EA ALPHA VIP
💱 الأداة / الزوج: {ticker}
⏳ الفريم الزمني: {interval}
📉 الحالة: {action}
💰 سعر الإغلاق: {close_price}
💡 انتظر دخول جديد ⏳
━━━━━━━━━━━━━━━━━
#Reversal #EA_ALPHA"""
    else:
        message = f"""⭐⚡ [فرصة عالية التأكيد] ⚡⭐
━━━━━━━━━━━━━━━━━
📊 مؤشر: EA ALPHA VIP
💱 الأداة / الزوج: {ticker}
⏳ الفريم الزمني: {interval}
🎯 نوع الصفقة: {action}
💰 سعر الدخول: {close_price}
🛑 وقف الخسارة (SL): {sl}
🎯 الهدف الأول (TP1): {tp1}
🎯 الهدف الثاني (TP2): {tp2}
━━━━━━━━━━━━━━━━━
#High_Confidence #EA_ALPHA"""

    send_to_telegram(message)
    return "OK", 200

# 2️⃣ تصفية وإرسال الأخبار الاقتصادية لجميع العملات
def check_forex_factory_news():
    try:
        url = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
        response = requests.get(url)
        if response.status_code != 200:
            return

        events = response.json()
        now_ksa = datetime.utcnow() + timedelta(hours=3)

        for event in events:
            currency = event.get("currency")
            impact = event.get("impact")
            title = event.get("title")
            date_str = event.get("date")

            if impact in ["High", "Medium"]:
                try:
                    event_time_utc = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                    event_time_ksa = event_time_utc.astimezone().replace(tzinfo=None) + timedelta(hours=3)
                    time_difference = (event_time_ksa - now_ksa).total_seconds() / 60
                    event_id = f"{title}_{date_str}"

                    if 58 <= time_difference <= 62 and event_id not in sent_alerts:
                        impact_emoji = "🔴" if impact == "High" else "🟠"
                        news_alert = f"""⏳ **تنبيه اقتصادي هام (بعد ساعة)**
━━━━━━━━━━━━━━━━━
📊 الحدث: {title}
💱 العملة / الأثر: {currency} {impact_emoji} ({impact})
⏰ الوقت: {event_time_ksa.strftime('%I:%M %p')} (بتوقيت السعودية)
━━━━━━━━━━━━━━━━━
#Economic_News #{currency}"""
                        send_to_telegram(news_alert)
                        sent_alerts.add(event_id)
                except Exception:
                    continue
    except Exception as e:
        print("خطأ في فحص الأخبار الاقتصادية:", e)

# ⚙️ المجدول الزمني
scheduler = BackgroundScheduler()
scheduler.add_job(func=check_forex_factory_news, trigger="interval", minutes=1)
scheduler.start()

@app.route('/')
def home():
    return "Bot is running!", 200

@app.route('/test-news')
def test_news():
    check_forex_factory_news()
    return "Done", 200

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
