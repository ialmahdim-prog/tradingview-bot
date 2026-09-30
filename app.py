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
    "Crude Oil Inventories": "مخزون النفط الأمريكي الخام",
    "Trimmed Mean CPI m/m": "مؤشر أسعار المستهلكين المذبذب (شهري)",
    "German Prelim CPI m/m": "مؤشر أسعار المستهلكين الألماني الأولي (شهري)",
    "ADP Non-Farm Employment Change": "تغير الوظائف غير الزراعية (ADP)",
    "Core PCE Price Index m/m": "مؤشر أسعار نفقات الاستهلاك الشخصي الأساسي (شهري)",
    "Final GDP q/q": "الناتج المحلي الإجمالي النهائي (ربعي)",
    "Import Prices m/m": "أسعار الاستيراد (شهري)",
    "Industrial Production m/m": "الإنتاج الصناعي (شهري)",
    "Unemployment Claims": "طلبات إعانة البطالة",
    "FOMC Member Kashkari Speaks": "خطاب عضوة الفيدرالي كاشكاري",
    "FOMC Member Waller Speaks": "خطاب عضو الفيدرالي والر جولر",
    "SNB Chairman Schlegel Speaks": "خطاب رئيس البنك السويسري شليجل",
    "BOE Gov Bailey Speaks": "خطاب محافظ البنك المركزي البريطاني بيلي"
}

# 💱 دالة استخراج عملة الخبر الحقيقية بدقة من المصدر دون تعميم
def format_currency(curr):
    if not curr:
        return "USD"
    return str(curr).strip().upper()

# 🕒 الدالة الموحدة والمختصرة للوقت (ص / م) بتوقيت السعودية
def format_arabic_time(dt):
    hour = dt.hour
    minute = dt.minute
    period = "ص" if hour < 12 else "م"
    h12 = hour if 1 <= hour <= 12 else (hour - 12 if hour > 12 else 12)
    return f"{h12:02d}:{minute:02d} {period} بتوقيت السعودية"

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

# 1️⃣ استقبال ومعالجة رسائل تريدينج فيو (بالتنسيق المختصر بدون اسم المؤشر المتكرر)
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
        return "OK", 200

    upper_raw = raw_data.upper()

    # 🚫 مانع الإزعاج: فلترة الفريمات الصغرى (1 دقيقة و 5 دقائق)
    if "1M" in upper_raw or "5M" in upper_raw or "دقيقة 1" in upper_raw or "دقيقة 5" in upper_raw:
        if "15M" not in upper_raw and "15 دقيقة" not in upper_raw:
            print("تم تجاهل تنبيه بسبب قدومه من فريم صغير (1m أو 5m).")
            return "Ignored small timeframe", 200

    ticker = "XAUUSD"
    if "EURUSD" in upper_raw: ticker = "EURUSD"
    elif "GBPUSD" in upper_raw: ticker = "GBPUSD"
    elif "BTCUSD" in upper_raw: ticker = "BTCUSD"
    elif "XAUUSD" in upper_raw: ticker = "XAUUSD"

    timeframe = "15m"
    if "30M" in upper_raw or "30 دقيقة" in upper_raw: timeframe = "30m"
    elif "1H" in upper_raw or "ساعة" in upper_raw: timeframe = "1h"
    elif "4H" in upper_raw: timeframe = "4h"
    elif "DAILY" in upper_raw or "يومي" in upper_raw: timeframe = "Daily"

    # 🛑 تحديد الحالة بشكل مختصر ونظيف
    if "سيناريو انعكاس بيعي" in upper_raw or ("انعكاس" in upper_raw and "بيعي" in upper_raw):
        status_text = "🔴 سيناريو انعكاس بيعي (هبوط محتمل)"
    elif "سيناريو انعكاس شرائي" in upper_raw or "سيناريو انعكاس صعودي" in upper_raw or ("انعكاس" in upper_raw and ("شرائي" in upper_raw or "صعودي" in upper_raw)):
        status_text = "🟢 سيناريو انعكاس شرائي (صعود محتمل)"
    elif "متوسطة" in upper_raw or "MEDIUM" in upper_raw or "متوسطة التوافق" in upper_raw:
        status_text = "🔹 فرصة متوسطة التوافق"
    elif "خروج" in upper_raw or "EXIT" in upper_raw:
        status_text = "⚠️ خروج مبكر من الصفقة"
    else:
        status_text = "🚨 تنبيه فني جديد"

    # ⚡ قالب الرسالة المدمج والمختصر (بدون تكرار اسم المؤشر)
    message = f"""⚡ *{ticker}* | ⏳ `{timeframe}`
📌 *الحالة:* {status_text}
💬 *التفاصيل:* {raw_data}"""

    send_to_telegram(message)
    return "OK", 200

