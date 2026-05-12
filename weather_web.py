from flask import Flask, request, render_template_string, jsonify
import requests
import re
from geopy.geocoders import Nominatim
from datetime import datetime

app = Flask(__name__)

# ==================== НАСТРОЙКИ ====================
CREATOR_NAME = "Соловьев Дмитрий Владимирович"
AI_NAME = "WeatherAI"

# ==================== ГЕОКОДИНГ ====================
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

# ==================== ПОГОДА ====================
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

def code2text(code):
    if code == 0: return "Ясно ☀️"
    if 1 <= code <= 3: return "Малооблачно ⛅"
    if code in (45, 48): return "Туман 🌫️"
    if 51 <= code <= 55: return "Морось 🌦️"
    if 61 <= code <= 65: return "Дождь 🌧️"
    if 71 <= code <= 75: return "Снег 🌨️"
    if code >= 95: return "Гроза ⛈️"
    return "Облачно 🌥️"

# ==================== ФУНКЦИЯ РЕКОМЕНДАЦИЙ ПО ОДЕЖДЕ ====================
def get_clothing_recommendation(temp, feels, wind, precip, condition_text):
    """Возвращает советы по одежде на основе погоды"""
    recommendations = []
    
    # Рекомендации по температуре
    if temp <= -25:
        recommendations.append("🧥 Арктический холод! Одевайся максимально тепло: пуховик, термобельё, две шапки, шарф, варежки.")
    elif temp <= -15:
        recommendations.append("🥶 Очень холодно! Нужен пуховик, тёплая шапка, шарф, перчатки и тёплая обувь.")
    elif temp <= -5:
        recommendations.append("🧣 Холодно. Надевай зимнюю куртку, шапку, шарф и перчатки.")
    elif temp <= 0:
        recommendations.append("🧥 Прохладно. Зимняя куртка или плотное пальто, шапка, шарф.")
    elif temp <= 5:
        recommendations.append("🧥 Зябко. Демисезонная куртка или пальто, шапка, шарф.")
    elif temp <= 10:
        recommendations.append("🧥 Прохладно. Лёгкая куртка или ветровка. Шарф не помешает.")
    elif temp <= 15:
        recommendations.append("🧥 Свежо. Кофта или толстовка + куртка. Шапка уже не нужна.")
    elif temp <= 20:
        recommendations.append("👕 Тепло. Можно одеться легко: футболка и джинсы. На вечер — кофта.")
    elif temp <= 25:
        recommendations.append("☀️ Очень тепло! Футболка, шорты/лёгкие брюки. Не забудь кепку или панаму.")
    else:
        recommendations.append("🩳 Жарко! Лёгкая одежда, шорты, панама, обязательно пей воду!")
    
    # Рекомендации по ветру
    if wind >= 25:
        recommendations.append("💨 Сильный ветер! Ветровка обязательно, даже если тепло.")
    elif wind >= 15:
        recommendations.append("🍃 Ветрено. Застегнись или накинь ветровку.")
    
    # Рекомендации по осадкам
    if precip > 5:
        recommendations.append("☔ Ожидаются осадки. Возьми зонт или дождевик.")
    elif "дождь" in condition_text.lower() or "ливень" in condition_text.lower():
        recommendations.append("☔ Идёт дождь. Не забудь зонт и непромокаемую обувь.")
    elif "снег" in condition_text.lower():
        recommendations.append("❄️ Идёт снег. Одевайся теплее, обувь должна быть непромокаемой.")
    
    # Финальный короткий вердикт (для отображения в заголовке)
    if temp <= 0:
        short = "Очень холодно ❄️"
    elif temp <= 10:
        short = "Прохладно 🧥"
    elif temp <= 20:
        short = "Тепло ☀️"
    else:
        short = "Жарко 🩳"
    
    return {
        "short": short,
        "full": " • ".join(recommendations) if recommendations else "Одевайся по погоде, чувствуй себя комфортно!"
    }

