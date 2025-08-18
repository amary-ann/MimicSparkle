from typing import Optional
from fastapi import FastAPI
import uvicorn
from models import WhatsAppWebhook

app = FastAPI()

@app.get("/")
async def root():
    return {"message": "Hello World"}

@app.post("/whatsapp/callback")
async def whatsapp_callback(payload: WhatsAppWebhook):
    # payload is now a fully validated Pydantic model
    if payload.object != "whatsapp_business_account":
        return {"error": "Invalid object"}

    for entry in payload.entry or []:
        for change in entry.changes or []:
            if change.field == "messages":
                for msg in change.value.messages or []:
                    print("Message from:", msg.from_, "Text:", msg.text.body if msg.text else None)
    return {"status": "ok"}
