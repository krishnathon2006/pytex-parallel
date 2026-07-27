DATABASE_URL = "postgresql+psycopg://postgres:postgres@localhost:7432/postgres"
REDIS_URL = "redis://localhost:7379/0"
PAYMENT_API_URL = "http://localhost:9001"
PROTECTION_API_URL = "http://localhost:9002"
BOOKING_TTL_MINUTES = 15

REDIS_EVENT_LOCK_TTL_SECONDS = 3
REDIS_EVENT_LOCK_WAIT_SECONDS = 1
REDIS_EVENT_CACHE_TTL_SECONDS = 60
REDIS_EVENT_NOT_FOUND_TTL_SECONDS = 10
# Доля от TTL, на которую он случайно растягивается, чтобы ключи не протухали разом.
REDIS_EVENT_CACHE_TTL_JITTER_RATIO = 0.2
