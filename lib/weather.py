import requests
import json
from urllib.parse import quote

def get_feels_like_celsius(city: str):
    """
    從 wttr.in 獲取指定城市的攝氏體感溫度。

    發送 HTTP 請求到 wttr.in 的 API，解析回傳的 JSON 資料，
    並提取目前的攝氏體感溫度。

    Args:
        city (str): 城市的英文名稱。

    Returns:
        str: 該城市目前的攝氏體感溫度（字串），如果獲取失敗則回傳錯誤訊息。
    """
    # 對城市名稱進行 URL 編碼，以處理空格或特殊字元
    encoded_city = quote(city)
    url = f"https://wttr.in/{encoded_city}?format=j1"
    try:
        response = requests.get(url)
        response.raise_for_status()  # 如果請求失敗 (例如 4xx 或 5xx)，則會觸發 HTTPError
        data = response.json()

        # 根據 wttr.in 的 JSON 結構，體感溫度通常在 current_condition[0] 之下
        feels_like_c = data['current_condition'][0]['FeelsLikeC']
        return feels_like_c
    except requests.exceptions.RequestException as e:
        return f"獲取天氣資料時發生錯誤: {e}"
    except (KeyError, IndexError) as e:
        return f"解析天氣資料時發生錯誤，JSON 結構可能已改變: {e}"
    except Exception as e:
        return f"發生未知錯誤: {e}"

if __name__ == "__main__":  
    # 範例使用：
    feels_like = get_feels_like_celsius(city="Taipei")
    print(f"台北目前的攝氏體感溫度: {feels_like}°C")
    feels_like_london = get_feels_like_celsius(city="London")
    print(f"倫敦目前的攝氏體感溫度: {feels_like_london}°C")
    feels_like_newyork = get_feels_like_celsius(city="New York")
    print(f"紐約目前的攝氏體感溫度: {feels_like_newyork}°C")