from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask, request
import requests
import json
import os

app = Flask(__name__)

# ⚙️ إعدادات بوت تيليجرام
TELEGRAM_BOT_TOKEN = "8655072721:AAF_-5t5Ld3APrYmvSjwz2M-WAMnFUDBjis"
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

def calculate_risk_reward(action, entry, sl, tp):
    """📊 حساب نسبة المخاطرة إلى العائد تلقائياً"""
    try:
        entry_f = float(entry)
        sl_f = float(sl)
        tp_f = float(tp)
        
        if action.lower() in ["شراء", "buy"]:
            risk = abs(entry_f - sl_f)
            reward = abs(tp_f - entry_f)
        else:
            risk = abs(sl_f - entry_f)
            reward = abs(entry_f - tp_f)
            
        if risk > 0:
            ratio = round(reward / risk, 1)
            return f"1:{ratio}"
    except Exception:
        pass
    return "غير محدد"

# 1️⃣ استقبال وتصنيف إشارات تريدينج فيو (Webhook)
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
        print("⚠️ تنبيه: لم يتم استلام بيانات صحيحة من تريدينج فيو.")
        return "Invalid Data", 400

    signal_type = data.get("type", "VIP").upper()
    ticker = data.get("ticker", "XAUUSD")
    interval = data.get("interval", "15m")
    action = data.get("action", "شراء")
    close_price = data.get("close", "0.0")
    sl = data.get("sl", "0.0")
    tp1 = data.get("tp1", "0.0")
    tp2 = data.get("tp2", "يُحدد هنا")
    tp3 = data.get("tp3", "يُحدد هنا")

    rr_ratio = calculate_risk_reward(action, close_price, sl, tp1)

    # 🚨 التصنيف الأول: صفقات VIP الرئيسية
    if signal_type == "VIP":
        message = f"""🚨🔥 [صفقة VIP رئيسية] 🔥🚨
━━━━━━━━━━━━━━━━━
📊 المؤشر: EA ALPHA VIP
💱 الزوج: {ticker}
⏳ الفريم: {interval}
🎯 الاتجاه: {action}
💰 الدخول: {close_price}
🛑 وقف الخسارة: {sl}
🎯 الهدف الأول: {tp1}
🎯 الهدف الثاني: {tp2}
🎯 الهدف الثالث: {tp3}
⚖️ نسبة المخاطرة للعائد: {rr_ratio}
━━━━━━━━━━━━━━━━━"""

    # ⭐ التصنيف الثاني: فرصة عالية
    elif signal_type == "HIGH":
        message = f"""⭐⚡ [فرصة عالية] ⚡⭐
━━━━━━━━━━━━━━━━━
📊 المؤشر: EA ALPHA VIP
💱 الزوج: {ticker}
⏳ الفريم: {interval}
🎯 الاتجاه: {action}
💰 الدخول: {close_price}
🛑 وقف الخسارة: {sl}
🎯 الهدف الأول: {tp1}
🎯 الهدف الثاني: {tp2}
⚖️ نسبة المخاطرة للعائد: {rr_ratio}
━━━━━━━━━━━━━━━━━"""

    # 🔹 التصنيف الثالث: فرصة متوسطة
    elif signal_type == "MEDIUM":
        message = f"""🔹📊 [فرصة متوسطة] 📊🔹
━━━━━━━━━━━━━━━━━
📊 المؤشر: EA ALPHA VIP
💱 الزوج: {ticker}
⏳ الفريم: {interval}
🎯 الاتجاه: {action}
💰 الدخول: {close_price}
🛑 وقف الخسارة: {sl}
🎯 الهدف الأول: {tp1}
⚖️ نسبة المخاطرة للعائد: {rr_ratio}
━━━━━━━━━━━━━━━━━"""

    # 🛑 تنبيهات الانعكاس أو الخروج
    elif signal_type == "REVERSAL":
        message = f"""🛑⚠️ [تنبيه انعكاس / خروج مبكر] ⚠️🛑
━━━━━━━━━━━━━━━━━
📊 المؤشر: EA ALPHA VIP
💱 الزوج: {ticker}
⏳ الفريم: {interval}
📉 الحالة: {action}
💰 سعر الإغلاق: {close_price}
💡 انتظر دخول جديد ⏳
━━━━━━━━━━━━━━━━━"""

    # 📂 التصنيف الافتراضي
    else:
        message = f"""📈 [إشارة تداول عامة] 📈
━━━━━━━━━━━━━━━━━
📊 المؤشر: EA ALPHA VIP
💱 الزوج: {ticker}
⏳ الفريم: {interval}
🎯 الاتجاه: {action}
💰 السعر: {close_price}
━━━━━━━━━━━━━━━━━"""

    send_to_telegram(message)
    return "OK", 200

