"""Thin database layer. Plain SQL via psycopg2, no ORM.

All functions take and return simple Python values so routes stay
easy to read and the layer is easy to mock in tests.
"""
import os
from contextlib import contextmanager

import psycopg2
import psycopg2.extras
from psycopg2 import pool

psycopg2.extras.register_uuid()

_pool = None


def _get_pool():
    global _pool
    if _pool is None:
        _pool = pool.SimpleConnectionPool(
            minconn=1,
            maxconn=5,
            host=os.environ.get("POSTGRES_HOST", "postgres"),
            port=int(os.environ.get("POSTGRES_PORT", "5432")),
            user=os.environ.get("POSTGRES_USER", "rsvp_app"),
            password=os.environ.get("POSTGRES_PASSWORD", ""),
            dbname=os.environ.get("POSTGRES_DB", "rsvp"),
        )
    return _pool


@contextmanager
def get_conn():
    p = _get_pool()
    conn = p.getconn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        p.putconn(conn)


def fetch_invitee_by_id(invitee_id):
    with get_conn() as conn, conn.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    ) as cur:
        cur.execute("SELECT * FROM invitees WHERE id = %s", (invitee_id,))
        return cur.fetchone()


def fetch_invitee_by_phrase(phrase):
    with get_conn() as conn, conn.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    ) as cur:
        cur.execute(
            "SELECT * FROM invitees WHERE lookup_phrase = %s", (phrase,)
        )
        return cur.fetchone()


def fetch_invitee_by_email(email):
    with get_conn() as conn, conn.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    ) as cur:
        cur.execute(
            "SELECT * FROM invitees WHERE lower(email) = lower(%s)", (email,)
        )
        return cur.fetchone()


def fetch_all_invitees():
    with get_conn() as conn, conn.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    ) as cur:
        cur.execute("SELECT * FROM invitees ORDER BY primary_name")
        return cur.fetchall()


def dashboard_counts():
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT
              count(*) AS total,
              count(*) FILTER (WHERE rsvp_status = 'Attending') AS attending,
              count(*) FILTER (WHERE rsvp_status = 'Declined') AS declined,
              count(*) FILTER (WHERE rsvp_status = 'Pending') AS pending,
              count(*) FILTER (WHERE comments IS NOT NULL AND comments <> '')
                AS with_comments
            FROM invitees
            """
        )
        total, attending, declined, pending, with_comments = cur.fetchone()
        return {
            "total": total,
            "attending": attending,
            "declined": declined,
            "pending": pending,
            "with_comments": with_comments,
        }


def update_rsvp(invitee_id, status, plus_one_details, comments):
    """Update an RSVP and write an audit row in one transaction."""
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT rsvp_status FROM invitees WHERE id = %s FOR UPDATE",
            (invitee_id,),
        )
        row = cur.fetchone()
        if row is None:
            return False
        old_status = row[0]
        cur.execute(
            """
            UPDATE invitees
               SET rsvp_status = %s, plus_one_details = %s, comments = %s
             WHERE id = %s
            """,
            (status, plus_one_details, comments, invitee_id),
        )
        cur.execute(
            """
            INSERT INTO rsvp_history (invitee_id, old_status, new_status)
            VALUES (%s, %s, %s)
            """,
            (invitee_id, old_status, status),
        )
        return True


def insert_invitee(primary_name, email, max_guests, lookup_phrase):
    """Insert one invitee. Raises psycopg2.errors.UniqueViolation on a
    phrase collision so the caller can regenerate and retry."""
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO invitees (primary_name, email, max_guests, lookup_phrase)
            VALUES (%s, %s, %s, %s)
            RETURNING id
            """,
            (primary_name, email or None, max_guests, lookup_phrase),
        )
        return cur.fetchone()[0]
