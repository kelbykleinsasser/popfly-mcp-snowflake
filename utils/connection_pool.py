"""
Snowflake connection pool manager for improved performance
"""
import logging
import threading
from queue import Queue, Empty
from typing import Optional, Dict, Any
from contextlib import contextmanager
import snowflake.connector
from snowflake.connector import SnowflakeConnection

from config.settings import settings
from auth.snowflake_auth import get_private_key_bytes


class ConnectionPool:
    """Thread-safe connection pool for Snowflake"""
    
    def __init__(self, min_size: int = 2, max_size: int = 10):
        """
        Initialize connection pool
        
        Args:
            min_size: Minimum number of connections to maintain
            max_size: Maximum number of connections allowed
        """
        self.min_size = min_size
        self.max_size = max_size
        self._pool = Queue(maxsize=max_size)
        self._all_connections = set()
        self._lock = threading.Lock()
        self._closed = False
        
        # Connection parameters
        self._conn_params = self._get_connection_params()
        
        # Initialize minimum connections
        self._initialize_pool()
        
        logging.info(f"Connection pool initialized with min={min_size}, max={max_size}")
    
    def _get_connection_params(self) -> Dict[str, Any]:
        """Get connection parameters based on environment"""
        if settings.environment == 'production' and settings.use_gcp_secrets:
            # Production with GCP secrets
            from auth.snowflake_auth_secure import get_private_key_from_secret
            private_key = get_private_key_from_secret()
            
            return {
                'account': settings.snowflake_account,
                'user': settings.snowflake_user,
                'private_key': private_key,
                'database': settings.snowflake_database,
                'schema': settings.snowflake_schema,
                'warehouse': settings.snowflake_warehouse,
                'role': settings.snowflake_role,
                'session_parameters': {
                    'QUERY_TAG': 'mcp_server_pooled'
                }
            }
        else:
            # Local environment
            private_key = get_private_key_bytes(
                settings.snowflake_private_key_path,
                settings.snowflake_private_key_passphrase
            )
            
            return {
                'account': settings.snowflake_account,
                'user': settings.snowflake_user,
                'private_key': private_key,
                'database': settings.snowflake_database,
                'schema': settings.snowflake_schema,
                'warehouse': settings.snowflake_warehouse,
                'role': settings.snowflake_role,
                'session_parameters': {
                    'QUERY_TAG': 'mcp_server_pooled'
                }
            }
    
    def _create_connection(self) -> SnowflakeConnection:
        """Create a new Snowflake connection"""
        try:
            conn = snowflake.connector.connect(**self._conn_params)
            logging.debug("Created new Snowflake connection")
            return conn
        except Exception as e:
            logging.error(f"Failed to create connection: {e}")
            raise
    
    def _initialize_pool(self):
        """Initialize the pool with minimum connections"""
        for _ in range(self.min_size):
            try:
                conn = self._create_connection()
                self._pool.put(conn)
                self._all_connections.add(conn)
            except Exception as e:
                logging.warning(f"Failed to create initial connection: {e}")
    
    @contextmanager
    def get_connection(self, timeout: Optional[float] = 5.0):
        """
        Get a connection from the pool
        
        Args:
            timeout: Maximum time to wait for a connection
            
        Yields:
            SnowflakeConnection: A connection from the pool
        """
        if self._closed:
            raise RuntimeError("Connection pool is closed")
        
        conn = None
        created_new = False
        
        try:
            # Try to get from pool
            try:
                conn = self._pool.get(timeout=timeout)
                # Test if connection is still alive
                cursor = conn.cursor()
                cursor.execute("SELECT 1")
                cursor.close()
            except Empty:
                # Pool is empty, try to create new connection if under max
                with self._lock:
                    if len(self._all_connections) < self.max_size:
                        conn = self._create_connection()
                        self._all_connections.add(conn)
                        created_new = True
                    else:
                        raise RuntimeError("Connection pool exhausted")
            except Exception:
                # Connection is dead, create a new one
                if conn:
                    self._all_connections.discard(conn)
                    try:
                        conn.close()
                    except:
                        pass
                conn = self._create_connection()
                self._all_connections.add(conn)
                created_new = True
            
            yield conn
            
        finally:
            # Return connection to pool
            if conn and not self._closed:
                try:
                    # Only return to pool if connection is healthy
                    cursor = conn.cursor()
                    cursor.execute("SELECT 1")
                    cursor.close()
                    
                    if not created_new or self._pool.qsize() < self.min_size:
                        self._pool.put(conn)
                    else:
                        # Pool has enough connections, close this one
                        with self._lock:
                            self._all_connections.discard(conn)
                        conn.close()
                except:
                    # Connection is unhealthy, close it
                    with self._lock:
                        self._all_connections.discard(conn)
                    try:
                        conn.close()
                    except:
                        pass
    
    def close_all(self):
        """Close all connections in the pool"""
        self._closed = True
        
        with self._lock:
            # Close all connections
            while not self._pool.empty():
                try:
                    conn = self._pool.get_nowait()
                    conn.close()
                except:
                    pass
            
            # Close any connections not in the pool
            for conn in self._all_connections:
                try:
                    conn.close()
                except:
                    pass
            
            self._all_connections.clear()
        
        logging.info("Connection pool closed")
    
    def get_stats(self) -> Dict[str, int]:
        """Get pool statistics"""
        return {
            'available': self._pool.qsize(),
            'total': len(self._all_connections),
            'in_use': len(self._all_connections) - self._pool.qsize()
        }


# Global connection pool instance
_pool: Optional[ConnectionPool] = None
_pool_lock = threading.Lock()


def get_pool() -> ConnectionPool:
    """Get or create the global connection pool"""
    global _pool
    
    if _pool is None:
        with _pool_lock:
            if _pool is None:
                _pool = ConnectionPool(
                    min_size=settings.connection_pool_min_size if hasattr(settings, 'connection_pool_min_size') else 2,
                    max_size=settings.connection_pool_max_size if hasattr(settings, 'connection_pool_max_size') else 10
                )
    
    return _pool


@contextmanager
def get_pooled_connection(timeout: Optional[float] = 5.0):
    """
    Get a connection from the global pool
    
    Args:
        timeout: Maximum time to wait for a connection
        
    Yields:
        SnowflakeConnection: A pooled connection
    """
    pool = get_pool()
    with pool.get_connection(timeout=timeout) as conn:
        yield conn


def close_pool():
    """Close the global connection pool"""
    global _pool
    
    if _pool:
        _pool.close_all()
        _pool = None