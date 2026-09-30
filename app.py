from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask, request
import requests
import json
import os
import re

app = Flask(__name__)

# ⚙️ إعدادات بوت تيليجرام
TELEGRAM_BOT_TOKEN = "8655072721:AAF_-5t5Ld3APrYmvSjwz2M-WAMnFUDBjis"
TELEGRAM_CHANNEL_ID = "-1004363846255"

# مجموعة لتسجيل الأخبار لمنع التكرار
sent_alerts = {} 
last_daily_summary_date = ""

# 📖 قاموس ترجمة أسماء الأخبار الاقتصادية الشاملة والمحدثة
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
    "ISM Manufacturing PMI": "مؤشر مديري المشتريات الصناعي (ISM)",
    "Trimmed Mean CPI m/m": "مؤشر أسعار المستهلكين المذبذب (شهري)",
    "German Prelim CPI m/m": "مؤشر أسعار المستهلكين الألماني الأولي (شهري)",
    "ADP Non-Farm Employment Change": "تغير الوظائف غير الزراعية (ADP)",
    "Core PCE Price Index m/m": "مؤشر أسعار نفقات الاستهلاك الشخصي الأساسي (شهري)",
    "Final GDP q/q": "الناتج المحلي الإجمالي النهائي (ربعي)",
    "Final GDP Price Index q/q": "مؤشر أسعار الناتج المحلي الإجمالي النهائي (ربعي)",
    "Import Prices m/m": "أسعار الاستيراد (شهري)",
    "Prelim German CPI m/m": "مؤشر أسعار المستهلك الألماني الأولي (شهري)",
    "French Consumer Spending m/m": "الإنفاق الاستهلاكي الفرنسي (شهري)",
    "German Unemployment Change": "تغير معدل البطالة في ألمانيا",
    "KOF Economic Barometer": "مؤشر كوف الاقتصادي",
    "Industrial Production m/m": "الإنتاج الصناعي (شهري)",
    "Retail Sales YoY": "مبيعات التجزئة (سنوي)"
}

def format_currency(curr):
    if not curr:
        return "الدولار الأمريكي 🇺🇸"
    curr_upper = str(curr).strip().upper()
    currencies_map = {
        "USD": "الدولار الأمريكي 🇺🇸",
        "EUR": "اليورو الأوروبي 🇪🇺",
        "GBP": "الجنيه الإسترليني 🇬🇧",
        "AUD": "الدولار الأسترالي 🇦🇺",
        "NZD": "الدولار النيوزيلندي 🇳🇿",
        "CAD": "الدولار الكندي 🇨🇦",
        "CHF": "الفرنك السويسري 🇨🇭",
        "JPY": "الين الياباني 🇯🇵",
        "CNY": "اليوان الصيني 🇨🇳"
    }
    return currencies_map.get(curr_upper, f"{curr_upper} 🌐")

def format_arabic_time(dt):
    hour = dt.hour
    minute = dt.minute
    period = "الصباح" if hour < 12 else "المساء"
    h12 = hour if 1 <= hour <= 12 else (hour - 12 if hour > 12 else 12)
    return f"{h12:02d}:{minute:02d} في وقت {period}"

def translate_news(title):
    return NEWS_TRANSLATIONS.get(title, title)

def send_to_telegram(message, reply_to_message_id=None):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHANNEL_ID,
        "text": message,
        "parse_mode": "Markdown",
    }
    if reply_to_message_id:
        payload["reply_to_message_id"] = reply_to_message_id

    try:
        response = requests.post(url, json=payload, timeout=10)
        res_data = response.json()
        if res_data.get("ok"):
            return res_data.get("result", {}).get("message_id")
        return None
    except Exception as e:
        print("خطأ في إرسال الرسالة إلى تيليجرام:", e)
        return None

