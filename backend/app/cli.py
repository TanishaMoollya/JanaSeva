"""Local admin bootstrap: python -m app.cli create-admin"""
import getpass
import sys
from sqlalchemy import select
from app.db import Base, SessionLocal, engine
from app.models import User
from app.security import hash_password

def main():
    if len(sys.argv) != 2 or sys.argv[1] != "create-admin":
        raise SystemExit("Usage: python -m app.cli create-admin")
    Base.metadata.create_all(bind=engine)
    email = input("Administrator email: ").strip().lower()
    name = input("Administrator name: ").strip()
    password = getpass.getpass("Administrator password (12+ characters): ")
    if len(password) < 12:
        raise SystemExit("Use a password with at least 12 characters")
    with SessionLocal() as db:
        if db.scalar(select(User).where(User.email == email)):
            raise SystemExit("That email already has an account")
        db.add(User(name=name, email=email, password_hash=hash_password(password), role="admin"))
        db.commit()
    print("Administrator created. Keep the password private.")

if __name__ == "__main__":
    main()
