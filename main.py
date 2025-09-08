import os
import json
import logging
import aiohttp
import uvicorn
from prompts import GENERAL_BOT_PROMPT, REQUEST_DETECTOR_PROMPT, TRANSFER_QA_PROMPT, RECIPIENT_TYPE_DETECTOR, TRANSFER_AGENT_SYSTEM_PROMPT, RECIPIENT_STORE_PROMPT, TRANSFER_DETAILS_PROMPT, CURRENT_BENEFICIARY_TRANSFER_PROMPT, BENEFICIARY_TRANSFER_PROMPT 
from trans_req import recipient_type_detector,get_default_response,transfer_qa, get_transaction_request, get_transfer_response, extract_beneficiary_details, extract_transfer_details, get_current_beneficiary_transfer_name, beneficiary_transfer_response, get_account_balance
from pprint import pprint
from typing import Optional
from datetime import datetime, timezone
from starlette.status import HTTP_403_FORBIDDEN
from dotenv import load_dotenv
from fastapi import FastAPI, Request, Security, HTTPException, Depends
from fastapi.security.api_key import APIKeyHeader
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie
from langchain_core.prompts import ChatPromptTemplate, PromptTemplate
from vfd_helper import VFDHelper
from utils import get_whatsapp_no_format, send_message, most_recent_beneficiaries, generate_invoice, is_image_url, extract_text_from_twilio_image, get_media_url_async
from models import MsgRequest, AppResponse,  Session, Message, User, Beneficiary,PinRequest, Pin, RegPinRequest, NotifyRequest, Balance

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

API_KEY = os.getenv("PROD_API_KEY")
API_KEY_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

async def get_api_key(api_key: str = Security(api_key_header)):
    if api_key == API_KEY:
        return api_key
    raise HTTPException(
        status_code=HTTP_403_FORBIDDEN, detail="Could not validate credentials"
    )

@app.get("/")
async def root():
    return {"message": "Mimic for Sparkle Meta WhatsApp API"}

@app.post("/notify")
async def notify(request:NotifyRequest, api_key: str = Depends(get_api_key)):

    user_acct = await Balance.find_one({"account_number":request.accountNumber})
    user =  await User.find_one({"account_number": request.accountNumber})
    phone_number = user.phone_number
    name = user.first_name

    if user_acct:
        user_acct.balance += request.amount
    await user_acct.save()

    result = f"Hi {name},\n\nYour account has been credited with *NGN {request.amount}* from {request.originatorAccountName}.\nYour new balance is *NGN {user_acct.balance}*.\nThank you for banking with us."
    whatsapp_msg = await send_text_message(phone_number, result)

    if whatsapp_msg:
        info = {"status": "sent", "sid": whatsapp_msg.sid}
        logging.info(f"{info}")
        return {"status":"success", "detail": "Successfully notified"} 
    else:
        return {"status":"failed", "detail": "Message not sent"} 

@app.post("/register-pin")
async def register_pin(request: RegPinRequest):

    session = await Session.find_one({"phone_number": request.phone_number})

    pin_data = Pin(pin=request.pin, confirm_pin=request.confirm_pin, phone_number=request.phone_number)
    await pin_data.insert()

    result="Congratulations 😃, you have completed your registration! Thank you for Joining us.\n\nI'm Mimic, an AI chatbot for Sparkle, here to help with all your bank transactions with Sparkle.\nYou can choose any from the menu below.\n 1. Perform Transfer\n2. Check Account Balance"

    if result:
        message = Message(message=result, is_user=False)
        session.chats.append(message)
        await session.save()

        logging.info("Bot response saved to session.")
        whatsapp_msg = await send_text_message(request.phone_number, result)
        if whatsapp_msg:
            info = {"status": "sent", "sid": whatsapp_msg.sid}
            logging.info(f"{info}")
            return {"success": True, "detail": "Pin created successfully"} 
        else:
            return {"success": True, "detail": "Message not sent"} 

