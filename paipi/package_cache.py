"""
Manages a local cache of PyPI package names for fast lookups.

This module downloads the complete list of packages from the PyPI Simple Index,
stores them in an SQLite database, and provides a fast, in-memory check
to verify if a package name is legitimate.
"""

import re
import sqlite3
from pathlib import Path
from typing import Set

import httpx

# --- Constants ---
CACHE_DB_PATH = Path("paipi_cache.db")
PYPI_SIMPLE_URL = "https://pypi.org/simple/"


class PackageCache:
    """A singleton class to manage the PyPI package name cache."""

    _instance = None
    _db_path: Path
    _connection: sqlite3.Connection | None = None
    _package_names: Set[str] | None = None

    def __new__(cls, db_path: Path = CACHE_DB_PATH):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._db_path = db_path
            cls._instance._init_db()
        return cls._instance

    def _init_db(self) -> None:
        """Initialize the database and table if they don't exist."""
        try:
            # check_same_thread=False is safe for this read-heavy, single-writer use case
            self._connection = sqlite3.connect(self._db_path, check_same_thread=False)
            cursor = self._connection.cursor()
            cursor.execute(
                """
                           CREATE TABLE IF NOT EXISTS packages
                           (
                               name
                               TEXT
                               PRIMARY
                               KEY
                           )
                           """
            )
            self._connection.commit()
            print(f"Cache database initialized at {self._db_path}")
        except sqlite3.Error as e:
            print(f"Database error during initialization: {e}")
            self._connection = None

    def load_into_memory(self):
        """Load all package names from DB into a set for fast lookups."""
        if self._package_names is not None:
            return  # Already loaded
        if self._connection:
            try:
                print("Loading package names from database into memory...")
                cursor = self._connection.cursor()
                cursor.execute("SELECT name FROM packages")
                self._package_names = {row[0] for row in cursor.fetchall()}
                print(
                    f"Loaded {len(self._package_names)} package names into memory cache."
                )
            except sqlite3.Error as e:
                print(f"Database error loading names into memory: {e}")
                self._package_names = set()
        else:
            self._package_names = set()

    def has_data(self) -> bool:
        """Check if the cache contains any package data."""
        if not self._connection:
            return False
        try:
            cursor = self._connection.cursor()
            # Use EXISTS for an efficient check without counting all rows
            cursor.execute("SELECT EXISTS(SELECT 1 FROM packages)")
            result = cursor.fetchone()
            return result[0] == 1 if result else False
        except sqlite3.Error as e:
            print(f"Database error checking for data: {e}")
            return False

    def update_cache(self) -> None:
        """Fetch all package names from PyPI and update the local SQLite cache."""
        if not self._connection:
            print("Cannot update cache: database connection not available.")
            return

        print("Starting PyPI package list update from server...")
        try:
            with httpx.Client() as client:
                response = client.get(PYPI_SIMPLE_URL, timeout=120.0)
                response.raise_for_status()

            # Regex to find package names in the href attributes of the simple index
            package_names = re.findall(r'<a href="/simple/([^/]+)/">', response.text)

            if not package_names:
                print("Could not find any package names. Aborting cache update.")
                return

            cursor = self._connection.cursor()

            # Use a transaction for much faster inserts
            cursor.execute("BEGIN TRANSACTION")
            cursor.execute("DELETE FROM packages")  # Clear old data
            cursor.executemany(
                "INSERT OR IGNORE INTO packages (name) VALUES (?)",
                [(name,) for name in package_names],
            )
            cursor.execute("COMMIT")

            print(f"Successfully updated cache with {len(package_names)} packages.")
            self._package_names = None  # Force reload on next check
            self.load_into_memory()  # Refresh in-memory set

        except httpx.RequestError as e:
            print(f"HTTP error while fetching package list: {e}")
        except sqlite3.Error as e:
            print(f"Database error during cache update: {e}")
            if self._connection:
                self._connection.rollback()
        except Exception as e:
            print(f"An unexpected error occurred during cache update: {e}")

    def package_exists(self, package_name: str) -> bool:
        """Check if a package exists in the cache (case-insensitive and normalized)."""
        if self._package_names is None:
            self.load_into_memory()

        # PyPI names are normalized to be lowercase with hyphens instead of underscores.
        normalized_name = package_name.lower().replace("_", "-")

        return normalized_name in self._package_names if self._package_names else False

    def close(self):
        """Closes the database connection."""
        if self._connection:
            self._connection.close()
            self._connection = None


# Global instance to be used across the application
package_cache = PackageCache()
