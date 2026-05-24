from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass

from rob.config.settings import configure_logging, load_base_settings
from rob.database.connection import Database
from rob.database.repositories import (
    BotStateRepository,
    CountingRepository,
    GuildSettingsRepository,
    LeaderboardsRepository,
    SendsRepository,
)
from rob.services.maintenance_service import MaintenanceService


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Rob backend operations.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("status", help="Show database, maintenance, and queue status.")

    maintenance = subparsers.add_parser("maintenance", help="Manage maintenance mode.")
    maintenance_subparsers = maintenance.add_subparsers(dest="maintenance_command", required=True)
    maintenance_subparsers.add_parser("status", help="Show maintenance mode state.")
    maintenance_on = maintenance_subparsers.add_parser("on", help="Enable maintenance mode.")
    maintenance_on.add_argument("reason", nargs="?", default="", help="Optional maintenance reason.")
    maintenance_subparsers.add_parser("off", help="Disable maintenance mode.")

    queue = subparsers.add_parser("queue", help="Inspect or release queued sends.")
    queue_subparsers = queue.add_subparsers(dest="queue_command", required=True)
    queue_subparsers.add_parser("status", help="Show queue counts.")
    queue_subparsers.add_parser("flush", help="Release queued maintenance sends to pending.")

    leaderboard = subparsers.add_parser("leaderboard", help="Leaderboard operations.")
    leaderboard_subparsers = leaderboard.add_subparsers(dest="leaderboard_command", required=True)
    leaderboard_subparsers.add_parser("refresh", help="Request a leaderboard refresh from the bot.")
    leaderboard_adopt = leaderboard_subparsers.add_parser(
        "adopt",
        help="Adopt existing Discord leaderboard messages into DB refs.",
    )
    leaderboard_adopt.add_argument("--guild-id", type=int, required=True)
    leaderboard_adopt.add_argument("--leaderboard-channel-id", type=int, required=True)
    leaderboard_adopt.add_argument("--leaderboard-message-id", type=int, required=True)
    leaderboard_adopt.add_argument("--stats-message-id", type=int, required=True)
    leaderboard_status = leaderboard_subparsers.add_parser("status", help="Show leaderboard status summary.")
    leaderboard_status.add_argument("--guild-id", type=int, default=None)
    leaderboard_preview = leaderboard_subparsers.add_parser("preview", help="Preview top leaderboard rows.")
    leaderboard_preview.add_argument("--guild-id", type=int, default=None)
    diagnose = leaderboard_subparsers.add_parser("diagnose", help="Diagnose leaderboard send matching.")
    diagnose.add_argument("--guild-id", type=int, default=None)
    repair = leaderboard_subparsers.add_parser(
        "repair-send-dommes",
        help="Repair sends.domme_user_id from dommes.id matches.",
    )
    repair.add_argument("--guild-id", type=int, default=None)
    repair.add_argument("--dry-run", action="store_true", help="Preview changes without writing.")

    throne = subparsers.add_parser("throne", help="Throne send operations.")
    throne_subparsers = throne.add_subparsers(dest="throne_command", required=True)
    throne_subparsers.add_parser("status", help="Show Throne command support status.")
    throne_subparsers.add_parser("dommes", help="Show Throne domme helper status.")
    throne_subparsers.add_parser("subs", help="Show Throne sub helper status.")
    throne_subparsers.add_parser(
        "invalidate-test-sends",
        help="Mark known Throne test-user sends so leaderboards can exclude them.",
    )

    sends = subparsers.add_parser("sends", help="Send record operations.")
    sends_subparsers = sends.add_subparsers(dest="sends_command", required=True)
    sends_list = sends_subparsers.add_parser("list", help="List recent sends.")
    sends_list.add_argument(
        "--status",
        choices=["pending", "posted", "failed", "queued_maintenance", "ignored", "all"],
        default="all",
    )
    sends_list.add_argument("--guild-id", type=int, default=None)
    sends_list.add_argument("--limit", type=int, default=25)
    sends_subparsers.add_parser(
        "backfill-public-ids",
        help="Generate and store missing public send IDs.",
    )
    sends_mark_posted = sends_subparsers.add_parser(
        "mark-posted",
        help="Force mark a send as posted.",
    )
    sends_mark_posted.add_argument("send_id", type=int)

    count = subparsers.add_parser("count", help="Counting operations.")
    count_subparsers = count.add_subparsers(dest="count_command", required=True)
    count_status = count_subparsers.add_parser("status", help="Show counting state.")
    count_status.add_argument("--guild-id", type=int, default=None)
    count_set = count_subparsers.add_parser("set", help="Set the current counting number.")
    count_set.add_argument("number", type=int)
    count_set.add_argument("--guild-id", type=int, default=None)

    return parser


