from __future__ import print_function # Python 2/3 compatibility
import boto3

from boto3.dynamodb.conditions import Key

from flask import render_template, url_for, redirect, request, flash
from app import webapp

from time import sleep

from app.databse import dynamo_search, get_lambda_ticker, add_lambda_ticker, remove_lambda_ticker, get_query_status

from app.config import aws_config, query_status, view_data

webapp.secret_key = b'_5#y2L"F4Q8z\n\xec]/'



@webapp.route('/back_to_main_page')
def back_to_main_page():

    flash("This is the Home Page")
    return render_template("main.html")


@webapp.route('/view_search_result')
def view_search_result():

    s3 = boto3.resource('s3')
    bucket = s3.Bucket(aws_config['bucket_name'])

    result = []
    for obj in bucket.objects.all():

        result.insert(0, obj.key)

    return render_template("show_search_result.html", results=result)


@webapp.route('/view_tweets<filename>')
def view_tweets(filename):

    s3 = boto3.client('s3')

    tweet_url = s3.generate_presigned_url('get_object',
                                          Params={'Bucket': aws_config['bucket_name'], 'Key': filename},
                                          ExpiresIn=100)

    return render_template("tweets_display.html", tweet_url=tweet_url,)


@webapp.route('/view_tweet_sentiment')
def view_tweet_sentiment():

    if request.args.get('period_name') is None:
        n = view_data['period']

        if request.args.get('ticker_name') is None:
            ticker = get_lambda_ticker()[0]

        else:
            ticker = request.args.get('ticker_name')

        view_data['ticker'] = ticker

    else:
        n = int(request.args.get('period_name'))

        ticker = view_data['ticker']

        view_data['period'] = n

    data = dynamo_search(ticker)

    time, stock, neutral, positive, negative, mixed = ([] for i in range(6))

    for i in data:
        time.append(i[0])
        stock.append(float(i[1]))
        neutral.append(i[2])
        positive.append(i[3])
        negative.append(i[4])
        mixed.append(i[5])

    print(ticker)
    print(time)
    print(stock)

    period_array = [-15, -30, -45, -60, -90, -120, -240, -300]

    tickers = get_lambda_ticker()

    return render_template("view_data.html", time=time[n:], stock=stock[n:], neutral=neutral[n:], positive=positive[n:],
                           negative=negative[n:], mixed=mixed[n:], tickers=tickers, old_ticker=ticker,
                           period_array=period_array, old_period=n)


@webapp.route('/update_query')
def update_query():

    query = request.args.get('query')
    if query is "":
        return redirect(url_for('main'))

    stack = boto3.resource('cloudformation').Stack(aws_config['stackName'])

    param = stack.parameters

    # index 0 is SearchQuery
    param[0]['ParameterValue'] = query

    tag = stack.tags

    response = stack.update(
        UsePreviousTemplate=True,
        Parameters=param,
        Capabilities=[
            'CAPABILITY_IAM',
        ],
        Tags=tag
    )

    sleep(2)

    stack = boto3.resource('cloudformation').Stack(aws_config['stackName'])
    while stack.stack_status != 'UPDATE_COMPLETE':
        stack = boto3.resource('cloudformation').Stack(aws_config['stackName'])
        sleep(1)

    flash("Update Completed")
    return redirect(url_for('main'))


@webapp.route('/add_ticker')
def add_ticker():

    ticker = request.args.get('ticker')

    if ticker is "":
        return redirect(url_for('main'))

    tickers = add_lambda_ticker(ticker)

    client = boto3.client('lambda')

    response = client.update_function_configuration(
        FunctionName=aws_config['LambdaName'],
        Environment={
            'Variables': {
                'ticker': tickers
            }
        })

    flash("Ticker Update Completed")
    return redirect(url_for('main'))


@webapp.route('/remove_ticker')
def remove_ticker():

    ticker = request.args.get('ticker')

    if ticker is "":
        return redirect(url_for('main'))

    tickers = remove_lambda_ticker(ticker)

    if tickers is not None:

        client = boto3.client('lambda')

        response = client.update_function_configuration(
            FunctionName=aws_config['LambdaName'],
            Environment={
                'Variables': {
                    'ticker': tickers
                }
            })

        flash("Ticker Update Completed")

    else:
        flash("Ticker Can't be Found")

    return redirect(url_for('main'))


@webapp.route('/stop_query')
def stop_query():

    if query_status['status'] != 'stopped':

        client = boto3.client('lambda')

        response = client.put_function_concurrency(
            FunctionName=aws_config['TwitterLambda'],
            ReservedConcurrentExecutions=0
        )

        query_status['status'] = 'stopped'

    return redirect(url_for('main'))


@webapp.route('/restart_query')
def restart_query():

    if query_status['status'] != 'running':

        client = boto3.client('lambda')

        response = client.put_function_concurrency(
            FunctionName=aws_config['TwitterLambda'],
            ReservedConcurrentExecutions=500
            )

        query_status['status'] = 'running'

    return redirect(url_for('main'))


#####igmore everything below

