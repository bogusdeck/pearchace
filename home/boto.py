import json
import boto3
from shopify_app.models import ClientCollections  #

def create_cloudwatch_rule(client, schedule_expression, lambda_arn,token):
    print("cloudwatch function running")
    cloudwatch_events = boto3.client('events', region_name='us-east-1')

    try:
        active_collections = ClientCollections.objects.filter(shop_id=client.shop_id, status=True)

        for collection in active_collections:
            collection_id = str(collection.collection_id)
            algo_id = collection.algo_id
            rule_name = f'sort_{client.shop_id}_collection_{collection_id}'

            # Create a CloudWatch rule
            response = cloudwatch_events.put_rule(
                Name=rule_name,
                ScheduleExpression=schedule_expression,
                State='ENABLED'
            )

            # Create CloudWatch target
            target_response = cloudwatch_events.put_targets(
                Rule=rule_name,
                Targets=[
                    {
                        'Id': f'collection_{collection_id}_target',
                        'Arn': lambda_arn,
                        'Input': json.dumps({
                            "shop_id": client.shop_id,
                            "collection_id": collection_id,
                            "algo_id": algo_id,
                            "token": token 
                        })
                    }
                ]
            )

        print("CloudWatch rules and targets created successfully.")

    except Exception as e:
        print(f"Error creating CloudWatch rule: {str(e)}")

def generate_custom_cron_expression(start_time, frequency_in_hours):
    print("cron expression bn rahi")
    start_hour = start_time.hour
    start_minute = start_time.minute


    cron_expression = f"cron({start_minute} {start_hour}/{frequency_in_hours} * * ? *)"
    print("cron expression bn gyi" , cron_expression)
    return cron_expression
