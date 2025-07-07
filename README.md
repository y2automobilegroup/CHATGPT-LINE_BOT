# LINE × ChatGPT × Supabase — Vercel 部署指南

這個專案示範如何在 **Vercel** 上部署使用 **LINE Messaging API**、
**OpenAI ChatGPT** 與 **Supabase** 的無伺服器聊天機器人。

## 快速開始

1. Fork 或 clone 此 repo。
2. 在本機複製 `.env.example` 為 `.env`，填入真實金鑰。
3. 安裝依賴並本地測試：
   ```bash
   pip install -r requirements.txt
   python api/webhook.py
   ```
4. Push 至 GitHub，於 Vercel 建立新專案並連結此 repo。
5. 將 Vercel 生成的 `/api/webhook` HTTPS URL 貼到 LINE Developers Webhook URL。

## 檔案結構
```
/                  # 專案根目錄
│  .env.example
│  requirements.txt
│  vercel.json
│  README.md
└─ api/
   └─ webhook.py
```
## 說明
- `api/webhook.py`：Flask 入口、整合 LINE → GPT → Supabase 查詢。
- `vercel.json`：設定 Vercel 使用 `@vercel/python` 執行 webhook。
