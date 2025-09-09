
import os
import io
import re
import base64
import json
from openai import OpenAI
import requests
from datetime import datetime
import uuid
import aiohttp
import aiofiles
from io import BytesIO
from PIL import Image
import easyocr
import mimetypes
from PIL import Image, ImageDraw, ImageFont
from motor.motor_asyncio import AsyncIOMotorClient
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


def ImageCipher(ImagePath, Type = 'encryption'):
    image = Image.open(ImagePath)
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG")
    image_bytes = buffer.getvalue()
    if(Type == 'encryption'): 
        encoded_image = base64.b64encode(image_bytes).decode("utf-8")
        return encoded_image
    elif (Type == 'decryption'): 
        decoded_image = base64.b64decode(image_bytes).decode("utf-8")
        return decoded_image
    else : 
        raise ValueError("Invalid type of image operation, use encryption or decryption")
    
def is_image_url(text):
    return re.match(r'^https:\/\/api\.twilio\.com\/.*\/Media\/.*$', text)

def extract_text_from_twilio_image(url, sid, token):
    response = requests.get(url, auth=(sid, token))
    image = Image.open(BytesIO(response.content))
    text = pytesseract.image_to_string(image)
    return text

def clean_ocr_output(text: str) -> str:
    # Normalize escape characters
    text = text.replace('\\n', '\n').replace('\\t', '\t')  # if double-escaped
    text = re.sub(r'[\n\r\t]+', ' ', text)

    # Remove weird symbols but keep letters, numbers, periods, commas
    text = re.sub(r'[^a-zA-Z0-9.,\s-]', '', text)

    # Collapse multiple spaces
    text = re.sub(r'\s{2,}', ' ', text).strip()

    # Split into words
    words = text.split()

    cleaned_words = []
    for word in words:
        # Keep full account numbers (like 10+ digits)
        if re.fullmatch(r'\d{6,}', word):
            cleaned_words.append(word)
        # Keep normal words or capitalized names
        elif re.fullmatch(r'[A-Za-z]{3,}', word):
            cleaned_words.append(word)
        # Keep things like "Access" or "bank"
        elif word.lower() in {'access', 'bank', 'gtbank', 'zenith', 'first', 'uba'}:
            cleaned_words.append(word)
        # Optionally allow numbers with dots (e.g. 1.25), but not letters mixed with digits
        elif re.fullmatch(r'\d+\.\d+', word):
            cleaned_words.append(word)
        # Everything else is considered junk and skipped

    return ' '.join(cleaned_words)
    

def most_recent_beneficiaries(phone_number, last_n_beneficiaries:int = 5):
    """Retrieve the last n number of beneficiaries from database storage"""
    mongo_string = "mongodb+srv://gerleojerry:5InOFZFPn8zoTSBV@mimic.0zr7s.mongodb.net/?retryWrites=true&w=majority&appName=Mimic"

    mongo_client = AsyncIOMotorClient(mongo_string)
    db = mongo_client["sparkle"]
    collection = db['sessions']

    pipeline =[
        {"$match": {"phone_number": phone_number}},
        {
            "$project": {
                "last_five_beneficiaries": {
                    "$slice": [
                        {"$reverseArray": {
                                "$sortArray": {
                                    "input": "$beneficiary",
                                    "sortBy": {"created_at": -1}
                                }
                            }
                        },
                        last_n_beneficiaries
                    ]
                }
            }
        }
    ]

    cursor = collection.aggregate(pipeline)
    result = cursor.to_list(length=1)

    if result:
        return result
    return []
        


def get_institution_code(bank_name):
    with open("banks.json", "r", encoding="utf-8") as f:
        loaded_banks = json.load(f)

    for bank in loaded_banks["bank"]:
        if bank["name"].lower() == bank_name.lower():
            return bank["code"]
    return None

async def get_media_bytes_async(mime_type, media_id:str):
    media_info_url = f"{os.getenv('BASE_URL')}/{os.getenv('API_VERSION')}/{media_id}"
    headers = {
        "Authorization": f"Bearer {os.getenv('WHATSAPP_ACCESS_TOKEN')}"
    }
    async with aiohttp.ClientSession() as session:
        try:
            print("Fetching media info from:", media_info_url)
            # Get the media metadata (to extract download URL)
            async with session.get(media_info_url, headers=headers) as resp:
                if resp.status != 200:
                    print(f"Failed to get media URL: {resp.status}")
                    return None

                media_info = await resp.json()
                download_url = media_info.get("url")
                print("Fetched media info:", media_info)
                if not download_url:
                    print("⚠️ No download URL found in media info")
                    return None
                
                # Step 2: Guess file extension
                ext = mimetypes.guess_extension(mime_type) or ""
                
                # Download the media content
                async with session.get(download_url, headers=headers) as download_resp:
                    if download_resp.status == 200:
                        print("Successfully downloaded media content")
                        media_bytes = await download_resp.read()
                        return ext, media_bytes
                    else:
                        print(f"Error downloading media: {download_resp.status}")
                        return None
        except Exception as e:
            print("Connection Error:", str(e))
            return None
        
