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
sent_alerts = {} 
last_daily_summary_date = ""

def send_to_telegram(message, reply_to_message_id=None):
    """🤖 دالة إرسال الرسائل إلى قناة تيليجرام مع دعم الرد المباشر"""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHANNEL_ID,
        "text": message,
        "parse_mode": "Markdown",
    }
    if reply_to_message_id:
        payload["reply_to_message_id"] = reply_to_message_id

    try:
        response = requests.post(url, json=payload)
        res_data = response.json()
        if res_data.get("ok"):
            return res_data.get("result", {}).get("message_id")
        return None
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

    if signal_type == "VIP":
        message = f"""🚨🔥 *صفقة VIP رئيسية* 🔥🚨
▪️▪️▪️▪️▪️▪️▪️▪️▪️
📊 المؤشر: EA ALPHA VIP
💱 الزوج: {ticker}
⏳ الفريم: {interval}
🎯 الاتجاه: {action}
💰 الدخول: {close_price}
🛑 وقف الخسارة: {sl}
🎯 الهدف الأول: {tp1}
🎯 الهدف الثاني: {tp2}
🎯 الهدف الثالث: {tp3}
⚖️ نسبة المخاطرة للعائد: {rr_ratio}"""
    elif signal_type == "HIGH":
        message = f"""⭐⚡ *فرصة عالية* ⚡⭐
▪️▪️▪️▪️▪️▪️▪️▪️▪️
📊 المؤشر: EA ALPHA VIP
💱 الزوج: {ticker}
⏳ الفريم: {interval}
🎯 الاتجاه: {action}
💰 الدخول: {close_price}
🛑 وقف الخسارة: {sl}
🎯 الهدف الأول: {tp1}
🎯 الهدف الثاني: {tp2}
⚖️ نسبة المخاطرة للعائد: {rr_ratio}"""
    elif signal_type == "MEDIUM":
        message = f"""🔹📊 *فرصة متوسطة* 📊🔹
▪️▪️▪️▪️▪️▪️▪️▪️▪️
📊 المؤشر: EA ALPHA VIP
💱 الزوج: {ticker}
⏳ الفريم: {interval}
🎯 الاتجاه: {action}
💰 الدخول: {close_price}
🛑 وقف الخسارة: {sl}
🎯 الهدف الأول: {tp1}
⚖️ نسبة المخاطرة للعائد: {rr_ratio}"""
    elif signal_type == "REVERSAL":
        message = f"""🛑⚠️ *تنبيه انعكاس / خروج مبكر* ⚠️🛑
▪️▪️▪️▪️▪️▪️▪️▪️▪️
📊 المؤشر: EA ALPHA VIP
💱 الزوج: {ticker}
⏳ الفريم: {interval}
📉 الحالة: {action}
💰 سعر الإغلاق: {close_price}
💡 انتظر دخول جديد ⏳"""
    elif signal_type == "REINFORCEMENT":
        message = f"""📦⚡ *منطقة تجميع وسيولة نشطة* ⚡📦
▪️▪️▪️▪️▪️▪️▪️▪️▪️
📊 المؤشر: EA ALPHA VIP
💱 الزوج: {ticker}
⏳ الفريم: {interval}
🎯 الحالة: {action}
💰 نطاق السعر: {close_price}
🎯 الهدف المقترح: +30 إلى +60 نقطة 🎯
💡 فرصة مضاربة سريعة مستقلة ⏳"""
    else:
        message = f"""📈 *إشارة تداول عامة* 📈
▪️▪️▪️▪️▪️▪️▪️▪️▪️
📊 المؤشر: EA ALPHA VIP
💱 الزوج: {ticker}
⏳ الفريم: {interval}
🎯 الاتجاه: {action}
💰 السعر: {close_price}"""

    send_to_telegram(message)
    return "OK", 200

