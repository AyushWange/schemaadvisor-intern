import sys
import os

# Add project root to sys.path so project_XX imports work inside tests
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
