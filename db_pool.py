import os
import logging
import psycopg2
from psycopg2 import pool
from contextlib import contextmanager

logger = logging.getLogger(__name__)

class DatabasePool:
    _instance = None
    _pool = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DatabasePool, cls).__new__(cls)
            cls._instance._initialize_pool()
        return cls._instance

    def _initialize_pool(self):
        try:
            # Load PG config from environment
            pg_host = os.environ.get("PG_HOST", "localhost")
            pg_port = os.environ.get("PG_PORT", "5432")
            pg_user = os.environ.get("PG_USER", "postgres")
            pg_pass = os.environ.get("PG_PASSWORD", "password")
            pg_db   = os.environ.get("PG_DB", "schema_test")

            logger.info(f"Initializing PostgreSQL ThreadedConnectionPool ({pg_host}:{pg_port})")
            
            self._pool = pool.ThreadedConnectionPool(
                minconn=2,
                maxconn=10,
                host=pg_host,
                port=pg_port,
                user=pg_user,
                password=pg_pass,
                dbname=pg_db
            )
            logger.info("Database pool initialized successfully (min: 2, max: 10)")
        except Exception as e:
            logger.error(f"Failed to initialize database pool: {str(e)}")
            self._pool = None

    @contextmanager
    def get_conn(self):
        """Context manager to get a connection from the pool and release it back."""
        if self._pool is None:
            # Fallback to direct connection if pool failed to initialize
            logger.warning("Database pool not available, using direct connection fallback")
            conn = psycopg2.connect(
                host=os.environ.get("PG_HOST", "localhost"),
                port=os.environ.get("PG_PORT", "5432"),
                user=os.environ.get("PG_USER", "postgres"),
                password=os.environ.get("PG_PASSWORD", "password"),
                dbname=os.environ.get("PG_DB", "schema_test")
            )
            try:
                yield conn
            finally:
                conn.close()
            return

        conn = self._pool.getconn()
        try:
            yield conn
        finally:
            self._pool.putconn(conn)

    def close_all(self):
        if self._pool:
            self._pool.closeall()
            logger.info("Database pool closed")

# Singleton instance
db_pool = DatabasePool()