@app.post("/verify-transaction")
async def verify_transaction(request: PinRequest):
    user = await Pin.find_one({"phone_number": request.phone_number})
    user_pin = user.confirm_pin
    if user_pin:
        # Define the correct PIN here
        if not request.pin.isdigit() or len(request.pin) != 6:
            raise HTTPException(status_code=400, detail="PIN must be exactly 6 digits")
        
        # Check if PIN is correct
        if request.pin != user_pin:
            raise HTTPException(status_code=401, detail="Incorrect PIN")
        
        session = await Session.find_one({"phone_number": request.phone_number})
        user_acct = session.account_number
        user_bal = await Balance.find_one({"account_number":user_acct})
        
        if session:
            # Extract transfer details to process transfer
            transfer_details = extract_transfer_details(session, TRANSFER_DETAILS_PROMPT)
            print("Transfer Details of new recipient transfer process: ", transfer_details)

            process_transfer = VFDHelper.transfer_withdraw(session, transfer_details)
            print("Transfer endpoint output: ",process_transfer)

            #Extract recipient details to store as beneficiary
            extracted_recipient = extract_beneficiary_details(session,RECIPIENT_STORE_PROMPT)
        
            # Store recipient details as beneficiary in database
            beneficiary = Beneficiary(phone_number = request.phone_number, name = extracted_recipient["receiverName"], account_number = extracted_recipient["receiverAccountNumber"],bank = extracted_recipient["receiverBank"]) 
            await beneficiary.insert()
            logging.info("Beneficiary details saved to database.")

            # Store beneficiary details in session
            if beneficiary:
                session.beneficiary.append(beneficiary)
                await session.save()
            logging.info("Beneficiary details saved to session.")
            
            image_url = generate_invoice(transfer_details)
            if process_transfer['status'] == '00':
                user_bal.balance -= float(transfer_details.get('amount'))
                result = f"Great news! 🎉 Your transaction was completed successfully.\nIf you have any questions or need help with anything else, feel free to reach out!"
                media_url = image_url
                await user_bal.save()
            else:
                result = f"{process_transfer['message']}"
                
            session.transfer_prompt_shown = False
            session.recipient_type = None  # Reset recipient type for next interaction
            await session.save()
            
        if result:
            message = Message(message=result, is_user=False)
            session.chats.append(message)
            await session.save()
            whatsapp_msg = await send_text_message(request.phone_number, result)
            if whatsapp_msg:
                info = {"status": "sent", "sid": whatsapp_msg.sid}
                logging.info(f"{info}")
                return {'success' : True, 'message' : "Pin Successfully validated"}
            else:
                return {"success": True, "detail": "Message not sent"} 
        

@app.post('/create')
async def create_user(request: User) : 
    try: 
        user = await User.find_one({'phone_number' : request.phone_number})
        logging.info(f"User : {user}")

        if user: 
            return {'success' : False, 'message' : "User already exist."}     

        new_user = User(phone_number = request.phone_number, first_name = request.first_name, last_name = request.last_name, email = request.email, address = request.address, dob = request.dob, bvn = request.bvn, account_number = request.account_number,account_link = request.account_link, is_account_active=False)

        new_user_balance = Balance(account_number=request.account_number)

        await new_user.insert()
        await new_user_balance.insert()

        response_message : str = f"🎉 Congratulations, {request.first_name}!, Your registration was successful — we're thrilled to have you on board! \nYour account number is {request.account_number}.\nBefore we move forward, a six digit pin was sent to your phone number via SMS, please take a moment to verify your account by filling the link with the code sent to you: 👉 {request.account_link}\nOnce you've completed the verification, please create your transaction pin here 👉 https://amary-ann.github.io/register-pin/. Thank you!"

        new_user.is_account_active = True
        await new_user.save()

        PhoneNo = request.phone_number

        if( PhoneNo[0] ==  "0"):
            phone = PhoneNo[1:]
        elif (PhoneNo[:2] ==  "234"):
            phone = PhoneNo[2:]
        elif (PhoneNo[:3] ==  "+234"):
            phone = PhoneNo[3:]
        else:
            phone = PhoneNo

        whatsapp_msg = await send_text_message(phone, response_message)
        if whatsapp_msg:
            info = {"status": "sent", "sid": whatsapp_msg.sid}
            logging.info(f"{info}")
            return {'success' : True, 'message' : "User created successfully."}
        else:
            return {"success": True, "detail": "Message not sent"} 

    except: 
        return {'success' : False, 'message' : "Error while creating new user."}
    

