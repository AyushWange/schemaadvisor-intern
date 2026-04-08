import sys
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

# Add project root to sys.path so project_XX imports work inside tests
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
