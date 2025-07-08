import os
import json
from flask import Flask, request, abort
from dotenv import load_dotenv
from linebot.v3.messaging import (
    Configuration, ApiClient, MessagingApi,
    ReplyMessageRequest, TextMessage
)
from linebot.v3.webhooks import validate_signature
from supabase import create_client
import openai

# 1. 讀環境變數
load_dotenv()
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

# 2. 欄位定義
FIELD_LIST = [
    "物件編號", "廠牌", "車款", "車型", "年式", "年份", "變速系統", "車門數", "驅動方式", "引擎燃料", "乘客數",
    "排氣量", "顏色", "安全性配備", "舒適性配備", "首次領牌時間", "行駛里程", "車身號碼", "引擎號碼",
    "外匯車資料", "車輛售價", "車輛賣點", "車輛副標題", "賣家保證", "特色說明", "影片看車", "物件圖片",
    "聯絡人", "行動電話", "賞車地址", "line", "檢測機構", "查定編號", "認證書"
]

# 3. 初始化
app = Flask(__name__)
config = Configuration(access_token=LINE_CHANNEL_ACCESS_TOKEN)
line_bot_api = MessagingApi(ApiClient(config))
openai.api_key = OPENAI_API_KEY
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# 4. GPT 問題判斷
def gpt_parse_question(user_text):
    field_str = "、".join(FIELD_LIST)
    prompt = f"""
你有以下欄位可查詢：
{field_str}

請將「{user_text}」這句話，判斷：
1. 用戶想查詢的欄位 field（只選一個最適合的，從上面欄位挑）
2. 資料查詢關鍵詞 keyword（通常是品牌、型號、年份等）

用這個格式回傳：
{{"field": "欄位名稱", "keyword": "主要關鍵詞"}}

如果是問價格，請 field 填「車輛售價」；如果問聯絡人，就填「聯絡人」；依此類推。
    """
    completion = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "system", "content": prompt}]
    )
    ans = completion.choices[0].message.content.strip()
    try:
        return json.loads(ans)
    except Exception:
        return {"field": "", "keyword": ""}

# 5. 查 Supabase 欄位
def query_supabase_by_field(field: str, keyword: str) -> str:
    if not field or not keyword or field not in FIELD_LIST:
        return ""
    cars = supabase.table("cars").select("*").ilike(field, f"%{keyword}%").limit(1).execute()
    if cars.data:
        value = cars.data[0].get(field, "")
        if value:
            return f"{field}：{value}"
    return f"很抱歉，找不到符合『{keyword}』的{field}資料。"

# 6. GPT補充
SYSTEM_PROMPT = """
你是亞鈺汽車智慧助理，負責解答用戶關於車輛與公司資訊的任何問題。請直接針對問題給出精確、有溫度、字數不超過250字的回應。
如果無法回答，請回：「感謝您的詢問，請詢問亞鈺汽車相關問題，我們很高興為您服務！😄」
"""
def ask_gpt(user_text: str, context: str = "") -> str:
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    if context:
        messages.append({"role": "assistant", "content": context})
    messages.append({"role": "user", "content": user_text})
    completion = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=messages,
    )
    return completion.choices[0].message.content.strip()

# 7. LINE Webhook
@app.route("/api/webhook", methods=["POST"])
def webhook():
    signature = request.headers.get("x-line-signature")
    body = request.get_data(as_text=True)

    # 簽名驗證
    try:
        validate_signature(body, signature, LINE_CHANNEL_SECRET)
    except Exception as e:
        print("Signature validation failed:", e)
        abort(400)

    # 解析事件 (json)
    events = json.loads(body).get("events", [])
    for event in events:
        if event.get("type") == "message" and event["message"].get("type") == "text":
            user_text = event["message"]["text"].strip()
            reply_token = event["replyToken"]

            try:
                parse_result = gpt_parse_question(user_text)
                field = parse_result.get('field', "")
                keyword = parse_result.get('keyword', "")
            except Exception as e:
                field = ""
                keyword = ""
                print(f"GPT解析失敗：{e}")

            reply_text = ""
            if field and keyword:
                reply_text = query_supabase_by_field(field, keyword)
            if not reply_text or "找不到" in reply_text:
                reply_text = ask_gpt(user_text)

            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=reply_token,
                    messages=[TextMessage(text=reply_text)]
                )
            )

    return "OK"

# 8. 本地測試
if __name__ == "__main__":
    app.run(port=3000)
