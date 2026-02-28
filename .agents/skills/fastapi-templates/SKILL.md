---
name: fastapi-templates
description: Create production-ready FastAPI projects with async patterns, dependency injection, and comprehensive error handling. Use when building new FastAPI applications or setting up backend API projects.
---

# FastAPI Project Templates

Production-ready FastAPI project structures with async patterns, dependency injection, middleware, and best practices for building high-performance APIs.

## When to Use This Skill

- Starting new FastAPI projects from scratch
- Implementing async REST APIs with Python
- Building high-performance web services and microservices
- Creating async applications with PostgreSQL, MongoDB
- Setting up API projects with proper structure and testing

## Core Concepts

### 1. Project Structure

**Recommended Layout:**

```
app/
├── api/                    # API routes
│   ├── v1/
│   │   ├── endpoints/
│   │   │   ├── users.py
│   │   │   ├── auth.py
│   │   │   └── items.py
│   │   └── router.py
│   
├── core/                   # Core configuration
│   ├── config.py
│   ├── security.py
│   └── database.py
|   └── dependencies.py     # Shared dependencies
├── models/                 # Database models
│   ├── user.py
│   └── item.py
├── schemas/                # Pydantic schemas
│   ├── user.py
│   └── item.py
├── services/               # Business logic
│   ├── user_service.py
│   └── auth_service.py
├── repositories/           # Data access
│   ├── user_repository.py
│   └── item_repository.py
└── main.py                 # Application entry
```

### 2. Dependency Injection

FastAPI's built-in DI system using `Depends`:

- Database session management
- Authentication/authorization
- Shared business logic
- Configuration injection

### 3. Async Patterns

Proper async/await usage:

- Async route handlers
- Async database operations
- Async background tasks
- Async middleware

## Implementation Patterns

### Pattern 1: Complete FastAPI Application

```python
# main.py
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # Startup
    await database.connect()
    yield
    # Shutdown
    await database.disconnect()

app = FastAPI(
    title="API Template",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
from app.api.v1.router import api_router
app.include_router(api_router, prefix="/api/v1")

# core/config.py
from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    """Application settings."""
    DATABASE_URL: str
    SECRET_KEY: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    API_V1_STR: str = "/api/v1"

    class Config:
        env_file = ".env"

@lru_cache()
def get_settings() -> Settings:
    return Settings()

# core/database.py
from contextlib import asynccontextmanager
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncAttrs, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

class Database:
    """
    Wraps async SQLAlchemy engine with read-only and write session context managers.
    
    Usage:
        db = Database(database_url="postgresql+asyncpg://...")
        async with db.get_read_only_session() as session:
            # read-only operations (auto-rollback)
        async with db.get_write_session() as session:
            # write operations (auto-commit/rollback)
        await db.dispose()
    """

    def __init__(
        self,
        database_url: str,
        echo: bool = False,
        pool_size: int = 5,
        max_overflow: int = 10,
        pool_recycle: int = 3600,
        pool_pre_ping: bool = True,
        pool_reset_on_return: str | None = "rollback",
    ):
        self._engine = create_async_engine(
            database_url,
            echo=echo,
            future=True,
            pool_size=pool_size,
            max_overflow=max_overflow,
            pool_recycle=pool_recycle,
            pool_pre_ping=pool_pre_ping,
            pool_reset_on_return=pool_reset_on_return,
        )
        self._session_factory = async_sessionmaker(
            self._engine,
            expire_on_commit=False,
        )

    @asynccontextmanager
    async def get_read_only_session(self) -> AsyncGenerator[AsyncSession, None]:
        """Yield a session for read-only operations. Rolls back on close."""
        async with self._session_factory() as session:
            try:
                yield session
            finally:
                await session.rollback()

    @asynccontextmanager
    async def get_write_session(self) -> AsyncGenerator[AsyncSession, None]:
        """Yield a session inside a transaction. Commits on success, rolls back on error."""
        async with self._session_factory() as session:
            try:
                async with session.begin():
                    yield session
            except Exception:
                await session.rollback()
                raise

    async def dispose(self) -> None:
        """Dispose of the engine and connection pool."""
        await self._engine.dispose()


class Base(AsyncAttrs, DeclarativeBase):
    pass


# core/sessions.py - FastAPI dependencies
from collections.abc import AsyncGenerator
from typing import Annotated
from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

async def get_read_session(request: Request) -> AsyncGenerator[AsyncSession, None]:
    """Get a read-only session from app state."""
    async with request.app.state.postgres_db.get_read_only_session() as session:
        yield session

ReadDBSession = Annotated[AsyncSession, Depends(get_read_session)]

async def get_write_session(request: Request) -> AsyncGenerator[AsyncSession, None]:
    """Get a write session from app state."""
    async with request.app.state.postgres_db.get_write_session() as session:
        yield session

WriteDBSession = Annotated[AsyncSession, Depends(get_write_session)]
```