# 2️⃣ تصفية وإرسال الأخبار الاقتصادية
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

                    if 10 <= time_difference <= 15 and event_id not in sent_alerts:
                        impact_emoji = "🔴" if impact == "High" else "🟠"
                        news_alert = f"""⏳ **تنبيه اقتصادي هام (قريب جداً)**
━━━━━━━━━━━━━━━━━
📊 الحدث: {title}
💱 العملة / الأثر: {currency} {impact_emoji} ({impact})
⏰ الوقت: {event_time_ksa.strftime('%I:%M %p')} (بتوقيت السعودية)
━━━━━━━━━━━━━━━━━"""
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
    return "News check executed successfully!", 200

@app.route('/test-webhook')
def test_webhook():
    rr = calculate_risk_reward("شراء", "2350.00", "2340.00", "2360.00")
    message = f"""🚨🔥 [صفقة VIP رئيسية] 🔥🚨
━━━━━━━━━━━━━━━━━
📊 المؤشر: EA ALPHA VIP
💱 الزوج: XAUUSD
⏳ الفريم: 15m
🎯 الاتجاه: شراء
💰 الدخول: 2350.00
🛑 وقف الخسارة: 2340.00
🎯 الهدف الأول: 2360.00
🎯 الهدف الثاني: 2370.00
🎯 الهدف الثالث: 2380.00
⚖️ نسبة المخاطرة للعائد: {rr}
━━━━━━━━━━━━━━━━━"""
    result = send_to_telegram(message)
    return f"Test Webhook Sent. Response: {result}", 200

@app.route('/test-high')
def test_high():
    rr = calculate_risk_reward("بيع", "1.0920", "1.0950", "1.0890")
    message = f"""⭐⚡ [فرصة عالية] ⚡⭐
━━━━━━━━━━━━━━━━━
📊 المؤشر: EA ALPHA VIP
💱 الزوج: EURUSD
⏳ الفريم: 30m
🎯 الاتجاه: بيع
💰 الدخول: 1.0920
🛑 وقف الخسارة: 1.0950
🎯 الهدف الأول: 1.0890
🎯 الهدف الثاني: 1.0860
⚖️ نسبة المخاطرة للعائد: {rr}
━━━━━━━━━━━━━━━━━"""
    result = send_to_telegram(message)
    return f"Test High Webhook Sent. Response: {result}", 200

@app.route('/test-medium')
def test_medium():
    rr = calculate_risk_reward("شراء", "1.3100", "1.3070", "1.3140")
    message = f"""🔹📊 [فرصة متوسطة] 📊🔹
━━━━━━━━━━━━━━━━━
📊 المؤشر: EA ALPHA VIP
💱 الزوج: GBPUSD
⏳ الفريم: 15m
🎯 الاتجاه: شراء
💰 الدخول: 1.3100
🛑 وقف الخسارة: 1.3070
🎯 الهدف الأول: 1.3140
⚖️ نسبة المخاطرة للعائد: {rr}
━━━━━━━━━━━━━━━━━"""
    result = send_to_telegram(message)
    return f"Test Medium Webhook Sent. Response: {result}", 200

@app.route('/test-news-format')
def test_news_format():
    try:
        currency = "USD"
        impact = "High"
        title = "معدل البطالة الأمريكي (تجريبي)"
        impact_emoji = "🔴"
        
        news_alert = f"""⏳ **تنبيه اقتصادي هام (اختبار الشكل)**
━━━━━━━━━━━━━━━━━
📊 الحدث: {title}
💱 العملة / الأثر: {currency} {impact_emoji} ({impact})
⏰ الوقت: تجريبي (يعمل بشكل صحيح)
━━━━━━━━━━━━━━━━━"""
        
        result = send_to_telegram(news_alert)
        return f"News format test sent! Response: {result}", 200
    except Exception as e:
        return f"Error: {e}", 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