@app.post('/send_message')
async def send_message_endpoint(msgreq: MsgRequest):
  phone_number = get_whatsapp_no_format(msgreq.phone_number)
  data = send_message(phone_number
                                ,msgreq.message)
  logging.info(f"Content: {pprint(data)}")
  await send_message(data)
  return {"status": "Message sent"}


# Send response to WhatsApp User
async def _post(data: dict):
        headers = {
    "Content-type": "application/json",
    "Authorization": f"Bearer {os.getenv('WHATSAPP_ACCESS_TOKEN')}",
    }
        async with aiohttp.ClientSession() as session:
            url = f"{os.getenv('BASE_URL')}/{os.getenv('API_VERSION')}/{os.getenv('PHONE_NUMBER_ID')}/messages"
            try:
                async with session.post(url, json=data,headers=headers) as resp:
                    if resp.status != 200:
                        return {"success":False, "message":"Error occurred"}
                    return {"success":True, "message":"Successful operation"}
            except Exception as e:
                logging.error(f"Error sending message: {e}")
                return {"success":False, "message": str(e)}

# Text message handler
async def process_message(to: str, text: str):
        
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

            request_type = get_transaction_request(session,REQUEST_DETECTOR_PROMPT)
            print(request_type.content)
        
            if(request_type.content == "default"):
                res = get_default_response(session, GENERAL_BOT_PROMPT)
                response = res['response_message']
                print("Default", response)
                
            elif(request_type.content == "qa"):
                res  = transfer_qa(session, TRANSFER_QA_PROMPT)
                result = res['response_message']
                media_url = None
                print("Transfer QA response", result)

            elif(request_type.content == "account_balance"):
                user_acct = user.account_number 
                user_bal = await Balance.find_one({"account_number":user_acct})
                balance = user_bal.balance
                result = f"Your account balance is *NGN {balance}* at *{datetime.now(timezone.utc).strftime('%d-%m-%Y %H:%M:%S')}* "
                media_url = None

            elif(request_type.content == "transfer"):
                    # Check if user already saw the transfer prompt
                if not session.transfer_prompt_shown:
                    recent_beneficiaries = await most_recent_beneficiaries(to)
                    lastfive = recent_beneficiaries[0]['last_five_beneficiaries']

                    if recent_beneficiaries and 'last_five_beneficiaries' in recent_beneficiaries[0]:
                        lastfive = recent_beneficiaries[0]['last_five_beneficiaries']
                    else:
                        lastfive = []
                        
                    if lastfive:
                        beneficiaries = "\n".join(
                            [f"-{b['name']} ({b['account_number']}, {b['bank']})" for b in lastfive]
                        )
                        response = f"🤔 We noticed you recently transferred to: {beneficiaries}. Would you like to send money to one of your saved beneficiaries again, or make a transfer to someone new?\nLet me know how you'd like to proceed — I'm here to help! 💬"
                    else:
                        response = "Hi there! 👋 It looks like you don’t have any beneficiaries yet — no worries at all!.\nYou can still make a transfer to a new recipient.\nReady to get started?"

                    # Save flag to session
                    session.transfer_prompt_shown = True
                    await session.save()

                    # Return early and wait for user reply
                    message = Message(message=result, is_user=False)
                    session.chats.append(message)
                    await session.save()
                    whatsapp_msg = await send_text_message(to, response)
                    logging.info("Prompted user with beneficiaries. Awaiting reply.")
                    if whatsapp_msg:
                        return {"status": "sent", "sid": whatsapp_msg.sid}
                    else:
                        return {"status": "error", "detail": "Message not sent"}
            
            recent_beneficiaries = await most_recent_beneficiaries(to)

            print("Recent beneficiaries:", recent_beneficiaries)

            lastfive = recent_beneficiaries[0]['last_five_beneficiaries'] 
            print("Five beneficiaries: ",lastfive)

            # Detect recipient type once and store in session
            if not session.recipient_type or session.recipient_type is None:
                recipient_type_data = recipient_type_detector(lastfive, session, RECIPIENT_TYPE_DETECTOR)
                session.recipient_type = recipient_type_data['recipient_type']
                await session.save()
                logging.info("Recipient type detected and saved: %s", session.recipient_type)
            else:
                logging.info("Using cached recipient type: %s", session.recipient_type)

            recipient_type = session.recipient_type
            logging.info("Recipient type detected:", recipient_type)

            if recipient_type == "new":
                logging.info("Entered the new recipient phase!")
                # Pass to the model for transfer
                transfer_response = get_transfer_response(session, TRANSFER_AGENT_SYSTEM_PROMPT)

                logging.info("Transfer response:", transfer_response)

                response = transfer_response['response_message']
            
            elif recipient_type == "old":
                logging.info("Entered the beneficiary phase!")
                current_beneficiary = get_current_beneficiary_transfer_name(session, CURRENT_BENEFICIARY_TRANSFER_PROMPT)
                beneficiary_name = current_beneficiary['beneficiary_name']
                if beneficiary_name is None:
                    response = current_beneficiary['response_message']
                else:
                    current_recipient = Beneficiary.find({"phone_number": to, "name": { "$regex": beneficiary_name, "$options": "i" }},
                                                            {
                                                                    "_id": 0,
                                                                    "name": 1,
                                                                    "account_number": 1,
                                                                    "bank": 1
                                                            }
                                                        )
                        
                    beneficiary_transfer = beneficiary_transfer_response(session, current_recipient,BENEFICIARY_TRANSFER_PROMPT)

                    response = beneficiary_transfer['response_message']
            else:
                if lastfive:
                    beneficiaries = "\n".join(
                        [f"-{b['name']} ({b['account_number']}, {b['bank']})" for b in lastfive]
                    )
                print("Beneficiaries:", beneficiaries)
                response = f"We noticed you recently transferred to: {beneficiaries}. Would you like to send money to one of your saved beneficiaries again, or make a transfer to someone new?\nLet me know how you'd like to proceed — I'm here to help! 💬"
                session.recipient_type = None  # Reset recipient type for next interaction
                await session.save()
            
        print("Response after transfer:", response)
        
        if response:
            message = Message(message=response, is_user=False)
            session.chats.append(message)
            await session.save()
            logging.info("Bot response saved to session.")
            whatsapp_msg = await send_text_message(to, response)
            if whatsapp_msg:
                return {"success": True, "detail":"Message sent"}
            else:
                return {"success": False, "detail": "Message not sent"}
            
