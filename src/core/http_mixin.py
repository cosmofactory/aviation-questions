from typing import Any, Dict, Optional
from urllib.parse import urljoin

import httpx
import logfire


class BaseHTTPMixin:
    """
    A base mixin class for making HTTP requests with common functionality.

    This class provides a foundation for building HTTP clients that need:
    - Centralized header management (authorization, content-type)
    - URL construction from base URL and endpoints
    - Built-in logging and error handling
    - Timeout management
    - Convenience methods for JSON responses

    Example:
        >>> class MyAPIClient(BaseHTTPMixin):
        ...     def __init__(self, http_client: httpx.AsyncClient):
        ...         super().__init__(
        ...             base_url="https://api.example.com",
        ...             client=http_client,
        ...             api_key="your-api-key-here",
        ...             content_type="application/json"
        ...         )
        ...
        ...     async def get_user(self, user_id: int) -> dict:
        ...         return await self.get_json(f"/users/{user_id}")

        >>> async with httpx.AsyncClient() as client:
        ...     api = MyAPIClient(client)
        ...     user_data = await api.get_user(123)
    """

    def __init__(
        self,
        base_url: str,
        client: httpx.AsyncClient,
        api_key: str,
        content_type: str = "application/json",
        timeout: Optional[float] = 30.0,
    ):
        """
        Initialize the HTTP mixin with connection details.

        Args:
            base_url (str): The base URL for all API requests (e.g., "https://api.example.com")
            client (httpx.AsyncClient): The HTTP client instance to use for requests
            api_key (str): API key for Bearer token authentication
            content_type (str, optional): Default content type for requests. Defaults to "application/json"
            timeout (Optional[float], optional): Default timeout in seconds. Defaults to 30.0

        Example:
            >>> async with httpx.AsyncClient() as client:
            ...     mixin = BaseHTTPMixin(
            ...         base_url="https://api.github.com",
            ...         client=client,
            ...         api_key="ghp_xxxxxxxxxxxx",
            ...         timeout=60.0
            ...     )
        """
        self.base_url = base_url.rstrip("/")  # Remove trailing slash
        self.client = client
        self.api_key = api_key
        self.content_type = content_type
        self.timeout = timeout

    @property
    def headers(self) -> dict:
        """
        Get the default headers for all requests.

        Returns:
            dict: Headers containing authorization and content-type

        Example:
            >>> mixin.headers
            {'authorization': 'Bearer your-api-key', 'Content-Type': 'application/json'}
        """
        return {"authorization": f"Bearer {self.api_key}", "Content-Type": self.content_type}

    def _make_headers(self, headers: dict) -> dict:
        """
        Merge default headers with additional headers.

        Args:
            headers (dict): Additional headers to merge with defaults

        Returns:
            dict: Combined headers with additional headers taking precedence

        Example:
            >>> mixin._make_headers({"X-Custom": "value"})
            {'authorization': 'Bearer key', 'Content-Type': 'application/json', 'X-Custom': 'value'}
        """
        return {**self.headers, **headers}

    def _build_url(self, endpoint: str) -> str:
        """
        Build full URL from base_url and endpoint.

        Args:
            endpoint (str): The API endpoint path (e.g., "/users/123" or "users/123")

        Returns:
            str: Complete URL ready for HTTP request

        Examples:
            >>> mixin = BaseHTTPMixin("https://api.example.com", ...)
            >>> mixin._build_url("/users/123")
            'https://api.example.com/users/123'
            >>> mixin._build_url("users/123")  # Leading slash is optional
            'https://api.example.com/users/123'
            >>> mixin._build_url("https://other-api.com/data")  # Full URLs pass through
            'https://other-api.com/data'
        """
        if endpoint.startswith(("http://", "https://")):
            return endpoint  # Already a full URL
        return urljoin(f"{self.base_url}/", endpoint.lstrip("/"))

    async def _make_request(self, method: str, endpoint: str, **kwargs) -> httpx.Response:
        """
        Internal method to make HTTP requests with common logic.

        Args:
            method (str): HTTP method (GET, POST, PUT, PATCH, DELETE)
            endpoint (str): API endpoint path
            **kwargs: Additional arguments passed to httpx request method

        Returns:
            httpx.Response: The HTTP response object

        Raises:
            httpx.TimeoutException: If the request times out
            httpx.RequestError: If there's a network or request error

        Example:
            >>> response = await mixin._make_request("GET", "/users/123")
            >>> response.status_code
            200
        """
        url = self._build_url(endpoint)
        headers = self._make_headers(kwargs.pop("headers", {}))

        if "timeout" not in kwargs and self.timeout:
            kwargs["timeout"] = self.timeout

        try:
            logfire.info(f"Making {method} request to {url}")
            response = await getattr(self.client, method.lower())(url, headers=headers, **kwargs)
            logfire.info(f"Response status: {response.status_code}")
            return response
        except httpx.TimeoutException as e:
            logfire.error(f"Request timeout for {method} {url}", error=e)
            raise
        except httpx.RequestError as e:
            logfire.error(f"Request error for {method} {url}", error=e)
            raise

    async def get(self, endpoint: str, **kwargs) -> httpx.Response:
        """
        Make a GET request to the specified endpoint.

        Args:
            endpoint (str): API endpoint path
            **kwargs: Additional arguments (params, headers, timeout, etc.)

        Returns:
            httpx.Response: The HTTP response object

        Example:
            >>> response = await mixin.get("/users/123")
            >>> response = await mixin.get("/search", params={"q": "python"})
        """
        return await self._make_request("GET", endpoint, **kwargs)

    async def post(self, endpoint: str, json: dict | None = None, **kwargs) -> httpx.Response:
        """
        Make a POST request to the specified endpoint.

        Args:
            endpoint (str): API endpoint path
            json (dict | None, optional): JSON data to send in request body
            **kwargs: Additional arguments (data, files, headers, etc.)

        Returns:
            httpx.Response: The HTTP response object

        Example:
            >>> response = await mixin.post("/users", json={"name": "John", "email": "john@example.com"})
            >>> response = await mixin.post("/upload", files={"file": file_content})
        """
        if json is not None:
            kwargs["json"] = json
        return await self._make_request("POST", endpoint, **kwargs)

    async def put(self, endpoint: str, json: dict | None = None, **kwargs) -> httpx.Response:
        """
        Make a PUT request to the specified endpoint.

        Args:
            endpoint (str): API endpoint path
            json (dict | None, optional): JSON data to send in request body
            **kwargs: Additional arguments (data, headers, etc.)

        Returns:
            httpx.Response: The HTTP response object

        Example:
            >>> response = await mixin.put("/users/123", json={"name": "Updated Name"})
        """
        if json is not None:
            kwargs["json"] = json
        return await self._make_request("PUT", endpoint, **kwargs)

    async def delete(self, endpoint: str, **kwargs) -> httpx.Response:
        """
        Make a DELETE request to the specified endpoint.

        Args:
            endpoint (str): API endpoint path
            **kwargs: Additional arguments (headers, params, etc.)

        Returns:
            httpx.Response: The HTTP response object

        Example:
            >>> response = await mixin.delete("/users/123")
            >>> response = await mixin.delete("/posts/456", params={"force": "true"})
        """
        return await self._make_request("DELETE", endpoint, **kwargs)

    async def patch(self, endpoint: str, json: dict | None = None, **kwargs) -> httpx.Response:
        """
        Make a PATCH request to the specified endpoint.

        Args:
            endpoint (str): API endpoint path
            json (dict | None, optional): JSON data to send in request body
            **kwargs: Additional arguments (data, headers, etc.)

        Returns:
            httpx.Response: The HTTP response object

        Example:
            >>> response = await mixin.patch("/users/123", json={"email": "newemail@example.com"})
        """
        if json is not None:
            kwargs["json"] = json
        return await self._make_request("PATCH", endpoint, **kwargs)

    # Convenience methods for common patterns
    async def get_json(self, endpoint: str, **kwargs) -> Dict[str, Any]:
        """
        GET request that returns JSON response.

        Args:
            endpoint (str): API endpoint path
            **kwargs: Additional arguments passed to GET request

        Returns:
            Dict[str, Any]: Parsed JSON response

        Raises:
            httpx.HTTPStatusError: If response status indicates an error (4xx, 5xx)

        Example:
            >>> user_data = await mixin.get_json("/users/123")
            >>> {"id": 123, "name": "John Doe", "email": "john@example.com"}
            >>>
            >>> search_results = await mixin.get_json("/search", params={"q": "python"})
        """
        response = await self.get(endpoint, **kwargs)
        response.raise_for_status()
        return response.json()

    async def post_json(self, endpoint: str, json: dict | None = None, **kwargs) -> Dict[str, Any]:
        """
        POST request that returns JSON response.

        Args:
            endpoint (str): API endpoint path
            json (dict | None, optional): JSON data to send in request body
            **kwargs: Additional arguments passed to POST request

        Returns:
            Dict[str, Any]: Parsed JSON response

        Raises:
            httpx.HTTPStatusError: If response status indicates an error (4xx, 5xx)

        Example:
            >>> new_user = await mixin.post_json("/users", json={
            ...     "name": "Jane Doe",
            ...     "email": "jane@example.com"
            ... })
            >>> {"id": 124, "name": "Jane Doe", "email": "jane@example.com", "created_at": "2025-08-11T..."}
        """
        response = await self.post(endpoint, json=json, **kwargs)
        response.raise_for_status()
        return response.json()