@dataclass(frozen=True)
class OperationsContext:
    settings: object
    database: Database
    bot_state: BotStateRepository
    maintenance: MaintenanceService
    sends: SendsRepository
    leaderboards: LeaderboardsRepository
    guild_settings: GuildSettingsRepository
    counting: CountingRepository


async def create_context() -> OperationsContext:
    settings = load_base_settings()
    configure_logging(settings.log_level)
    database = Database(settings.database_url)
    await database.connect()
    bot_state = BotStateRepository(database)
    return OperationsContext(
        settings=settings,
        database=database,
        bot_state=bot_state,
        maintenance=MaintenanceService(bot_state),
        sends=SendsRepository(database),
        leaderboards=LeaderboardsRepository(database),
        guild_settings=GuildSettingsRepository(database),
        counting=CountingRepository(database),
    )


async def resolve_guild_id(ctx: OperationsContext, guild_id: int | None) -> int:
    if guild_id is not None:
        return guild_id
    guild_ids = await ctx.guild_settings.list_guild_ids()
    if len(guild_ids) == 1:
        return guild_ids[0]
    if not guild_ids:
        raise RuntimeError("No guild_settings rows exist yet. Add one first or pass --guild-id.")
    raise RuntimeError("Multiple guilds exist. Pass --guild-id explicitly.")


async def handle_status(ctx: OperationsContext) -> None:
    healthy = await ctx.database.health_check()
    maintenance = await ctx.maintenance.get_state()
    queue = await ctx.sends.count_statuses()
    print(f"database_ok={healthy}")
    print(f"maintenance_mode={'on' if maintenance.enabled else 'off'}")
    print(f"maintenance_reason={maintenance.reason or ''}")
    print(
        "queue_counts="
        f"pending:{queue.pending},"
        f"queued_maintenance:{queue.queued_maintenance},"
        f"posted:{queue.posted},"
        f"failed:{queue.failed},"
        f"ignored:{queue.ignored}"
    )


async def handle_maintenance(ctx: OperationsContext, args: argparse.Namespace) -> None:
    if args.maintenance_command == "status":
        state = await ctx.maintenance.get_state()
        print(f"maintenance_mode={'on' if state.enabled else 'off'}")
        print(f"maintenance_reason={state.reason or ''}")
        return
    if args.maintenance_command == "on":
        await ctx.maintenance.enable(reason=args.reason or "")
        print("maintenance_mode=on")
        if args.reason:
            print(f"maintenance_reason={args.reason}")
        print("leaderboard_refresh=requested")
        return
    if args.maintenance_command == "off":
        await ctx.maintenance.disable()
        released = await ctx.sends.release_queued_maintenance()
        print("maintenance_mode=off")
        print(f"released={released}")
        print("leaderboard_refresh=requested")
        return
    raise RuntimeError(f"Unsupported maintenance command: {args.maintenance_command}")


async def handle_queue(ctx: OperationsContext, args: argparse.Namespace) -> None:
    if args.queue_command == "status":
        queue = await ctx.sends.count_statuses()
        print(f"pending={queue.pending}")
        print(f"queued_maintenance={queue.queued_maintenance}")
        print(f"posted={queue.posted}")
        print(f"failed={queue.failed}")
        print(f"ignored={queue.ignored}")
        return
    if args.queue_command == "flush":
        if await ctx.maintenance.is_enabled():
            raise RuntimeError("Maintenance mode is still on. Disable it before flushing the queue.")
        released = await ctx.sends.release_queued_maintenance()
        print(f"released={released}")
        return
    raise RuntimeError(f"Unsupported queue command: {args.queue_command}")


