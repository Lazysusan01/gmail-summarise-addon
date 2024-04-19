import base64
import json
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from email.mime.text import MIMEText
import datetime
from anthropic import AI_PROMPT, HUMAN_PROMPT, AnthropicBedrock
from dotenv import load_dotenv
import os
import re

email_address_to_search = 'me'

keywords = ['proposal', 'contract', 'quotes', 'events', 'tradeshows', 'negotiations', 'negotiation']

def get_gmail_service(access_token):
    creds = Credentials(token=access_token)
    service = build('gmail', 'v1', credentials=creds)
    print('Gmail service created!')
    return service

def get_user_email(service):
    user_profile = service.users().getProfile(userId='me').execute()
    return user_profile['emailAddress']

def list_emails(service, user_id='me', query=''):
    try:
        response = service.users().messages().list(userId=user_id, q=query).execute()
        messages = response.get('messages', [])
        
        # Handle pagination
        while 'nextPageToken' in response:
            page_token = response['nextPageToken']
            response = service.users().messages().list(userId=user_id, q=query, pageToken=page_token).execute()
            messages.extend(response.get('messages', []))
        
        return messages
    except Exception as error:
        print(f'An error occurred: {error}')
        return None
     
def get_email_body(parts, mime_type='text/plain'):
    """
    Recursively search the email parts for the specified mime type and return the decoded content.
    """
    body = ""
    for part in parts:
        if part['mimeType'] == mime_type and 'data' in part['body']:
            body = base64.urlsafe_b64decode(part['body']['data']).decode('utf-8')
            break
        elif part['mimeType'] == 'multipart/alternative' or part['mimeType'] == 'multipart/mixed':
            # Recurse into subparts
            if 'parts' in part:
                body = get_email_body(part['parts'], mime_type)
                if body:  # Stop if we found something
                    break
    return body     

def get_email_details(service, user_id, email_id):
    try:
        message = service.users().messages().get(userId=user_id, id=email_id, format='full').execute()
        
        # Extract headers
        headers = message['payload']['headers']
        details = {'id': email_id}
        for header in headers:
            header_name = header['name'].lower()
            if header_name in ['from', 'to', 'subject', 'date', 'cc']:
                details[header_name] = header['value']
        
        # Check if the email is multipart
        if 'parts' in message['payload']:
            parts = message['payload']['parts']
        else:
            # For non-multipart emails, create a single-part list to use with the get_email_body function
            parts = [message['payload']]

        # Attempt to get both plain text and HTML bodies
        body_plain = get_email_body(parts, 'text/plain')
        
        # Prefer plain text body; fall back to HTML if plain text is unavailable
        details['body'] = body_plain
        
        return details
    except Exception as error:
        print(f'An error occurred: {error}')
        return None

def filter_emails_by_keywords(email_details, keywords):
    # Filter emails where any keyword is found in the subject or body
    filtered_emails = [
        email for email in email_details
        if any(keyword.lower() in email.get('subject', '').lower() for keyword in keywords)
        or any(keyword.lower() in email.get('body', '').lower() for keyword in keywords)
    ]
    return filtered_emails

def list_emails_and_details(service, query, user_id=email_address_to_search):
    emails = list_emails(service, user_id=user_id, query=query)
    if not emails:  # Check if emails is empty or None
        return []  # Return an empty list if there are no emails to avoid errors in the next line
    email_details = [get_email_details(service, user_id, email['id']) for email in emails]
    return email_details

def remove_urls(emails):
    url_pattern = r'https?://\S+|www\.\S+'
    unicode_pattern = r'\\u[0-9a-fA-F]+'
    for email in emails:
        email['body'] = re.sub(url_pattern, '', email['body'])
        email['body'] = re.sub(unicode_pattern, '', email['body'])
    return emails

def create_message(sender, to, subject, message_text):
    """
    Create a message for an email.

    :param sender: Email address of the sender.
    :param to: Email address of the receiver.
    :param subject: The subject of the email message.
    :param bcc: Optional. Email addresses for BCC recipients, separated by commas.
    :param message_text: The text of the email message.
    :return: An object containing a base64url encoded email object.
    """
    message = MIMEText(message_text,'html')
    message['to'] = to
    message['from'] = sender
    message['bcc'] = 'nico@chemwatch.net'
    message['subject'] = subject
    return {'raw': base64.urlsafe_b64encode(message.as_bytes()).decode()}

def send_message(service, user_id, message):
    """
    Send an email message.

    :param service: Authorized Gmail API service instance.
    :param user_id: User's email address. The special value "me" can be used to indicate the authenticated user.
    :param message: Message to be sent.
    """
    try:
        message = (service.users().messages().send(userId=user_id, body=message).execute())
        print(f"Message Id: {message['id']}")
        return message
    except Exception as error:
        print(f'An error occurred: {error}')

