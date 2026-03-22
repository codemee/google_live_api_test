import requests
import json
from urllib.parse import quote

def get_city_geo_info(city: str):
    """
    透過 Open-Meteo 的地理編碼 API 獲取指定城市的經緯度資訊。

    Args:
        city (str): 城市的英文名稱。

    Returns:
        dict: 包含 'lat' (緯度) 和 'lon' (經度) 的字典，
              如果找不到城市資訊則回傳 None。
    """
    encoded_city = quote(city)
    geocode_url = (
        f"https://geocoding-api.open-meteo.com/v1"
        f"/search?name={encoded_city}&count=1&language=zh"
    )
    geo_resp = requests.get(geocode_url)
    geo_data = geo_resp.json()

    if geo_data.get('results', None):
        lat = geo_data['results'][0]['latitude']
        lon = geo_data['results'][0]['longitude']
        return {
            'lat': lat,
            'lon': lon
        }
    return None

def get_feels_like_celsius(city: str):
    """
    透過 Open-Meteo API 獲取指定城市的攝氏體趕溫度。

    首先會透過地理編碼 API 獲取城市的經緯度，然後使用
    這些經緯度查詢該城市的當前溫度。

    Args:
        city (str): 城市的英文名稱。

    Returns:
        str: 該城市目前的攝氏溫度（字串），
             如果無法擷取溫度則回傳錯誤訊息。
    """
    geo_info = get_city_geo_info(city)
    if geo_info:
        weather_url = (
            "https://api.open-meteo.com/v1/"
            f"forecast?latitude={geo_info['lat']}&"
            f"longitude={geo_info['lon']}"
            "&current=apparent_temperature"
            "&timezone=Asia/Taipei"
        )
        weather_resp = requests.get(weather_url)
        weather_data = weather_resp.json()

        current = weather_data['current']
        return f"{current['apparent_temperature']}"
    return "無法擷取溫度"

if __name__ == "__main__":  
    # 範例使用：
    feels_like = get_feels_like_celsius(city="Taipei")
    print(f"台北目前的攝氏體感溫度: {feels_like}°C")
    feels_like_london = get_feels_like_celsius(city="London")
    print(f"倫敦目前的攝氏體感溫度: {feels_like_london}°C")
    feels_like_newyork = get_feels_like_celsius(city="New York")
    print(f"紐約目前的攝氏體感溫度: {feels_like_newyork}°C")