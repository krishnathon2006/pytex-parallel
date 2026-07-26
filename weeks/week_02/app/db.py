from app.config import DATABASE_URL
from app.infra.postgres.postgres import PostgresClient

postgres = PostgresClient(DATABASE_URL)