### Pattern 2: CRUD Repository Pattern

```python
# repositories/base_repository.py
from typing import Generic, TypeVar, Type, Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

ModelType = TypeVar("ModelType")
CreateSchemaType = TypeVar("CreateSchemaType", bound=BaseModel)
UpdateSchemaType = TypeVar("UpdateSchemaType", bound=BaseModel)

class BaseRepository(Generic[ModelType, CreateSchemaType, UpdateSchemaType]):
    """Base repository for CRUD operations."""

    def __init__(self, model: Type[ModelType]):
        self.model = model

    async def get(self, db: AsyncSession, id: int) -> Optional[ModelType]:
        """Get by ID."""
        result = await db.execute(
            select(self.model).where(self.model.id == id)
        )
        return result.scalars().first()

    async def get_multi(
        self,
        db: AsyncSession,
        skip: int = 0,
        limit: int = 100
    ) -> List[ModelType]:
        """Get multiple records."""
        result = await db.execute(
            select(self.model).offset(skip).limit(limit)
        )
        return result.scalars().all()

    async def create(
        self,
        db: AsyncSession,
        obj_in: CreateSchemaType
    ) -> ModelType:
        """Create new record."""
        db_obj = self.model(**obj_in.dict())
        db.add(db_obj)
        await db.flush()
        await db.refresh(db_obj)
        return db_obj

    async def update(
        self,
        db: AsyncSession,
        db_obj: ModelType,
        obj_in: UpdateSchemaType
    ) -> ModelType:
        """Update record."""
        update_data = obj_in.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_obj, field, value)
        await db.flush()
        await db.refresh(db_obj)
        return db_obj

    async def delete(self, db: AsyncSession, id: int) -> bool:
        """Delete record."""
        obj = await self.get(db, id)
        if obj:
            await db.delete(obj)
            return True
        return False

# repositories/user_repository.py
from app.repositories.base_repository import BaseRepository
from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate

class UserRepository(BaseRepository[User, UserCreate, UserUpdate]):
    """User-specific repository."""

    async def get_by_email(self, db: AsyncSession, email: str) -> Optional[User]:
        """Get user by email."""
        result = await db.execute(
            select(User).where(User.email == email)
        )
        return result.scalars().first()

    async def is_active(self, db: AsyncSession, user_id: int) -> bool:
        """Check if user is active."""
        user = await self.get(db, user_id)
        return user.is_active if user else False

user_repository = UserRepository(User)
```

### Pattern 3: Service Layer

```python
# services/user_service.py
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.repositories.user_repository import user_repository
from app.schemas.user import UserCreate, UserUpdate, User
from app.core.security import get_password_hash, verify_password

class UserService:
    """Business logic for users."""

    def __init__(self):
        self.repository = user_repository

    async def create_user(
        self,
        db: AsyncSession,
        user_in: UserCreate
    ) -> User:
        """Create new user with hashed password."""
        # Check if email exists
        existing = await self.repository.get_by_email(db, user_in.email)
        if existing:
            raise ValueError("Email already registered")

        # Hash password
        user_in_dict = user_in.dict()
        user_in_dict["hashed_password"] = get_password_hash(user_in_dict.pop("password"))

        # Create user
        user = await self.repository.create(db, UserCreate(**user_in_dict))
        return user

    async def authenticate(
        self,
        db: AsyncSession,
        email: str,
        password: str
    ) -> Optional[User]:
        """Authenticate user."""
        user = await self.repository.get_by_email(db, email)
        if not user:
            return None
        if not verify_password(password, user.hashed_password):
            return None
        return user

    async def update_user(
        self,
        db: AsyncSession,
        user_id: int,
        user_in: UserUpdate
    ) -> Optional[User]:
        """Update user."""
        user = await self.repository.get(db, user_id)
        if not user:
            return None

        if user_in.password:
            user_in_dict = user_in.dict(exclude_unset=True)
            user_in_dict["hashed_password"] = get_password_hash(
                user_in_dict.pop("password")
            )
            user_in = UserUpdate(**user_in_dict)

        return await self.repository.update(db, user, user_in)

user_service = UserService()
```

