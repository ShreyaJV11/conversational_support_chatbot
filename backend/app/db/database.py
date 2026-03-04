import psycopg2
from app.core.config import settings

def get_connection():
    print("DB_NAME:", settings.DB_NAME)
    print("DB_USER:", settings.DB_USER)
    print("DB_HOST:", settings.DB_HOST)
    print("DB_PORT:", settings.DB_PORT)

    return psycopg2.connect(
        dbname=settings.DB_NAME,
        user=settings.DB_USER,
        password=settings.DB_PASSWORD,
        host=settings.DB_HOST,
        port=settings.DB_PORT
    )