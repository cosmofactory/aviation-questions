# Default embedding dimensions. Change this constant (and run a migration)
# if you switch to a model with a different output size.
# text-embedding-3-small → 1536, text-embedding-3-large → 3072
EMBEDDING_DIM: int = 1536

# Upload constraints
MAX_FILE_SIZE_BYTES: int = 25 * 1024 * 1024  # 25 MB
ALLOWED_EXTENSIONS: set[str] = {".odt"}
ODT_CONTENT_TYPE: str = "application/vnd.oasis.opendocument.text"

# Chunking parameters
TARGET_CHUNK_TOKENS: int = 800
MAX_CHUNK_TOKENS: int = 1200
TOKEN_MULTIPLIER: float = 1.3  # words × 1.3 ≈ tokens
