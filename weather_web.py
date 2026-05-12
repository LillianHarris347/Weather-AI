from flask import Flask, request, render_template_string, jsonify
import requests
import re
from geopy.geocoders import Nominatim
from datetime import datetime, timedelta

app = Flask(__name__)

CREATOR_NAME = "Ваше Имя"
AI_NAME = "WeatherAI"

def get_coords(city):
    geolocator = Nominatim(user_agent="weather_bot_russia", timeout=10)
    try:
        query = f"{city}, Российская Федерация"
        location = geolocator.geocode(query, language='ru')
        if not location:
            location = geolocator.geocode(city, language='ru')
        if location:
            return location.latitude, location.longitude
    except:
        pass
    return None, None

def get_current(lat, lon):
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat, "longitude": lon,
        "current": ["temperature_2m", "relative_humidity_2m", "wind_speed_10m",
                    "weather_code", "apparent_temperature", "pressure_msl",
                    "precipitation", "cloud_cover"],
        "timezone": "auto"
    }
    try:
        r = requests.get(url, params=params, timeout=10)
        data = r.json()
        cur = data["current"]
        return {
            "temp": cur["temperature_2m"],
            "feels": cur["apparent_temperature"],
            "humidity": cur["relative_humidity_2m"],
            "wind": cur["wind_speed_10m"],
            "press": cur["pressure_msl"],
            "precip": cur["precipitation"],
            "clouds": cur["cloud_cover"],
            "code": cur["weather_code"]
        }
    except:
        return None

def get_weekly(lat, lon):
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat, "longitude": lon,
        "daily": ["temperature_2m_max", "temperature_2m_min", "weather_code",
                  "wind_speed_10m_max", "precipitation_sum"],
        "timezone": "auto",
        "forecast_days": 7
    }
    try:
        r = requests.get(url, params=params, timeout=10)
        data = r.json()
        daily = data["daily"]
        days = []
        for i in range(7):
            days.append({
                "date": daily["time"][i],
                "tmax": daily["temperature_2m_max"][i],
                "tmin": daily["temperature_2m_min"][i],
                "code": daily["weather_code"][i],
                "wind": daily["wind_speed_10m_max"][i],
                "precip": daily["precipitation_sum"][i]
            })
        return days
    except:
        return None

def get_hourly_48h(lat, lon):
    """Почасовой прогноз на 48 часов (2 дня)"""
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat, "longitude": lon,
        "hourly": ["temperature_2m", "weather_code", "precipitation", "wind_speed_10m"],
        "timezone": "auto",
        "forecast_days": 2
    }
    try:
        r = requests.get(url, params=params, timeout=10)
        data = r.json()
        hourly = data.get("hourly", {})
        times = hourly.get("time", [])
        temps = hourly.get("temperature_2m", [])
        codes = hourly.get("weather_code", [])
        precip = hourly.get("precipitation", [])
        winds = hourly.get("wind_speed_10m", [])
        
        result = []
        for i in range(len(times)):
            dt = datetime.fromisoformat(times[i])
            now = datetime.now()
            if dt.date() == now.date():
                day_label = "СЕГОДНЯ"
            elif dt.date() == now.date() + timedelta(days=1):
                day_label = "ЗАВТРА"
            else:
                day_label = dt.strftime("%d.%m")
            
            result.append({
                "day": day_label,
                "time": dt.strftime("%H:00"),
                "temp": temps[i] if i < len(temps) else None,
                "code": codes[i] if i < len(codes) else 0,
                "precip": precip[i] if i < len(precip) and precip[i] is not None else 0,
                "wind": winds[i] if i < len(winds) else 0
            })
        return result
    except Exception as e:
        print(f"Hourly error: {e}")
        return None

def code2text(code):
    if code == 0: return "Ясно ☀️"
    if 1 <= code <= 3: return "Малооблачно ⛅"
    if code in (45, 48): return "Туман 🌫️"
    if 51 <= code <= 55: return "Морось 🌦️"
    if 61 <= code <= 65: return "Дождь 🌧️"
    if 66 <= code <= 67: return "Ледяной дождь ❄️🌧️"
    if 71 <= code <= 75: return "Снег 🌨️"
    if 80 <= code <= 82: return "Ливень ☔"
    if 85 <= code <= 86: return "Снегопад ❄️☔"
    if code >= 95: return "Гроза ⛈️"
    return "Облачно 🌥️"