async def handle_leaderboard(ctx: OperationsContext, args: argparse.Namespace) -> None:
    if args.leaderboard_command == "refresh":
        await ctx.maintenance.request_leaderboard_refresh()
        print("leaderboard_refresh=requested")
        return
    if args.leaderboard_command == "adopt":
        await ctx.leaderboards.upsert_message(
            guild_id=args.guild_id,
            message_key="leaderboard",
            leaderboard_type="leaderboard",
            channel_id=args.leaderboard_channel_id,
            message_id=args.leaderboard_message_id,
        )
        await ctx.leaderboards.upsert_message(
            guild_id=args.guild_id,
            message_key="leaderboard_stats",
            leaderboard_type="leaderboard_stats",
            channel_id=args.leaderboard_channel_id,
            message_id=args.stats_message_id,
        )
        print("leaderboard_adopted=true")
        print(f"guild_id={args.guild_id}")
        print(f"channel_id={args.leaderboard_channel_id}")
        print(f"leaderboard_message_id={args.leaderboard_message_id}")
        print(f"stats_message_id={args.stats_message_id}")
        return
    if args.leaderboard_command == "status":
        guild_id = await resolve_guild_id(ctx, getattr(args, "guild_id", None))
        summary = await ctx.leaderboards.get_summary(
            guild_id,
            include_test_sends=ctx.settings.throne_parse_test_sends_as_real_sends,
            test_gifter_usernames=ctx.settings.throne_test_gifter_usernames,
            owner_test_user_id=ctx.settings.throne_test_send_leaderboard_owner_user_id,
        )
        print(f"guild_id={guild_id}")
        print(f"registered_dommes={summary.domme_count}")
        print(f"tracked_sends={summary.send_count}")
        print(f"tracked_total_cents={summary.total_cents}")
        return
    if args.leaderboard_command == "preview":
        guild_id = await resolve_guild_id(ctx, getattr(args, "guild_id", None))
        rows = await ctx.leaderboards.get_top_dommes(
            guild_id,
            limit=ctx.settings.leaderboard_limit,
            include_test_sends=ctx.settings.throne_parse_test_sends_as_real_sends,
            test_gifter_usernames=ctx.settings.throne_test_gifter_usernames,
            owner_test_user_id=ctx.settings.throne_test_send_leaderboard_owner_user_id,
        )
        print(f"guild_id={guild_id}")
        print("preview=top_dommes")
        if not rows:
            print("rows=none")
            return
        for index, row in enumerate(rows, 1):
            print(
                f"{index}. user_id={row.user_id or 0} amount_cents={row.total_cents} send_count={row.send_count}"
            )
        return
    if args.leaderboard_command == "diagnose":
        guild_id = await resolve_guild_id(ctx, getattr(args, "guild_id", None))
        report = await ctx.leaderboards.diagnose(
            guild_id,
            include_test_sends=ctx.settings.throne_parse_test_sends_as_real_sends,
            test_gifter_usernames=ctx.settings.throne_test_gifter_usernames,
            owner_test_user_id=ctx.settings.throne_test_send_leaderboard_owner_user_id,
            limit=ctx.settings.leaderboard_limit,
        )
        print("Leaderboard Diagnose")
        print(f"Guild ID: {report.guild_id}")
        print(f"Registered Dom/mes: {report.registered_dommes}")
        print(f"Counted sends: {report.counted_sends}")
        print(f"Excluded sends: {report.excluded_sends}")
        print("Excluded reasons:")
        print(f"- not posted: {report.excluded_not_posted}")
        print(f"- private: {report.excluded_private}")
        print(f"- test send excluded: {report.excluded_test_send}")
        print(f"- domme_user_id missing/mismatch: {report.excluded_domme_mismatch}")
        print(f"- guild mismatch: {report.excluded_guild_mismatch}")
        print("Dom/me Rows:")
        if not report.domme_rows:
            print("(none)")
        for row in report.domme_rows:
            print(f"{row.label} total={row.total_cents} sends={row.send_count}")
        print("Sends with no matching Dom/me:")
        if not report.unmatched_sends:
            print("(none)")
        for send_id, domme_user_id, send_guild_id in report.unmatched_sends:
            print(f"id={send_id} domme_user_id={domme_user_id} guild_id={send_guild_id}")
        return
    if args.leaderboard_command == "repair-send-dommes":
        guild_id = await resolve_guild_id(ctx, getattr(args, "guild_id", None))
        candidates, updated = await ctx.sends.repair_send_domme_user_ids(
            guild_id=guild_id,
            dry_run=bool(args.dry_run),
        )
        print(f"guild_id={guild_id}")
        print(f"dry_run={bool(args.dry_run)}")
        print(f"candidates={candidates}")
        print(f"updated={updated}")
        return
    raise RuntimeError(f"Unsupported leaderboard command: {args.leaderboard_command}")


