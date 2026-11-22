# MySQL setup

The application connects to a MySQL Server. MySQL Workbench is used to manage
the server; it is not itself the server. Configure the app and Workbench to use
the same MySQL server address and database.

## Create the database and an application user

Connect to your MySQL Server in Workbench and run the following SQL. Replace
the sample password with a strong password of your own:

```sql
CREATE DATABASE IF NOT EXISTS campuslink
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

CREATE USER IF NOT EXISTS 'campuslink_app'@'127.0.0.1'
  IDENTIFIED BY 'replace-with-a-strong-password';

GRANT SELECT, INSERT, UPDATE, DELETE, CREATE
  ON campuslink.*
  TO 'campuslink_app'@'127.0.0.1';
```

The application creates the `tickets`, `technicians`, and `migration_state`
tables on startup. It imports the existing `maintenance_db.json` and
`techs.json` data once into an empty MySQL database, if those files are present.
Keep the JSON files until the import has completed and the records are verified
in Workbench.

## Configure a local application

Add these values to the project's ignored `.env` file. Use the same password
you set for the MySQL application user:

```dotenv
MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306
MYSQL_DATABASE=campuslink
MYSQL_USER=campuslink_app
MYSQL_PASSWORD=replace-with-a-strong-password
```

Install dependencies and start the app from the project directory:

```text
pip install -r requirements.txt
python app.py
```

The MySQL account must be allowed to connect from the app's host. For the
local example, the account is granted access from `127.0.0.1`. If the app is
hosted elsewhere, configure a reachable MySQL server and an account/host grant
appropriate to that hosting provider; `127.0.0.1` would refer to the app host,
not your personal computer.

## Configure Render

Set `MYSQL_HOST`, `MYSQL_DATABASE`, `MYSQL_USER`, and `MYSQL_PASSWORD` in the
Render service environment to the values supplied by your MySQL hosting
provider. `MYSQL_PORT` defaults to `3306`. Ensure that the provider permits
connections from Render and that its firewall/allowlist is configured
accordingly.