def get_clothing_recommendation(temp, feels, wind, precip, condition_text):
    recommendations = []
    if temp <= -25:
        recommendations.append("🧥 Арктический холод! Пуховик, термобельё, две шапки.")
    elif temp <= -15:
        recommendations.append("🥶 Очень холодно! Пуховик, тёплая шапка, шарф, перчатки.")
    elif temp <= -5:
        recommendations.append("🧣 Холодно. Зимняя куртка, шапка, шарф, перчатки.")
    elif temp <= 0:
        recommendations.append("🧥 Прохладно. Зимняя куртка или плотное пальто, шапка.")
    elif temp <= 5:
        recommendations.append("🧥 Зябко. Демисезонная куртка, шапка, шарф.")
    elif temp <= 10:
        recommendations.append("🧥 Свежо. Лёгкая куртка или ветровка.")
    elif temp <= 15:
        recommendations.append("🧥 Тепло? Кофта + куртка. Шапка не нужна.")
    elif temp <= 20:
        recommendations.append("👕 Тепло. Футболка и джинсы. На вечер — кофта.")
    elif temp <= 25:
        recommendations.append("☀️ Очень тепло! Футболка, шорты, кепка.")
    else:
        recommendations.append("🩳 Жарко! Лёгкая одежда, панама, пей воду.")
    if wind >= 25:
        recommendations.append("💨 Сильный ветер! Ветровка обязательна.")
    elif wind >= 15:
        recommendations.append("🍃 Ветрено. Застегнись.")
    if precip > 5 or "дождь" in condition_text.lower():
        recommendations.append("☔ Осадки — возьми зонт.")
    short = "Очень холодно ❄️" if temp <= 0 else "Прохладно 🧥" if temp <= 10 else "Тепло ☀️" if temp <= 20 else "Жарко 🩳"
    return {"short": short, "full": " • ".join(recommendations) if recommendations else "Одевайся по погоде."}

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=yes">
    <title>{{ ai_name }} — Погода + Почасовой прогноз</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        .container { max-width: 650px; margin: 0 auto; }
        .card { background: white; border-radius: 25px; padding: 24px; margin-bottom: 20px; box-shadow: 0 10px 40px rgba(0,0,0,0.2); }
        h1 { font-size: 24px; text-align: center; margin-bottom: 8px; }
        .subtitle { text-align: center; color: #666; font-size: 14px; margin-bottom: 20px; border-bottom: 1px solid #eee; padding-bottom: 16px; }
        .search-box { display: flex; gap: 12px; margin-bottom: 20px; }
        input { flex: 1; padding: 14px 18px; border: 2px solid #e0e0e0; border-radius: 30px; font-size: 16px; outline: none; }
        input:focus { border-color: #667eea; }
        button { padding: 14px 24px; background: #667eea; color: white; border: none; border-radius: 30px; font-weight: 600; cursor: pointer; transition: transform 0.2s; }
        button:active { transform: scale(0.96); }
        .period-buttons { display: flex; gap: 12px; margin-bottom: 20px; }
        .period-btn { flex: 1; padding: 12px; background: #f0f0f0; color: #666; border: none; border-radius: 30px; font-size: 14px; cursor: pointer; }
        .period-btn.active { background: #667eea; color: white; }
        .weather-card { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; border-radius: 25px; padding: 24px; text-align: center; }
        .temp { font-size: 64px; font-weight: bold; margin: 16px 0; }
        .clothing-card { background: #fff8e7; border-left: 5px solid #ff9800; border-radius: 16px; padding: 16px; margin-top: 20px; text-align: left; }
        .clothing-title { font-weight: bold; font-size: 18px; display: flex; align-items: center; gap: 8px; }
        .day-group { margin-top: 20px; }
        .day-header { font-size: 18px; font-weight: bold; background: rgba(255,255,255,0.25); padding: 8px 12px; border-radius: 30px; display: inline-block; margin-bottom: 12px; }
        .hourly-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(110px,1fr)); gap: 12px; }
        .hour-item { background: rgba(255,255,255,0.15); border-radius: 16px; padding: 10px; text-align: center; backdrop-filter: blur(4px); }
        .hour-time { font-weight: bold; font-size: 15px; margin-bottom: 4px; }
        .hour-temp { font-size: 20px; font-weight: bold; }
        .hour-desc { font-size: 11px; opacity: 0.9; margin-top: 4px; }
        .forecast-item { display: flex; justify-content: space-between; padding: 12px 0; border-bottom: 1px solid #eee; }
        .loader { text-align: center; padding: 40px; display: none; }
        .error { background: #fee; color: #c33; padding: 16px; border-radius: 16px; text-align: center; margin-top: 16px; }
        .spinner { width: 40px; height: 40px; border: 4px solid #e0e0e0; border-top-color: #667eea; border-radius: 50%; animation: spin 0.8s linear infinite; margin: 0 auto; }
        @keyframes spin { to { transform: rotate(360deg); } }
        footer { text-align: center; color: rgba(255,255,255,0.7); font-size: 12px; padding: 20px; }
        .note { font-size: 11px; margin-top: 12px; opacity: 0.7; text-align: center; }
    </style>
</head>
<body>
<div class="container">
    <div class="card">
        <h1>🌤 {{ ai_name }}</h1>
        <div class="subtitle">Погода + одежда + почасовой прогноз на 2 дня</div>
        <div class="search-box">
            <input type="text" id="cityInput" placeholder="Например: Алатырь, Москва" value="Москва">
            <button onclick="getWeather()">🔍</button>
        </div>
        <div class="period-buttons">
            <button class="period-btn" id="todayBtn" onclick="setPeriod('today')">🌡 СЕГОДНЯ</button>
            <button class="period-btn" id="hourlyBtn" onclick="setPeriod('hourly')">⏰ 48 ЧАСОВ</button>
            <button class="period-btn" id="weekBtn" onclick="setPeriod('week')">📅 НЕДЕЛЯ</button>
        </div>
        <div id="loader" class="loader"><div class="spinner"></div><p>Загрузка...</p></div>
        <div id="weatherResult"></div>
    </div>
    <footer>Создатель: {{ creator_name }}<br>Данные: Open-Meteo API</footer>
</div>
<script>
    let currentPeriod = 'today';
    function setPeriod(period) {
        currentPeriod = period;
        document.getElementById('todayBtn').classList.remove('active');
        document.getElementById('hourlyBtn').classList.remove('active');
        document.getElementById('weekBtn').classList.remove('active');
        document.getElementById(period + 'Btn').classList.add('active');
        getWeather();
    }
    async function getWeather() {
        const city = document.getElementById('cityInput').value.trim();
        if (!city) { alert('Введите город'); return; }
        document.getElementById('loader').style.display = 'block';
        document.getElementById('weatherResult').innerHTML = '';
        try {
            const res = await fetch('/weather', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ city: city, period: currentPeriod })
            });
            const data = await res.json();
            if (data.error) {
                document.getElementById('weatherResult').innerHTML = `<div class="error">❌ ${data.error}</div>`;
            } else if (currentPeriod === 'today') {
                displayCurrent(data);
            } else if (currentPeriod === 'hourly') {
                displayHourly(data);
            } else {
                displayWeekly(data);
            }
        } catch(e) {
            document.getElementById('weatherResult').innerHTML = '<div class="error">❌ Ошибка соединения</div>';
        } finally {
            document.getElementById('loader').style.display = 'none';
        }
    }
    function displayCurrent(data) {
        const clothingHtml = data.clothing ? `
            <div class="clothing-card">
                <div class="clothing-title">👗 ${data.clothing.short}</div>
                <div>${data.clothing.full}</div>
            </div>` : '';
        const html = `
            <div class="weather-card">
                <div class="city-name">${data.city}</div>
                <div class="temp">${data.temp}°C</div>
                <div class="feels">Ощущается ${data.feels}°C</div>
                <div style="display:grid; grid-template-columns:1fr 1fr; gap:12px; margin-top:20px;">
                    <div>💧 Влажность ${data.humidity}%</div>
                    <div>💨 Ветер ${data.wind} км/ч</div>
                    <div>☁️ Облачность ${data.clouds}%</div>
                    <div>🌧 Осадки ${data.precip} мм</div>
                    <div>🧭 Давление ${data.pressure} мм</div>
                    <div>${data.condition}</div>
                </div>
            </div>${clothingHtml}`;
        document.getElementById('weatherResult').innerHTML = html;
    }
    function displayHourly(data) {
        let groups = {};
        for (let h of data) {
            const day = h.day;
            if (!groups[day]) groups[day] = [];
            groups[day].push(h);
        }
        let html = `<div class="weather-card"><div style="font-size:18px; margin-bottom:16px;">⏰ ПОЧАСОВОЙ ПРОГНОЗ НА 2 ДНЯ (48 часов)</div>`;
        for (let day in groups) {
            html += `<div class="day-group"><div class="day-header">📅 ${day}</div><div class="hourly-grid">`;
            for (let h of groups[day]) {
                const conditionText = getConditionText(h.code);
                html += `
                    <div class="hour-item">
                        <div class="hour-time">${h.time}</div>
                        <div class="hour-temp">${h.temp}°C</div>
                        <div class="hour-desc">${conditionText}</div>
                        <div class="hour-desc">💨 ${h.wind} км/ч</div>
                        <div class="hour-desc">🌧 ${h.precip} мм</div>
                    </div>`;
            }
            html += `</div></div>`;
        }
        html += `<div class="note">📌 Данные обновляются каждый час. Время — местное.</div></div>`;
        document.getElementById('weatherResult').innerHTML = html;
    }
    function getConditionText(code) {
        if (code === 0) return "Ясно ☀️";
        if (code >= 1 && code <= 3) return "Малооблачно ⛅";
        if (code === 45 || code === 48) return "Туман 🌫️";
        if (code >= 51 && code <= 55) return "Морось 🌦️";
        if (code >= 61 && code <= 65) return "Дождь 🌧️";
        if (code >= 71 && code <= 75) return "Снег 🌨️";
        if (code >= 95) return "Гроза ⛈️";
        return "Облачно 🌥️";
    }
    function displayWeekly(data) {
        let rows = '';
        for (let d of data) {
            rows += `<div class="forecast-item"><span>${d.date}</span><span>${d.tmin}→${d.tmax}°C</span><span>${d.condition}</span><span>💨${d.wind}</span><span>🌧${d.precip}мм</span></div>`;
        }
        document.getElementById('weatherResult').innerHTML = `<div class="weather-card"><div style="font-size:20px;">📅 НЕДЕЛЯ</div>${rows}</div>`;
    }
    window.onload = () => { getWeather(); };
</script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE, ai_name=AI_NAME, creator_name=CREATOR_NAME)

@app.route('/weather', methods=['POST'])
def weather():
    data = request.get_json()
    city = data.get('city', '').strip()
    period = data.get('period', 'today')
    
    if not city:
        return jsonify({'error': 'Введите город'})
    
    lat, lon = get_coords(city)
    if lat is None:
        return jsonify({'error': f'Город "{city}" не найден. Проверьте название.'})
    
    if period == 'today':
        w = get_current(lat, lon)
        if not w:
            return jsonify({'error': 'Не удалось получить текущую погоду'})
        press_mm = round(w['press'] * 0.75006) if w['press'] else 0
        condition = code2text(w['code'])
        clothing = get_clothing_recommendation(w['temp'], w['feels'], w['wind'], w['precip'], condition)
        return jsonify({
            'city': city.title(),
            'temp': w['temp'],
            'feels': w['feels'],
            'humidity': w['humidity'],
            'wind': w['wind'],
            'clouds': w['clouds'],
            'precip': w['precip'],
            'pressure': press_mm,
            'condition': condition,
            'clothing': clothing
        })
    elif period == 'hourly':
        hourly = get_hourly_48h(lat, lon)
        if not hourly or len(hourly) == 0:
            return jsonify({'error': 'Не удалось получить почасовой прогноз'})
        return jsonify(hourly)
    else:  # week
        week = get_weekly(lat, lon)
        if not week:
            return jsonify({'error': 'Не удалось получить прогноз на неделю'})
        ru_days = ["ПН", "ВТ", "СР", "ЧТ", "ПТ", "СБ", "ВС"]
        result = []
        for i, d in enumerate(week):
            dt = datetime.strptime(d['date'], "%Y-%m-%d")
            result.append({
                'date': f"{dt.strftime('%d.%m')} ({ru_days[dt.weekday()]})",
                'tmin': d['tmin'],
                'tmax': d['tmax'],
                'condition': code2text(d['code']),
                'wind': d['wind'],
                'precip': d['precip']
            })
        return jsonify(result)

if __name__ == '__main__':
    print("\n" + "="*60)
    print("🌤 ПОГОДНЫЙ СЕРВЕР ЗАПУЩЕН 🌤")
    print("="*60)
    print("\n📱 Локальный доступ: http://localhost:5000")
    print("🌐 Для доступа с телефона: http://ВАШ_IP:5000")
    print("\n" + "="*60)
    app.run(host='0.0.0.0', port=5000, debug=False)
