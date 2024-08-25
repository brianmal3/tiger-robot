import json
import logging
import os
import re
import time
import zipfile
from datetime import datetime, timedelta

import pandas as pd
import psycopg2
from dotenv import load_dotenv
from fpdf import FPDF
from O365 import Account
from O365.utils.token import FileSystemTokenBackend
import requests
from robocorp import vault
from robocorp.tasks import task

from RPA.Database import Database
from bank.fnb import BankAPI
from recon.recon_process import RECON

load_dotenv()

transactions = []
tag = "🥦🥦🥦 FNB Robot 🥦"


# http://localhost:8080/fnb/getFakeTransactions
@task
def start():
    """Connect to Backend to get Transactions"""
    status = os.getenv("STATUS")
    url = os.getenv("REMOTE_URL")
    if status == "dev":
        url = os.getenv("LOCAL_URL")

    try:
        f_url = f"{url}fnb/getFakeTransactions"
        print(f"{tag} Connecting to Backend ...: {f_url}")
        resp = requests.get(f_url)
        if resp.status == 200:
            transactions = resp.json()
            print(f"{tag} response is OK : {len(transactions)}")

    except Exception as e:
        print(f"{tag} Error connecting to Backend: {str(e)}")


@task
def reconcile_fnb_transactions():
    
    client_id = os.getenv('CLIENT_ID')
    client_secret = os.getenv('CLIENT_SECRET')
    base_url = os.getenv('BASE_URL')
    auth_url = os.getenv('AUTH_URL')
    dannys_account_number = os.getenv('SETTLEMENT_ACC')
    
    current_date = (datetime.now().date()) + timedelta(days=1)
    from_date = current_date - timedelta(days=1)
    
    from_date_str = from_date.strftime("%Y-%m-%d")
    to_date_str = current_date.strftime("%Y-%m-%d")
    
    db_config = {
        'host': os.getenv('HOST'),
        'database': os.getenv('DATABASE'),
        'user': 'postgres',
        'password': os.getenv('PASSWORD')
    }

    # Initialize the FNB client
    fnb = BankAPI(client_id, client_secret, base_url, auth_url, db_config)
    
    # Step 1: authorize and get fnb transactions
    trans_df = fnb.get_transaction_history(dannys_account_number, from_date_str, to_date_str) 
    
    db_conn = fnb.connect_to_database()
    
    # Step 2: Insert transactions to db
    if db_conn is None:
        print("Error: No database connection available.")

    try:
        if not trans_df.empty:
            # Step 3: Recon transactions
            recon_client = RECON(trans_df)
            recon_client.process_transactions(trans_df, db_conn)
        else:
            print("No transactions to process.")
    except Exception as e:
        print(f"Error processing transactions: {str(e)}")
    finally:
        fnb.disconnect_from_database()