async def save_media_to_file(mime_type, media_id: str, filename: str | None = None) -> str | None:
    result = await get_media_bytes_async(mime_type,media_id)
    if not result:
        return None

    ext, media_bytes = result
    filename = filename or f"{media_id}{ext}"

    async with aiofiles.open(filename, "wb") as f:
        await f.write(media_bytes)

    print(f"✅ Saved media as {filename}")
    return filename


def ocr_space_file(filename, overlay=False, api_key=os.getenv("OCR_API_KEY"), language='eng'):
    """ OCR.space API request with local file.
        Python3.5 - not tested on 2.7
    :param filename: Your file path & name.
    :param overlay: Is OCR.space overlay required in your response.
                    Defaults to False.
    :param api_key: OCR.space API key.
                    Defaults to 'helloworld'.
    :param language: Language code to be used in OCR.
                    List of available language codes can be found on https://ocr.space/OCRAPI
                    Defaults to 'en'.
    :return: Result in JSON format.
    """

    payload = {'isOverlayRequired': overlay,
               'apikey': api_key,
               'language': language,
               }
    with open(filename, 'rb') as f:
        r = requests.post('https://api.ocr.space/parse/image',
                          files={filename: f},
                          data=payload,
                          )
    return r.content.decode()


# def ocr_space_url(url, overlay=False, api_key='helloworld', language='eng'):
#     """ OCR.space API request with remote file.
#         Python3.5 - not tested on 2.7
#     :param url: Image url.
#     :param overlay: Is OCR.space overlay required in your response.
#                     Defaults to False.
#     :param api_key: OCR.space API key.
#                     Defaults to 'helloworld'.
#     :param language: Language code to be used in OCR.
#                     List of available language codes can be found on https://ocr.space/OCRAPI
#                     Defaults to 'en'.
#     :return: Result in JSON format.
#     """

#     payload = {'url': url,
#                'isOverlayRequired': overlay,
#                'apikey': api_key,
#                'language': language,
#                }
#     r = requests.post('https://api.ocr.space/parse/image',
#                       data=payload,
#                       )
#     return r.content.decode()


# Use examples:
def process_audio_bytes(audio_bytes: bytes) -> str:
    client = OpenAI()
    # Save to a temporary file (Whisper needs file-like object)
    with open("temp_audio.ogg", "wb") as f:
        f.write(audio_bytes)
    
    with open("temp_audio.ogg", "rb") as f:
        transcript = client.audio.transcriptions.create(
            model="gpt-4o-transcribe",
            file=f
        )
    return transcript.text

def generate_invoice(transfer_details):
    
    amount = transfer_details.get('amount')
    receiverName = transfer_details.get('receiverName', 'Unknown')
    receiverBank = transfer_details.get('receiverBank')
    receiverAccountNumber = transfer_details.get('receiverAccountNumber')

    # Create blank image
    img = Image.new('RGB', (600, 300), color='white')
    draw = ImageDraw.Draw(img)
    
    # Fonts
    try:
        font_bold = ImageFont.truetype("arialbd.ttf", 28)
        font_regular = ImageFont.truetype("arial.ttf", 20)
    except:
        font_bold = font_regular = None  # fallback if fonts not available

    # Draw content
    draw.text((50, 30), "Transfer Successful!", fill="green", font=font_bold)
    draw.text((50, 90), "Amount:", font=font_bold, fill="black")
    draw.text((200, 90), f"{amount}", font=font_regular, fill="black")

    draw.text((50, 130), "To:", font=font_bold, fill="black")
    draw.text((200, 130), f"{receiverName}", font=font_regular, fill="black")

    draw.text((50, 170), "Account:", font=font_bold, fill="black")
    draw.text((200, 170), f"******{receiverAccountNumber[-4:]}", font=font_regular, fill="black")

    draw.text((50, 210), "Bank:", font=font_bold, fill="black")
    draw.text((200, 210), f"{receiverBank}", font=font_regular, fill="black")

    draw.text((50, 250), "Date:", font=font_bold, fill="black")
    draw.text((200, 250), datetime.now().strftime("%Y-%m-%d %H:%M"), font=font_regular, fill="black")

    # Reference
    ref = str(uuid.uuid4())[:8]
    # Optional footer
    draw.text((50, 280), f"Ref: {ref}", font=font_regular, fill="gray")

    # Save image with unique filename
    filename = f"invoice_{ref}.png"
    path = os.path.join("invoices", filename)
    
    os.makedirs("invoices", exist_ok=True)  # Ensure directory exists
    img.save(path)

    with open(path, 'rb') as image_file:
        encoded_image = base64.b64encode(image_file.read()).decode('utf-8')
        response = requests.post(
            "https://api.imgbb.com/1/upload",
            data={
            "key": "421b23434663c0f95a5690f45231107f",
            "image": encoded_image
        }
        )
    
    # Check and print the image link
    if response.status_code == 200:
        image_url = response.json()['data']['url']
        print('Uploaded to ImgBB:', image_url)
        return image_url
    else:
        print('Upload failed:', response.json())
        return None


