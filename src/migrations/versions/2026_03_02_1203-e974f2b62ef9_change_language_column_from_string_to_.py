"""change language column from string to enum

Revision ID: e974f2b62ef9
Revises: 5a2aabd35dfc
Create Date: 2026-03-02 12:03:09.659111

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'e974f2b62ef9'
down_revision: Union[str, None] = '5a2aabd35dfc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Convert language column from VARCHAR(10) to a native enum."""
    # 1. Create the enum type
    op.execute("CREATE TYPE language AS ENUM ('eng', 'rus')")

    # 2. Migrate existing data: 'en' -> 'eng' (any unknown values default to 'eng')
    op.execute("UPDATE documents SET language = 'eng' WHERE language = 'en'")
    op.execute("UPDATE documents SET language = 'eng' WHERE language NOT IN ('eng', 'rus')")

    # 3. Drop the old default (VARCHAR 'en'), alter type, then set new default
    op.execute("ALTER TABLE documents ALTER COLUMN language DROP DEFAULT")
    op.execute(
        "ALTER TABLE documents "
        "ALTER COLUMN language TYPE language USING language::language"
    )
    op.execute("ALTER TABLE documents ALTER COLUMN language SET DEFAULT 'eng'")

    # 4. Update column comment
    op.execute(
        "COMMENT ON COLUMN documents.language IS "
        "'Document language: ''eng'' (English), ''rus'' (Russian)'"
    )


def downgrade() -> None:
    """Revert language column back to VARCHAR(10)."""
    op.execute("ALTER TABLE documents ALTER COLUMN language DROP DEFAULT")
    op.execute(
        "ALTER TABLE documents "
        "ALTER COLUMN language TYPE VARCHAR(10) USING language::text"
    )
    op.execute("ALTER TABLE documents ALTER COLUMN language SET DEFAULT 'en'")
    op.execute("DROP TYPE IF EXISTS language")
    op.execute(
        "COMMENT ON COLUMN documents.language IS "
        "'ISO 639-1 language code, e.g. ''en'', ''fr'', ''de'''"
    )
