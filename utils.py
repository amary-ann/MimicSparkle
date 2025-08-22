
import os
import json
import aiohttp
from prompts import GENERAL_PROMPT
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, PromptTemplate
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage


# Function to format phone numbers for WhatsApp
def get_whatsapp_no_format(phone_number: str) -> str:
    """
    Formats the phone number to the WhatsApp format.
    :param phone_number: The phone number to format.
    :return: The formatted phone number.
    """
   
    if( phone_number[0] ==  "0"):
        phone = "+234" + phone_number[1:]
    elif (phone_number[:2] ==  "234"):
        phone = "+" + phone_number
    elif (phone_number[:3] ==  "+234"):
        phone = phone_number
    else:
        phone = "Please enter a valid phone number"

    print("Formatted phone number:", phone)
    return phone

# Function to create a JSON message input for WhatsApp
def get_message_input(recipient, data='Hello!', type="text"):
    
    if type == "text":
        OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
        llm_model_name = 'gpt-4o'
        llm = ChatOpenAI(model = llm_model_name, temperature=0.2)
        chat_template = ChatPromptTemplate([
            SystemMessage(content=GENERAL_PROMPT),
            HumanMessage(content='{user_message}'),
        ])
        
        bot_response = chat_template.invoke({"user_message":data})
        print(f"Bot response: {bot_response.content}")

        return json.dumps({
        "messaging_product": "whatsapp",
        "preview_url": False,
        "recipient_type": "individual",
        "to": recipient,
        "type": type,
        "text": {
            "body": bot_response.content
        }
  })
    else:
        return json.dumps({
        "messaging_product": "whatsapp",
        "preview_url": False,
        "recipient_type": "individual",
        "to": recipient,
        "type": 'text',
        "text": {
            "body": data
        }
        })

# Function to send a message via WhatsApp API
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

