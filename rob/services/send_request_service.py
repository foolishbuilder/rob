from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from rob.database.repositories.models import SendRecord
from rob.database.repositories.send_requests import SendRequestsRepository
from rob.services.send_service import SendService


@dataclass(frozen=True)
class SendRequestDecision:
    ok: bool
    status: str
    send: SendRecord | None = None
    request_sub_user_id: int | None = None
    request_domme_user_id: int | None = None
    amount_cents: int | None = None
    method: str | None = None
    note: str | None = None
    denial_reason: str | None = None


class SendRequestService:
    RATE_LIMIT = 3

    def __init__(self, *, send_requests: SendRequestsRepository, send_service: SendService) -> None:
        self.send_requests = send_requests
        self.send_service = send_service

    async def is_rate_limited(self, *, guild_id: int, sub_user_id: int, domme_user_id: int) -> bool:
        since = datetime.now(timezone.utc) - timedelta(hours=24)
        count = await self.send_requests.count_since(
            guild_id=guild_id,
            sub_user_id=sub_user_id,
            domme_user_id=domme_user_id,
            since=since,
        )
        return count >= self.RATE_LIMIT

    async def approve(
        self,
        *,
        request_id: int,
        guild_id: int,
        domme_id: int | None,
        acted_by_user_id: int,
    ) -> SendRequestDecision:
        request = await self.send_requests.get(request_id)
        if request is None:
            return SendRequestDecision(ok=False, status="missing")
        if request.status != "pending":
            return SendRequestDecision(
                ok=False,
                status=request.status,
                request_sub_user_id=request.sub_user_id,
                request_domme_user_id=request.domme_user_id,
                amount_cents=request.amount_cents,
                method=request.method,
                note=request.note,
                denial_reason=request.denial_reason,
            )
        if acted_by_user_id != request.domme_user_id:
            return SendRequestDecision(ok=False, status="forbidden")

        resolved = await self.send_requests.resolve_if_pending(
            request.id,
            status="approved",
            resolved_by_user_id=acted_by_user_id,
        )
        if resolved is None:
            latest = await self.send_requests.get(request_id)
            return SendRequestDecision(ok=False, status=latest.status if latest is not None else "missing")
        send = await self.send_service.record_manual_send(
            guild_id=guild_id,
            domme_id=domme_id,
            domme_user_id=request.domme_user_id,
            amount_cents=request.amount_cents,
            currency=request.currency,
            method=request.method,
            note=request.note,
            sub_user_id=request.sub_user_id,
            source="send_request",
        )
        return SendRequestDecision(
            ok=send is not None,
            status="approved" if send is not None else "approved_without_send",
            send=send,
            request_sub_user_id=request.sub_user_id,
            request_domme_user_id=request.domme_user_id,
            amount_cents=request.amount_cents,
            method=request.method,
            note=request.note,
        )

    async def deny(self, *, request_id: int, reason: str, acted_by_user_id: int) -> SendRequestDecision:
        request = await self.send_requests.get(request_id)
        if request is None:
            return SendRequestDecision(ok=False, status="missing")
        if request.status != "pending":
            return SendRequestDecision(
                ok=False,
                status=request.status,
                request_sub_user_id=request.sub_user_id,
                request_domme_user_id=request.domme_user_id,
                amount_cents=request.amount_cents,
                method=request.method,
                note=request.note,
                denial_reason=request.denial_reason,
            )
        if acted_by_user_id != request.domme_user_id:
            return SendRequestDecision(ok=False, status="forbidden")
        resolved = await self.send_requests.resolve_if_pending(
            request.id,
            status="denied",
            denial_reason=reason,
            resolved_by_user_id=acted_by_user_id,
        )
        if resolved is None:
            latest = await self.send_requests.get(request_id)
            return SendRequestDecision(ok=False, status=latest.status if latest is not None else "missing")
        return SendRequestDecision(
            ok=True,
            status="denied",
            request_sub_user_id=request.sub_user_id,
            request_domme_user_id=request.domme_user_id,
            amount_cents=request.amount_cents,
            method=request.method,
            note=request.note,
            denial_reason=reason,
        )
