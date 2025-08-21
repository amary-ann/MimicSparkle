from typing import Optional
from fastapi import FastAPI
import uvicorn
import aiohttp
import json
from models import WhatsAppWebhook
import os
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()

@app.get("/")
async def root():
    return {"message": "Hello World"}

@app.post('/send_message')
async def send_message():
  data = get_text_message_input("+2348183808266"
                                , 'Hi there, I\'m Mimic! This is a test message');
  await send_message(data)
  return {"status": "Message sent"}

@app.post("/whatsapp/callback")
async def whatsapp_callback(payload):
    print("Received payload:", payload)
    
    # payload is now a fully validated Pydantic model
    if payload.object != "whatsapp_business_account":
        return {"error": "Invalid object"}

    for entry in payload.entry or []:
        for change in entry.changes or []:
            if change.field == "messages":
                for msg in change.value.messages or []:
                    print("Message from:", msg.from_, "Text:", msg.text.body if msg.text else None)
    return {"status": "ok"}


async def send_message(data):
  headers = {
    "Content-type": "application/json",
    "Authorization": f"Bearer {os.getenv('WHATSAPP_ACCESS_TOKEN')}",
    }
  
  async with aiohttp.ClientSession() as session:
    url = f'{os.getenv('BASE_URL')}' + f"/{os.getenv('API_VERSION')}/{os.getenv('PHONE_NUMBER_ID')}/messages"
    try:
      async with session.post(url, data=data, headers=headers) as response:
        if response.status == 200:
          print("Status:", response.status)
          print("Content-type:", response.headers['content-type'])

          html = await response.text()
          print("Body:", html)
        else:
          print(response.status)        
          print(response)        
    except aiohttp.ClientConnectorError as e:
      print('Connection Error', str(e))

def get_text_message_input(recipient, text):
  return json.dumps({
    "messaging_product": "whatsapp",
    "preview_url": False,
    "recipient_type": "individual",
    "to": recipient,
    "type": "text",
    "text": {
        "body": text
    }
  })