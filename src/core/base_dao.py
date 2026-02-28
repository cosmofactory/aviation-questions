from collections.abc import Mapping, Sequence
from typing import Any, Type, TypeVar, overload

from fastapi_pagination import LimitOffsetPage
from fastapi_pagination.ext.sqlalchemy import paginate
from sqlalchemy import CursorResult, delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import ColumnElement

from src.core.engine import Base
from src.core.exceptions import ObjectNotFoundException

T = TypeVar("T", bound=Base)


class BaseDAO:
    model: Type[T]

    @classmethod
    async def get_all(
        cls,
        session: AsyncSession,
        *where: ColumnElement,
        order_by: Sequence[ColumnElement] = (),
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[T]:
        """
        Retrieve multiple records with optional filters, ordering, and pagination.

        Args:
            session (AsyncSession): Database session.
            *where (ColumnElement): SQLAlchemy filter expressions.
            order_by (Sequence[ColumnElement]): SQLAlchemy ordering expressions.
            limit (int, optional): Max number of records to return.
            offset (int, optional): Number of records to skip.

        Returns:
            list[T]: List of model instances.

        Example:
            users = await UserOrderDAO.get_all(
                session,
                UserOrder.user_id == user_id,
                order_by=[UserOrder.created_at.desc()],
                limit=20,
                offset=0
            )
        """
        stmt = select(cls.model)

        if where:
            stmt = stmt.where(*where)

        if order_by:
            stmt = stmt.order_by(*order_by)

        if offset is not None:
            stmt = stmt.offset(offset)
        if limit is not None:
            stmt = stmt.limit(limit)

        result = await session.execute(stmt)
        return list(result.scalars().all())

    @classmethod
    async def get_first(
        cls,
        session: AsyncSession,
        *where: ColumnElement,
    ) -> T | None:
        """
        Return the first record matching optional filters, or None if none found.

        Args:
            session (AsyncSession): Database session.
            *where (ColumnElement): SQLAlchemy filter expressions.

        Returns:
            T | None: A single model instance or None.

        Example:
            order = await UserOrderDAO.get_first(
                session,
                UserOrder.status == 'PENDING'
            )
        """
        stmt = select(cls.model)
        if where:
            stmt = stmt.where(*where)
        result = await session.execute(stmt)
        return result.scalars().first()

    @classmethod
    async def get_one_or_none(
        cls,
        session: AsyncSession,
        *where: ColumnElement,
    ) -> T | None:
        """
        Return exactly one record matching filters, or None if zero found.
        Raises if multiple records match.

        Args:
            session (AsyncSession): Database session.
            *where (ColumnElement): SQLAlchemy filter expressions.

        Returns:
            T | None: A single model instance or None.

        Example:
            user = await UserOrderDAO.get_one_or_none(
                session,
                UserOrder.id == order_id
            )
        """
        stmt = select(cls.model)
        if where:
            stmt = stmt.where(*where)
        result = await session.execute(stmt)
        return result.scalars().one_or_none()

    @classmethod
    async def get_by_id(
        cls,
        session: AsyncSession,
        id: int,
    ) -> T | None:
        """
        Fetch a record by its primary key.

        Args:
            session (AsyncSession): Database session.
            id (int): Primary key value.

        Returns:
            T | None: Model instance or None if not found.

        Example:
            order = await UserOrderDAO.get_by_id(session, 123)
        """
        return await session.get(cls.model, id)

    @classmethod
    async def get_paginated(
        cls,
        session: AsyncSession,
        *where: ColumnElement,
    ) -> LimitOffsetPage[T]:
        """
        Retrieve objects from the database with fastapi-pagination integration.

        Pagination (limit/offset) will be applied at the DB level.

        Args:
            session (AsyncSession): Database session.
            *where (ColumnElement): SQLAlchemy filter expressions.

        Returns:
            LimitOffsetPage[T]: Paginated results.

        Example:
            paginated_orders = await UserOrderDAO.get_paginated(
                session,
                UserOrder.user_id == user_id
            ).
        """
        stmt = select(cls.model)
        if where:
            stmt = stmt.where(*where)
        return await paginate(session, stmt)

    @classmethod
    async def get_object_or_error(
        cls,
        session: AsyncSession,
        *where: ColumnElement,
    ) -> T:
        """
        Return the first record matching filters, or raise ObjectNotFoundException.

        Args:
            session (AsyncSession): Database session.
            *where (ColumnElement): SQLAlchemy filter expressions.

        Returns:
            T: A single model instance.

        Raises:
            ObjectNotFoundException: If no record matches.

        Example:
            order = await UserOrderDAO.get_object_or_error(
                session,
                UserOrder.id == order_id
            )
        """
        stmt = select(cls.model)
        if where:
            stmt = stmt.where(*where)
        result = await session.execute(stmt)
        instance = result.scalars().first()
        if instance:
            return instance
        raise ObjectNotFoundException(f"Object of type {cls.model.__name__} not found.")

    @classmethod
    @overload
    async def create(cls, db: AsyncSession, object_data: T) -> T: ...

    @classmethod
    @overload
    async def create(cls, db: AsyncSession, object_data: Mapping[str, Any]) -> T: ...

    @classmethod
    async def create(
        cls,
        db: AsyncSession,
        *args: Any,
        **kwargs: Any,
    ) -> T:
        """
        Instantiate and persist a new record, returning the instance.

        Args:
            db (AsyncSession): Database session (in transaction).
            object_data (T | dict[str, Any]): Model instance or dict with fields to set.

        Returns:
            T: The newly created model instance.

        Example:
            new_order = await UserOrderDAO.create(
                session,
                user_id=42,
                amount=Decimal('99.99')
            )

            or

            new_order = await UserOrderDAO.create(
                session,
                UserOrder(user_id=42, amount=Decimal('99.99'))
            )
        """
        if args and isinstance(args[0], cls.model):
            instance = args[0]
        elif args and isinstance(args[0], Mapping):
            instance = cls.model(**args[0])
        elif "object_data" in kwargs and isinstance(kwargs["object_data"], Mapping):
            instance = cls.model(**kwargs.pop("object_data"))
        else:
            instance = cls.model(**kwargs)
        db.add(instance)
        await db.flush()
        await db.refresh(instance)
        return instance

    @classmethod
    @overload
    async def update(
        cls,
        db: AsyncSession,
        object_data: T,
    ) -> T: ...

    @classmethod
    @overload
    async def update(
        cls,
        db: AsyncSession,
        object_data: Mapping[str, Any],
    ) -> T: ...

    @classmethod
    async def update(
        cls,
        db: AsyncSession,
        *args: Any,
        **kwargs: Any,
    ) -> T:
        """
        Merge and persist changes for an existing record by primary key.

        Args:
            db (AsyncSession): Database session (in transaction).
            object_data (T | dict[str, Any]): Model instance or dict with fields to update.

        Returns:
            T: The updated model instance.

        Example:
            updated = await UserOrderDAO.update(
                session,
                id=123,
                status='WORKING'
            )

            or

            updated = await UserOrderDAO.update(
                session,
                UserOrder(id=123, status='WORKING')
            )
        """
        if args:
            data = args[0]
            if isinstance(data, cls.model):
                instance = data
            elif isinstance(data, Mapping):
                instance = cls.model(**data)
            else:
                raise TypeError(f"Unexpected update arg: {data!r}")
        else:
            instance = cls.model(**kwargs)
        merged_object = await db.merge(instance)
        await db.flush()
        await db.refresh(merged_object)
        return merged_object

    @classmethod
    async def delete(
        cls,
        db: AsyncSession,
        id: Any,
    ) -> None:
        """
        Delete a single record by primary key.

        Args:
            db (AsyncSession): Database session (in transaction).
            id (Any): Primary‐key value of the record to delete.

        Raises:
            ObjectNotFoundException: If no record with that PK exists.

        Example:
            await UserOrderDAO.delete(session, 123)
        """
        stmt = delete(cls.model).where(cls.model.id == id)
        result: CursorResult = await db.execute(stmt)  # type: ignore[assignment]
        await db.flush()
        if (result.rowcount or 0) == 0:
            raise ObjectNotFoundException(f"Object of type {cls.model.__name__} not found.")

    @classmethod
    async def bulk_create(
        cls,
        db: AsyncSession,
        objects_data: Sequence[dict[str, Any]],
        batch_size: int = 100,
    ) -> list[T]:
        """
        Bulk-insert multiple records in batches.

        Args:
            db (AsyncSession): Database session (in transaction).
            objects_data (Sequence[dict[str, Any]]): List of field‐value dicts for new records.
            batch_size (int, optional): Number of records per batch. Defaults to 100.

        Returns:
            list[T]: List of newly created model instances.

        Example:
            new_orders = await UserOrderDAO.bulk_create(
                session,
                [
                    {"user_id": 1, "amount": Decimal("9.99")},
                    {"user_id": 2, "amount": Decimal("19.99")},
                    # ...
                ],
                batch_size=50,
            )
        """
        created: list[T] = []
        for i in range(0, len(objects_data), batch_size):
            chunk = objects_data[i : i + batch_size]
            instances = [cls.model(**data) for data in chunk]
            db.add_all(instances)
            await db.flush()
            for instance in instances:
                await db.refresh(instance)
            created.extend(instances)
        return created

    @classmethod
    async def bulk_update(
        cls,
        db: AsyncSession,
        objects_data: Sequence[dict[str, Any]],
        batch_size: int = 100,
    ) -> list[T]:
        """
        Bulk-merge (update) multiple records in batches.

        Args:
            db (AsyncSession): Database session (in transaction).
            objects_data (Sequence[dict[str, Any]]): List of dicts containing primary key + fields to update.
            batch_size (int, optional): Number of records per batch. Defaults to 100.

        Returns:
            list[T]: List of updated model instances.

        Example:
            updated = await UserOrderDAO.bulk_update(
                session,
                [
                    {"id": 1, "status": "COMPLETED"},
                    {"id": 2, "amount": Decimal("49.99")},
                ],
                batch_size=50,
            )
        """
        updated_instances: list[T] = []
        for i in range(0, len(objects_data), batch_size):
            chunk = objects_data[i : i + batch_size]
            instances = [cls.model(**data) for data in chunk]
            merged = []
            for inst in instances:
                merged_inst = await db.merge(inst)
                merged.append(merged_inst)
            await db.flush()
            for inst in merged:
                await db.refresh(inst)
            updated_instances.extend(merged)
        return updated_instances

    @classmethod
    async def bulk_delete(
        cls,
        db: AsyncSession,
        ids: Sequence[Any],
        batch_size: int = 100,
    ) -> int:
        """
        Bulk-delete multiple records by primary-key values in batches.

        Args:
            db (AsyncSession): Database session (in transaction).
            ids (Sequence[Any]): List of primary-key values to delete.
            batch_size (int, optional): Number of records to delete per batch. Defaults to 100.

        Returns:
            int: Total number of rows deleted.

        Example:
            deleted_count = await UserOrderDAO.bulk_delete(
                session,
                [1, 2, 3, 4],
                batch_size=2,
            )
        """
        total_deleted = 0
        for i in range(0, len(ids), batch_size):
            chunk = ids[i : i + batch_size]
            stmt = delete(cls.model).where(cls.model.id.in_(chunk))
            result: CursorResult = await db.execute(stmt)  # type: ignore[assignment]
            await db.flush()
            total_deleted += result.rowcount or 0
        return total_deleted

    @classmethod
    async def bulk_get(
        cls,
        session: AsyncSession,
        ids: Sequence[Any],
    ) -> list[T]:
        """
        Retrieve multiple records by a list of primary-key values.

        Args:
            session (AsyncSession): Database session.
            ids (Sequence[Any]): List of primary-key values to fetch.
            preserve_order (bool): If True, results are returned in the same order as `ids`.

        Returns:
            list[T]: List of model instances.

        Example:
            users = await UserDAO.bulk_get(session, [3, 1, 2], preserve_order=True)
        """
        stmt = select(cls.model).where(cls.model.id.in_(ids))
        result = await session.execute(stmt)
        return list(result.scalars().all())