# 📅 دالة إرسال ملخص أبرز أخبار اليوم الاقتصادية
def send_daily_economic_briefing(events, now_ksa):
    today_str = now_ksa.strftime('%Y-%m-%d')
    today_events = []
    
    for event in events:
        date_str = event.get("date")
        impact = event.get("impact")
        if impact in ["High", "Medium"] and date_str:
            try:
                event_time_utc = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                event_time_ksa = event_time_utc.astimezone().replace(tzinfo=None) + timedelta(hours=3)
                if event_time_ksa.strftime('%Y-%m-%d') == today_str:
                    today_events.append((event_time_ksa, event))
            except Exception:
                continue

    if not today_events:
        return

    # ترتيب الأخبار تصاعدياً حسب الوقت
    today_events.sort(key=lambda x: x[0])

    message = "📊 *أبرز أخبار اليوم الاقتصادية*\n▪️▪️▪️▪️▪️▪️▪️▪️▪️\n"
    for time_ksa, event in today_events:
        title = event.get("title")
        currency = event.get("currency")
        impact = event.get("impact")
        impact_str = "عالي 🔴" if impact == "High" else "متوسط 🟠"
        message += f"⏰ {time_ksa.strftime('%I:%M %p')} | {currency} - {title} ({impact_str})\n"

    send_to_telegram(message)

# 2️⃣ تصفية ومتابعة الأخبار الاقتصادية ونتائجها
def check_forex_factory_news():
    global last_daily_summary_date
    try:
        url = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
        response = requests.get(url)
        if response.status_code != 200:
            return

        events = response.json()
        now_ksa = datetime.utcnow() + timedelta(hours=3)
        today_str = now_ksa.strftime('%Y-%m-%d')

        # إرسال الملخص اليومي تلقائياً الساعة 1:00 فجراً بتوقيت السعودية (مع بداية اليوم الجديد)
        if now_ksa.hour == 1 and now_ksa.minute == 0 and last_daily_summary_date != today_str:
            send_daily_economic_briefing(events, now_ksa)
            last_daily_summary_date = today_str

        for event in events:
            currency = event.get("currency")
            impact = event.get("impact")
            title = event.get("title")
            date_str = event.get("date")
            actual = event.get("actual")
            forecast = event.get("forecast")
            previous = event.get("previous")

            if impact in ["High", "Medium"]:
                try:
                    event_time_utc = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                    event_time_ksa = event_time_utc.astimezone().replace(tzinfo=None) + timedelta(hours=3)
                    time_difference = (event_time_ksa - now_ksa).total_seconds() / 60
                    event_id = f"{title}_{date_str}"

                    # أ) إرسال تنبيه قبل الخبر (بين 10 إلى 20 دقيقة)
                    if 10 <= time_difference <= 20 and event_id not in sent_alerts:
                        impact_emoji = "🔴" if impact == "High" else "🟠"
                        news_alert = f"""⏳ *تنبيه اقتصادي هام (قريب جداً)*
▪️▪️▪️▪️▪️▪️▪️▪️▪️
📊 الحدث: {title}
💱 العملة / الأثر: {currency} {impact_emoji} ({impact})
⏰ الوقت: {event_time_ksa.strftime('%I:%M %p')} (بتوقيت السعودية)"""
                        
                        msg_id = send_to_telegram(news_alert)
                        if msg_id:
                            sent_alerts[event_id] = {
                                "message_id": msg_id,
                                "result_sent": False
                            }

                    # ب) إرسال النتيجة (متابعة بعد صدور الخبر بـ 0 إلى 15 دقيقة لضمان التقاط التحديث)
                    elif 0 <= time_difference <= 15 and event_id in sent_alerts:
                        alert_data = sent_alerts[event_id]
                        if not alert_data["result_sent"] and actual is not None and str(actual).strip() != "":
                            result_message = f"""📊 *نتيجة الخبر الاقتصادي*
▪️▪️▪️▪️▪️▪️▪️▪️▪️
📌 الحدث: {title}
📈 الفعلي (Actual): {actual}
📉 المتوقع (Forecast): {forecast if forecast else 'غير متوفر'}
هـ. السابق (Previous): {previous if previous else 'غير متوفر'}"""
                            
                            send_to_telegram(result_message, reply_to_message_id=alert_data["message_id"])
                            alert_data["result_sent"] = True

                except Exception:
                    continue
    except Exception as e:
        print("خطأ في فحص ومتابعة الأخبار الاقتصادية:", e)

