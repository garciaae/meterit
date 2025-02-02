from datetime import datetime
from datetime import timedelta
from dotenv import load_dotenv
from logging.config import dictConfig
import os
import requests

from celery.schedules import crontab
from celery.utils.log import get_task_logger

from flask import Flask
from flask import jsonify
from flask import request

from flaskext.mysql import MySQL
from flask_caching import Cache
from tasks.tasks import make_celery


# Load environment variables from .env file
load_dotenv()
REE_TOKEN = os.environ.get('REE_TOKEN')

dictConfig({
    'version': 1,
    'formatters': {'default': {
        'format': '[%(asctime)s] %(levelname)s in %(module)s: %(message)s',
    }},
    'handlers': {'wsgi': {
        'class': 'logging.StreamHandler',
        'stream': 'ext://sys.stdout',
        'formatter': 'default'
    }},
    'root': {
        'level': 'INFO',
        'handlers': ['wsgi']
    }
})


app = Flask(__name__)
mysql = MySQL()

# MySQL configuration
app.config['MYSQL_DATABASE_USER'] = 'meteruser'
app.config['MYSQL_DATABASE_PASSWORD'] = os.environ.get('MYSQL_DATABASE_PASSWORD')
app.config['MYSQL_DATABASE_DB'] = 'meterdb'
app.config['MYSQL_DATABASE_HOST'] = 'localhost'

mysql.init_app(app)

task_logger = get_task_logger(__name__)

app.config.update(
    BROKER_BACKEND="redis",
    BROKER_HOST="localhost",
    BROKER_PORT=6379,
    BROKER_VHOST="0",
    CELERY_BROKER_URL="redis://localhost:6379",
    CELERY_RESULT_BACKEND="redis://localhost:6379",
    REDIS_HOST=6379,
    REDIS_PORT=6379,
    REDIS_DB=0,
)

# Config celery beat
app.config['CELERYBEAT_SCHEDULE'] = {
    # Executes every day at 20:45 
    'get_prices-every-day': {
        'task': 'get_prices',
        'schedule': crontab(hour="20", minute="45"),
    },
}

celery = make_celery(app)

# Cache configuration
cache = Cache(
    app, 
    config={
        'CACHE_TYPE': 'redis',
        'CACHE_KEY_PREFIX': 'meterit',
        'CACHE_REDIS_HOST': 'localhost',
        'CACHE_REDIS_PORT': 6379,
        'CACHE_REDIS_URL': 'redis://localhost:6379',
    }
)


@app.route('/', methods=['GET'])
def get():
    cur = mysql.connect().cursor()
    cur.execute("""SELECT * FROM meterdb.meterlog""")
    r = [dict((cur.description[i][0], value) for i, value in enumerate(row))for row in cur.fetchall()]
    return jsonify({'readings': r})


@app.route('/current_price', methods=['GET'])
def get_current_price():
    """ Return the current electricity price"""
    return jsonify({'price': str(current_price())})


@cache.cached(timeout=60)
def current_price():
    # Get it from the DB
    conn = mysql.connect()
    cursor = conn.cursor()
    sql = (
        "select price "
        "from meterdb.meterprice "
        "where date = date_sub(CONVERT_TZ(now(),'UTC','CET'), "
        "INTERVAL date_format(CONVERT_TZ(now(),'UTC','CET'),'%i:%s') MINUTE_SECOND);"
    )
    try:
        cursor.execute(sql)
        row = cursor.fetchone()
    except Exception as e:
        print("Error while connecting: %s", e)
        result = 0
    else:
        if row:
            app.logger.info("Getting electricity value: %s", row[0])
            result = float(row[0])
        else:
            app.logger.error("Error getting the price from DB")
            result = 0
    finally:
        cursor.close()
        conn.close()
    return result


@app.route('/force_get_prices', methods=['GET'])
def force_get_prices():
    get_prices()
    return jsonify({'status': 200, 'message': 'OK'})

@app.route('/ping', methods=['GET'])
def ping():
    return jsonify({'status': 200, 'message': 'OK'})

@app.route('/', methods=['POST'])
def post():
    req_data = request.get_json()
    watts = req_data.get('watts')
    station_id = req_data.get('station_id')
    price = str(current_price())
    data = (watts, station_id, price)
    if all(data):
        sql = "INSERT INTO meterlog(watts, station_id, price) VALUES(%s, %s, %s)"
        try:
            conn = mysql.connect()
            cursor = conn.cursor()
            cursor.execute(sql, data)
            conn.commit()
            response = jsonify({"status": 200, "message": "OK"})
            response.status_code = 200
        except Exception as e:
            print("An exception occurred")
            print(e)
        finally:
            cursor.close()
            conn.close()
    else:
        response = jsonify({"status": 400, "message": "Bad Request"})
        response.status_code = 400
    return response


@celery.task(name='get_prices')
def get_prices(today=False):
    print('Getting the prices')

    # previous indicator was 1876
    api_url = (
        'https://api.esios.ree.es/indicators/1001?'
        'start_date={:%d-%M-%Y}T00%3A00&end_date={:%d-M-%Y}T23%3A30'
    ).format
    if today:
        fetch_date = datetime.utcnow()
    else:
        fetch_date = datetime.utcnow() + timedelta(days=1)
    url = api_url(fetch_date.date(), fetch_date.date())
    task_logger.info(url)
    response = requests.get(
        url,
        headers={
            'content-type': 'application/json',
            'accept': 'application/json; application/vnd.esios-api-v2+json',
            'x-api-key': REE_TOKEN,
            'Host': 'api.esios.ree.es'
        }
    )

    values = response.json().get('indicator')['values']
    for value in values:
        if value.get('geo_id') == 8741:  # peninsula
            data = (value["value"], value["datetime"], 0)
            sql = "INSERT INTO meterprice(price, date, percentage) VALUES(%s, %s, %s)"
            try:
                conn = mysql.connect()
                cursor = conn.cursor()
                cursor.execute(sql, data)
                conn.commit()
            except Exception as e:
                # Try to update it
                task_logger.warning("Error inserting the prices; %s", e)
            finally:
                cursor.close()
                conn.close()


if __name__ == '__main__':
    app.run(host='0.0.0.0')

