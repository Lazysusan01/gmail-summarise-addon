from anthropic import AI_PROMPT, HUMAN_PROMPT, AnthropicBedrock
import boto3 
from botocore.session import Session
from botocore.config import Config

my_config = Config(
    region_name='us-east-1'
)

# Create a boto3 session with the specified profile
session = boto3.Session(profile_name='nicomcgill')


# Retrieve temporary credentials using assume_role
sts_client = session.client('sts', config=my_config)
assumed_role_object = sts_client.assume_role(
    RoleArn="arn:aws:iam::015567113302:role/NicoMcGillServerless",
    RoleSessionName="gmail-email-summary"
)
credentials = assumed_role_object['Credentials']

# Create an Anthropic Bedrock client using the temporary credentials
client = AnthropicBedrock(
    aws_access_key=credentials['AccessKeyId'],
    aws_secret_key=credentials['SecretAccessKey'],
    aws_session_token=credentials['SessionToken'],
    aws_region='us-east-1'
)

print(credentials['AccessKeyId'])