# 1️⃣ استقبال ومعالجة رسائل تريدينج فيو بطريقة استخراج النصوص والأرقام الذكية
@app.route("/webhook", endpoint="webhook_receiver", methods=["POST"])
def webhook():
    raw_data = ""
    if request.is_json:
        data = request.get_json(silent=True)
        if isinstance(data, dict):
            raw_data = data.get("message", data.get("text", json.dumps(data)))
        else:
            raw_data = str(data)
    elif request.form:
        raw_data = request.form.get("message", request.form.get("text", str(request.form.to_dict())))
    else:
        raw_data = request.data.decode('utf-8', errors='ignore')

    if not raw_data:
        raw_data = "تنبيه عام من المؤشر"

    # استخراج البيانات بذكاء من النص القادم
    ticker = "XAUUSD"
    if "EURUSD" in raw_data.upper(): ticker = "EURUSD"
    elif "GBPUSD" in raw_data.upper(): ticker = "GBPUSD"
    elif "BTCUSD" in raw_data.upper(): ticker = "BTCUSD"
    elif "XAUUSD" in raw_data.upper(): ticker = "XAUUSD"

    # تحديد نوع الرسالة بناءً على محتوى النص الوارد من المنصة
    upper_raw = raw_data.upper()
    
    if "انعكاس" in raw_raw or "REVERSAL" in upper_raw or "بيعي" in raw_raw:
        message = f"""🛑⚠️ *تنبيه انعكاس / سيناريو بيعي* ⚠️🛑
▪️▪️▪️▪️▪️▪️▪️▪️▪️
📊 المؤشر: EA ALPHA VIP
💱 الزوج: {ticker}
⏳ الفريم: 15m
📉 التفاصيل: {raw_data}
💡 انتظر تأكيد الدخول الجديد ⏳"""
    elif "متوسطة" in raw_raw or "MEDIUM" in upper_raw or "متوسطة التوافق" in raw_raw:
        message = f"""🔹📊 *فرصة متوسطة التوافق* 📊🔹
▪️▪️▪️▪️▪️▪️▪️▪️▪️
📊 المؤشر: EA ALPHA VIP
💱 الزوج: {ticker}
⏳ الفريم: 15m
📌 التفاصيل: {raw_data}"""
    elif "خروج" in raw_raw or "EXIT" in upper_raw:
        message = f"""⚠️🚨 *خروج مبكر من الصفقة* 🚨⚠️
▪️▪️▪️️▪️▪️▪️▪️▪️▪️
📊 المؤشر: EA ALPHA VIP
💱 الزوج: {ticker}
⏳ الفريم: 15m
📌 التفاصيل: {raw_data}
💡 تم رصد انعكاس سلبي قبل الأهداف ⏳"""
    else:
        message = f"""🚨 *تنبيه من المؤشر (EA ALPHA VIP)* 🚨
▪️▪️▪️▪️▪️️▪️▪️▪️▪️
💱 الزوج: {ticker}
📌 التفاصيل: {raw_data}"""

    send_to_telegram(message)
    return "OK", 200

# 📅 دالة إرسال ملخص أبرز أخبار اليوم الاقتصادية
def send_daily_economic_briefing(events, now_ksa):
    today_str = now_ksa.strftime('%Y-%m-%d')
    today_events = []
    
    for event in events:
        date_str = event.get("date")
        impact = event.get("impact")
        raw_currency = event.get("currency")
        formatted_curr = format_currency(raw_currency)
        
        if impact in ["High", "Medium"] and date_str:
            try:
                event_time_utc = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                event_time_ksa = event_time_utc.astimezone().replace(tzinfo=None) + timedelta(hours=3)
                
                if event_time_ksa.strftime('%Y-%m-%d') == today_str:
                    today_events.append((event_time_ksa, event, formatted_curr))
            except Exception:
                continue

    if not today_events:
        send_to_telegram("📊 *أبرز أخبار اليوم الاقتصادية*\n▪️▪️▪️▪️▪️️▪️▪️▪️▪️\n\nلا توجد أخبار اقتصادية ذات تأثير عالي أو متوسط مسجلة لهذا اليوم.")
        return

    today_events.sort(key=lambda x: x[0])

    message = "📊 *أبرز أخبار اليوم الاقتصادية*\n▪️▪️▪️▪️▪️▪️▪️▪️▪️\n\n"
    for time_ksa, event, formatted_curr in today_events:
        title = translate_news(event.get("title"))
        impact = event.get("impact")
        impact_str = "عالي 🔴" if impact == "High" else "متوسط 🟠"
        time_arabic = format_arabic_time(time_ksa)
        message += f"⏰ `{time_arabic}`\n💱 العملة: {formatted_curr}\n📌 الحدث: {title}\n⚠️ التأثير: {impact_str}\n\n"

    message += "🕒 *جميع الأوقات بتوقيت المملكة العربية السعودية*"
    send_to_telegram(message)

