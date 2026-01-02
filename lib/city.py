import requests
import json

def get_current_city_name():
    """
    從 ip-api.com 獲取目前所在城市的名稱，無需 API Key。

    發送 HTTP 請求到 ip-api.com 的 API，解析回傳的 JSON 資料，
    並提取目前所在的城市名稱。

    Returns:
        str: 目前所在城市的名稱（字串），如果獲取失敗則回傳錯誤訊息。
    """
    url = "http://ip-api.com/json?lang=zh-TW"
    try:
        response = requests.get(url)
        response.raise_for_status()  # 如果請求失敗 (例如 4xx 或 5xx)，則會觸發 HTTPError
        data = response.json()

        if data['status'] == 'success':
            city = data.get('city')
            if city:
                return city
            else:
                return "無法從 API 回傳中找到城市名稱。"
        else:
            return f"API 請求失敗：{data.get('message', '未知錯誤')}"
    except requests.exceptions.RequestException as e:
        return f"獲取地理位置資料時發生網路錯誤: {e}"
    except (KeyError, IndexError) as e:
        return f"解析地理位置資料時發生錯誤，JSON 結構可能已改變或缺少鍵值: {e}"
    except Exception as e:
        return f"發生未知錯誤: {e}"

if __name__ == "__main__":
    # 範例使用：
    current_city = get_current_city_name()
    print(f"您目前所在的城市是: {current_city}")