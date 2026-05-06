#!/usr/bin/env python3
"""Staff account management CLI.

Usage:
  python manage.py add-user <username> <password>
  python manage.py set-password <username> <new_password>
  python manage.py deactivate-user <username>
  python manage.py list-users
"""

import argparse
import asyncio
import sys
import os

# Allow running from project root
sys.path.insert(0, os.path.dirname(__file__))

from app.database import async_engine, AsyncSessionLocal
from app.auth import hash_password
from app.models.staff_user import StaffUser


async def add_user(username: str, password: str) -> None:
    from sqlmodel import select
    async with AsyncSessionLocal() as session:
        existing = await session.exec(select(StaffUser).where(StaffUser.username == username))
        if existing.first():
            print(f"Error: user '{username}' already exists", file=sys.stderr)
            sys.exit(1)
        import uuid
        session.add(StaffUser(
            user_id=str(uuid.uuid4()),
            username=username,
            password_hash=hash_password(password),
        ))
        await session.commit()
    print(f"User '{username}' created.")


async def set_password(username: str, new_password: str) -> None:
    from sqlmodel import select
    async with AsyncSessionLocal() as session:
        result = await session.exec(select(StaffUser).where(StaffUser.username == username))
        user = result.first()
        if not user:
            print(f"Error: user '{username}' not found", file=sys.stderr)
            sys.exit(1)
        user.password_hash = hash_password(new_password)
        session.add(user)
        await session.commit()
    print(f"Password updated for '{username}'.")


async def deactivate_user(username: str) -> None:
    from sqlmodel import select
    async with AsyncSessionLocal() as session:
        result = await session.exec(select(StaffUser).where(StaffUser.username == username))
        user = result.first()
        if not user:
            print(f"Error: user '{username}' not found", file=sys.stderr)
            sys.exit(1)
        user.active = False
        session.add(user)
        await session.commit()
    print(f"User '{username}' deactivated.")


async def list_users() -> None:
    from sqlmodel import select
    async with AsyncSessionLocal() as session:
        result = await session.exec(select(StaffUser))
        users = result.all()
        if not users:
            print("No users found.")
            return
        print(f"{'Username':<20} {'Active':<8} {'Created'}")
        print("-" * 50)
        for u in users:
            print(f"{u.username:<20} {'Yes' if u.active else 'No':<8} {u.created_at}")


def main():
    parser = argparse.ArgumentParser(description="KMS Staff Account Manager")
    sub = parser.add_subparsers(dest="command", required=True)

    p_add = sub.add_parser("add-user", help="Create a new staff user")
    p_add.add_argument("username")
    p_add.add_argument("password")

    p_pw = sub.add_parser("set-password", help="Change a staff user's password")
    p_pw.add_argument("username")
    p_pw.add_argument("new_password")

    p_deact = sub.add_parser("deactivate-user", help="Deactivate a staff user")
    p_deact.add_argument("username")

    sub.add_parser("list-users", help="List all staff users")

    args = parser.parse_args()

    if args.command == "add-user":
        asyncio.run(add_user(args.username, args.password))
    elif args.command == "set-password":
        asyncio.run(set_password(args.username, args.new_password))
    elif args.command == "deactivate-user":
        asyncio.run(deactivate_user(args.username))
    elif args.command == "list-users":
        asyncio.run(list_users())


if __name__ == "__main__":
    main()
