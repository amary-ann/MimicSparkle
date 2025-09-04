import json
from vfd_integration import vfd
from models import Session
import logging
logging.basicConfig(level=logging.INFO,  
                    format='%(asctime)s - %(levelname)s - %(message)s',  
                    handlers=[logging.FileHandler('app.log', mode='w'), logging.StreamHandler()])

class VFDHelper:
    def transfer_withdraw(session, transfer_details):
        try:
            amount = transfer_details.get('amount')
            receiverBank = transfer_details.get('receiverBank')
            receiverAccountNumber = transfer_details.get('receiverAccountNumber')
            # narration = transfer_details.get('narration', "Test Withdraw")

            transfer_process = vfd.TransferWithdraw(amount, receiverBank, receiverAccountNumber)
            logging.info("Transfer initiated")

            if not session.is_transfer_initiated:
                session.is_transfer_initiated = True
            session.save()

            logging.info(f"Transfer process:{transfer_process}")

            return transfer_process
            
        except Exception as e:
            logging.info("Exception - ", e)
            return "An error occurred"
