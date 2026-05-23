from __future__ import annotations

from datetime import datetime, timezone

from asyncpg import Record

from rob.database.connection import Database
from rob.database.repositories.models import SendRequestRecord


def _build_send_request(row: Record) -> SendRequestRecord:
    return SendRequestRecord(
        id=int(row["id"]),
        guild_id=int(row["guild_id"]),
        sub_user_id=int(row["sub_user_id"]),
        domme_user_id=int(row["domme_user_id"]),
        amount_cents=int(row["amount_cents"]),
        currency=str(row["currency"]),
        method=str(row["method"]),
        note=row["note"],
        status=str(row["status"]),
        created_at=row["created_at"],
        resolved_at=row["resolved_at"],
        denial_reason=row["denial_reason"] if "denial_reason" in row else None,
        resolved_by_user_id=int(row["resolved_by_user_id"]) if ("resolved_by_user_id" in row and row["resolved_by_user_id"] is not None) else None,
    )


class SendRequestsRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    async def create(
        self,
        *,
        guild_id: int,
        sub_user_id: int,
        domme_user_id: int,
        amount_cents: int,
        currency: str,
        method: str,
        note: str | None,
    ) -> SendRequestRecord:
        created_at = datetime.now(timezone.utc)
        async with self.database.acquire() as connection:
            row = await connection.fetchrow(
                """
                INSERT INTO send_requests (
                    guild_id,
                    sub_user_id,
                    domme_user_id,
                    amount_cents,
                    currency,
                    method,
                    note,
                    status,
                    created_at
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, 'pending', $8)
                RETURNING *
                """,
                guild_id,
                sub_user_id,
                domme_user_id,
                amount_cents,
                currency,
                method,
                note,
                created_at,
            )
        assert row is not None
        return _build_send_request(row)

    async def count_since(
        self,
        *,
        guild_id: int,
        sub_user_id: int,
        domme_user_id: int,
        since: datetime,
    ) -> int:
        async with self.database.acquire() as connection:
            value = await connection.fetchval(
                """
                SELECT COUNT(*)
                FROM send_requests
                WHERE guild_id = $1
                AND sub_user_id = $2
                AND domme_user_id = $3
                AND created_at >= $4
                """,
                guild_id,
                sub_user_id,
                domme_user_id,
                since,
            )
        return int(value or 0)

    async def get(self, request_id: int) -> SendRequestRecord | None:
        async with self.database.acquire() as connection:
            row = await connection.fetchrow(
                "SELECT * FROM send_requests WHERE id = $1",
                request_id,
            )
        if row is None:
            return None
        return _build_send_request(row)

    async def resolve(
        self,
        request_id: int,
        *,
        status: str,
        denial_reason: str | None = None,
        resolved_by_user_id: int | None = None,
    ) -> None:
        async with self.database.acquire() as connection:
            await connection.execute(
                """
                UPDATE send_requests
                SET
                    status = $2,
                    resolved_at = now(),
                    denial_reason = $3,
                    resolved_by_user_id = $4
                WHERE id = $1
                """,
                request_id,
                status,
                denial_reason,
                resolved_by_user_id,
            )

    async def resolve_if_pending(
        self,
        request_id: int,
        *,
        status: str,
        denial_reason: str | None = None,
        resolved_by_user_id: int | None = None,
    ) -> SendRequestRecord | None:
        async with self.database.acquire() as connection:
            row = await connection.fetchrow(
                """
                UPDATE send_requests
                SET
                    status = $2,
                    resolved_at = now(),
                    denial_reason = $3,
                    resolved_by_user_id = $4
                WHERE id = $1
                AND status = 'pending'
                RETURNING *
                """,
                request_id,
                status,
                denial_reason,
                resolved_by_user_id,
            )
        if row is None:
            return None
        return _build_send_request(row)

    async def delete(self, request_id: int) -> None:
        async with self.database.acquire() as connection:
            await connection.execute(
                "DELETE FROM send_requests WHERE id = $1",
                request_id,
            )
