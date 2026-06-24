# VERSUS — CS460 Final Project

VERSUS is a Flask and MySQL web application for creating and running tournament brackets. Users can create brackets, make Round 1 predictions, vote during active rounds, comment on matchups, follow other users, earn achievements, and view a leaderboard and completed champion path.

## Setup

Install Python 3 and MySQL first.

Clone the repository:

```bash
git clone https://github.com/rohanyadavreal/CS460VersusProject.git
cd CS460VersusProject
```

Create and activate a virtual environment:

```bash
python3 -m venv cs460env
source cs460env/bin/activate
```

Install Python dependencies:

```bash
cd versus_skeleton
pip install -r requirements.txt
```

Open `app.py` and set this value to the MySQL root password for the computer:

```python
DB_PASSWORD = 'YOUR_PASSWORD'
```

Start MySQL:

```bash
/usr/local/mysql/support-files/mysql.server start
```

Create the database and load the schema:

```bash
/usr/local/mysql/bin/mysql -u root -p < schema.sql
```

Run the Flask application:

```bash
python3 app.py
```

Open the site in a browser:

```text
http://127.0.0.1:5001/
```