async def handle_count(ctx: OperationsContext, args: argparse.Namespace) -> None:
    guild_id = await resolve_guild_id(ctx, getattr(args, "guild_id", None))
    if args.count_command == "status":
        state = await ctx.counting.get(guild_id)
        if state is None:
            print(f"guild_id={guild_id}")
            print("counting_state=missing")
            return
        print(f"guild_id={guild_id}")
        print(f"enabled={state.is_enabled}")
        print(f"channel_id={state.channel_id or 0}")
        print(f"current_number={state.current_number}")
        print(f"last_user_id={state.last_user_id or 0}")
        return
    if args.count_command == "set":
        existing = await ctx.counting.get(guild_id)
        channel_id = existing.channel_id if existing is not None else None
        is_enabled = existing.is_enabled if existing is not None else channel_id is not None
        await ctx.counting.upsert(
            guild_id=guild_id,
            channel_id=channel_id,
            current_number=max(0, int(args.number)),
            last_user_id=None,
            is_enabled=is_enabled,
            pending_restore=False,
        )
        print(f"guild_id={guild_id}")
        print(f"current_number={max(0, int(args.number))}")
        return
    raise RuntimeError(f"Unsupported count command: {args.count_command}")


async def handle_throne(ctx: OperationsContext, args: argparse.Namespace) -> None:
    if args.throne_command in {"status", "dommes", "subs"}:
        print(f"{args.throne_command}=planned but not implemented in this robctl release")
        return
    if args.throne_command == "invalidate-test-sends":
        usernames = list(ctx.settings.throne_test_gifter_usernames)
        updated = await ctx.sends.mark_known_test_sends(test_gifter_usernames=usernames)
        print(f"updated={updated}")
        print(f"usernames={','.join(usernames)}")
        return
    raise RuntimeError(f"Unsupported throne command: {args.throne_command}")


async def handle_sends(ctx: OperationsContext, args: argparse.Namespace) -> None:
    if args.sends_command == "list":
        guild_id = getattr(args, "guild_id", None)
        if guild_id is None:
            try:
                guild_id = await resolve_guild_id(ctx, None)
            except RuntimeError:
                guild_id = None
        rows = await ctx.sends.list_sends(
            guild_id=guild_id,
            status=args.status,
            limit=max(1, int(args.limit)),
        )
        print(f"status={args.status}")
        print(f"guild_id={guild_id if guild_id is not None else 'all'}")
        print(f"rows={len(rows)}")
        for send in rows:
            print(
                f"id={send.id} guild_id={send.guild_id} domme_user_id={send.domme_user_id} "
                f"sub_user_id={send.sub_user_id or 0} amount_cents={send.amount_cents} "
                f"status={send.discord_post_status} is_private={send.is_private} is_test_send={send.is_test_send}"
            )
        return
    if args.sends_command == "backfill-public-ids":
        updated = await ctx.sends.backfill_public_send_ids()
        print(f"updated={updated}")
        return
    if args.sends_command == "mark-posted":
        updated = await ctx.sends.force_mark_posted(args.send_id)
        print(f"send_id={args.send_id}")
        print(f"updated={updated}")
        return
    raise RuntimeError(f"Unsupported sends command: {args.sends_command}")


async def main_async() -> None:
    parser = build_parser()
    args = parser.parse_args()
    ctx = await create_context()
    try:
        if args.command == "status":
            await handle_status(ctx)
        elif args.command == "maintenance":
            await handle_maintenance(ctx, args)
        elif args.command == "queue":
            await handle_queue(ctx, args)
        elif args.command == "leaderboard":
            await handle_leaderboard(ctx, args)
        elif args.command == "count":
            await handle_count(ctx, args)
        elif args.command == "throne":
            await handle_throne(ctx, args)
        elif args.command == "sends":
            await handle_sends(ctx, args)
        else:
            raise RuntimeError(f"Unsupported command: {args.command}")
    finally:
        await ctx.database.close()


def main() -> None:
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
