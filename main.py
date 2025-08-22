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
async def send_message(request: MsgRequest):

  phone_number = get_whatsapp_no_format(request.to)
  data = get_message_input(phone_number
                                ,request.message)
  logging.info(f"Content: {pprint(data)}")
  await send_message(data)
  return {"status": "Message sent"}


@app.post("/whatsapp/callback")
async def whatsapp_callback(payload:dict):
    pprint(f"{payload=}")

    # payload is now a fully validated Pydantic model
    if payload['object'] != "whatsapp_business_account":
        return {"error": "Invalid object"}

    for entry in payload['entry'] or []:
        for change in entry['changes'] or []:
            if change['field'] == "messages":
                for msg in change['value']['messages'][0] or []:
                    if msg['type'] == "text":
                      print(f"{msg['from']} sent you a message!\n The content of the message reads:\
                             {msg['text']['body'] if msg['text'] else None}")
                      data = get_message_input(msg['from'], msg['text']['body'], msg['type'])
                      await send_message(data)
    return {"success": True,
            "status": "Message received"}

