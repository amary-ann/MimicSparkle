import os
import logging

from dotenv import load_dotenv
from pymongo import MongoClient
from motor.motor_asyncio import AsyncIOMotorClient

from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, PromptTemplate
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langchain_core.output_parsers import JsonOutputParser, StrOutputParser
from pydantic import BaseModel, Field
from models import Session

load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s',  handlers=[logging.FileHandler('app.log', mode='w'), logging.StreamHandler()])

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

llm_model_name = 'gpt-4o'

llm = ChatOpenAI(model = llm_model_name, temperature=0.2)

def get_chat_history(session):
    convo_string = ""
    messages = []
    user_query = ""
    for message in session.chats:
        if message.is_user:
            convo_string += f"Customer: {message.message}\n"
            messages.append(HumanMessage(content=message.message))
            
            # Set user_query to the last message from the user
            user_query = message.message
        else:
            convo_string += f"Mimic: {message.message}\n"
            messages.append(AIMessage(content=message.message))
    
    return convo_string, messages, user_query

def get_transaction_request(session: Session, request_type_prompt):
    convo_string, _, user_query = get_chat_history(session)
    request_type= PromptTemplate.from_template(request_type_prompt)
    request_chain = request_type | llm

    response = request_chain.invoke({"chat_history" : convo_string })

    return response

def get_default_response(session, general_prompt):
    """Handle the default response unrelated to transaction requests."""
    convo_string, _, user_query = get_chat_history(session)
    general_prompt = ChatPromptTemplate.from_template(general_prompt)

    general_chain = general_prompt | llm | JsonOutputParser()

    response = general_chain.invoke({
        'chat_history': convo_string
        })
    return response

def get_account_balance(session, account_balance_prompt):
    """Get the account balance from the chat history."""
    convo_string, _, user_query = get_chat_history(session)
    account_balance_prompt = ChatPromptTemplate.from_template(account_balance_prompt)
    account_balance_chain = account_balance_prompt | llm | JsonOutputParser()

    # change the logic here to retrieve account balance from database session
    # account_balance_process = SparkleHelper.account_balance(session)
    # account_balance = account_balance_process['data']['balance']

    acct_bal = account_balance_chain.invoke({
        "chat_history": convo_string,
        # "account_balance_info": account_balance
    })
    logging.info("Account balance extracted successfully!")
    return acct_bal

def recipient_type_detector(beneficiaries, session, recipient_type_detector):
    convo_string, _, user_query = get_chat_history(session)

    recipient_type_detector = ChatPromptTemplate.from_template(recipient_type_detector)
    
    smart_llm = ChatOpenAI(model = 'gpt-4o')

    recipient_type_chain = recipient_type_detector | smart_llm | JsonOutputParser()


    beneficiary_text = "\n".join(
        [f"-{b['name']} ({b['account_number']}, {b['bank']})" for b in beneficiaries]
    )

    response = recipient_type_chain.invoke({
        "beneficiaries":beneficiary_text, 
        "user_query": user_query,
        "chat_history": convo_string
        })

    logging.info(f"Recipient type!")
    return response


def transfer_qa(session, transfer_qa_prompt):
    """Handles other qa conversations"""
    convo_string, _, user_query = get_chat_history(session)
    # Transfer Phase Agents System Prompts
    transfer_qa_prompt = ChatPromptTemplate.from_template(transfer_qa_prompt)
    
    smart_llm = ChatOpenAI(model = 'gpt-4o')

    transfer_qa_chain = transfer_qa_prompt | smart_llm | JsonOutputParser()

    response = transfer_qa_chain.invoke({
        "user_query": user_query,
        "chat_history": convo_string
        })

    logging.info(f"QA Response Generated!")
    return response

def get_transfer_response(session, transfer_prompt):
    """Handle the transfer request."""
    convo_string, _, user_query = get_chat_history(session)
    # Transfer Phase Agents System Prompts
    transfer_prompt = ChatPromptTemplate.from_template(transfer_prompt)

    transfer_chain = transfer_prompt | llm | JsonOutputParser()

    # beneficiaries = find_beneficiary.invoke({"last_n_beneficiaries":5})

    # beneficiary_text = "\n".join(
    #     [f"-{b["name"]} ({b['account_number']}, {b['bank']})" for b in beneficiaries]
    # )

    response = transfer_chain.invoke({
        "user_query": user_query,
        "chat_history": convo_string
        })

    logging.info(f"Transfer Response Generated!")
    return response

def extract_beneficiary_details(session, recipient_store_prompt):
    """Extract beneficiary details from the chat history."""
    convo_string, _, user_query = get_chat_history(session)
    recipient_storage_prompt = ChatPromptTemplate.from_template(recipient_store_prompt)
    recipient_storage_chain = recipient_storage_prompt | llm | JsonOutputParser()

    store_recipient = recipient_storage_chain.invoke({
        "chat_history": convo_string
    })
    logging.info("Beneficiary details extracted successfully!")
    return store_recipient

def extract_transfer_details(session, transfer_details_prompt):
    """Extract transfer details from the chat history."""
    convo_string, _, user_query = get_chat_history(session)
    transfer_details_prompt = ChatPromptTemplate.from_template(transfer_details_prompt)
    transfer_details_chain = transfer_details_prompt | llm | JsonOutputParser()

    transfer_details = transfer_details_chain.invoke({
        "chat_history": convo_string
    })
    logging.info("Transfer details extracted successfully!")
    return transfer_details

def get_current_beneficiary_transfer_name(session, current_beneficiary_prompt):
    """Get the current beneficiary transfer name from the chat history."""
    convo_string, _, user_query = get_chat_history(session)
    current_beneficiary_prompt = ChatPromptTemplate.from_template(current_beneficiary_prompt)
    current_beneficiary_chain = current_beneficiary_prompt | llm | JsonOutputParser()

    current_beneficiary = current_beneficiary_chain.invoke({
        "chat_history": convo_string
    })
    logging.info("Current beneficiary transfer name extracted successfully!")
    return current_beneficiary

def beneficiary_transfer_response(session, beneficiary_details, beneficiary_transfer_prompt):
    """Handle the beneficiary transfer request."""
    convo_string, _, user_query = get_chat_history(session)
    beneficiary_transfer_prompt = ChatPromptTemplate.from_template(beneficiary_transfer_prompt)
    beneficiary_transfer_chain = beneficiary_transfer_prompt | llm | JsonOutputParser()

    response = beneficiary_transfer_chain.invoke({
        "chat_history": convo_string,
        "beneficiary_info": beneficiary_details,
    })
    logging.info("Beneficiary transfer response generated successfully!")
    return response

