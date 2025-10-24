import json
import hashlib
import logging
from typing import Optional, Any
import redis.asyncio as redis
from src.config.settings import settings

logger = logging.getLogger(__name__)


class RedisCache:
    def __init__(self):
        self.client: Optional[redis.Redis] = None
        self.enabled = settings.cache_enabled
    
    async def connect(self):
        if not self.enabled:
            logger.info("Cache disabled via configuration")
            return
        
        try:
            self.client = redis.from_url(
                settings.redis_url,
                encoding="utf-8",
                decode_responses=True
            )
            await self.client.ping()
            logger.info("Redis cache connected successfully")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            self.enabled = False
    
    async def close(self):
        if self.client:
            await self.client.close()
    
    def _make_key(self, prefix: str, identifier: str) -> str:
        return f"{prefix}:{identifier}"
    
    def _hash_prompt(self, prompt: str) -> str:
        return hashlib.sha256(prompt.encode()).hexdigest()[:16]
    
    async def get(self, key: str) -> Optional[Any]:
        if not self.enabled or not self.client:
            return None
        
        try:
            value = await self.client.get(key)
            if value:
                logger.debug(f"Cache HIT: {key}")
                return json.loads(value)
            logger.debug(f"Cache MISS: {key}")
        except Exception as e:
            logger.error(f"Cache get error for {key}: {e}")
        
        return None
    
    async def set(self, key: str, value: Any, ttl: Optional[int] = None):
        if not self.enabled or not self.client:
            return
        
        try:
            serialized = json.dumps(value, default=str)
            if ttl:
                await self.client.setex(key, ttl, serialized)
            else:
                await self.client.set(key, serialized)
            logger.debug(f"Cache SET: {key} (TTL: {ttl})")
        except Exception as e:
            logger.error(f"Cache set error for {key}: {e}")
    
    async def get_resume(self, submission_id: str) -> Optional[dict]:
        key = self._make_key("resume", submission_id)
        return await self.get(key)
    
    async def set_resume(self, submission_id: str, parsed_data: dict):
        key = self._make_key("resume", submission_id)
        await self.set(key, parsed_data, settings.cache_ttl_parse)
    
    async def get_transcript(self, submission_id: str) -> Optional[dict]:
        key = self._make_key("transcript", submission_id)
        return await self.get(key)
    
    async def set_transcript(self, submission_id: str, parsed_data: dict):
        key = self._make_key("transcript", submission_id)
        await self.set(key, parsed_data, settings.cache_ttl_parse)
    
    async def get_scrape(self, url: str) -> Optional[dict]:
        key = self._make_key("scrape", hashlib.sha256(url.encode()).hexdigest()[:16])
        return await self.get(key)
    
    async def set_scrape(self, url: str, result: dict):
        key = self._make_key("scrape", hashlib.sha256(url.encode()).hexdigest()[:16])
        await self.set(key, result, settings.cache_ttl_scrape)
    
    async def get_gpt_response(self, prompt: str) -> Optional[str]:
        key = self._make_key("gpt", self._hash_prompt(prompt))
        result = await self.get(key)
        return result.get("response") if result else None
    
    async def set_gpt_response(self, prompt: str, response: str):
        key = self._make_key("gpt", self._hash_prompt(prompt))
        await self.set(key, {"response": response}, settings.cache_ttl_gpt)


# Global cache instance
cache = RedisCache()
