#!/bin/bash

echo "Fixing bcrypt and passlib compatibility..."

# Deactivate virtual environment if active
deactivate 2>/dev/null

# Remove problematic packages
pip uninstall passlib bcrypt python-jose -y

# Install compatible versions
pip install passlib==1.7.4 bcrypt==4.0.1 python-jose[cryptography]==3.3.0

# Test the imports
python -c "
from passlib.context import CryptContext
print('✅ passlib works')
ctx = CryptContext(schemes=['bcrypt'])
hash = ctx.hash('test123')
print('✅ bcrypt works:', hash)
print('Setup completed successfully!')
"

echo "You can now run: uvicorn src.main:app --reload --port 8000"