# 📅 دالة إرسال ملخص أبرز أخبار اليوم الاقتصادية مع الرمز الصحيح لكل عملة
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
        send_to_telegram("📊 *أبرز أخبار اليوم الاقتصادية*\n▪️▪️▪️▪️▪️▪️▪️▪️▪️\n\nلا توجد أخبار اقتصادية ذات تأثير عالي أو متوسط مسجلة لهذا اليوم.")
        return

    today_events.sort(key=lambda x: x[0])

    message = "📊 *أبرز أخبار اليوم الاقتصادية*\n▪️▪️▪️▪️▪️▪️▪️▪️▪️\n\n"
    for time_ksa, event, formatted_curr in today_events:
        title = translate_news(event.get("title"))
        impact = event.get("impact")
        impact_str = "عالي 🔴" if impact == "High" else "متوسط 🟠"
        time_arabic = format_arabic_time(time_ksa)
        message += f"⏰ `{time_arabic}`\n💱 العملة: `{formatted_curr}`\n📌 الحدث: {title}\n⚠️ التأثير: {impact_str}\n\n"

    send_to_telegram(message)

def parse_float(val):
    if val is None:
        return None
    try:
        val_str = str(val).replace('B', '').replace('M', '').replace('K', '').replace('%', '').strip()
        return float(val_str)
    except:
        return None

def analyze_news_impact(raw_title, actual, forecast):
    act_val = parse_float(actual)
    fore_val = parse_float(forecast)
    
    title_lower = str(raw_title).lower()
    is_inverse = "unemployment" in title_lower or "inventories" in title_lower or "jobless" in title_lower
    
    direction = "محايد ⚪"
    if act_val is not None and fore_val is not None:
        if act_val > fore_val:
            direction = "سلبي 🔴" if is_inverse else "إيجابي 🟢"
        elif act_val < fore_val:
            direction = "إيجابي 🟢" if is_inverse else "سلبي 🔴"

    note = "النتيجة تقيس قوة مؤشرات السوق مقارنة بالتوقعات."
    if "inventories" in title_lower:
        note = "نقص بالمخزون إيجابي، وزيادته سلبية للنفط والأصول المرتبطة."
    elif "employment" in title_lower or "non-farm" in title_lower:
        note = "ارتفاع الوظائف الفعلي فوق التوقعات يعتبر إيجابياً للعملة."
    elif "cpi" in title_lower or "inflation" in title_lower:
        note = "ارتفاع التضخم قد يدفع البنك المركزي لتشديد السياسة النقدية."
    elif "rate" in title_lower:
        note = "قرار الفائدة الفعلي يحدد وجهة وقوة السيولة للعملة."

    return direction, note

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

                    # 1️⃣ تنبيه ما قبل الخبر بـ 15 دقيقة
                    if 10 <= time_difference <= 20 and event_id not in sent_alerts:
                        impact_emoji = "🔴" if impact == "High" else "🟠"
                        news_alert = f"""⏳ *تنبيه اقتصادي هام (قريب جداً)*
▪️▪️▪️▪️▪️▪️▪️️▪️▪️
📊 الحدث: {title}
💱 العملة: `{formatted_curr}`
⚠ الأثر: {impact_emoji} ({impact})
⏰ الوقت: `{time_arabic}`"""
                        
                        msg_id = send_to_telegram(news_alert)
                        if msg_id:
                            sent_alerts[event_id] = {
                                "message_id": msg_id,
                                "result_sent": False
                            }

                    # 2️⃣ متابعة النتيجة لحظياً كل 15 ثانية ضمن النافذة (من -3 إلى 0 دقائق)
                    elif -3 <= time_difference <= 0 and event_id in sent_alerts:
                        alert_data = sent_alerts[event_id]
                        if not alert_data["result_sent"] and actual is not None and str(actual).strip() != "":
                            direction, note = analyze_news_impact(raw_title, actual, forecast)
                            
                            result_message = f"""📊 *صدر الآن :*
▪️▪️▪️▪️▪️▪️▪️▪️▪️
📌 العملة / الأصل: *{formatted_curr}*
📌 الحدث: {title}

▪️ السابق : {previous if previous else 'غير متوفر'}
▪ التقدير : {forecast if forecast else 'غير متوفر'}
▪️ الحالي : *{actual}*

👉 *النتيجة* : {direction} للأصول المرتبطة 🛢️

📦 *ملاحظة* :
{note}"""
                            
                            send_to_telegram(result_message, reply_to_message_id=alert_data["message_id"])
                            alert_data["result_sent"] = True

                except Exception as e:
                    continue
    except Exception as e:
        print("خطأ في فحص ومتابعة الأخبار الاقتصادية:", e)

# ⚡ تشغيل الجدولة بفحص متسارع كل 15 ثانية
scheduler = BackgroundScheduler()
scheduler.add_job(func=check_forex_factory_news, trigger="interval", seconds=15)
scheduler.start()

@app.route('/')
def home():
    return "Bot is running with correct per-event currency mapping!", 200

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
    message = "🚨 صفقة تجريبية ناجحة: XAUUSD شراء"
    result = send_to_telegram(message)
    return f"Test Webhook Sent. Response: {result}", 200

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
