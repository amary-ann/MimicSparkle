import json
import logging
import uvicorn
from pprint import pprint
from typing import Optional
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from utils import get_whatsapp_no_format, get_message_input, send_message
from models import WhatsAppWebhook, MsgRequest

load_dotenv()

logging.basicConfig(level=logging.INFO,  format='%(asctime)s - %(levelname)s - %(message)s',  handlers=[logging.FileHandler('app.log', mode='w'), logging.StreamHandler()])

app = FastAPI()

@app.get("/")
async def root():
    return {"message": "Mimic for Sparkle Meta WhatsApp API"}

@app.post('/send_message')
async def send_message_endpoint(msgreq: MsgRequest):
  phone_number = get_whatsapp_no_format(msgreq.phone_number)
  data = get_message_input(phone_number
                                ,msgreq.message)
  logging.info(f"Content: {pprint(data)}")
  await send_message(data)
  return {"status": "Message sent"}


@app.post("/whatsapp/callback")
async def whatsapp_callback(request: Request):
    payload = await request.json()  # parse JSON body into dict
    pprint(f"{payload=}")

    if payload.get("object") != "whatsapp_business_account":
        return {"error": "Invalid object"}

    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            if change.get("field") == "messages":
                for msg in change.get("value", {}).get("messages", []):
                    if msg.get("type") == "text":
                        print(
                            f"{msg.get('from')} sent you a message!\n"
                            f"The content of the message reads: {msg.get('text', {}).get('body')}"
                        )
                        data = get_message_input(
                            msg.get("from"),
                            msg.get("text", {}).get("body"),
                            msg.get("type")
                        )
                        await send_message(data)
                    else:
                        print(f"Received a non-text message: {msg.get('type')}")

                        data = get_message_input(
                            msg.get("from"),
                            f"Received a non-text message! {msg.get('type')}",
                            msg.get('type')
                        )
                        await send_message(data)

    return {"success": True, "status": "Message received"}
