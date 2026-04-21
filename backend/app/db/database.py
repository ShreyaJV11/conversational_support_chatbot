import psycopg2
from psycopg2 import pool
from app.core.config import settings

# Create a connection pool (reuse connections instead of creating new ones)
connection_pool = None

def init_connection_pool():
    """Initialize the connection pool on startup"""
    global connection_pool
    if connection_pool is None:
        connection_pool = psycopg2.pool.SimpleConnectionPool(
            minconn=1,
            maxconn=20,  # Maximum 20 connections
            dbname=settings.DB_NAME,
            user=settings.DB_USER,
            password=settings.DB_PASSWORD,
            host=settings.DB_HOST,
            port=settings.DB_PORT or 5432
        )

def get_connection():
    """Get a connection from the pool"""
    if connection_pool is None:
        init_connection_pool()
    return connection_pool.getconn()

def return_connection(conn):
    """Return connection to the pool"""
    if connection_pool and conn:
        connection_pool.putconn(conn)

def close_all_connections():
    """Close all connections in the pool"""
    global connection_pool
    if connection_pool:
        connection_pool.closeall()
        connection_pool = None