def email_error(service, error, email_address, total_emails):
    email_content = create_message("nico@chemwatch.net", email_address, f'Error', f"Hi there, <br><br> We ran into an error: {str(error)} <br> Sorry about that, please reduce the date range you want summarising. Total emails: {total_emails} <br><br> Kind regards, <br><br> Nico")
    send_message(service, 'me', email_content)

def process_data(start_date, end_date, access_token):
    try:
        print(f"Dates: {start_date} , {end_date}")
        print(f"Access Token: {access_token[0:15]}")
        # ##############################################################
        start_date_part = start_date.split('T')[0]
        end_date_part = end_date.split('T')[0]   
        # Parse the date part
        start_date_time = datetime.datetime.strptime(start_date_part, "%Y-%m-%d")
        end_date_time = datetime.datetime.strptime(end_date_part, "%Y-%m-%d")
        end_date_time += datetime.timedelta(days=1)  # Add one day to include the end date   
        
        # Format to "%Y/%m/%d"
        formatted_start_date = start_date_time.strftime("%Y/%m/%d")
        formatted_end_date = end_date_time.strftime("%Y/%m/%d") 
        
        query = f'after:{formatted_start_date} before:{formatted_end_date}'
        
        service = get_gmail_service(access_token)
        email_address = get_user_email(service)
        email_details = list_emails_and_details(service, query=query)
        filtered_emails = remove_urls(email_details)

        # Save to JSON file
        with open('/tmp/filtered_email_details.json', 'w') as f:
            json.dump(filtered_emails, f, indent=4)

        print("Email details saved to 'filtered_email_details.json'")
        print(f"Total emails: {len(filtered_emails)}")
        
        # ##############################################################
        # Anthropic Bedrock Summarising the emails

        # open filtered_email_details.json  
        with open('/tmp/filtered_email_details.json') as f:
            filtered_emails = json.load(f)

        client = AnthropicBedrock()
        try:
            completion = client.messages.create(
                model="anthropic.claude-3-sonnet-20240229-v1:0",
                max_tokens=4096,
                messages=[
                    {'role': 'user', 'content' : f"""Hi Claude, i'd like you to provide a summary of the following emails in English,
                    you should decide which emails are the most important, if they are direct requests, important updates/news, or ignore them if they don't seem important to you.
                    Please provide the HTML format for an email summary. Use placeholders 'message_summary' for the text summary and 'message_id' for the hyperlink URL.
                    The output must look like this:
                    <ul>
                        <li>message_summary   <a href='https://mail.google.com/mail/u/0/#inbox/message_id'>Link to Email</a> \n</li>
                        <li>message_summary   <a href='https://mail.google.com/mail/u/0/#inbox/message_id'>Link to Email</a> \n</li>
                    </ul>
                        Email data: {email_details}"""}
                    ]
            )            
            output = completion.content[0].text
            input_tokens = completion.usage.input_tokens
            output_tokens = completion.usage.output_tokens
            print(f"Input tokens: {input_tokens}")
            print(f"Output tokens: {output_tokens}")
            
            total_tokens = input_tokens + output_tokens 
            total_cost = input_tokens*0.000003 + output_tokens*0.000015
            # round to two decimal places
            total_cost = round(total_cost, 2)

        except Exception as error:
            print(f"An error occurred: {error}")
            email_error(service, error, email_address, total_emails=len(filtered_emails))
            return {
                'statusCode': 500,
                'body': json.dumps(f'An error occurred: {error.message}')
            }

        # Sending email summary to user
        email_address = get_user_email(service)
        email_content = create_message("nico@chemwatch.net", email_address, f'Your email summary', f"Hi there, <br> {output} <br> Total emails summarised: {len(filtered_emails)} <br> Total cost: $USD: {total_cost} <br> Kind regards, <br> Nico")
        send_message(service, 'me', email_content)
        
        return {
            'statusCode': 200,
            'body': json.dumps(f'Emails summarised and sent to {email_address}!')
    }
    except ValueError as error:
        print(f'An error occurred: {str(error)}')
        email_error(service, error, email_address)
        return {
            'statusCode': 500,
            'body': json.dumps(f'Error in date format: {str(error)}')
        }
    except Exception as error:
        print(f'An error occurred: {str(error)}')
        email_error(service, error, email_address)
        return {
            'statusCode': 500,
            'body': json.dumps(f'An error occurred: {str(error)}')
        }
        
def lambda_handler(event, context):
    # immediate response
    start_date = event.get('start_date')
    end_date = event.get('end_date')
    access_token = event.get('gmail_access_token')
    
    if not start_date or not end_date or not access_token:
        return {
            'statusCode': 400,
            'body': json.dumps('Missing required parameters.')
        }
    else:
        process_data(start_date, end_date, access_token)
        response = {
            'statusCode': 202,
            'body': json.dumps('Process started. You will receive an email once the process is complete.')
        }
    
    return response