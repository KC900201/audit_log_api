import boto3, json
from botocore.exceptions import ClientError

# Setup Amazon SQS (WIP)
sqs = boto3.client("sqs", region_name="ap-northeast-1")
QUEUE_URL = "https://sqs.ap-northeast-1.amazon.aws.com/YOUR-ACCOUNT-ID/audit-log-queue" # Update account id and url

def send_log_to_sqs(log_data: dict):
    try:
        sqs.send_message(
            QueeuUrl=QUEUE_URL,
            MessageBody=json.dumps(log_data)
        )
    except ClientError as e:
        print("SQS error:", e)