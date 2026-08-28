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
                AS with_comments,
              count(*) FILTER (WHERE origin = 'self') AS self_registered,
              count(*) FILTER (WHERE origin = 'self' AND NOT reviewed) AS pending_review
            FROM invitees
            """
        )
        total, attending, declined, pending, with_comments, self_registered, pending_review = cur.fetchone()
        return {
            "total": total,
            "attending": attending,
            "declined": declined,
            "pending": pending,
            "with_comments": with_comments,
            "self_registered": self_registered,
            "pending_review": pending_review,
        }


def update_rsvp(invitee_id, status, plus_one_details, comments, email):
    """Update an RSVP (and the contact email alongside it) and write an
    audit row in one transaction. email is required, not optional --
    every caller already has a current value in hand (the guest's own
    submission, or an admin edit), so there's no "leave it alone"
    sentinel to design around."""
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
               SET rsvp_status = %s, plus_one_details = %s, comments = %s, email = %s
             WHERE id = %s
            """,
            (status, plus_one_details, comments, email or None, invitee_id),
        )
        cur.execute(
            """
            INSERT INTO rsvp_history (invitee_id, old_status, new_status)
            VALUES (%s, %s, %s)
            """,
            (invitee_id, old_status, status),
        )
        return True


def update_invitee(invitee_id, primary_name, email, max_guests):
    """Update an invitee's contact info. Returns False if no such id."""
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            UPDATE invitees
               SET primary_name = %s, email = %s, max_guests = %s
             WHERE id = %s
            """,
            (primary_name, email or None, max_guests, invitee_id),
        )
        return cur.rowcount > 0


def delete_invitee(invitee_id):
    """Delete an invitee. Returns False if no such id."""
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM invitees WHERE id = %s", (invitee_id,))
        return cur.rowcount > 0


def mark_invitee_reviewed(invitee_id):
    """Dismiss the dashboard's pending-review flag on a self-registered
    invitee. Doesn't affect their access -- self-registration already
    grants a real invite immediately; this is bookkeeping only.
    Returns False if no such id."""
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("UPDATE invitees SET reviewed = true WHERE id = %s", (invitee_id,))
        return cur.rowcount > 0


def insert_invitee(primary_name, email, max_guests, lookup_phrase, origin="admin", reviewed=True):
    """Insert one invitee. Raises psycopg2.errors.UniqueViolation on a
    phrase collision so the caller can regenerate and retry."""
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO invitees (primary_name, email, max_guests, lookup_phrase, origin, reviewed)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (primary_name, email or None, max_guests, lookup_phrase, origin, reviewed),
        )
        return cur.fetchone()[0]


def insert_self_invitee(primary_name, email, max_guests, lookup_phrase):
    """Thin wrapper around insert_invitee for the public self-registration
    flow (anonymous-phrase flyer/poster signups). Always sets
    origin='self' and reviewed=False so admins can flag these rows for
    review on the dashboard. Kept separate rather than passing origin
    through phrases.insert_with_unique_phrase's *args, since that
    helper always appends the generated phrase as the last positional
    argument -- threading extra params through there would land in
    the wrong slot."""
    return insert_invitee(
        primary_name, email, max_guests, lookup_phrase, origin="self", reviewed=False
    )
