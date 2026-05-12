from flask import Flask, request, render_template_string, jsonify
import requests
import re
from geopy.geocoders import Nominatim
from datetime import datetime, timedelta

app = Flask(__name__)

CREATOR_NAME = "Соловьев Дмитрий Владимирович"
AI_NAME = "WeatherAI"

def get_coords(city):
    """Поиск координат города (работает со всеми городами РФ)"""
    geolocator = Nominatim(user_agent="weather_bot_russia_48h", timeout=15)
    try:
        # Сначала ищем с уточнением "Россия"
        query = f"{city}, Россия"
        location = geolocator.geocode(query, language='ru')
        if not location:
            # Если не нашли, пробуем без уточнения
            location = geolocator.geocode(city, language='ru')
        if location:
            print(f"✅ Найден город: {city} → {location.latitude}, {location.longitude}")
            return location.latitude, location.longitude
        else:
            print(f"❌ Город {city} не найден")
            return None, None
    except Exception as e:
        print(f"⚠️ Ошибка геокодинга: {e}")
        return None, None

def get_current_weather(lat, lon):
    """ТОЧНАЯ текущая погода (на момент запроса)"""
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "current": [
            "temperature_2m",
            "relative_humidity_2m",
            "wind_speed_10m",
            "weather_code",
            "apparent_temperature",
            "pressure_msl",
            "precipitation",
            "cloud_cover"
        ],
        "timezone": "auto"
    }
    try:
        response = requests.get(url, params=params, timeout=15)
        response.raise_for_status()
        data = response.json()
        current = data.get("current", {})
        
        weather_data = {
            "temp": current.get("temperature_2m"),
            "feels": current.get("apparent_temperature"),
            "humidity": current.get("relative_humidity_2m"),
            "wind": current.get("wind_speed_10m"),
            "pressure": current.get("pressure_msl"),
            "precipitation": current.get("precipitation"),
            "clouds": current.get("cloud_cover"),
            "code": current.get("weather_code", 0)
        }
        print(f"✅ Текущая погода получена: {weather_data['temp']}°C")
        return weather_data
    except Exception as e:
        print(f"⚠️ Ошибка текущей погоды: {e}")
        return None

def get_weekly_forecast(lat, lon):
    """Прогноз на 7 дней"""
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "daily": [
            "temperature_2m_max",
            "temperature_2m_min",
            "weather_code",
            "wind_speed_10m_max",
            "precipitation_sum"
        ],
        "timezone": "auto",
        "forecast_days": 7
    }
    try:
        response = requests.get(url, params=params, timeout=15)
        response.raise_for_status()
        data = response.json()
        daily = data.get("daily", {})
        
        forecast = []
        for i in range(7):
            forecast.append({
                "date": daily["time"][i],
                "tmax": daily["temperature_2m_max"][i],
                "tmin": daily["temperature_2m_min"][i],
                "code": daily["weather_code"][i],
                "wind": daily["wind_speed_10m_max"][i],
                "precip": daily["precipitation_sum"][i]
            })
        print(f"✅ Прогноз на неделю получен")
        return forecast
    except Exception as e:
        print(f"⚠️ Ошибка недельного прогноза: {e}")
        return None

def get_hourly_forecast_48h(lat, lon):
    """ТОЧНЫЙ почасовой прогноз на 48 часов (2 дня)"""
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": ["temperature_2m", "weather_code", "precipitation", "wind_speed_10m"],
        "timezone": "auto",
        "forecast_days": 2
    }
    try:
        response = requests.get(url, params=params, timeout=15)
        response.raise_for_status()
        data = response.json()
        hourly = data.get("hourly", {})
        
        times = hourly.get("time", [])
        temps = hourly.get("temperature_2m", [])
        codes = hourly.get("weather_code", [])
        precip = hourly.get("precipitation", [])
        winds = hourly.get("wind_speed_10m", [])
        
        result = []
        now_date = datetime.now().date()
        
        for i in range(min(48, len(times))):
            dt = datetime.fromisoformat(times[i])
            day_label = "" if dt.date() == now_date else " (завтра)"
            
            result.append({
                "time": f"{dt.strftime('%H:00')}{day_label}",
                "datetime": dt.strftime("%d.%m %H:00"),
                "temp": round(temps[i], 1),
                "code": codes[i],
                "precip": round(precip[i], 1) if precip[i] else 0,
                "wind": round(winds[i], 1)
            })
        
        print(f"✅ Почасовой прогноз на {len(result)} часов")
        return result
    except Exception as e:
        print(f"⚠️ Ошибка почасового прогноза: {e}")
        return None

