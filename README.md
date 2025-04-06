# Installation guide

* Run:
```shell
git clone git@github.com:Cherimolah/roleplayhelper.git
cd roleplayhelper
python3 -m venv venv
source venv/bin/activate  # Linux
venv\Scripts\activate.bat  # Windows
```
* Create PostgreSQL database <br>
* Create `.env` file <br>
* Fill `.env` by sample in `.env_sample` <br>
* Run:
```shell
sudo apt-get install libpq-dev
pip3 install -r requirements.txt
alembic init alembic
```
* Set in `alembic.ini` <br>
```ini
sqlalchemy.url = postgres://postgres:pass@localhost/dbname
```
* Add in start of `alembic/env.py`: <br>
```python
from service.db_engine import db
```
* Set in the same file:
```python
target_metadata = db
```
* Run:
```shell
alembic revision -m "first migration" --autogenerate --head head
alembic upgrade head
```

* Configure a systemd file for restart! <br>
```shell
nano /etc/systemd/system/roleplayhelper.service
```

* Example for `roleplayhelper.service` <br>
```
[Unit]
Description=Roleplay Helper VK

[Service]
ExecStart=/bin/bash /root/roleplayhelper/startbot
KillMode=mixed

[Install]
WantedBy=multiuser.target
```
**Note that `ExecStart` need to execute `startbot` file**

* That's all, run code <br>
```shell
systemctl restart roleplayhelper
```