# ⚙️ المجدول الزمني
scheduler = BackgroundScheduler()
scheduler.add_job(func=check_forex_factory_news, trigger="interval", minutes=1)
scheduler.start()

@app.route('/')
def home():
    return "Bot is running with 1 AM Daily Briefing!", 200

@app.route('/test-news')
def test_news():
    check_forex_factory_news()
    return "News check executed successfully!", 200

@app.route('/test-briefing')
def test_briefing():
    try:
        url = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
        response = requests.get(url)
        if response.status_code == 200:
            now_ksa = datetime.utcnow() + timedelta(hours=3)
            send_daily_economic_briefing(response.json(), now_ksa)
            return "Daily briefing test executed and sent to Telegram successfully!", 200
    except Exception as e:
        return f"Error: {str(e)}", 500
    return "Failed to fetch briefing", 500

@app.route('/test-webhook')
def test_webhook():
    rr = calculate_risk_reward("شراء", "2350.00", "2340.00", "2360.00")
    message = f"""🚨🔥 *صفقة VIP رئيسية* 🔥🚨
▪️▪️▪️▪️▪️▪️▪️▪️▪️
📊 المؤشر: EA ALPHA VIP
💱 الزوج: XAUUSD
⏳ الفريم: 15m
🎯 الاتجاه: شراء
💰 الدخول: 2350.00
🛑 وقف الخسارة: 2340.00
🎯 الهدف الأول: 2360.00
🎯 الهدف الثاني: 2370.00
🎯 الهدف الثالث: 2380.00
⚖️ نسبة المخاطرة للعائد: {rr}"""
    result = send_to_telegram(message)
    return f"Test Webhook Sent. Response: {result}", 200

@app.route('/test-high')
def test_high():
    rr = calculate_risk_reward("بيع", "1.0920", "1.0950", "1.0890")
    message = f"""⭐⚡ *فرصة عالية* ⚡⭐
▪️▪️▪️▪️▪️▪️▪️▪️▪️
📊 المؤشر: EA ALPHA VIP
💱 الزوج: EURUSD
⏳ الفريم: 30m
🎯 الاتجاه: بيع
💰 الدخول: 1.0920
🛑 وقف الخسارة: 1.0950
🎯 الهدف الأول: 1.0890
🎯 الهدف الثاني: 1.0860
⚖️ نسبة المخاطرة للعائد: {rr}"""
    result = send_to_telegram(message)
    return f"Test High Webhook Sent. Response: {result}", 200

@app.route('/test-medium')
def test_medium():
    rr = calculate_risk_reward("شراء", "1.3100", "1.3070", "1.3140")
    message = f"""🔹📊 *فرصة متوسطة* 📊🔹
▪️▪️▪️▪️▪️▪️▪️▪️▪️
📊 المؤشر: EA ALPHA VIP
💱 الزوج: GBPUSD
⏳ الفريم: 15m
🎯 الاتجاه: شراء
💰 الدخول: 1.3100
🛑 وقف الخسارة: 1.3070
🎯 الهدف الأول: 1.3140
⚖️ نسبة المخاطرة للعائد: {rr}"""
    result = send_to_telegram(message)
    return f"Test Medium Webhook Sent. Response: {result}", 200

@app.route('/test-reinforcement')
def test_reinforcement():
    message = f"""📦⚡ *منطقة تجميع وسيولة نشطة* ⚡📦
▪️▪️▪️▪️▪️▪️▪️▪️▪️
📊 المؤشر: EA ALPHA VIP
💱 الزوج: XAUUSD
⏳ الفريم: 15m
🎯 الحالة: 🟢 شراء تعزيزي وتجميع
💰 نطاق السعر: 4280.00 - 4285.00
🎯 الهدف المقترح: +30 إلى +60 نقطة 🎯
💡 فرصة مضاربة سريعة مستقلة ⏳"""
    result = send_to_telegram(message)
    return f"Test Reinforcement Sent. Response: {result}", 200

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
