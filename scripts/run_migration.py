#!/usr/bin/env python3
"""Run database migrations for AI Chat Layer Rewrite.

Creates chat_messages table and seeds standard agent definitions.
Usage: python scripts/run_migration.py
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'ai_service'))

import asyncio
import psycopg
from config import settings


async def run_sql_file(conn, filepath: str) -> None:
    """Execute a SQL file against the database."""
    with open(filepath, 'r') as f:
        sql = f.read()
    await conn.execute(sql)
    print(f"  ✓ Executed: {os.path.basename(filepath)}")


async def main():
    print(f"Connecting to: {settings.postgres_uri}")

    try:
        conn = await psycopg.AsyncConnection.connect(
            settings.postgres_uri,
            autocommit=True,
        )
        print("Connected.\n")
    except Exception as e:
        print(f"ERROR: Could not connect to database: {e}")
        print("Make sure PostgreSQL is running and the connection string is correct.")
        sys.exit(1)

    try:
        migration_dir = os.path.join(
            os.path.dirname(__file__), '..', 'ai_service', 'db', 'migrations'
        )

        # Run migrations
        migrations = [
            '001_create_chat_messages.sql',
            '002_seed_agents_and_setup.sql',
        ]

        for m in migrations:
            path = os.path.join(migration_dir, m)
            if os.path.exists(path):
                await run_sql_file(conn, path)
            else:
                print(f"  ✗ Not found: {m}")

        # Verify
        print("\n--- Verifying ---")

        # Check agents
        cursor = await conn.execute(
            "SELECT id, display_name, enabled FROM agent_definitions ORDER BY priority DESC"
        )
        agents = await cursor.fetchall()
        print(f"\nAgents ({len(agents)}):")
        for row in agents:
            status = "✓" if row[2] else "✗"
            print(f"  {status} {row[0]:20s} {row[1]}")

        # Check chat_messages table exists
        await conn.execute("SELECT 1 FROM chat_messages LIMIT 0")
        print("\n✓ chat_messages table exists")

        print("\n✓ Migration complete.")
    except Exception as e:
        print(f"\nERROR: {e}")
        sys.exit(1)
    finally:
        await conn.close()


if __name__ == '__main__':
    asyncio.run(main())
