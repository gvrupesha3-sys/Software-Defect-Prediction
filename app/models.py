from flask_login import UserMixin
import database as db

class User(UserMixin):
    def __init__(self, user_data: dict):
        self.data = user_data or {}
        self.id = str(self.data.get("user_id") or self.data.get("_id") or "")
        self.user_id = self.id
        self.username = self.data.get("username", "")
        self.email = self.data.get("email", "")
        self.full_name = self.data.get("full_name", "")
        self.role = self.data.get("role", "user")
        self.created_at = self.data.get("created_at")

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"

    def get_id(self) -> str:
        return self.id

    @classmethod
    def get(cls, user_id):
        if not user_id:
            return None
        doc = db.get_user_by_id(user_id)
        if doc:
            return cls(doc)
        return None

    @classmethod
    def get_by_identifier(cls, identifier: str):
        if not identifier:
            return None
        doc = db.get_user_by_identifier(identifier)
        if doc:
            return cls(doc)
        return None
