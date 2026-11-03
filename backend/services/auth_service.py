"""
Auth Service Module
User identity, guest session generation, and admin authentication.
"""

from typing import Dict, Any, Optional
from backend.database import db_session
from backend.telemetry import append_structured_log

class AuthService:
    def __init__(self):
        self.service_name = "auth-service"

    async def get_user_profile(self, username: str) -> Optional[Dict[str, Any]]:
        """Fetch user profile details from SQLite."""
        from backend.sentinel.simulation_engine import simulation_engine
        await simulation_engine.check_and_apply_fault(self.service_name)

        with db_session() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, username, email, full_name, role FROM users WHERE username = ?;", (username,))
            row = cursor.fetchone()
            if row:
                return {
                    "id": row["id"],
                    "username": row["username"],
                    "email": row["email"],
                    "full_name": row["full_name"],
                    "role": row["role"]
                }
        return None

    async def authenticate_user(self, username: str) -> Dict[str, Any]:
        """Authenticate user or create guest shopper account."""
        user = await self.get_user_profile(username)
        if not user:
            # Create guest user
            with db_session() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO users (username, email, full_name, role)
                    VALUES (?, ?, ?, 'shopper');
                """, (username, f"{username}@sentinel.local", username.title()))
            user = await self.get_user_profile(username)

        append_structured_log(
            service=self.service_name,
            level="INFO",
            message=f"User authenticated: {username}",
            metadata={"username": username}
        )
        return user

    def health_check(self) -> Dict[str, Any]:
        """Service health check."""
        with db_session() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM users;")
            count = cursor.fetchone()[0]
        return {
            "service": self.service_name,
            "status": "UP",
            "registered_users": count
        }

auth_service = AuthService()
