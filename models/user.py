from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from models.db import query


class User(UserMixin):
    def __init__(self, id, first_name, last_name, email, password_hash, created_at=None, last_login=None):
        self.id            = id
        self.first_name    = first_name
        self.last_name     = last_name
        self.email         = email
        self.password_hash = password_hash
        self.created_at    = created_at
        self.last_login    = last_login

    @property
    def name(self):
        return f"{self.first_name} {self.last_name}"

    @property
    def initial(self):
        return self.first_name[0].upper() if self.first_name else '?'

    # ── Flask-Login requires this ──────────────────────
    def get_id(self):
        return str(self.id)

    # ── CRUD ──────────────────────────────────────────
    @staticmethod
    def get_by_id(user_id):
        row = query("SELECT * FROM users WHERE id = %s", (user_id,), fetchone=True)
        return User(**row) if row else None

    @staticmethod
    def get_by_email(email):
        row = query("SELECT * FROM users WHERE email = %s", (email,), fetchone=True)
        return User(**row) if row else None

    @staticmethod
    def create(first_name, last_name, email, password):
        hashed = generate_password_hash(password)
        user_id = query(
            "INSERT INTO users (first_name, last_name, email, password_hash) VALUES (%s,%s,%s,%s)",
            (first_name, last_name, email, hashed),
            commit=True
        )
        return User.get_by_id(user_id)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def update_last_login(self):
        query("UPDATE users SET last_login = NOW() WHERE id = %s", (self.id,), commit=True)
