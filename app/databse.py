import boto3
from operator import itemgetter
from boto3.dynamodb.conditions import Key

from app.config import aws_config

from flask import flash


def add_lambda_ticker(ticker):

    client = boto3.client('lambda')
    response = client.get_function_configuration(FunctionName=aws_config['LambdaName'])
    tickers = response['Environment']['Variables']['ticker'] + " " + ticker

    return tickers


def get_lambda_ticker():

    client = boto3.client('lambda')
    response = client.get_function_configuration(FunctionName=aws_config['LambdaName'])
    tickers = response['Environment']['Variables']['ticker'].split()

    return tickers


def remove_lambda_ticker(ticker_moved):

    tickers = get_lambda_ticker()

    if ticker_moved in tickers:
        tickers.remove(ticker_moved)

        update = ''
        for ticker in tickers:
            update = update + " " + ticker

        return update

    else:

        return None


def get_query_status():

    client = boto3.client('lambda')
    response = client.get_function(
        FunctionName=aws_config['TwitterLambda'],
    )

    Concurrency = response['Concurrency']['ReservedConcurrentExecutions']

    if Concurrency == 500:
        return 'Active'

    else:
        return 'Inactive'


def get_lambda_query():

    stack = boto3.resource('cloudformation').Stack(aws_config['stackName'])

    param = stack.parameters

    # index 0 is SearchQuery

    return param[0]['ParameterValue']


def dynamo_search(ticker):

    dynamo_db = boto3.resource('dynamodb', region_name='us-east-1')

    table = dynamo_db.Table(aws_config['DynamoName'])

    response = table.scan(FilterExpression=Key('ticker').eq(ticker))

    sentiment_data = []

    for i in response['Items']:

        item = [i['time_stamp'], i['price'], i['neutral'], i['positive'], i['negative'], i['mixed']]

        sentiment_data.append(item)

    while 'LastEvaluatedKey' in response:
        response = table.scan(
            ilterExpression=Key('ticker').eq(ticker),
            ExclusiveStartKey=response['LastEvaluatedKey']
        )

        for i in response['Items']:
            item = [i['time_stamp'], i['price'], i['neutral'], i['positive'], i['negative'], i['mixed']]
            sentiment_data.append(item)

    sentiment_data.sort(key=itemgetter(0))

    return sentiment_data

