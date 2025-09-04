import os
import uuid
import base64
import requests
import logging
from requests.structures import CaseInsensitiveDict
from dotenv import load_dotenv
from utils import get_institution_code

load_dotenv(override=True)
logging.basicConfig(level=logging.INFO,  
                    format='%(asctime)s - %(levelname)s - %(message)s',  
                    handlers=[logging.FileHandler('app.log', mode='w'), logging.StreamHandler()])

class VFD:
    def __init__(self):
        self.BaseUrl = os.getenv('VFD_PROD_BASE_URL')
        self.headers = CaseInsensitiveDict()
        self.headers['accept'] = '*/*'
        self.password = os.getenv('VFD_PROD_SECRET_KEY')

        if not self.password:
            raise Exception("VFD_PROD_SECRET_KEY environment variables not set!")
    
    def GetHealth(self):
        self.headers['X-Api-Key'] = f"{self.password}="
        
        response = requests.get(f"{self.BaseUrl}/wallet/health",
                                 headers=self.headers)
        
        if response.status_code == 200:
            logging.info("VFD API is healthy.")
        elif response.status_code != 200:
            raise Exception("VFD API is not healthy. Please check the service status.")
        else:
            raise Exception("An unexpected error occurred while checking VFD API health.")
        
        return "Successfully connected to VFD API"
    
    
    
    def TransferWithdraw(self, amount, receiverBank, receiverAccountNumber, narration="Withdrawal"):
        self.headers['X-Api-Key'] = f"{self.password}="

        receiverBankCode = get_institution_code(receiverBank)
        
        json = {
            "amount": amount,
            "receiverBankCode": receiverBankCode,
            "receiverAccountNumber": receiverAccountNumber,
            "narration": narration
        }
        
        response = requests.post(f"{self.BaseUrl}/wallet/vfd/withdraw",
                                 headers=self.headers, json=json)
        
        
        if response.status_code == 200:
            data = response.json()
            logging.info(f"Transfer successful: {data}")
            return data
        else:
            return data
    
vfd = VFD()
