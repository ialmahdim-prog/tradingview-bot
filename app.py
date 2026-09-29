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

# 📖 قاموس ترجمة أسماء الأخبار الاقتصادية الشاملة
NEWS_TRANSLATIONS = {
    "Cash Rate": "سعر الفائدة",
    "RBA Rate Statement": "بيان الفائدة للبنك المركزي الاسترالي",
    "RBA Press Conference": "مؤتمر رئيس البنك المركزي الاسترالي",
    "ECB President Lagarde Speaks": "خطاب رئيسة البنك المركزي الأوروبي (لاغارد)",
    "GDP m/m": "الناتج المحلي الإجمالي (شهري)",
    "GDP q/q": "الناتج المحلي الإجمالي (ربعي)",
    "CB Consumer Confidence": "مؤشر ثقة المستهلك",
    "JOLTS Job Openings": "فرص العمل المتاحة (JOLTS)",
    "Non-Farm Employment Change": "التغير في الوظائف غير الزراعية",
    "Unemployment Rate": "معدل البطالة",
    "CPI m/m": "مؤشر أسعار المستهلكين (شهري)",
    "CPI y/y": "مؤشر أسعار المستهلكين السنوي",
    "Core CPI m/m": "مؤشر أسعار المستهلكين الأساسي (شهري)",
    "FOMC Statement": "بيان الفيدرالي الأمريكي",
    "Federal Funds Rate": "سعر الفائدة الفيدرالي",
    "FOMC Press Conference": "مؤتمر رئيس الفيدرالي الأمريكي",
    "Retail Sales m/m": "مبيعات التجزئة (شهري)",
    "ISM Manufacturing PMI": "مؤشر مديري المشتريات الصناعي (ISM)"
}

def translate_news(title):
    return NEWS_TRANSLATIONS.get(title, title)

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
    """📊 حساب نسبة المخاطرة للعائد تلقائياً"""
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

    today_events.sort(key=lambda x: x[0])

    message = "📊 *أبرز أخبار اليوم الاقتصادية*\n▪️▪️▪️▪️▪️▪️▪️▪️▪️\n"
    for time_ksa, event in today_events:
        title = translate_news(event.get("title"))
        currency = event.get("currency", "USD")
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

        # إرسال الملخص اليومي تلقائياً الساعة 1:00 فجراً
        if now_ksa.hour == 1 and now_ksa.minute == 0 and last_daily_summary_date != today_str:
            send_daily_economic_briefing(events, now_ksa)
            last_daily_summary_date = today_str

        for event in events:
            currency = event.get("currency", "USD")
            impact = event.get("impact")
            raw_title = event.get("title")
            title = translate_news(raw_title)
            date_str = event.get("date")
            actual = event.get("actual")
            forecast = event.get("forecast")
            previous = event.get("previous")

            if impact in ["High", "Medium"]:
                try:
                    event_time_utc = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                    event_time_ksa = event_time_utc.astimezone().replace(tzinfo=None) + timedelta(hours=3)
                    time_difference = (event_time_ksa - now_ksa).total_seconds() / 60
                    event_id = f"{raw_title}_{date_str}"

                    # أ) إرسال تنبيه قبل الخبر بالعربي
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

                    # ب) إرسال النتيجة بالعربي
                    elif 0 <= time_difference <= 15 and event_id in sent_alerts:
                        alert_data = sent_alerts[event_id]
                        if not alert_data["result_sent"] and actual is not None and str(actual).strip() != "":
                            result_message = f"""📊 *نتيجة الخبر الاقتصادي*
▪️▪️▪️▪️▪️▪️▪️▪️▪️
📌 الحدث: {title}
📈 الفعلي (Actual): {actual}
📉 المتوقع (Forecast): {forecast if forecast else 'غير متوفر'}
📌 السابق (Previous): {previous if previous else 'غير متوفر'}"""
                            
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
    return "Bot is running perfectly with clean layout!", 200

@app.route('/test-briefing')
def test_briefing():
    try:
        url = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
        response = requests.get(url)
        if response.status_code == 200:
            now_ksa = datetime.utcnow() + timedelta(hours=3)
            send_daily_economic_briefing(response.json(), now_ksa)
            return "Test briefing executed successfully!", 200
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

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
