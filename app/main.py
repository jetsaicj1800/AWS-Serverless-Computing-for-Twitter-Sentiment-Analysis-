
from flask import render_template, url_for
from app import webapp
from app.databse import get_lambda_ticker, get_lambda_query, get_query_status
from app.config import query_status


@webapp.route('/')
@webapp.route('/index')
def main():

    tickers = get_lambda_ticker()
    query = get_lambda_query()
    status = get_query_status()

    if status == 'Active':
        query_status['status'] = 'running'

    else:
        query_status['status'] = 'stopped'

    return render_template("main.html", tickers=tickers, query=query, status=status)




