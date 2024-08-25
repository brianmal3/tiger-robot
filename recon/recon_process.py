import logging
import re
from datetime import datetime
from pathlib import Path

import pandas as pd
import numpy as np
import psycopg2
from fpdf import FPDF
from O365 import Account
from O365.utils.token import FileSystemTokenBackend
from robocorp import vault

#todo - study in detail
class RECON:
    def __init__(self, trans_data):
        self.trans_data = trans_data
        self.run_count = {} 
    
    
    def extract_customer_id(self, row):
        customer_id = self._extract_from_text(row.get('remittanceInfo'))
        if customer_id:
            return customer_id

        customer_id = self._extract_from_text(row.get('reference'))
        if customer_id:
            return customer_id

        return None


    def _extract_from_text(self, text):
        # Helper function to extract customer ID from a given text
        if text:
            match = re.search(r'ADT CASH DEPO\d+\s([A-Z]{3}\d{2})', text, re.IGNORECASE)
            if match:
                return '101' + match.group(1).upper()
            
            match = re.search(r'\b(101[A-Z]{2}\d{3})\b', text, re.IGNORECASE)
            if match:
                return match.group(1).upper()
            else:
                # Special case: Extract customer IDs from other longer strings
                special_cases = [
                    r'(?<!\d)(101[A-Z]{3}\d{2})(?=\w)',
                    r'(?<!\d)([A-Z]{3}\d{2})(?=\w)',
                    r'(?<!\d)(101[A-Z]{3}\d{2})', 
                    r'(?<!\d)([A-Z]{3}\d{2})'           
                ]
                
                for pattern in special_cases:
                    match = re.search(pattern, text, re.IGNORECASE)
                    if match:
                        return '101' + match.group(1).upper() if not match.group(1).startswith('101') else match.group(1).upper()

            match = re.search(r'\b(101[A-Za-z]{3}\d{2}|([A-Za-z]{3}\d{2}))\b', text, re.IGNORECASE)
            if match:
                return '101' + match.group(2).upper() if match.group(2) else match.group(1).upper()

            # Match for customer IDs preceded by other text, including those that may be part of longer strings
            match = re.search(r'\b(101[A-Za-z]{3}\d{2})\b', text)
            if match:
                return match.group(1).upper()

            match = re.search(r'\b([A-Za-z]{3}\d{2})\b', text)
            if match:
                return '101' + match.group(1).upper()

            match = re.search(r'([A-Za-z]{3})\s(\d{2})', text)
            if match:
                return '101' + match.group(1).upper() + match.group(2)

        return None

    def read_and_apply_discounts(self, df, db_connection):
        """
        Read transactions, apply discounts, and merge with customer data.

        Args:
            df (pandas.DataFrame): DataFrame containing transaction data.
            db_connection (psycopg2.extensions.connection): The database connection object.

        Returns:
            tuple:
                - pandas.DataFrame: DataFrame with applied discounts and customer information.
                - pandas.DataFrame: DataFrame of unmatched transactions.
                - pandas.DataFrame: Original copy of unmodified bank transactions.
        """

        df_trans_cpy = df.copy() 
        #unmatched_transactions = pd.DataFrame()
        try:
            with db_connection.cursor() as cur:
                query = "SELECT username AS customer_id, payment_terms FROM crm.customers"
                cur.execute(query)
                customers_df = pd.DataFrame(cur.fetchall(), columns=['customer_id', 'payment_terms'])

            df['customer_id'] = df.apply(self.extract_customer_id, axis=1)
            df['reference'] = df['customer_id']

            df = df.merge(customers_df, how='left', on='customer_id')

            unmatched_trans_df = df[df['payment_terms'].isnull()]

            # Apply 10% discount on ALL 31-DAY debtor accounts 
            df['discount'] = df.apply(lambda row: (round((df['amount'] / 90) * 100, 2)[row.name] - row['amount']) 
                                      if row['payment_terms'] == '10% STRICTLY 31 DAYS' and round((df['amount'] / 90) * 100, 2)[row.name] > 0 
                                      else 0,
                                      axis=1
                                      )

            df['discount'] = df['discount'].astype(float).round(2)
           
            return df, unmatched_trans_df, df_trans_cpy

        except (Exception, psycopg2.Error) as error:
            print(f"Error in read_and_apply_discounts: {error}")
            return df, unmatched_trans_df, df_trans_cpy
    
        
    def apply_discount_at_transaction_level(self, df):
        df['total'] = df.apply(lambda row: row['amount'] + row['discount'], axis=1)
        return df
    

    def insert_batch(self, db_conn, branch_code, batch_date, operator_name, sub_total, discount, total):
        try:
            insert_batch_query = """
            INSERT INTO fin.batch (branch_code, batch_date, operator_name, sub_total, discount, total, posted)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING batch_id
            """
              
            batch_data = (branch_code, batch_date, operator_name, float(sub_total), float(discount), float(total), False)

            with db_conn.cursor() as cur:
                cur.execute(insert_batch_query, batch_data)
                result = cur.fetchone()
                print("Batch inserted successfully.")
                return result[0]

        except Exception as e:
            print(f"Error while inserting batch into PostgreSQL: {e}")
            return None


    def check_batch_balance(self, df, sub_total, discount, total):
        return df['amount'].sum() == sub_total and df['discount'].sum() == discount and df['total'].sum() == total

   
    def insert_bank_transactions(self, db_conn, trans_df, batch_id):
        """
        Insert multiple bank transactions into the database.

        Args:
            db_conn (psycopg2.extensions.connection): The database connection object.
            trans_df (pandas.DataFrame): A DataFrame containing the transaction history.
            batch_id (str): The ID of the batch associated with the transactions.

        Returns:
            None
        """
        try:
            with db_conn.cursor() as cur:
                sql = """
                    INSERT INTO fin.batch_transactions
                    (booking_date, value_date, remittance_info, reference,
                    amount, discount, currency, credit_debit_indicator, batch_id)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """

                data = [
                    (
                        row['bookingDate'],
                        row['valueDate'],
                        row['remittanceInfo'],
                        row['reference'],
                        row['amount'],
                        row['discount'],
                        row['currency'],
                        row['availableCreditDebitIndicator'],
                        batch_id
                    )
                    for _, row in trans_df.iterrows()
                ]

                psycopg2.extras.execute_batch(cur, sql, data)
                db_conn.commit()

                print(f"Successfully inserted {len(data)} transactions.")

        except (Exception, psycopg2.Error) as error:
            print(f"Error inserting transactions: {error}")
            db_conn.rollback()


    def post_to_general_ledger(self, db, batch_id, total_amount):
        try:
            date_str = datetime.now().strftime("%Y-%m-%d")

            insert_ledger_query = """
            INSERT INTO fin.general_ledger (batch_id, posting_date, total_amount)
            VALUES (%s, %s, %s)
            """
            ledger_data = (batch_id, date_str, float(total_amount))

            with db.cursor() as cur:
                cur.execute(insert_ledger_query, ledger_data)

                update_batch_query = "UPDATE fin.batch SET posted = TRUE WHERE batch_id = %s"
                cur.execute(update_batch_query, (batch_id,))
                db.commit()

                print("Batch posted to the general ledger successfully.")

        except Exception as e:
            print("Error while posting to the general ledger:", e)
            db.rollback()


    
    def generate_pdf_report(self, df, batch_id, total_amount, total_discount, batch_type):
        pdf = FPDF()
        pdf.add_page()
    

        pdf.set_font("Helvetica", style='B', size=14) 
    
        batch_date = datetime.now().strftime('%d%b%Y')

        pdf.cell(200, 10, txt=f"{batch_type} DEBTOR ACCOUNTS", ln=True, align='C')
        pdf.cell(200, 10, txt=f"TRANSACTION SUMMARY REPORT - {batch_date}", ln=True, align='C')

        pdf.set_font("Helvetica", style='B', size=10) 
        pdf.cell(200, 10, txt="BATCH ID: " + str(batch_id).upper(), ln=True, align='L')
    
        formatted_total_amount = f"R{total_amount:,.2f}".replace(',', ' ')
        pdf.cell(200, 10, txt="TOTAL AMOUNT: " + formatted_total_amount, ln=True, align='L')

        formatted_total_discount = f"R{total_discount:,.2f}".replace(',', ' ')
        pdf.cell(200, 10, txt="TOTAL DISCOUNT: " + formatted_total_discount, ln=True, align='L')
    
        pdf.set_font("Helvetica", size=6) 

        pdf.cell(40, 10, txt="TRANSACTION DATE", border=1, align='C')
        pdf.cell(30, 10, txt="REFERENCE", border=1, align='C') 
        pdf.cell(30, 10, txt="AMOUNT", border=1, align='C')
        pdf.cell(30, 10, txt="DISCOUNT", border=1, align='C')
        pdf.cell(30, 10, txt="TOTAL", border=1, align='C')
        pdf.ln()

        # Table Rows
        for index, row in df.iterrows():
            pdf.cell(40, 8, txt=str(row['valueDate']), border=1)
            pdf.cell(30, 8, txt=str(row['reference']), border=1) 
            pdf.cell(30, 8, txt="{:.2f}".format(row['amount']), border=1)
            pdf.cell(30, 8, txt="{:.2f}".format(row['discount']), border=1)
            pdf.cell(30, 8, txt="{:.2f}".format(row['total']), border=1)
            pdf.ln()

        pdf.set_font("Helvetica", size=10)
        pdf.cell(0, 10, txt=f"Page {pdf.page_no()}", align='R')
        pdf.ln()

        pdf.set_font("Helvetica", style='B', size=12)
        pdf.cell(0, 10, txt="END OF REPORT", align='C')

        pdf_file_name = f"FNB {batch_type} Transactions BATCH {batch_id}_{batch_date}.pdf"

        pdf.output(pdf_file_name)
        print(f"PDF {batch_type} report generated successfully: {pdf_file_name}")
        return pdf_file_name


    def send_email_with_attachments(self, recipients, subject, body, file_1, file_2, signature_image):
        email_credentials = vault.get_secret("DANNYEMAIL") 

        try:
            tk = FileSystemTokenBackend(token_path=".", token_filename="o365_token.txt")

            credentials = (email_credentials['CLIENT-ID'], email_credentials['CLIENT-SECRET'])
            scopes = [email_credentials['DEFAULT-SCOPES']]

            account = Account(credentials, auth_flow_type='credentials', tenant_id=email_credentials['TENANT-ID'], token_backend=tk)

            if account.authenticate(scopes=scopes):
                logging.info('Authenticated!')

            mailbox = account.mailbox('rpa@dannysauto.co.za')
            m = mailbox.new_message()
            
            for recipient in recipients:
                m.to.add(recipient)
            m.subject = subject
            m.attachments.add(signature_image)

            body_with_signature = body.replace('src="cid:dannys_email_signature.png"', f'src="cid:{Path(signature_image).name}"')
            m.body = body_with_signature

            m.attachments.add(file_1)
            m.attachments.add(file_2)
            m.send()
            logging.info('Email sent successfully.')

        except Exception as e:
            logging.error(f"An error occurred while sending the email: {str(e)}")


    def save_raw_transactions_excel(self, df, output_file_name, batch_date, current_time):
        """
        Generate a raw Excel file with unprocessed bank transactions.

        Args:
            df (pandas.DataFrame): DataFrame containing the transaction history.
            batch_date (str): Date of the batch in 'YYYYMMDD' format.
            current_time (str): Current time in 'HH:MM' format.

        Returns:
            str: Path to the generated Excel file.
        """
        try:
            formatted_time = current_time.replace(':', '-')
            output_file = f"{output_file_name}_{batch_date}_{formatted_time}.xlsx"
            
            column_order = [
                'valueDate',
                'remittanceInfo', 
                'reference',
                'amount', 
                'creditDebitIndicator'
                ]

            raw_transactions = df[column_order]
            raw_transactions.to_excel(output_file, index=False)

            print(f"Transactions Excel file generated: {output_file}")
            return output_file

        except Exception as e:
            logging.error(f"An error occurred while saving the Excel file: {str(e)}")
            raise


    def process_transactions(self, fnb_trans_df, db_conn):
        
        batch_date = datetime.now().strftime('%Y-%m-%d')
        current_date_str = datetime.now().strftime("%d-%b-%Y").upper()
        current_time = datetime.now().strftime("%H:%M").upper()
        recipients = ['sharon@dannysauto.co.za',
                      'shakila1@dannysauto.co.za',
                      'francina@dannysauto.co.za', 
                      'yanum@dannysauto.co.za',
                      'fathima@dannysauto.co.za'
                     ]
    
        matched_email_body = f"""
                <p>Dear Debtors Team,</p>
                <br>
                <p>I hope this email finds you well.</p>
                <br>
                <p>Please find attached the latest FNB Bank Recon for the date <b>{current_date_str}</b>.</p>
                <p><b>Batch completion time:</b> {current_time}</p>
                <br>
                <p>The bank recon process has been completed. Kindly review the processed balances and let us know of any issues.</p>
                <br>
                <p>Best regards,</p>
                <p>RPA and Automation</p>
                <p>For issues and queries contact: <a href="mailto:rpa@dannyautomotive.co.za">rpa@dannyautomotive.co.za</a></p>
                <br>
                <img src="cid:dannys_email_signature.png" alt="Danny's Email Signature">
                """

        df_with_discount, unmatched_trans_df, df_trans_cpy = self.read_and_apply_discounts(fnb_trans_df, db_conn)
        df = self.apply_discount_at_transaction_level(df_with_discount)

        # Separate transactions by payment terms
        df_30_day = df[df['payment_terms'] == '10% STRICTLY 31 DAYS']
        df_7_day = df[df['payment_terms'] == '7 DAY ONLY ACC.']
        df_cod = df[df['payment_terms'] == 'CASH ONLY (NOTES)']
        
        file_name = 'Latest_FNB_Bank_Statement'
        raw_excel_file = self.save_raw_transactions_excel(df_trans_cpy, file_name, batch_date, current_time)
        
        file_name = 'Unmatched_FNB_Trans'
        unmatched_trans_excel_file = self.save_raw_transactions_excel(unmatched_trans_df, file_name, batch_date, current_time)
        
        
        batch_id_30_day = self.insert_batch(
            db_conn, 'BR001', 
            batch_date, 
            'Finance (Bot)',
            df_30_day['amount'].sum(), 
            df_30_day['discount'].sum(), 
            df_30_day['total'].sum()
        )
        
        if batch_id_30_day:
            self.insert_bank_transactions(db_conn, df_30_day, batch_id_30_day)
            if self.check_batch_balance(df_30_day, df_30_day['amount'].sum(), df_30_day['discount'].sum(), df_30_day['total'].sum()):
                self.post_to_general_ledger(db_conn, 
                                            batch_id_30_day, 
                                            df_30_day['total'].sum())
                
                pdf_file_30_day = self.generate_pdf_report(df_30_day, batch_id_30_day, 
                                                           df_30_day['total'].sum(), 
                                                           df_30_day['discount'].sum(), 
                                                           '30-DAY')
                
                self.send_email_with_attachments(recipients, 
                                                 f'FNB 30-DAY BATCH {batch_id_30_day} - {current_date_str} - {current_time}', 
                                                 matched_email_body, 
                                                 pdf_file_30_day, raw_excel_file, 
                                                 'input/dannys_email_signature.png')

        batch_id_7_day = self.insert_batch(
            db_conn, 'BR001', 
            batch_date, 
            'Finance (Bot)',
            df_7_day['amount'].sum(), 
            df_7_day['discount'].sum(), 
            df_7_day['total'].sum()
        )

        if batch_id_7_day:
            self.insert_bank_transactions(db_conn, df_7_day, batch_id_7_day)
            if self.check_batch_balance(df_7_day, df_7_day['amount'].sum(), df_7_day['discount'].sum(), df_7_day['total'].sum()):
                self.post_to_general_ledger(db_conn, 
                                            batch_id_7_day, 
                                            df_7_day['total'].sum())
                
                pdf_file_7_day = self.generate_pdf_report(df_7_day, 
                                                          batch_id_7_day, 
                                                          df_7_day['total'].sum(), 
                                                          df_7_day['discount'].sum(), 
                                                          '7-DAY')
                
                self.send_email_with_attachments(recipients, 
                                                  f'FNB 7-DAY BATCH {batch_id_7_day} - {current_date_str} - {current_time}', 
                                                  matched_email_body, 
                                                  pdf_file_7_day, 
                                                  raw_excel_file, 
                                                  'input/dannys_email_signature.png')
        
        batch_id_cod = self.insert_batch(
            db_conn, 'BR001', batch_date, 'Finance (Bot)',
            df_cod['amount'].sum(),  df_cod['discount'].sum(), 
            df_cod['total'].sum()
        )
        
        if batch_id_cod:
            self.insert_bank_transactions(db_conn, df_cod, batch_id_cod)

            if self.check_batch_balance(df_cod, df_cod['amount'].sum(), df_cod['discount'].sum(), df_cod['total'].sum()):    
                self.post_to_general_ledger(db_conn, 
                                            batch_id_cod, 
                                            df_cod['total'].sum())
                
                pdf_file_cod = self.generate_pdf_report(df_cod, 
                                                        batch_id_cod, 
                                                        df_cod['total'].sum(), 
                                                        df_cod['discount'].sum(), 
                                                        'CASH ONLY (NOTES)')
                
                self.send_email_with_attachments(recipients, 
                                                  f'FNB CASH ONLY (COD) BATCH {batch_id_cod} - {current_date_str} - {current_time}', 
                                                  matched_email_body, 
                                                  pdf_file_cod, 
                                                  raw_excel_file, 
                                                  'input/dannys_email_signature.png')
                


