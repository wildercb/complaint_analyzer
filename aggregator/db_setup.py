import os
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

def setup_database():
    # Get database configuration from environment variables
    db_user = os.getenv('POSTGRES_USER', 'postgres')
    db_pass = os.getenv('POSTGRES_PASSWORD', 'postgres')
    db_name = os.getenv('POSTGRES_DB', 'complaintsdb')
    db_host = os.getenv('POSTGRES_HOST', 'localhost')

    # Connect to the default 'postgres' database to create a new database
    conn = psycopg2.connect(
        dbname='postgres',
        user=db_user,
        password=db_pass,
        host=db_host
    )
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    
    cur = conn.cursor()
    
    # Create the database if it doesn't exist
    cur.execute(f"SELECT 1 FROM pg_catalog.pg_database WHERE datname = '{db_name}'")
    exists = cur.fetchone()
    if not exists:
        cur.execute(f'CREATE DATABASE {db_name}')
        print(f"Database '{db_name}' created.")
    else:
        print(f"Database '{db_name}' already exists.")

    cur.close()
    conn.close()

    # Connect to the new database to create tables
    conn = psycopg2.connect(
        dbname=db_name,
        user=db_user,
        password=db_pass,
        host=db_host
    )
    cur = conn.cursor()

    # Create tables
    cur.execute('''
        CREATE TABLE IF NOT EXISTS complaints (
            id SERIAL PRIMARY KEY,
            type VARCHAR(50) NOT NULL,
            content JSONB NOT NULL,
            category VARCHAR(100) NOT NULL,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    conn.commit()
    cur.close()
    conn.close()

    print("Database setup completed.")

if __name__ == "__main__":
    setup_database()