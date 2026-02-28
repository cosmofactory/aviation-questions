---
name: python-testing-patterns
description: Comprehensive testing strategies with pytest, fixtures, mocking, and async testing. Use when writing Python tests, setting up test suites, mocking dependencies, or implementing test-driven development.
user-invokable: false
---

# Python Testing Patterns

Comprehensive guide to implementing robust testing strategies in Python using pytest, fixtures, mocking, parameterization, and test-driven development practices.

## Core Concepts

### Test Structure (AAA Pattern)

- **Arrange**: Set up test data and preconditions
- **Act**: Execute the code under test
- **Assert**: Verify the results

### Test Isolation

- Tests should be independent
- No shared state between tests
- Each test should clean up after itself

## Fundamental Patterns

### Basic pytest Tests

```python
import pytest

def test_addition():
    calc = Calculator()
    assert calc.add(2, 3) == 5
    assert calc.add(-1, 1) == 0

def test_division_by_zero():
    calc = Calculator()
    with pytest.raises(ValueError, match="Cannot divide by zero"):
        calc.divide(5, 0)
```

### Fixtures for Setup and Teardown

```python
@pytest.fixture
def db() -> Generator[Database, None, None]:
    database = Database("sqlite:///:memory:")
    database.connect()
    yield database
    database.disconnect()

def test_database_query(db):
    results = db.query("SELECT * FROM users")
    assert len(results) == 1
```

### Parameterized Tests

```python
@pytest.mark.parametrize("email,expected", [
    ("user@example.com", True),
    ("invalid.email", False),
    ("@example.com", False),
])
def test_email_validation(email, expected):
    assert is_valid_email(email) == expected
```

### Mocking with unittest.mock

```python
from unittest.mock import Mock, patch

def test_get_user_success():
    client = APIClient("https://api.example.com")
    mock_response = Mock()
    mock_response.json.return_value = {"id": 1, "name": "John Doe"}
    mock_response.raise_for_status.return_value = None

    with patch("requests.get", return_value=mock_response) as mock_get:
        user = client.get_user(1)
        assert user["id"] == 1
        mock_get.assert_called_once_with("https://api.example.com/users/1")
```

### Testing Exceptions

```python
def test_exception_message():
    with pytest.raises(ZeroDivisionError, match="Division by zero"):
        divide(5, 0)

def test_exception_info():
    with pytest.raises(ValueError) as exc_info:
        int("not a number")
    assert "invalid literal" in str(exc_info.value)
```

## Advanced Patterns

### Testing Async Code

```python
@pytest.mark.asyncio
async def test_fetch_data():
    result = await fetch_data("https://api.example.com")
    assert result["url"] == "https://api.example.com"

@pytest.mark.asyncio
async def test_concurrent_fetches():
    urls = ["url1", "url2", "url3"]
    tasks = [fetch_data(url) for url in urls]
    results = await asyncio.gather(*tasks)
    assert len(results) == 3
```

### Monkeypatch for Testing

```python
def test_database_url_custom(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://localhost/test")
    assert get_database_url() == "postgresql://localhost/test"

def test_monkeypatch_attribute(monkeypatch):
    config = Config()
    monkeypatch.setattr(config, "api_key", "test-key")
    assert config.get_api_key() == "test-key"
```

### Mocking Time with Freezegun

```python
from freezegun import freeze_time

@freeze_time("2026-01-15 10:00:00")
def test_token_expiry():
    token = create_token(expires_in_seconds=3600)
    assert token.expires_at == datetime(2026, 1, 15, 11, 0, 0)
```

### Testing Retry Behavior

```python
def test_retries_on_transient_error():
    client = Mock()
    client.request.side_effect = [
        ConnectionError("Failed"),
        ConnectionError("Failed"),
        {"status": "ok"},
    ]
    service = ServiceWithRetry(client, max_retries=3)
    result = service.fetch()
    assert result == {"status": "ok"}
    assert client.request.call_count == 3
```

## Test Design Principles

### One Behavior Per Test

```python
# GOOD - focused tests
def test_create_user_assigns_id():
    user = service.create_user(data)
    assert user.id is not None

def test_create_user_stores_email():
    user = service.create_user(data)
    assert user.email == data["email"]
```

### Test Error Paths

```python
def test_get_user_raises_not_found():
    with pytest.raises(UserNotFoundError) as exc_info:
        service.get_user("nonexistent-id")
    assert "nonexistent-id" in str(exc_info.value)
```

### Test Naming Convention

```python
# Pattern: test_<unit>_<scenario>_<expected>
def test_create_user_with_valid_data_returns_user(): ...
def test_create_user_with_duplicate_email_raises_conflict(): ...
def test_get_user_with_unknown_id_returns_none(): ...
```

## Testing Database Code

```python
@pytest.fixture(scope="function")
def db_session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    yield session
    session.close()

def test_create_user(db_session):
    user = User(name="Test User", email="test@example.com")
    db_session.add(user)
    db_session.commit()
    assert user.id is not None

def test_unique_email_constraint(db_session):
    from sqlalchemy.exc import IntegrityError
    user1 = User(name="User 1", email="same@example.com")
    db_session.add(user1)
    db_session.commit()
    user2 = User(name="User 2", email="same@example.com")
    db_session.add(user2)
    with pytest.raises(IntegrityError):
        db_session.commit()
```

## Best Practices

1. **Write tests first** (TDD) or alongside code
2. **One assertion per test** when possible
3. **Use descriptive test names** that explain behavior
4. **Keep tests independent** and isolated
5. **Use fixtures** for setup and teardown
6. **Mock external dependencies** appropriately
7. **Parametrize tests** to reduce duplication
8. **Test edge cases** and error conditions