@webapp.route('/create_table')
def create_table():

    table = dynamodb.create_table(
        TableName=tableName,
        KeySchema=[
            {
                'AttributeName': 'IssueId',
                'KeyType': 'HASH'  #Partition key
            },
            {
                'AttributeName': 'Title',
                'KeyType': 'RANGE'  #Sort key
            }
        ],
        GlobalSecondaryIndexes=[
            {
                'IndexName': "CreateDateIndex",
                'KeySchema': [
                    {
                        'KeyType': 'HASH',
                        'AttributeName': 'CreateDate'
                    },
                    {
                        'KeyType': 'RANGE',
                        'AttributeName': 'IssueId'
                    }
                ],
                'Projection': {
                    'ProjectionType': 'INCLUDE',
                    'NonKeyAttributes': ['Description', 'Status']
                },
                'ProvisionedThroughput' : {
                    'ReadCapacityUnits': 2,
                    'WriteCapacityUnits': 2
                }
            },
            {
                'IndexName': "TitleIndex",
                'KeySchema': [
                    {
                        'KeyType': 'HASH',
                        'AttributeName': 'Title'
                    },
                    {
                        'KeyType': 'RANGE',
                        'AttributeName': 'IssueId'
                    }
                ],
                'Projection': {
                    'ProjectionType': 'KEYS_ONLY'
                },
                'ProvisionedThroughput': {
                    'ReadCapacityUnits': 2,
                    'WriteCapacityUnits': 2
                }
            },
            {
                'IndexName': "DueDateIndex",
                'KeySchema': [
                    {
                        'KeyType': 'HASH',
                        'AttributeName': 'DueDate'
                    }
                ],
                'Projection': {
                    'ProjectionType': 'ALL'
                },
                'ProvisionedThroughput' : {
                    'ReadCapacityUnits': 2,
                    'WriteCapacityUnits': 2
                }
            }
        ],

        AttributeDefinitions=[
            {
                'AttributeName': 'IssueId',
                'AttributeType': 'S'
            },
            {
                'AttributeName': 'Title',
                'AttributeType': 'S'
            },
            {
                'AttributeName': 'CreateDate',
                'AttributeType': 'S'
            },
            {
                'AttributeName': 'DueDate',
                'AttributeType': 'S'
            },

        ],
        ProvisionedThroughput={
            'ReadCapacityUnits': 10,
            'WriteCapacityUnits': 10
        }
    )

    return redirect(url_for('main'))


@webapp.route('/delete_table')
def delete_table():
    #dynamodb = boto3.client('dynamodb', region_name='us-east-1', endpoint_url="http://localhost:8000")
    dynamodb = boto3.client('dynamodb', region_name='us-east-1')

    response = dynamodb.delete_table(
        TableName=tableName
    )

    return redirect(url_for('main'))




def putItem(issueId, title, description, createDate,
    lastUpdateDate, dueDate, priority, status):

    table = dynamodb.Table(tableName)

    response = table.put_item(
       Item={
            'IssueId': issueId,
            'Title': title,
            'Description': description,
            'CreateDate': createDate,
            'LastUpdateDate': lastUpdateDate,
            'DueDate': dueDate,
            'Priority': priority,
            'Status': status
        }
    )

    return


@webapp.route('/load_data')
def load_data():

    print("Loading data into table " + tableName + "...")

    # IssueId, Title,
    # Description,
    # CreateDate, LastUpdateDate, DueDate,
    # Priority, Status

    putItem("A-101", "Compilation error",
            "Can't compile Project X - bad version number. What does this mean?",
            "2017-04-01", "2017-04-02", "2017-04-10",
            1, "Assigned")

    putItem("A-102", "Can't read data file",
            "The main data file is missing, or the permissions are incorrect",
            "2017-04-01", "2017-04-04", "2017-04-30",
            2, "In progress")

    putItem("A-103", "Test failure",
            "Functional test of Project X produces errors",
            "2017-04-01", "2017-04-02", "2017-04-10",
            1, "In progress")

    putItem("A-104", "Compilation error",
            "Variable 'messageCount' was not initialized.",
            "2017-04-15", "2017-04-16", "2017-04-30",
            3, "Assigned")

    putItem("B-101", "Network issue",
            "Can't ping IP address 127.0.0.1. Please fix this.",
            "2017-04-15", "2017-04-16", "2017-04-19",
            5, "Assigned")


    return redirect(url_for('main'))


@webapp.route('/list_all/<indexName>')
def list_all(indexName):

    table = dynamodb.Table(tableName)

    response = table.scan(IndexName = indexName)


    records = []

    for i in response['Items']:
        records.append(i)

    while 'LastEvaluatedKey' in response:
        response = table.scan(
            IndexName=indexName,
            ExclusiveStartKey=response['LastEvaluatedKey']
            )

        for i in response['Items']:
            records.append(i)

    return render_template("issues.html", issues=records)


@webapp.route('/query_createdate')
def query_createdate():
    table = dynamodb.Table(tableName)

    date = request.args.get('date')

    response = table.query(
        IndexName = 'CreateDateIndex',
        KeyConditionExpression= Key('CreateDate').eq(date) & Key('IssueId').begins_with("A-")
    )

    records = []

    for i in response['Items']:
        records.append(i)

    return render_template("issues.html", issues=records)


@webapp.route('/query_title')
def query_title():
    table = dynamodb.Table(tableName)

    title = request.args.get('title')

    response = table.query(
        IndexName = 'TitleIndex',
        KeyConditionExpression= Key('Title').eq(title)
    )

    records = []

    for i in response['Items']:
        records.append(i)

    return render_template("issues.html", issues=records)


@webapp.route('/query_duedate')
def query_duedate():
    table = dynamodb.Table(tableName)

    duedate = request.args.get('duedate')

    response = table.query(
        IndexName = 'DueDateIndex',
        KeyConditionExpression= Key('DueDate').eq(duedate)
    )

    records = []

    for i in response['Items']:
        records.append(i)

    return render_template("issues.html", issues=records)

