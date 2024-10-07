import boto3
from datetime import datetime, timedelta

def create_cloudwatch_rule(client, schedule_expression, lambda_arn):
    print("cloudwatch function running")
    cloudwatch_events = boto3.client('events', region_name='us-east-1')
    print("yha tk chl rha")

    rule_name = f'sort_{client.shop_id}_collections'
    

    response = cloudwatch_events.put_rule(
        Name=rule_name,
        ScheduleExpression=schedule_expression,  
        State='ENABLED'
    )

    print("cloudwatch rule put ho gya")

    
    target_response = cloudwatch_events.put_targets(
        Rule=rule_name,
        Targets=[
            {
                'Id': '1',
                'Arn': lambda_arn,
                'Input': json.dumps({
                    "shop_id": client.shop_id,
                    "collection_id": client.collection_id,
                    "algo_id": client.algo_id,
                    "token": client.access_token 
                })
            }
        ]
    )

    print("cloudwatch put target ho rha")

    return response, target_response

def generate_custom_cron_expression(start_time, frequency_in_hours):
    print("cron expression bn rahi")
    start_hour = start_time.hour
    start_minute = start_time.minute


    cron_expression = f"cron({start_minute} {start_hour}/{frequency_in_hours} * * ? *)"
    print("cron expression bn gyi" , cron_expression)
    return cron_expression
