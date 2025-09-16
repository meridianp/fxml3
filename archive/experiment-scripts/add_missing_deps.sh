#!/bin/bash
# Quick fix script to add missing dependencies to existing image

echo "Adding missing authentication dependencies to FXML4 image..."

# Create a new image from the existing one with missing dependencies
docker run --name fxml4-temp fxml4:latest /bin/bash -c "
    pip install --no-cache-dir \
        python-jose[cryptography]==3.3.0 \
        python-multipart==0.0.6 \
        > /dev/null 2>&1 \
    && echo '✅ Dependencies installed successfully'
"

# Commit the changes to a new image
docker commit fxml4-temp fxml4:patched

# Remove temporary container
docker rm fxml4-temp

echo "✅ Created fxml4:patched with authentication dependencies"
echo "Test with: docker run --rm fxml4:patched python -c \"from fxml4.api.main import app; print('✅ API working')\""