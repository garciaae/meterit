# Meterit: A Flask App for Electricity Usage & Pricing

This application reads and stores electricity usage data in MySQL, and automatically fetches daily electricity prices from an external API. It provides a simple Flask-based API to retrieve the current or historical prices and usage readings.

## Requirements

- **Python >= 3.5**
- **MySQL** (with an existing database named `meterdb`)
- **Redis** (for Celery task scheduling and caching)
- **Environment Variables** (in a `.env` file):
  - `REE_TOKEN` (API key for the external electricity prices service)
  - `MYSQL_DATABASE_PASSWORD` (MySQL database password)

## Setup & Installation

1. **Clone the Repository**  
   ```bash
   git clone https://your-repo-url.git
   cd your-repo
```

2. **Create and Activate a Virtual Environment (Optional but Recommended)**
```
python3 -m venv venv
source venv/bin/activate
```

3. **Install Dependencies**
```
pip install -r requirements.txt
```

4. **Configure Your Environment Variables**
```
REE_TOKEN=your-ree-token
MYSQL_DATABASE_PASSWORD=your-db-password
```

5. **Start required services**
- make sure mysql is running (and you have a meterdb database set up).
- make sure redis is running on localhost:6379 (or update the config).

6. **run the application**
```
python app.py
```
The flask app will start on http://0.0.0.0:5000.

7. **Run celery for scheduled tasks** 
if you want the daily price-fetching to run automatically, you need to start celery:

```bash
celery -a tasks.tasks:celery worker --beat --loglevel=info
```

Adjust your celery command as needed, ensuring it points to your celery instance (`tasks.tasks:celery`) and includes the `--beat` flag to schedule tasks.

## useful endpoints

- GET /
returns all meter readings from the database.

- GET /current_price
returns the current electricity price.

- GET /ping
basic health check, returns {"status": 200, "message": "ok"}.

- GET /force_get_prices
Manually triggers the price-fetch task.

- POST /
Inserts a new meter reading into the database with the json body:

```json
{
  "watts": 123,
  "station_id": "my-station"
}
```

## Contributing
Feel free to submit issues or pull requests if you find a bug or want to propose improvements.

