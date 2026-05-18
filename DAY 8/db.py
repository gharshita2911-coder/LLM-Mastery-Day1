"""
db.py - Database helpers + Step 4: Store
=========================================
Responsibilities:
  - Open / initialise the SQLite DB from schema.sql
  - INSERT one TicketRecord into the tickets table
  - Return id, created_at, and row_count after insert
"""

import sqlite3
from datetime import datetime,timezone

from config import DB_PATH,TicketRecord

def get_conn()->sqlite3.Connection: #This function returns a SQLite connection object.
    conn=sqlite3.connect(DB_PATH) 
    conn.row_factory=sqlite3.Row
    return conn

def init_db():
    """Create tables/views from schema.sql if they don't exist yet."""

    with open("schema.sql") as f:
        sql = f.read()
    with get_conn() as conn:
        conn.executescript(sql)


_INSERT_SQL="""
INSERT INTO tickets
(raw_text,person,company,product,issue,category,summary,prompt_tokens,candidates_tokens,total_tokens,status,error_step,error_msg,latency_ms,created_at)

VALUES
(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
"""

def step4_store(record: TicketRecord)->tuple[int,str,int]:
    """
    Persist *record* to DB regardless of success/failure.
    Returns (id, created_at, row_count).
    """
    created_at = datetime.now(timezone.utc).isoformat()
    c = record.completion

    with get_conn() as conn:
        cur = conn.execute(
            _INSERT_SQL,
            (
                record.raw_text,
                record.person,
                record.company,
                record.product,
                record.issue,
                record.category,
                record.summary,
                c.prompt_token_count,
                c.candidates_token_count,
                c.total_token_count,
                record.status,
                record.error_step,
                record.error_msg,
                record.latency_ms,
                created_at,
            ),
        )
        row_id = cur.lastrowid
 
        # Total rows stored so far
        row_count = conn.execute("SELECT COUNT(*) FROM tickets").fetchone()[0]
 
    return row_id, created_at, row_count