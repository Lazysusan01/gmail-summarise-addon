import base64
import json
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
import os
import pickle
import datetime
from anthropic import AI_PROMPT, HUMAN_PROMPT, AnthropicBedrock
import boto3 
from botocore.config import Config
import os
from send_email import *
from dotenv import load_dotenv
import re

SCOPES = ['https://www.googleapis.com/auth/gmail.readonly', 
          'https://www.googleapis.com/auth/gmail.send']

email_address_to_search = 'me'

keywords = ['proposal', 'contract', 'quotes', 'events', 'tradeshows', 'negotiations', 'negotiation']

def get_gmail_service():
    creds = None
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)
    service = build('gmail', 'v1', credentials=creds)
    return service

def list_threads(service, user_id='me', query=''):
    try:
        response = service.users().threads().list(userId=user_id, q=query).execute()
        threads = response.get('threads', [])
        
        # Handle pagination
        while 'nextPageToken' in response:
            page_token = response['nextPageToken']
            response = service.users().threads().list(userId=user_id, q=query, pageToken=page_token).execute()
            threads.extend(response.get('threads', []))
        
        return threads
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

def get_latest_email_from_thread(service, user_id, thread_id):
    try:
        thread = service.users().threads().get(userId=user_id, id=thread_id, format='full').execute()
        # The latest message is the last one in the thread
        latest_message = thread['messages'][-1]
        return get_email_details(service, user_id, latest_message['id'])
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
    threads = list_threads(service, user_id=user_id, query=query)
    if not threads:  # Check if threads is empty or None
        return []  # Return an empty list if there are no threads to avoid errors in the next line
    email_details = [get_latest_email_from_thread(service, user_id, thread['id']) for thread in threads]
    return email_details

def remove_urls(emails):
    url_pattern = r'https?://\S+|www\.\S+'
    unicode_pattern = r'\\u[0-9a-fA-F]+'
    for email in emails:
        email['body'] = re.sub(url_pattern, '', email['body'])
        email['body'] = re.sub(unicode_pattern, '', email['body'])
    return emails

a_week_ago = datetime.datetime.now() - datetime.timedelta(days=1)

service = get_gmail_service()
email_details = list_emails_and_details(service, query=f'after:{a_week_ago.strftime("%Y/%m/%d")}')
# from:(mayumi@chemwatch.net OR richard.endsley@chemwatch.net)
# filtered_emails = filter_emails_by_keywords(email_details, keywords)

# cleaned_emails = remove_urls(email_details)
cleaned_emails = email_details

# Save to JSON file
with open('email_details.json', 'w') as f:    
    json.dump(cleaned_emails, f, indent=4)

print("Email details saved to 'email_details.json'")

# ##############################################################

# Anthropic Bedrock Summarising the emails

# open filtered_email_details.json  
with open('email_details.json') as f:
    email_details = json.load(f)
    
print(f"Total emails: {len(email_details)}")    
print(f"Estimated tokens: {len(str(email_details))/6}")

print(email_details[0])

# load_dotenv('.env')

# aws_access_key=os.getenv('aws_access_key_id')
# aws_secret_access_key = os.getenv('aws_secret_access_key')
# aws_session_token = os.getenv('aws_session_token')
# region = 'us-east-1'

# Get AWS region from the config file



load_dotenv('.env')

aws_access_key=os.getenv('aws_access_key_id')
aws_secret_key=os.getenv('aws_secret_access_key')
aws_session_token=os.getenv('aws_session_token')
aws_region='us-east-1'


# Create an Anthropic Bedrock client using the temporary credentials
# client = AnthropicBedrock(
#     aws_access_key=credentials['AccessKeyId'],
#     aws_secret_key=credentials['SecretAccessKey'],
#     aws_session_token=credentials['SessionToken'],
#     aws_region='us-east-1'
# )

client = AnthropicBedrock(aws_access_key=aws_access_key, aws_region=aws_region, aws_secret_key=aws_secret_key, aws_session_token=aws_session_token)

completion = client.messages.create(
    model="anthropic.claude-3-sonnet-20240229-v1:0",
    max_tokens=1024,
    messages=[
         {'role': 'user', 'content' : f"""Hi Claude, i'd like you to provide a summary of the following emails,
          you should decide which emails are the most important, if they are direct requests, important updates/news, or ignore them if they don't seem important to you.
          Please provide the HTML format for an email summary. Use placeholders '(message_summary)' for the text summary and '(message_id)' for the hyperlink URL.
          The output should look like this:
            <p>(message_summary)</p>
            <a href='https://mail.google.com/mail/u/0/#inbox/(message_id)'>Link</a> \n.
             
            Email data: {email_details}"""}
        ]
)

output = completion.content[0].text
print(output)

service = get_gmail_service()  # Ensure you have this function from your Gmail API setup
email_content = create_message("nico@chemwatch.net", "nico@chemwatch.net", f'Summary of emails since {a_week_ago.strftime("%Y/%m/%d")}', f"Hi there, \n {output}")
send_message(service, 'me', email_content)

