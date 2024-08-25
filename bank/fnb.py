import json
import os
import uuid

import pandas as pd
import psycopg2
from psycopg2 import extras
import requests
from requests.auth import HTTPBasicAuth

from RPA.Database import Database

class BankAPI:
    def __init__(self, client_id, client_secret, base_url, auth_url, db_config):
        self.client_id = client_id
        self.client_secret = client_secret
        self.access_token = None
        self.refresh_token = None
        self.base_url = base_url
        self.auth_url = auth_url
        self.db_config = db_config
        self.db_conn = None
        self.__auth_tokens()
    
    
    def connect_to_database(self):
        try:
            self.db_conn = psycopg2.connect(**self.db_config)
            print("Connection to the database was successful.")
            return self.db_conn
        except Exception as e:
            print(f"Failed to connect to the database: {e}")
            return None
    

    def insert_bank_transactions(self, db_conn, trans_df):
        """
        Insert multiple bank transactions into the database.

        Args:
            db_conn (psycopg2.extensions.connection): The database connection object.
            trans_df (pandas.DataFrame): A DataFrame containing the transaction history.

        Returns:
            None
        """
        try:
            with db_conn.cursor() as cur:
                # Prepare the SQL statement
                sql = """
                    INSERT INTO public.batch_transactions
                    (booking_date, value_date, remittance_info, reference,
                    amount, currency, credit_debit_indicator)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """

                # Prepare the data for batch insertion
                data = [
                    (
                        row['bookingDate'],
                        row['valueDate'],
                        row['remittanceInfo'],
                        row['reference'],
                        row['amount'],
                        row['currency'],
                        row['availableCreditDebitIndicator']
                    )
                    for _, row in trans_df.iterrows()
                ]

                psycopg2.extras.execute_batch(cur, sql, data)
                db_conn.commit()

                print(f"Successfully inserted {len(data)} transactions.")

        except (Exception, psycopg2.Error) as error:
            print(f"Error inserting transactions: {error}")
            db_conn.rollback()


    def disconnect_from_database(self):
        """
        Disconnect from the database by closing the connection.

        Args:
            db_conn: The database connection object to be closed.

        Returns:
            None
        """
        if self.db_conn is not None:
            try:
                self.db_conn.close()
                print("Database connection closed successfully.")
                self.db_conn = None
            except Exception as e:
                print(f"Error while closing database connection: {e}")
        else:
            print("No active database connection to close.")



    def __auth_tokens(self):
        """
        Authenticate with the FNB API and obtain an access token and refresh token.
        """
        # Scope for Transaction History API
        scope = 'i_can'
        
        # Request body for authentication
        auth_data = {
            'grant_type': 'client_credentials',
            'scope': scope
            }
    
        auth_response = requests.post(self.auth_url, data=auth_data, auth=HTTPBasicAuth(self.client_id, self.client_secret))
    
        # Check if authentication was successful
        if auth_response.status_code == 200:
            tokens = json.loads(auth_response.text)
            self.access_token = tokens['access_token']
            self.refresh_token = None
        else:
            print(f'Authentication failed with status code: {auth_response.status_code}')
            print(auth_response.text)
    

    def get_transaction_history(self, account_number, from_date, to_date):
        """
        Retrieve transaction history for a given account number and date range.
        
        Args:
            account_number (str): The account number for which to retrieve transaction history.
            from_date (str): The start date for the transaction history (YYYY-MM-DD).
            to_date (str): The end date for the transaction history (YYYY-MM-DD).
            
        Returns:
            dict: A dictionary containing the transaction history, or None if no transactions were found or an error occurred.
        """
        # API endpoint URL
        transaction_history_url = f'{self.base_url}/transaction-history/retrieve/v2/{account_number}'
        
        # Generate unique UUID header variables
        request_id = str(uuid.uuid4()) 
        idempotency_id = str(uuid.uuid4()) 
       
        headers = {
            'Authorization': f'Bearer {self.access_token}',
            'Content-Type': 'application/json',
            'X-Request-ID': request_id, 
            'X-Idempotency-ID': idempotency_id 
        }
        
        
        params = {
            'fromDate': from_date,
            'toDate': to_date
        }
        
        # Make the API call
        response = requests.get(transaction_history_url, headers=headers, params=params)
        
        # Check the response status code
        if response.status_code == 200:
            transactions = response.json()
            entries = transactions['entry']

            df = pd.json_normalize(entries)
            
            df = df.rename(columns={
                           'bookingDate.Date': 'bookingDate',
                           'valueDate.Date': 'valueDate',
                           'entryDetails.transactionDetails.remittanceInfo.unstructured': 'remittanceInfo',
                           'entryDetails.transactionDetails.reference.endToEndId': 'reference',
                           'amount.amount': 'amount',
                           'amount.currency': 'currency',
                           'availability.creditDebitIndicator': 'availableCreditDebitIndicator'
                       })
            
            df['amount'] = pd.to_numeric(df['amount']).abs()
            df['bookingDate'] = pd.to_datetime(df['bookingDate']).dt.date
            df['valueDate'] = pd.to_datetime(df['valueDate']).dt.date

            column_order = ['entryId', 'bookingDate', 'valueDate', 'remittanceInfo','reference', 'amount', 'currency', 
                'creditDebitIndicator', 'availableCreditDebitIndicator']
            
            df = df[column_order]
            df['discount'] = 0.0
            df['total'] = 0.0
                  
            return df
        elif response.status_code == 204:
            print('No transactions found')
            return None
        elif response.status_code == 401:
            # Access token expired, refresh token
            self.__refresh_access_token()
            if self.access_token:
                headers['Authorization'] = f'Bearer {self.access_token}'
                response = requests.get(transaction_history_url, headers=headers, params=params)
                if response.status_code == 200:
                    transactions = json.loads(response)
                    # Convert to DataFrame
                    df = pd.DataFrame.from_dict(transactions)
                    return df
                else:
                    print(f'Error: {response.status_code}')
                    return None
            else:
                print('Error refreshing token')
                return None
        else:
            print(f'Error: {response.status_code}')
            return None
        

    def __refresh_access_token(self):
        """
        Refresh the access token using the refresh token.
        """
        refresh_url = f'{self.base_url}/oauth2/token/v2'
        refresh_payload = {
            'grant_type': 'refresh_token',
            'refresh_token': self.refresh_token,
            'client_id': self.client_id,
            'client_secret': self.client_secret
        }
        
        refresh_response = requests.post(refresh_url, data=refresh_payload)

        if refresh_response.status_code == 200:
            refresh_data = refresh_response.json()
            self.access_token = refresh_data['access_token']
            self.refresh_token = refresh_data['refresh_token']
        else:
            print(f'Error refreshing token: {refresh_response.status_code}')
            self.access_token = None
            self.refresh_token = None    