# ==================== HTML ШАБЛОН (с блоком рекомендаций) ====================
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=yes">
    <title>{{ ai_name }} — Погода + Советы по одежде</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        .container {
            max-width: 600px;
            margin: 0 auto;
        }
        .card {
            background: white;
            border-radius: 25px;
            padding: 24px;
            margin-bottom: 20px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.2);
        }
        h1 {
            font-size: 24px;
            color: #333;
            text-align: center;
            margin-bottom: 8px;
        }
        .subtitle {
            text-align: center;
            color: #666;
            font-size: 14px;
            margin-bottom: 20px;
            padding-bottom: 16px;
            border-bottom: 1px solid #eee;
        }
        .creator {
            text-align: center;
            font-size: 12px;
            color: #888;
            margin-top: 8px;
        }
        .search-box {
            display: flex;
            gap: 12px;
            margin-bottom: 20px;
        }
        input {
            flex: 1;
            padding: 14px 18px;
            border: 2px solid #e0e0e0;
            border-radius: 30px;
            font-size: 16px;
            outline: none;
            transition: border 0.3s;
        }
        input:focus {
            border-color: #667eea;
        }
        button {
            padding: 14px 24px;
            background: #667eea;
            color: white;
            border: none;
            border-radius: 30px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            transition: transform 0.2s, background 0.2s;
        }
        button:active {
            transform: scale(0.96);
        }
        .period-buttons {
            display: flex;
            gap: 12px;
            margin-bottom: 20px;
        }
        .period-btn {
            flex: 1;
            padding: 12px;
            background: #f0f0f0;
            color: #666;
            border: none;
            border-radius: 30px;
            font-size: 14px;
            cursor: pointer;
            transition: all 0.2s;
        }
        .period-btn.active {
            background: #667eea;
            color: white;
        }
        .weather-card {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border-radius: 25px;
            padding: 24px;
            text-align: center;
        }
        .temp {
            font-size: 64px;
            font-weight: bold;
            margin: 16px 0;
        }
        .feels {
            font-size: 16px;
            opacity: 0.9;
        }
        .weather-details {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 16px;
            margin-top: 24px;
            padding-top: 16px;
            border-top: 1px solid rgba(255,255,255,0.3);
        }
        .detail {
            text-align: center;
        }
        .detail-value {
            font-size: 20px;
            font-weight: bold;
        }
        .detail-label {
            font-size: 12px;
            opacity: 0.8;
            margin-top: 4px;
        }
        .clothing-card {
            background: #fff8e7;
            border-left: 5px solid #ff9800;
            border-radius: 16px;
            padding: 16px;
            margin-top: 20px;
            text-align: left;
        }
        .clothing-title {
            font-weight: bold;
            font-size: 18px;
            color: #333;
            margin-bottom: 8px;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        .clothing-recommendation {
            font-size: 15px;
            color: #555;
            line-height: 1.4;
        }
        .forecast {
            margin-top: 20px;
        }
        .forecast-item {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 12px 0;
            border-bottom: 1px solid #eee;
        }
        .forecast-date {
            width: 80px;
            font-weight: 600;
        }
        .forecast-temp {
            width: 80px;
            text-align: center;
        }
        .forecast-desc {
            flex: 1;
            text-align: center;
        }
        .forecast-wind {
            width: 70px;
            text-align: right;
            font-size: 12px;
            color: #666;
        }
        .loader {
            text-align: center;
            padding: 40px;
            display: none;
        }
        .error {
            background: #fee;
            color: #c33;
            padding: 16px;
            border-radius: 16px;
            text-align: center;
            margin-top: 16px;
        }
        .city-name {
            font-size: 28px;
            font-weight: bold;
            margin-bottom: 8px;
        }
        @keyframes spin {
            to { transform: rotate(360deg); }
        }
        .spinner {
            width: 40px;
            height: 40px;
            border: 4px solid #e0e0e0;
            border-top-color: #667eea;
            border-radius: 50%;
            animation: spin 0.8s linear infinite;
            margin: 0 auto;
        }
        footer {
            text-align: center;
            color: rgba(255,255,255,0.7);
            font-size: 12px;
            padding: 20px;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="card">
            <h1>🌤 {{ ai_name }}</h1>
            <div class="subtitle">Погода + Советы по одежде 👕</div>
            
            <div class="search-box">
                <input type="text" id="cityInput" placeholder="Например: Москва, Алатырь, Сочи" value="">
                <button onclick="getWeather()">🔍</button>
            </div>
            
            <div class="period-buttons">
                <button class="period-btn" id="todayBtn" onclick="setPeriod('today')">🌡 СЕГОДНЯ</button>
                <button class="period-btn" id="weekBtn" onclick="setPeriod('week')">📅 НЕДЕЛЯ</button>
            </div>
            
            <div id="loader" class="loader">
                <div class="spinner"></div>
                <p style="margin-top: 12px;">Загружаем погоду...</p>
            </div>
            
            <div id="weatherResult"></div>
        </div>
        <footer>
            Создатель: {{ creator_name }}<br>
            Данные: Open-Meteo API
        </footer>
    </div>
    
    <script>
        let currentPeriod = 'today';
        
        function setPeriod(period) {
            currentPeriod = period;
            document.getElementById('todayBtn').classList.remove('active');
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
                    displayCurrentWeather(data);
                } else {
                    displayWeeklyForecast(data);
                }
            } catch (error) {
                document.getElementById('weatherResult').innerHTML = `<div class="error">❌ Ошибка соединения</div>`;
            } finally {
                document.getElementById('loader').style.display = 'none';
            }
        }
        
        function displayCurrentWeather(data) {
            const clothingHtml = data.clothing ? `
                <div class="clothing-card">
                    <div class="clothing-title">
                        <span>👗 ${data.clothing.short}</span>
                    </div>
                    <div class="clothing-recommendation">
                        ${data.clothing.full}
                    </div>
                </div>
            ` : '';
            
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
                            <div class="detail-label">Состояние</div>
                        </div>
                    </div>
                </div>
                ${clothingHtml}
            `;
            document.getElementById('weatherResult').innerHTML = html;
        }
        
        function displayWeeklyForecast(data) {
            let daysHtml = '<div class="weather-card" style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 20px; text-align: left;"><div style="text-align: center; font-size: 20px; margin-bottom: 16px;">📅 ПРОГНОЗ НА НЕДЕЛЮ</div><div class="forecast">';
            
            for (let day of data) {
                daysHtml += `
                    <div class="forecast-item">
                        <div class="forecast-date">${day.date}</div>
                        <div class="forecast-temp">${day.tmin}→${day.tmax}°C</div>
                        <div class="forecast-desc">${day.condition}</div>
                        <div class="forecast-wind">💨${day.wind}</div>
                    </div>
                `;
            }
            daysHtml += '</div></div>';
            document.getElementById('weatherResult').innerHTML = daysHtml;
        }
        
        window.onload = function() {
            // Можно загрузить погоду для Москвы по умолчанию
            document.getElementById('cityInput').value = 'Москва';
            getWeather();
        }
    </script>
</body>
</html>
"""

# ==================== API МАРШРУТЫ ====================
@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE, 
                                  ai_name=AI_NAME, 
                                  creator_name=CREATOR_NAME)

@app.route('/weather', methods=['POST'])
def weather():
    data = request.get_json()
    city = data.get('city', '').strip()
    period = data.get('period', 'today')
    
    if not city:
        return jsonify({'error': 'Введите название города'})
    
    lat, lon = get_coords(city)
    if lat is None:
        return jsonify({'error': f'Город "{city}" не найден'})
    
    if period == 'today':
        w = get_current(lat, lon)
        if not w:
            return jsonify({'error': 'Не удалось получить погоду'})
        press_mm = round(w['press'] * 0.75006) if w['press'] else 0
        condition = code2text(w['code'])
        
        # Получаем рекомендации по одежде
        clothing = get_clothing_recommendation(
            temp=w['temp'],
            feels=w['feels'],
            wind=w['wind'],
            precip=w['precip'],
            condition_text=condition
        )
        
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
    else:
        week = get_weekly(lat, lon)
        if not week:
            return jsonify({'error': 'Не удалось получить прогноз'})
        
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
    print(f"🌤 {AI_NAME} — ВЕБ-СЕРВЕР С РЕКОМЕНДАЦИЯМИ ПО ОДЕЖДЕ 🌤")
    print("="*60)
    print("\n📱 ДЛЯ ДОСТУПА С ТЕЛЕФОНА (в одной Wi-Fi сети):")
    print("\nШАГ 1: Узнайте IP вашего компьютера:")
    print("   Откройте cmd и введите: ipconfig")
    print("   Найдите IPv4-адрес (например: 192.168.1.100)")
    print("\nШАГ 2: На телефоне откройте браузер и введите:")
    print(f"   http://ВАШ_IP:5000")
    print("\nШАГ 3 (альтернатива — на этом же компьютере):")
    print("   http://localhost:5000")
    print("\n" + "="*60)
    print("Нажмите Ctrl+C для остановки сервера\n")
    
    app.run(host='0.0.0.0', port=5000, debug=False)
