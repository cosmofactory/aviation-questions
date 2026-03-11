from collections.abc import AsyncIterator
from contextlib import AsyncExitStack, asynccontextmanager

import logfire
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi_pagination import add_pagination

from src.core.embedding import EmbeddingClient
from src.core.engine import Database
from src.core.s3 import S3Client
from src.documents.router import router as documents_router
from src.questions.router import router as questions_router
from src.settings import settings

# === Logfire: configure BEFORE creating the app ===
logfire.configure(
    inspect_arguments=True,
    service_name=settings.SERVICE_NAME,
    metrics=False,
    environment=settings.ENV,
)

# Instrument frameworks before creating clients/app
logfire.instrument_httpx()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """
    Manage application lifespan events.

    Sets up database connection on startup and cleans up on shutdown.
    AsyncExitStack is used to manage connection context and gracefully
    close sessions.
    """
    async with AsyncExitStack() as stack:
        # === Postgres Client Initialization ===
        database = Database(database_url=settings.database.DATABASE_URL)
        app.state.postgres_db = database
        stack.push_async_callback(database.dispose)

        # Instrument SQLAlchemy engine for query tracing
        logfire.instrument_sqlalchemy(engine=database._engine.sync_engine)

        # === S3 Client Initialization ===
        s3_client = S3Client(settings.s3)
        await stack.enter_async_context(s3_client)
        app.state.s3 = s3_client

        # === Embedding Client Initialization ===
        embedding_client = EmbeddingClient(settings.openai)
        await stack.enter_async_context(embedding_client)
        app.state.embedding_client = embedding_client

        yield


app = FastAPI(lifespan=lifespan)

logfire.instrument_fastapi(app)


origins = [
    "http://localhost:3000",
]


app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(documents_router, prefix="/documents", tags=["Documents"])
app.include_router(questions_router, prefix="/questions", tags=["Questions"])

add_pagination(app)
