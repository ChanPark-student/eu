from dotenv import load_dotenv
load_dotenv()

from app.db.database import engine, Base
from app.models.verify import VerifyReport
from app.models.user import User  # if user model exists

print("Creating tables in PostgreSQL...")
Base.metadata.create_all(bind=engine)
print("Tables created successfully.")
