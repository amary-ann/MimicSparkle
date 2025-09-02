import os
import json
import logging
import aiohttp
import uvicorn
from prompts import GENERAL_PROMPT
from langchain_openai import ChatOpenAI
from pprint import pprint
from typing import Optional
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie
from langchain_core.prompts import ChatPromptTemplate, PromptTemplate
from utils import get_whatsapp_no_format, get_message_input, send_message
from models import WhatsAppWebhook, MsgRequest, AppResponse,  Session, Message, User, Beneficiary,PinRequest, Pin, RegPinRequest, NotifyRequest, Balance

load_dotenv()

logging.basicConfig(level=logging.INFO,  format='%(asctime)s - %(levelname)s - %(message)s',  handlers=[logging.FileHandler('app.log', mode='w'), logging.StreamHandler()])

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("execution before startup")
    collection_name =  os.getenv("MONGO_DB_COLLECTION")
    mongo_string = os.getenv("MONGO_CONNECTION_STRING")
    client = AsyncIOMotorClient(mongo_string)

    await init_beanie(
        database=client[collection_name],
        document_models=[Session, User, Beneficiary, Pin, Balance]
    )
    yield print("Execute before closed")

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


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

# Send response to WhatsApp User
async def _post(data: dict) -> AppResponse:
        async with aiohttp.ClientSession() as session:
            url = f"{os.getenv('BASE_URL')}/{os.getenv('API_VERSION')}/{os.getenv('PHONE_NUMBER_ID')}/messages"
            try:
                async with session.post(url, json=data) as resp:
                    if resp.status != 200:
                        return AppResponse(False, "Error occurred")
                    return AppResponse(True, "Successful operation")
            except Exception as e:
                logging.error(f"Error sending message: {e}")
                return AppResponse(False, str(e))

# Text message handler
async def send_text_message(to: str, text: str, preview_url: bool = False) -> AppResponse:
        
        # Check if user exists in the database
        user = await User.find_one({'phone_number' : to})

        if not user: 
            session = Session(phone_number = to)
            message = Message(message = text , is_user = True)
            session.chats = [message]
            await session.insert()
            response = "👋 Welcome! It looks like you're new here, and we're excited to have you with us. \nTo get started, please click the link below: 👇\nhttps://sparklemimicfrontend.netlify.app/"
            
        
        else:
            session = await Session.find_one({"phone_number": to})
            message = Message(message = text, is_user = True)

            if session:
                session.chats.append(message)
                await session.save()
                logging.info("User message saved to session")

            else:
                user_acct = user.account_number 
                session = Session(phone_number=to, account_number=user_acct)
                session.chats = [message]
                await session.insert()
                logging.info("New session created and user message saved.")

        
            OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
            llm_model_name = 'gpt-4o'
            llm = ChatOpenAI(model = llm_model_name, temperature=0.2)
            chat_template = ChatPromptTemplate.from_messages([
                ("system","{system_prompt}"),
                ("human","{user_message}"),
            ])
            
            prompt_value = chat_template.invoke({
            "system_prompt":GENERAL_PROMPT,
            "user_message":text})
            
            response = llm.invoke(prompt_value).content

        
        print(f"Bot response: {response}")
        return await _post({
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "text",
            "text": {"preview_url": preview_url, "body": response}
        })

# Webhook to receive messages from WhatsApp
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
                    # check if user exists in the database
                    
                    if msg.get("type") == "text":
                        print(
                            f"{msg.get('from')} sent you a message!\n"
                            f"The content of the message reads: {msg.get('text', {}).get('body')}"
                        )
                        await send_text_message(
                            msg.get("from"),
                            msg.get("text", {}).get("body", "")
                        )
                    else:
                        print(f"Received a non-text message: {msg.get('type')}")

                        await send_text_message(
                            msg.get("from"),
                            f"Received a non-text message of type: {msg.get('type')}"
                        )

    return {"success": True, "status": "Message received"}
