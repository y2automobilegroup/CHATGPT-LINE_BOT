import os
from flask import Flask, request, abort
from dotenv import load_dotenv
from linebot.v3.messaging import Configuration, ApiClient, MessagingApi, ReplyMessageRequest, TextMessage
from linebot.v3.webhook import WebhookParser
from linebot.v3.webhooks import MessageEvent, TextMessageContent
from supabase import create_client
import openai

# 載入 .env
load_dotenv()

# ChatGPT 系統角色
SYSTEM_PROMPT = """
你是亞鈺汽車智慧助理，負責解答用戶關於車輛與公司資訊的任何問題。
你是亞鈺汽車的50年資深客服專員，擅長解決問題且擅長思考拆解問題，請先透過參考資料判斷並解析問題點，只詢問參考資料需要的問題，不要問不相關參考資料的問題，如果詢問內容不在參考資料內，請先判斷這句話是什麼類型的問題，然後針對參考資料內的資料做反問問題，最後問到需要的答案，請用最積極與充滿溫度的方式回答，若參考資料與問題無關，比如他是來聊天的，請回覆罐頭訊息："感謝您的詢問，請詢問亞鈺汽車相關問題，我們很高興為您服務！😄"，整體字數不要超過250個字，請針對問題直接回答答案
請依下列流程處理：
1. 問題拆解：辨識用戶意圖與關鍵字（如品牌、年份、問題類型）。
2. 資料查詢：
   2.1 先以語意搜尋 Supabase 的 cars 表（欄位 text）。
   2.2 若未找到足夠資訊，再查詢 company 表。
3. 結果評估：若找到結果，整理最相關回答；若仍不足，進入第 4 步。
4. 追問：向用戶提出 1 個具體問題，以釐清或補充必要細節，避免一次詢問過多。
回答務必親切、精確，並盡量附帶具體數據或範例。
"""

# 初始化 Flask
app = Flask(__name__)

# 初始化 LINE Messaging API (v3)
config = Configuration(access_token=os.getenv("LINE_CHANNEL_ACCESS_TOKEN"))
messaging_api = MessagingApi(ApiClient(config))
parser = WebhookParser(os.getenv("LINE_CHANNEL_SECRET"))

# OpenAI Key
openai.api_key = os.getenv("OPENAI_API_KEY")

# Supabase 初始化
supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
supabase = create_client(supabase_url, supabase_key)

# 查詢 Supabase
def query_supabase(question: str) -> str:
    cars = supabase.table("cars").select("*").ilike("text", f"%{question}%").limit(3).execute()
    if cars.data:
        first = cars.data[0]
        return f"車輛資訊：{first.get('text', '')}"

    company = supabase.table("company").select("*").ilike("text", f"%{question}%").limit(1).execute()
    if company.data:
        return f"公司資訊：{company.data[0].get('text', '')}"

    return ""  # 無結果

# GPT 補充回答
def ask_gpt(user_text: str, context: str = "") -> str:
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT}
    ]
    if context:
        messages.append({"role": "assistant", "content": context})
    messages.append({"role": "user", "content": user_text})

    completion = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=messages,
    )
    return completion.choices[0].message.content.strip()

# LINE Webhook
@app.route("/api/webhook", methods=["POST"])
def callback():
    signature = request.headers.get("x-line-signature")
    body = request.get_data(as_text=True)

    try:
        events = parser.parse(body, signature)
    except Exception as e:
        print("Webhook parse error:", e)
        abort(400)

    for event in events:
        if isinstance(event, MessageEvent) and isinstance(event.message, TextMessageContent):
            user_text = event.message.text.strip()

            # 先查 Supabase
            reply_text = query_supabase(user_text)

            # 無結果時交給 GPT
            if not reply_text:
                reply_text = ask_gpt(user_text)

            # v3 回覆
            messaging_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text=reply_text)]
                )
            )
    return "OK"

# 本地測試用
if __name__ == "__main__":
    app.run(port=3000)