async def send_text_message(to:str, text: str, preview_url: bool = False):
        
    print(f"Bot response: {text}")
    return await _post({
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to,
        "type": "text",
        "text": {"preview_url": preview_url, "body": text}
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
                        await process_message(
                            msg.get("from"),
                            msg.get("text", {}).get("body", "")
                        )
                    elif msg.get("type") == "image":
                        media_content_type = msg.get("image",{}).get("mime_type", "")
                        message_body = await get_media_url_async( msg.get("image",{}).get("id", None))

                        # message_body = msg.get("image",{}).get("caption","")

                        # msg_content = f"Image Message content: {msg}"
                        print(f"{message_body=}")
                        await send_text_message(
                            msg.get("from"),
                            message_body
                        )


                    elif msg.get("type") == "audio":
                        media_content_type = msg.get("audio",{}).get("mime_type", "")
                        # media_url = await get_media_url_async( msg.get("audio",{}).get("id", None))

                        msg_content = f"Audio Message content: {msg}"
                        print(msg_content)
                        await send_text_message(
                            msg.get("from"),
                            msg_content
                        )

                    else:
                        print(f"Received an unsupported message type {msg.get('type')}")

                        await send_text_message(
                            msg.get("from"),
                            f"Received an unsupported message of type: {msg.get('type')}"
                        )

    return {"success": True, "status": "Message received"}
