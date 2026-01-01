# Live API

使用 Gemini Live API 進行即時語音對話的應用程式。

## 設定

1. 安裝依賴：
```bash
uv sync
```

2. 建立 `.env` 檔案並設定您的 Gemini API key：
```
GEMINI_API_KEY=your_api_key_here
```

3. 執行程式：
```bash
uv run python main.py
```

## 注意事項

- 請確保您的麥克風和揚聲器已正確連接
- 程式會使用預設的輸入和輸出音訊裝置
- 按 Ctrl+C 可中斷程式執行
