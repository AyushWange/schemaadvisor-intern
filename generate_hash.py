import sys
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def generate_hash(password: str):
    return pwd_context.hash(password)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python generate_hash.py <password>")
        sys.exit(1)
    
    password = sys.argv[1]
    hashed = generate_hash(password)
    print(f"\nPassword: {password}")
    print(f"Hash: {hashed}")
    print("\nCopy the hash into your .env file as ADMIN_PASSWORD_HASH")
