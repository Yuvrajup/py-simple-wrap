import pytest
import sqlite3
from py_simple.easy_sql import (
open_db, 
EasySqlError, 
run_update,
ExperimentalWarning, 
run_select,
conditional_run_select,
run_insert,
run_delete, 
delete_all_from_table,
_check_if_valid,
)

def test_open_db_success():
    """Test if the database opens successfully."""
    # SQLite has a cool trick: using ":memory:" creates a temporary 
    # database in your computer's RAM that deletes itself when finished!
    conn, cursor = open_db(":memory:")
    
    # Assert (check) that the function gave us back the right types of objects
    assert isinstance(conn, sqlite3.Connection)
    assert isinstance(cursor, sqlite3.Cursor)
    
    # Close the connection safely
    conn.close()

def test_open_db_error():
    """Test if EasySqlError is raised when given a bad path."""
    # We give it a completely impossible file path to force it to fail
    invalid_path = "/this/directory/does/not/exist/test.db"
    
    # Assert that calling the function with a bad path raises Sara's custom error
    with pytest.raises(EasySqlError):
        open_db(invalid_path)

@pytest.fixture
def users_db():
    """Sets up an in-memory database with a small users table."""
    conn, cursor = open_db(":memory:")
    cursor.execute(
        "CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT, age INTEGER)")
    cursor.executemany(
        "INSERT INTO users (name, age) VALUES (?, ?)",
        [("Ada", 25), ("Grace", 40)],
    )
    conn.commit()
    yield conn, cursor
    conn.close()


def test_run_update_changes_matching_row(users_db):
    """Test that run_update only changes the row matching the condition."""
    conn, cursor = users_db

    run_update(conn, cursor, "users", {"age": 30}, "name = ?", ("Ada",))

    cursor.execute("SELECT age FROM users WHERE name = ?", ("Ada",))
    assert cursor.fetchone()[0] == 30

    # Grace's row should be untouched
    cursor.execute("SELECT age FROM users WHERE name = ?", ("Grace",))
    assert cursor.fetchone()[0] == 40


def test_run_update_multiple_columns(users_db):
    """Test that run_update can set more than one column at once."""
    conn, cursor = users_db

    run_update(conn, cursor, "users", {"name": "Ada Lovelace", "age": 36},
               "name = ?", ("Ada",))

    cursor.execute("SELECT name, age FROM users WHERE age = 36")
    row = cursor.fetchone()
    assert row == ("Ada Lovelace", 36)


def test_run_update_invalid_table_name_raises(users_db):
    """Test that an unsafe table_name raises EasySqlError instead of running."""
    conn, cursor = users_db

    with pytest.raises(EasySqlError):
        run_update(conn, cursor, "users; DROP TABLE users;", {"age": 99},
                   "name = ?", ("Ada",))


def test_run_update_invalid_column_name_raises(users_db):
    """Test that an unsafe column name in updates raises EasySqlError."""
    conn, cursor = users_db

    with pytest.raises(EasySqlError):
        run_update(conn, cursor, "users", {"age; DROP TABLE users;": 99},
                   "name = ?", ("Ada",))


def test_run_update_bad_condition_raises(users_db):
    """Test that a condition referencing a non-existent column surfaces as EasySqlError."""
    conn, cursor = users_db

    with pytest.raises(EasySqlError):
        run_update(conn, cursor, "users", {"age": 99},
                   "not_a_real_column = ?", ("Ada",))


def test_run_update_closes_connection_when_requested(users_db):
    """Test that close_conn_after=True closes the connection after updating."""
    conn, cursor = users_db

    run_update(conn, cursor, "users", {"age": 50}, "name = ?", ("Ada",),
               close_conn_after=True)

    with pytest.raises(sqlite3.ProgrammingError):
        conn.execute("SELECT 1") 
        
def test_check_if_valid_accepts_plain_identifier():
    assert _check_if_valid("users") is True
 
 
def test_check_if_valid_accepts_comma_separated_columns():
    assert _check_if_valid("name, age") is True
 
 
def test_check_if_valid_accepts_star():
    assert _check_if_valid("*") is True
 
 
def test_check_if_valid_rejects_non_string():
    assert _check_if_valid(123) is False
 
 