def code_to_text(code):
    """Код погоды в человекочитаемый текст"""
    weather_codes = {
        0: "Ясно ☀️",
        1: "В основном ясно 🌤️",
        2: "Переменная облачность ⛅",
        3: "Пасмурно ☁️",
        45: "Туман 🌫️",
        48: "Туман с изморозью 🌫️",
        51: "Лёгкая морось 🌦️",
        53: "Умеренная морось 🌦️",
        55: "Сильная морось 🌧️",
        56: "Ледяная морось ❄️",
        57: "Сильная ледяная морось ❄️",
        61: "Лёгкий дождь 🌧️",
        63: "Умеренный дождь 🌧️",
        65: "Сильный дождь ☔",
        66: "Ледяной дождь ❄️🌧️",
        67: "Сильный ледяной дождь ❄️☔",
        71: "Лёгкий снег 🌨️",
        73: "Умеренный снег 🌨️",
        75: "Сильный снег ❄️",
        77: "Снежные зёрна ❄️",
        80: "Лёгкий ливень ☔",
        81: "Умеренный ливень ☔",
        82: "Сильный ливень ⛈️",
        85: "Лёгкий снегопад ❄️",
        86: "Сильный снегопад 🌨️",
        95: "Гроза ⛈️",
        96: "Гроза с градом ⛈️🌨️",
        99: "Сильная гроза ⛈️"
    }
    return weather_codes.get(code, "Неизвестно")

def get_clothing_recommendation(temp, feels, wind, precip, condition_text):
    """Рекомендации по одежде на основе погоды"""
    recommendations = []
    
    # Температурные рекомендации
    if temp <= -25:
        recommendations.append("🧥 Арктический холод! Пуховик, термобельё, две шапки, шарф, варежки")
    elif temp <= -15:
        recommendations.append("🥶 Очень холодно! Пуховик, тёплая шапка, шарф, перчатки, тёплая обувь")
    elif temp <= -5:
        recommendations.append("🧣 Холодно. Зимняя куртка, шапка, шарф, перчатки")
    elif temp <= 0:
        recommendations.append("🧥 Прохладно. Зимняя куртка или плотное пальто, шапка, шарф")
    elif temp <= 5:
        recommendations.append("🧥 Зябко. Демисезонная куртка, шапка, шарф")
    elif temp <= 10:
        recommendations.append("🧥 Свежо. Лёгкая куртка или ветровка, шапка не нужна")
    elif temp <= 15:
        recommendations.append("🧥 Тепло? Кофта + куртка. Шапка не нужна")
    elif temp <= 20:
        recommendations.append("👕 Тепло. Футболка и джинсы. На вечер — кофта")
    elif temp <= 25:
        recommendations.append("☀️ Очень тепло! Футболка, шорты/лёгкие брюки, кепка")
    else:
        recommendations.append("🩳 Жарко! Лёгкая одежда, шорты, панама, пей воду")
    
    # Ветер
    if wind >= 25:
        recommendations.append("💨 Сильный ветер! Ветровка обязательно, застегнись")
    elif wind >= 15:
        recommendations.append("🍃 Ветрено. Накинь ветровку или застегнись")
    
    # Осадки
    if precip > 5 or "дождь" in condition_text.lower():
        recommendations.append("☔ Возьми зонт, обувь по погоде")
    elif "снег" in condition_text.lower():
        recommendations.append("❄️ Идёт снег. Одевайся теплее")
    
    # Короткий вердикт
    if temp <= 0:
        short = "Очень холодно ❄️"
    elif temp <= 10:
        short = "Прохладно 🧥"
    elif temp <= 20:
        short = "Тепло ☀️"
    else:
        short = "Жарко 🩳"
    
    full_text = " • ".join(recommendations) if recommendations else "Одевайся по погоде"
    return {"short": short, "full": full_text}