# 2️⃣ تصفية ومتابعة الأخبار الاقتصادية ونتائجها بدقة تامة
def check_forex_factory_news():
    global last_daily_summary_date
    try:
        url = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code != 200:
            return

        events = response.json()
        now_ksa = datetime.utcnow() + timedelta(hours=3)
        today_str = now_ksa.strftime('%Y-%m-%d')

        if 1 <= now_ksa.hour < 3 and last_daily_summary_date != today_str:
            send_daily_economic_briefing(events, now_ksa)
            last_daily_summary_date = today_str

        for event in events:
            raw_currency = event.get("currency")
            formatted_curr = format_currency(raw_currency)
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
                    time_arabic = format_arabic_time(event_time_ksa)

                    # إرسال التنبيه القبلي
                    if 10 <= time_difference <= 20 and event_id not in sent_alerts:
                        impact_emoji = "🔴" if impact == "High" else "🟠"
                        news_alert = f"""⏳ *تنبيه اقتصادي هام (قريب جداً)*
▪️▪️▪️▪️▪️▪️▪️▪️▪️
📊 الحدث: {title}
💱 العملة: {formatted_curr}
⚠️ الأثر: {impact_emoji} ({impact})
⏰ الوقت: `{time_arabic}` بتوقيت السعودية"""
                        
                        msg_id = send_to_telegram(news_alert)
                        if msg_id:
                            sent_alerts[event_id] = {
                                "message_id": msg_id,
                                "result_sent": False
                            }

                    # إرسال نتيجة الخبر بمجرد صدورها (متابعة لمدة 3 ساعات بعد الحدث لضمان التقاط التحديث)
                    elif -10 <= time_difference <= 180 and event_id in sent_alerts:
                        alert_data = sent_alerts[event_id]
                        if not alert_data["result_sent"] and actual is not None and str(actual).strip() != "":
                            result_message = f"""📊 *نتيجة الخبر الاقتصادي*
▪️▪️▪️▪️▪️️▪️▪️▪️▪️
📌 الحدث: {title}
💱 العملة: {formatted_curr}
📈 الفعلي (Actual): {actual}
📉 المتوقع (Forecast): {forecast if forecast else 'غير متوفر'}
📌 السابق (Previous): {previous if previous else 'غير متوفر'}"""
                            
                            send_to_telegram(result_message, reply_to_message_id=alert_data["message_id"])
                            alert_data["result_sent"] = True

                except Exception as e:
                    continue
    except Exception as e:
        print("خطأ في فحص ومتابعة الأخبار الاقتصادية:", e)

# ⚙️ المجدول الزمني
scheduler = BackgroundScheduler()
scheduler.add_job(func=check_forex_factory_news, trigger="interval", minutes=1)
scheduler.start()

@app.route('/')
def home():
    return "Bot is fully operational with raw alert text parser and extended news listener!", 200

@app.route('/test-briefing')
def test_briefing():
    try:
        url = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code == 200:
            now_ksa = datetime.utcnow() + timedelta(hours=3)
            global last_daily_summary_date
            last_daily_summary_date = "" 
            send_daily_economic_briefing(response.json(), now_ksa)
            return "Test briefing executed successfully!", 200
        else:
            return f"Failed to fetch from external source, status code: {response.status_code}", 500
    except Exception as e:
        return f"Error: {str(e)}", 500

@app.route('/test-webhook')
def test_webhook():
    message = "🚨 صفقة تجريبية ناجحة: XAUUSD شراء من السعر 2350.00"
    result = send_to_telegram(message)
    return f"Test Webhook Sent. Response: {result}", 200

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