@pytest.mark.parametrize("bad_value", [
    "users; DROP TABLE users;",
    "SELECT * FROM users",
    "name -- comment",
    "sqlite_master",
    "users JOIN other",
])
def test_check_if_valid_rejects_forbidden_keywords_and_symbols(bad_value):
    assert _check_if_valid(bad_value) is False

def test_run_select_returns_all_matching_rows(users_db):
    conn, cursor = users_db
    with pytest.warns(ExperimentalWarning):
        rows = run_select(conn, cursor, "users", "name, age")
    assert set(rows) == {("Ada", 25), ("Grace", 40)}
 
 
def test_run_select_star_returns_full_rows(users_db):
    conn, cursor = users_db
    with pytest.warns(ExperimentalWarning):
        rows = run_select(conn, cursor, "users", "*")
    assert len(rows) == 2
    assert len(rows[0]) == 3  # id, name, age
 
 
def test_run_select_invalid_table_name_raises(users_db):
    conn, cursor = users_db
    with pytest.warns(ExperimentalWarning), pytest.raises(EasySqlError):
        run_select(conn, cursor, "users; DROP TABLE users;", "*")
 
 
def test_run_select_invalid_to_select_raises(users_db):
    conn, cursor = users_db
    with pytest.warns(ExperimentalWarning), pytest.raises(EasySqlError):
        run_select(conn, cursor, "users", "name; DROP TABLE users;")
 
 
def test_run_select_nonexistent_table_raises(users_db):
    conn, cursor = users_db
    with pytest.warns(ExperimentalWarning), pytest.raises(EasySqlError):
        run_select(conn, cursor, "not_a_table", "*")
 
 
def test_run_select_closes_connection_when_requested(users_db):
    conn, cursor = users_db
    with pytest.warns(ExperimentalWarning):
        run_select(conn, cursor, "users", "*", close_conn_after=True)
    with pytest.raises(sqlite3.ProgrammingError):
        conn.execute("SELECT 1")
 
def test_conditional_run_select_filters_rows(users_db):
    conn, cursor = users_db
    with pytest.warns(ExperimentalWarning):
        rows = conditional_run_select(
            conn, cursor, "users", "name", "age > ?", (30,))
    assert rows == [("Grace",)]
 
 
def test_conditional_run_select_no_matches_returns_empty_list(users_db):
    conn, cursor = users_db
    with pytest.warns(ExperimentalWarning):
        rows = conditional_run_select(
            conn, cursor, "users", "name", "age > ?", (100,))
    assert rows == []
 
 
def test_conditional_run_select_invalid_table_name_raises(users_db):
    conn, cursor = users_db
    with pytest.warns(ExperimentalWarning), pytest.raises(EasySqlError):
        conditional_run_select(
            conn, cursor, "users; DROP TABLE users;", "name", "age > ?", (30,))
 
 
def test_conditional_run_select_bad_condition_raises(users_db):
    conn, cursor = users_db
    with pytest.warns(ExperimentalWarning), pytest.raises(EasySqlError):
        conditional_run_select(
            conn, cursor, "users", "name", "not_a_real_column = ?", (30,))
 
 
def test_conditional_run_select_closes_connection_when_requested(users_db):
    conn, cursor = users_db
    with pytest.warns(ExperimentalWarning):
        conditional_run_select(
            conn, cursor, "users", "name", "age > ?", (0,),
            close_conn_after=True)
    with pytest.raises(sqlite3.ProgrammingError):
        conn.execute("SELECT 1")
def test_run_insert_adds_row(users_db):
    conn, cursor = users_db
    with pytest.warns(ExperimentalWarning):
        run_insert(conn, cursor, ["Lin", 28], "users", ["name", "age"])
    cursor.execute("SELECT name, age FROM users WHERE name = ?", ("Lin",))
    assert cursor.fetchone() == ("Lin", 28)
 
 
def test_run_insert_commits_data(users_db):
    conn, cursor = users_db
    with pytest.warns(ExperimentalWarning):
        run_insert(conn, cursor, ["Lin", 28], "users", ["name", "age"])
    # A brand-new cursor should still see the committed row
    new_cursor = conn.cursor()
    new_cursor.execute("SELECT COUNT(*) FROM users")
    assert new_cursor.fetchone()[0] == 3
 
 