### Pattern 4: API Endpoints with Dependencies

```python
# api/v1/endpoints/users.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from app.core.database import get_db
from app.schemas.user import User, UserCreate, UserUpdate
from app.services.user_service import user_service
from app.api.dependencies import get_current_user

router = APIRouter()

@router.post("/", response_model=User, status_code=status.HTTP_201_CREATED)
async def create_user(
    user_in: UserCreate,
    db: AsyncSession = Depends(get_db)
):
    """Create new user."""
    try:
        user = await user_service.create_user(db, user_in)
        return user
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/me", response_model=User)
async def read_current_user(
    current_user: User = Depends(get_current_user)
):
    """Get current user."""
    return current_user

@router.get("/{user_id}", response_model=User)
async def read_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get user by ID."""
    user = await user_service.repository.get(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

@router.patch("/{user_id}", response_model=User)
async def update_user(
    user_id: int,
    user_in: UserUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update user."""
    if current_user.id != user_id:
        raise HTTPException(status_code=403, detail="Not authorized")

    user = await user_service.update_user(db, user_id, user_in)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete user."""
    if current_user.id != user_id:
        raise HTTPException(status_code=403, detail="Not authorized")

    deleted = await user_service.repository.delete(db, user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="User not found")
```

### Pattern 5: Authentication & Authorization

```python
# core/security.py
from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from app.core.config import get_settings

settings = get_settings()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

ALGORITHM = "HS256"

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Create JWT access token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against hash."""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """Hash password."""
    return pwd_context.hash(password)

# api/dependencies.py
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import ALGORITHM
from app.core.config import get_settings
from app.repositories.user_repository import user_repository

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/login")

async def get_current_user(
    db: AsyncSession = Depends(get_db),
    token: str = Depends(oauth2_scheme)
):
    """Get current authenticated user."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        user_id: int = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = await user_repository.get(db, user_id)
    if user is None:
        raise credentials_exception

    return user
```

## Testing

```python
# tests/conftest.py
import asyncio
from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import Base
from app.core.sessions import get_read_session, get_write_session
from app.core.config import get_settings

settings = get_settings()

# Build test database URL from settings, appending "_test" to the DB name
TEST_DATABASE_URL = settings.DATABASE_URL.replace(
    f"/{settings.DB_NAME}", f"/{settings.DB_NAME}_test"
)

test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
test_session_factory = async_sessionmaker(test_engine, expire_on_commit=False)


@pytest.fixture(scope="session")
def event_loop():
    """Create a single event loop for the entire test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session", autouse=True)
async def setup_database():
    """Create all tables before tests and drop them after."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await test_engine.dispose()


@pytest.fixture
async def session() -> AsyncGenerator[AsyncSession, None]:
    """Provide a transactional session that rolls back after each test."""
    async with test_session_factory() as session:
        async with session.begin():
            yield session
            await session.rollback()


@pytest.fixture
async def ac(session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Provide an AsyncClient with DB session overrides."""
    from app.main import app

    async def override_read_session():
        yield session

    async def override_write_session():
        yield session

    app.dependency_overrides[get_read_session] = override_read_session
    app.dependency_overrides[get_write_session] = override_write_session

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client

    app.dependency_overrides.clear()

# tests/test_users.py
import pytest

async def test_create_user(ac):
    response = await ac.post(
        "/api/v1/users/",
        json={
            "email": "test@example.com",
            "password": "testpass123",
            "name": "Test User"
        }
    )
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "test@example.com"
    assert "id" in data
```

## Resources

- **references/fastapi-architecture.md**: Detailed architecture guide
- **references/async-best-practices.md**: Async/await patterns
- **references/testing-strategies.md**: Comprehensive testing guide
- **assets/project-template/**: Complete FastAPI project
- **assets/docker-compose.yml**: Development environment setup

## Best Practices

1. **Async All The Way**: Use async for database, external APIs
2. **Dependency Injection**: Leverage FastAPI's DI system
3. **Repository Pattern**: Separate data access from business logic
4. **Service Layer**: Keep business logic out of routes
5. **Pydantic Schemas**: Strong typing for request/response
6. **Error Handling**: Consistent error responses
7. **Testing**: Test all layers independently

## Common Pitfalls

- **Blocking Code in Async**: Using synchronous database drivers
- **No Service Layer**: Business logic in route handlers
- **Missing Type Hints**: Loses FastAPI's benefits
- **Ignoring Sessions**: Not properly managing database sessions
- **No Testing**: Skipping integration tests
- **Tight Coupling**: Direct database access in routes
