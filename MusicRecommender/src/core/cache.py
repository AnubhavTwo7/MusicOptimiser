import redis
import json
import pickle
from typing import Any, Optional, Union
import logging
from datetime import timedelta

from .config import config

logger = logging.getLogger(__name__)

class CacheManager:
    def __init__(self):
        self.redis_client = redis.Redis(
            host=config.redis.host,
            port=config.redis.port,
            password=config.redis.password,
            decode_responses=False,  # We'll handle encoding ourselves
            socket_connect_timeout=5,
            socket_timeout=5,
            retry_on_timeout=True,
            health_check_interval=30
        )
        
    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        try:
            value = self.redis_client.get(key)
            if value is None:
                return None
            
            # Try to deserialize as JSON first, then pickle
            try:
                return json.loads(value.decode('utf-8'))
            except (json.JSONDecodeError, UnicodeDecodeError):
                return pickle.loads(value)
                
        except Exception as e:
            logger.error(f"Cache get error for key {key}: {str(e)}")
            return None
    
    async def set(self, key: str, value: Any, ttl: int = 3600) -> bool:
        """Set value in cache with TTL."""
        try:
            # Try to serialize as JSON first, then pickle
            try:
                serialized_value = json.dumps(value)
            except TypeError:
                serialized_value = pickle.dumps(value)
            
            return self.redis_client.setex(key, ttl, serialized_value)
            
        except Exception as e:
            logger.error(f"Cache set error for key {key}: {str(e)}")
            return False
    
    async def delete(self, key: str) -> bool:
        """Delete key from cache."""
        try:
            return bool(self.redis_client.delete(key))
        except Exception as e:
            logger.error(f"Cache delete error for key {key}: {str(e)}")
            return False
    
    async def exists(self, key: str) -> bool:
        """Check if key exists in cache."""
        try:
            return bool(self.redis_client.exists(key))
        except Exception as e:
            logger.error(f"Cache exists error for key {key}: {str(e)}")
            return False
    
    async def get_many(self, keys: list) -> dict:
        """Get multiple values from cache."""
        try:
            values = self.redis_client.mget(keys)
            result = {}
            
            for key, value in zip(keys, values):
                if value is not None:
                    try:
                        result[key] = json.loads(value.decode('utf-8'))
                    except (json.JSONDecodeError, UnicodeDecodeError):
                        result[key] = pickle.loads(value)
                        
            return result
            
        except Exception as e:
            logger.error(f"Cache get_many error: {str(e)}")
            return {}
    
    async def set_many(self, mapping: dict, ttl: int = 3600) -> bool:
        """Set multiple values in cache."""
        try:
            pipe = self.redis_client.pipeline()
            
            for key, value in mapping.items():
                try:
                    serialized_value = json.dumps(value)
                except TypeError:
                    serialized_value = pickle.dumps(value)
                    
                pipe.setex(key, ttl, serialized_value)
            
            pipe.execute()
            return True
            
        except Exception as e:
            logger.error(f"Cache set_many error: {str(e)}")
            return False
    
    async def increment(self, key: str, amount: int = 1) -> int:
        """Increment a counter in cache."""
        try:
            return self.redis_client.incr(key, amount)
        except Exception as e:
            logger.error(f"Cache increment error for key {key}: {str(e)}")
            return 0
    
    async def expire(self, key: str, ttl: int) -> bool:
        """Set expiration for a key."""
        try:
            return bool(self.redis_client.expire(key, ttl))
        except Exception as e:
            logger.error(f"Cache expire error for key {key}: {str(e)}")
            return False
    
    def health_check(self) -> bool:
        """Check Redis connection health."""
        try:
            self.redis_client.ping()
            return True
        except Exception as e:
            logger.error(f"Redis health check failed: {str(e)}")
            return False

# Global cache manager instance
cache_manager = CacheManager()