def test_run_insert_invalid_table_name_raises(users_db):
    conn, cursor = users_db
    with pytest.warns(ExperimentalWarning), pytest.raises(EasySqlError):
        run_insert(conn, cursor, ["Lin", 28], "users; DROP TABLE users;",
                   ["name", "age"])
 
 
def test_run_insert_invalid_column_name_raises(users_db):
    conn, cursor = users_db
    with pytest.warns(ExperimentalWarning), pytest.raises(EasySqlError):
        run_insert(conn, cursor, ["Lin", 28], "users",
                   ["name", "age; DROP TABLE users;"])
 
 
def test_run_insert_mismatched_values_raises(users_db):
    conn, cursor = users_db
    # Two columns declared but three values supplied -> underlying sqlite error
    with pytest.warns(ExperimentalWarning), pytest.raises(EasySqlError):
        run_insert(conn, cursor, ["Lin", 28, "extra"], "users",
                   ["name", "age"])
 
 
def test_run_insert_closes_connection_when_requested(users_db):
    conn, cursor = users_db
    with pytest.warns(ExperimentalWarning):
        run_insert(conn, cursor, ["Lin", 28], "users", ["name", "age"],
                   close_conn_after=True)
    with pytest.raises(sqlite3.ProgrammingError):
        conn.execute("SELECT 1")

def test_run_delete_removes_matching_row(users_db):
    conn, cursor = users_db
    with pytest.warns(ExperimentalWarning):
        run_delete(conn, cursor, "users", "name = ?", ("Ada",))
    cursor.execute("SELECT COUNT(*) FROM users WHERE name = ?", ("Ada",))
    assert cursor.fetchone()[0] == 0
    # Grace should remain untouched
    cursor.execute("SELECT COUNT(*) FROM users WHERE name = ?", ("Grace",))
    assert cursor.fetchone()[0] == 1
 
 
def test_run_delete_invalid_table_name_raises(users_db):
    conn, cursor = users_db
    with pytest.warns(ExperimentalWarning), pytest.raises(EasySqlError):
        run_delete(conn, cursor, "users; DROP TABLE users;", "name = ?",
                   ("Ada",))
 
 
def test_run_delete_bad_condition_raises(users_db):
    conn, cursor = users_db
    with pytest.warns(ExperimentalWarning), pytest.raises(EasySqlError):
        run_delete(conn, cursor, "users", "not_a_real_column = ?", ("Ada",))
 
 
def test_run_delete_closes_connection_when_requested(users_db):
    conn, cursor = users_db
    with pytest.warns(ExperimentalWarning):
        run_delete(conn, cursor, "users", "name = ?", ("Ada",),
                   close_conn_after=True)
    with pytest.raises(sqlite3.ProgrammingError):
        conn.execute("SELECT 1")
def test_delete_all_from_table_empties_table_but_keeps_schema(users_db):
    conn, cursor = users_db
    with pytest.warns(ExperimentalWarning):
        delete_all_from_table(conn, cursor, "users")
    cursor.execute("SELECT COUNT(*) FROM users")
    assert cursor.fetchone()[0] == 0
    # Table itself should still exist and accept inserts
    cursor.execute("INSERT INTO users (name, age) VALUES ('Zoe', 22)")
    cursor.execute("SELECT COUNT(*) FROM users")
    assert cursor.fetchone()[0] == 1
 
 
def test_delete_all_from_table_invalid_table_name_raises(users_db):
    conn, cursor = users_db
    with pytest.warns(ExperimentalWarning), pytest.raises(EasySqlError):
        delete_all_from_table(conn, cursor, "users; DROP TABLE users;")
 
 
def test_delete_all_from_table_nonexistent_table_raises(users_db):
    conn, cursor = users_db
    with pytest.warns(ExperimentalWarning), pytest.raises(EasySqlError):
        delete_all_from_table(conn, cursor, "not_a_table")
 
 
def test_delete_all_from_table_closes_connection_when_requested(users_db):
    conn, cursor = users_db
    with pytest.warns(ExperimentalWarning):
        delete_all_from_table(conn, cursor, "users", close_conn_after=True)
    with pytest.raises(sqlite3.ProgrammingError):
        conn.execute("SELECT 1")
