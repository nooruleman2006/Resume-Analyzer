from models.db import query


def get_setting(key, default=None):
    """Retrieve a value from site_settings by key."""
    row = query("SELECT value FROM site_settings WHERE key = ?", (key,), fetchone=True)
    return row['value'] if row else default


def set_setting(key, value):
    """Insert or update a key/value pair in site_settings."""
    existing = get_setting(key)
    if existing is not None:
        query(
            "UPDATE site_settings SET value = ? WHERE key = ?",
            (value, key), commit=True
        )
    else:
        query(
            "INSERT INTO site_settings (key, value) VALUES (?, ?)",
            (key, value), commit=True
        )
