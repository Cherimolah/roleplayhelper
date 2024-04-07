Run:
`git clone git@github.com:Cherimolah/roleplayhelper.git`
`cd roleplayhelper`
`python3 -m venv venv`
`source venv/bin/activate` or `venv\Scripts\activate.bat`
Create PostgreSQL database
Create `.env` file
Fill .env by sample in .env_sample
Run:
`pip3 install -r requirements.txt`
`alembic init alembic`
Set in alembic.ini
`sqlalchemy.url = postgres://postgres:pass@localhost/dbname`
Add in start of alembic/env.py:
`from service.db_engine import db`
Set in the same file:
`target_metadata = db`
Run:
`alembic revision -m "first migration" --autogenerate --head head`
`alembic upgrade head`

Configure a systemd file for restart!