# HTML шаблон с анимированным фоном
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=yes">
    <title>{{ ai_name }} — Точный прогноз + 48 часов</title>
    <script src="https://cdn.jsdelivr.net/npm/qrcodejs@1.0.0/qrcode.min.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
            min-height: 100vh;
            padding: 20px;
            background: linear-gradient(135deg, #1a2a6c, #b21f1f, #fdbb4d);
            background-size: 400% 400%;
            animation: gradientShift 12s ease infinite;
        }
        @keyframes gradientShift {
            0% { background-position: 0% 50%; }
            50% { background-position: 100% 50%; }
            100% { background-position: 0% 50%; }
        }
        .container { max-width: 650px; margin: 0 auto; }
        .card { background: rgba(255,255,255,0.95); border-radius: 25px; padding: 24px; margin-bottom: 20px; box-shadow: 0 10px 40px rgba(0,0,0,0.2); backdrop-filter: blur(2px); }
        h1 { font-size: 24px; text-align: center; margin-bottom: 8px; }
        .subtitle { text-align: center; color: #666; font-size: 14px; margin-bottom: 20px; border-bottom: 1px solid #eee; padding-bottom: 16px; }
        .search-box { display: flex; gap: 12px; margin-bottom: 20px; }
        input { flex: 1; padding: 14px 18px; border: 2px solid #e0e0e0; border-radius: 30px; font-size: 16px; outline: none; }
        input:focus { border-color: #667eea; }
        button { padding: 14px 24px; background: #667eea; color: white; border: none; border-radius: 30px; font-weight: 600; cursor: pointer; transition: transform 0.2s; }
        button:active { transform: scale(0.96); }
        .period-buttons { display: flex; gap: 12px; margin-bottom: 20px; flex-wrap: wrap; }
        .period-btn { flex: 1; padding: 12px; background: #f0f0f0; color: #666; border: none; border-radius: 30px; font-size: 14px; cursor: pointer; transition: all 0.2s; }
        .period-btn.active { background: #667eea; color: white; }
        .share-btn { background: #4caf50; margin-bottom: 20px; width: 100%; }
        .qr-container { text-align: center; margin-top: 20px; padding: 16px; background: #f9f9f9; border-radius: 20px; display: none; }
        .qr-container.show { display: block; }
        .qr-instruction { font-size: 14px; color: #555; margin-bottom: 16px; }
        .weather-card { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; border-radius: 25px; padding: 24px; text-align: center; }
        .city-name { font-size: 28px; font-weight: bold; margin-bottom: 8px; }
        .temp { font-size: 64px; font-weight: bold; margin: 16px 0; }
        .feels { font-size: 16px; opacity: 0.9; }
        .weather-details { display: grid; grid-template-columns: repeat(2, 1fr); gap: 16px; margin-top: 24px; padding-top: 16px; border-top: 1px solid rgba(255,255,255,0.3); }
        .detail { text-align: center; }
        .detail-value { font-size: 20px; font-weight: bold; }
        .detail-label { font-size: 12px; opacity: 0.8; margin-top: 4px; }
        .clothing-card { background: #fff8e7; border-left: 5px solid #ff9800; border-radius: 16px; padding: 16px; margin-top: 20px; text-align: left; }
        .clothing-title { font-weight: bold; font-size: 18px; display: flex; align-items: center; gap: 8px; margin-bottom: 8px; }
        .hourly-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(130px,1fr)); gap: 12px; margin-top: 20px; max-height: 600px; overflow-y: auto; padding: 4px; }
        .hour-item { background: rgba(255,255,255,0.2); border-radius: 16px; padding: 12px; text-align: center; backdrop-filter: blur(4px); transition: transform 0.2s; }
        .hour-item:hover { transform: scale(1.02); }
        .hour-time { font-weight: bold; font-size: 14px; margin-bottom: 6px; }
        .hour-temp { font-size: 22px; font-weight: bold; margin: 6px 0; }
        .hour-desc { font-size: 12px; opacity: 0.9; margin: 4px 0; }
        .forecast-item { display: flex; justify-content: space-between; align-items: center; padding: 12px 0; border-bottom: 1px solid #eee; }
        .forecast-item span:first-child { width: 85px; font-weight: 600; }
        .forecast-item span:nth-child(2) { width: 80px; text-align: center; }
        .forecast-item span:nth-child(3) { flex: 1; text-align: center; }
        .forecast-item span:last-child { width: 80px; text-align: right; }
        .loader { text-align: center; padding: 40px; display: none; }
        .error { background: #fee; color: #c33; padding: 16px; border-radius: 16px; text-align: center; margin-top: 16px; }
        .spinner { width: 40px; height: 40px; border: 4px solid #e0e0e0; border-top-color: #667eea; border-radius: 50%; animation: spin 0.8s linear infinite; margin: 0 auto; }
        @keyframes spin { to { transform: rotate(360deg); } }
        footer { text-align: center; color: rgba(0,0,0,0.6); font-size: 12px; padding: 20px; background: rgba(255,255,255,0.5); border-radius: 20px; margin-top: 20px; }
        @media (max-width: 550px) {
            .hourly-grid { grid-template-columns: repeat(auto-fill, minmax(105px,1fr)); }
            .period-btn { font-size: 11px; padding: 10px; }
        }
    </style>
</head>
<body>
<div class="container">
    <div class="card">
        <h1>🌤 {{ ai_name }}</h1>
        <div class="subtitle">Точная погода + одежда + 48‑часовой прогноз</div>

        <button class="share-btn" onclick="toggleQR()">📲 Поделиться сайтом (QR‑код)</button>
        <div id="qrContainer" class="qr-container">
            <div class="qr-instruction">📱 Поднесите второй телефон к экрану</div>
            <div id="qrcode"></div>
            <div style="margin-top: 12px; font-size: 12px; color: #777;">Ссылка: <span id="pageUrl"></span></div>
        </div>

        <div class="search-box">
            <input type="text" id="cityInput" placeholder="Введите город: Москва, Санкт-Петербург, Алатырь..." value="Москва">
            <button onclick="getWeather()">🔍</button>
        </div>
        
        <div class="period-buttons">
            <button class="period-btn" id="todayBtn" onclick="setPeriod('today')">🌡 СЕГОДНЯ</button>
            <button class="period-btn" id="hourlyBtn" onclick="setPeriod('hourly')">⏰ 48 ЧАСОВ</button>
            <button class="period-btn" id="weekBtn" onclick="setPeriod('week')">📅 НЕДЕЛЯ</button>
        </div>
        
        <div id="loader" class="loader"><div class="spinner"></div><p>Загрузка погоды...</p></div>
        <div id="weatherResult"></div>
    </div>
    <footer>Создатель: {{ creator_name }}<br>Данные: Open-Meteo API (обновление каждые 1-3 часа)</footer>
</div>
<script>
    let currentPeriod = 'today';
    let qrGenerated = false;

    function toggleQR() {
        const container = document.getElementById('qrContainer');
        if (container.classList.contains('show')) {
            container.classList.remove('show');
        } else {
            if (!qrGenerated) {
                const url = window.location.href;
                document.getElementById('pageUrl').innerText = url;
                new QRCode(document.getElementById("qrcode"), {
                    text: url,
                    width: 200,
                    height: 200,
                    colorDark: "#000000",
                    colorLight: "#ffffff",
                    correctLevel: QRCode.CorrectLevel.H
                });
                qrGenerated = true;
            }
            container.classList.add('show');
        }
    }

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
        if (!city) {
            alert('Введите название города');
            return;
        }
        
        document.getElementById('loader').style.display = 'block';
        document.getElementById('weatherResult').innerHTML = '';
        
        try {
            const response = await fetch('/weather', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ city: city, period: currentPeriod })
            });
            const data = await response.json();
            
            if (data.error) {
                document.getElementById('weatherResult').innerHTML = `<div class="error">❌ ${data.error}</div>`;
            } else if (currentPeriod === 'today') {
                displayCurrent(data);
            } else if (currentPeriod === 'hourly') {
                displayHourly(data);
            } else {
                displayWeekly(data);
            }
        } catch(error) {
            document.getElementById('weatherResult').innerHTML = '<div class="error">❌ Ошибка соединения с сервером</div>';
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
                <div class="feels">Ощущается как ${data.feels}°C</div>
                <div class="weather-details">
                    <div class="detail">
                        <div class="detail-value">${data.humidity}%</div>
                        <div class="detail-label">Влажность</div>
                    </div>
                    <div class="detail">
                        <div class="detail-value">${data.wind} км/ч</div>
                        <div class="detail-label">Ветер</div>
                    </div>
                    <div class="detail">
                        <div class="detail-value">${data.clouds}%</div>
                        <div class="detail-label">Облачность</div>
                    </div>
                    <div class="detail">
                        <div class="detail-value">${data.precip} мм</div>
                        <div class="detail-label">Осадки</div>
                    </div>
                    <div class="detail">
                        <div class="detail-value">${data.pressure} мм</div>
                        <div class="detail-label">Давление</div>
                    </div>
                    <div class="detail">
                        <div class="detail-value">${data.condition}</div>
                        <div class="detail-label">Погода</div>
                    </div>
                </div>
            </div>${clothingHtml}
        `;
        document.getElementById('weatherResult').innerHTML = html;
    }

    function displayHourly(data) {
        let items = '';
        for (let i = 0; i < data.length; i++) {
            const h = data[i];
            items += `
                <div class="hour-item">
                    <div class="hour-time">${h.time}</div>
                    <div class="hour-temp">${h.temp}°C</div>
                    <div class="hour-desc">${h.condition}</div>
                    <div class="hour-desc">💨 ${h.wind} км/ч</div>
                    <div class="hour-desc">🌧 ${h.precip} мм</div>
                </div>`;
        }
        const html = `
            <div class="weather-card">
                <div style="font-size: 20px; margin-bottom: 12px;">⏰ ПОЧАСОВОЙ ПРОГНОЗ (48 часов)</div>
                <div class="hourly-grid">${items}</div>
            </div>
        `;
        document.getElementById('weatherResult').innerHTML = html;
    }

    function displayWeekly(data) {
        let rows = '';
        for (let i = 0; i < data.length; i++) {
            const d = data[i];
            rows += `
                <div class="forecast-item">
                    <span>${d.date}</span>
                    <span>${d.tmin}→${d.tmax}°C</span>
                    <span>${d.condition}</span>
                    <span>💨${d.wind}</span>
                </div>`;
        }
        const html = `
            <div class="weather-card">
                <div style="font-size: 20px; margin-bottom: 12px;">📅 ПРОГНОЗ НА НЕДЕЛЮ</div>
                <div class="forecast-item" style="border-bottom: 2px solid rgba(255,255,255,0.5); padding-bottom: 8px; margin-bottom: 8px;">
                    <span style="font-weight:bold;">Дата</span>
                    <span style="font-weight:bold;">Температура</span>
                    <span style="font-weight:bold;">Погода</span>
                    <span style="font-weight:bold;">Ветер</span>
                </div>
                ${rows}
            </div>
        `;
        document.getElementById('weatherResult').innerHTML = html;
    }

    window.onload = function() {
        getWeather();
    };
</script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE, ai_name=AI_NAME, creator_name=CREATOR_NAME)

@app.route('/weather', methods=['POST'])
def weather_api():
    try:
        data = request.get_json()
        city = data.get('city', '').strip()
        period = data.get('period', 'today')
        
        if not city:
            return jsonify({'error': 'Введите название города'})
        
        # Поиск координат
        lat, lon = get_coords(city)
        if lat is None or lon is None:
            return jsonify({'error': f'Город "{city}" не найден. Попробуйте написать на английском или уточните название'})
        
        # Текущая погода (сегодня)
        if period == 'today':
            weather = get_current_weather(lat, lon)
            if not weather:
                return jsonify({'error': 'Не удалось получить погоду. Проверьте интернет или повторите позже'})
            
            pressure_mm = round(weather['pressure'] * 0.75006) if weather['pressure'] else 0
            condition_text = code_to_text(weather['code'])
            clothing = get_clothing_recommendation(
                weather['temp'],
                weather['feels'],
                weather['wind'],
                weather['precipitation'],
                condition_text
            )
            
            return jsonify({
                'city': city.title(),
                'temp': weather['temp'],
                'feels': weather['feels'],
                'humidity': weather['humidity'],
                'wind': weather['wind'],
                'clouds': weather['clouds'],
                'precip': weather['precipitation'],
                'pressure': pressure_mm,
                'condition': condition_text,
                'clothing': clothing
            })
        
        # Почасовой прогноз на 48 часов
        elif period == 'hourly':
            hourly = get_hourly_forecast_48h(lat, lon)
            if not hourly:
                return jsonify({'error': 'Не удалось получить почасовой прогноз'})
            
            for h in hourly:
                h['condition'] = code_to_text(h['code'])
            return jsonify(hourly)
        
        # Прогноз на неделю
        elif period == 'week':
            weekly = get_weekly_forecast(lat, lon)
            if not weekly:
                return jsonify({'error': 'Не удалось получить прогноз на неделю'})
            
            days_ru = ['ПН', 'ВТ', 'СР', 'ЧТ', 'ПТ', 'СБ', 'ВС']
            result = []
            for i, day in enumerate(weekly):
                date_obj = datetime.strptime(day['date'], '%Y-%m-%d')
                result.append({
                    'date': f"{date_obj.strftime('%d.%m')} ({days_ru[date_obj.weekday()]})",
                    'tmin': round(day['tmin']),
                    'tmax': round(day['tmax']),
                    'condition': code_to_text(day['code']),
                    'wind': round(day['wind'])
                })
            return jsonify(result)
        
        else:
            return jsonify({'error': 'Неизвестный период'})
            
    except Exception as e:
        print(f"⚠️ Ошибка в API: {e}")
        return jsonify({'error': f'Внутренняя ошибка сервера: {str(e)}'})

if __name__ == '__main__':
    print("\n" + "="*60)
    print("🌤 WeatherAI — ПОГОДНЫЙ СЕРВЕР (анимированный фон + 48 часов)")
    print("="*60)
    print("\n✅ Локальный доступ: http://localhost:5000")
    print("✅ На телефоне: откройте браузер и введите IP вашего компьютера:5000")
    print("✅ Для всех городов России работает через геокодинг")
    print("\n" + "="*60)
    app.run(host='0.0.0.0', port=5000, debug=False)
