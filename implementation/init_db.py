"""Initialize the SQLite lab database with schema and seed data."""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

DEFAULT_DB_PATH = Path(__file__).resolve().parent / "lab.db"

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS students (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    name    TEXT    NOT NULL,
    cohort  TEXT    NOT NULL,
    score   REAL    NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS courses (
    id    INTEGER PRIMARY KEY AUTOINCREMENT,
    code  TEXT    NOT NULL UNIQUE,
    title TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS enrollments (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    course_id  INTEGER NOT NULL REFERENCES courses(id)  ON DELETE CASCADE,
    grade      REAL    NOT NULL DEFAULT 0
);
"""

STUDENTS_SEED = [
    (1, "Alice Nguyen",   "A1", 92.5),
    (2, "Bao Tran",       "A1", 78.0),
    (3, "Chau Le",        "A2", 85.5),
    (4, "Duy Pham",       "A2", 64.0),
    (5, "Emily Vo",       "A1", 88.0),
    (6, "Felix Hoang",    "B1", 71.5),
    (7, "Giang Bui",      "B1", 95.0),
    (8, "Hieu Dao",       "B2", 59.5),
]

COURSES_SEED = [
    (1, "CS101", "Intro to Computer Science"),
    (2, "DS200", "Data Structures"),
    (3, "ML300", "Machine Learning"),
]

ENROLLMENTS_SEED = [
    (1, 1, 1, 90.0),
    (2, 1, 2, 88.0),
    (3, 2, 1, 72.0),
    (4, 3, 2, 84.5),
    (5, 3, 3, 91.0),
    (6, 4, 1, 60.0),
    (7, 5, 3, 95.0),
    (8, 6, 2, 70.0),
    (9, 7, 3, 99.0),
    (10, 8, 1, 55.0),
]


def create_database(db_path: os.PathLike | str = DEFAULT_DB_PATH) -> str:
    """Create (or reset) the lab database and seed it.

    Returns the absolute path to the database file.
    """
    db_path = Path(db_path).resolve()
    if db_path.exists():
        db_path.unlink()

    conn = sqlite3.connect(db_path)
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.executescript(SCHEMA_SQL)
        conn.executemany(
            "INSERT INTO students (id, name, cohort, score) VALUES (?, ?, ?, ?)",
            STUDENTS_SEED,
        )
        conn.executemany(
            "INSERT INTO courses (id, code, title) VALUES (?, ?, ?)",
            COURSES_SEED,
        )
        conn.executemany(
            "INSERT INTO enrollments (id, student_id, course_id, grade) VALUES (?, ?, ?, ?)",
            ENROLLMENTS_SEED,
        )
        conn.commit()
    finally:
        conn.close()

    return str(db_path)


if __name__ == "__main__":
    path = create_database()
    print(f"Initialized database at: {path}")
