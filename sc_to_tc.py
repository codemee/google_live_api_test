import re
import zhconv


def sc_to_tc(text: str) -> str:
    """將簡體中文轉換為繁體中文，並移除語音辨識輸出中字元間的多餘空白。

    範例：
        '东 京 和 汉 城 现 在 哪 边 比 较 冷 ?' -> '東京和漢城現在哪邊比較冷？'
    """
    # 移除中文字元與標點符號之間的空白
    text = re.sub(
        r'(?<=[\u4e00-\u9fff\uff00-\uffef])\s+'
        r'(?=[\u4e00-\u9fff\uff00-\uffef?？！，。、：；「」【】])',
        '',
        text
    )
    # 移除中文字元後、ASCII 標點前的空白（如 '冷 ?'）
    text = re.sub(
        r'(?<=[\u4e00-\u9fff])\s+(?=[?!,.])',
        '',
        text
    )
    # 簡體轉繁體（台灣用字）
    return zhconv.convert(text, 'zh-tw')


if __name__ == "__main__":
    samples = [
        "东 京 和 汉 城 现 在 哪 边 比 较 冷 ?",
        "台 湾 看 得 到 吗 ?",
        "高 雄 和 台 北 现 在 哪 里 比 较 热 ?",
        "我 现 在 在 哪 一 座 城 市 ?",
    ]
    for s in samples:
        print(f"原文：{s}")
        print(f"轉換：{sc_to_tc(s)}")
        print()
