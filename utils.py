import boto3, json
from botocore.exceptions import ClientError
from opensearchpy import OpenSearch

# Setup Amazon SQS
sqs = boto3.client("sqs", region_name="ap-northeast-1")
QUEUE_URL = "https://sqs.ap-northeast-1.amazon.aws.com/YOUR-ACCOUNT-ID/audit-log-queue" # Update account id and url

# OpenSearch client
opensearch_client = OpenSearch(
    hosts=[{"host": "localhost", "port": 9200}],
    http_compress=True,
    use_ssl=False
)

def send_log_to_sqs(log_data: dict):
    try:
        sqs.send_message(
            QueueUrl=QUEUE_URL,
            MessageBody=json.dumps(log_data)
        )
    except ClientError as e:
        print("SQS error:", e)

def index_log_to_opensearch(log: dict, index: str):
    response = opensearch_client.index(
        index=index,
        body=log
    )

    return response