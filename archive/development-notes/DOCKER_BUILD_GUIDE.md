# FXML4 Docker Build Guide

## Docker Build Issue Resolution

### Issue Description
The original Docker build failed due to:
- `boruta_py` package not being available in PyPI
- Some dependency conflicts in requirements.txt
- Heavy dependencies causing build timeouts

### Solutions Provided

#### 1. Fixed Requirements Files

**`requirements-docker.txt`** - Docker-optimized dependencies
- Removes problematic packages (boruta_py, heavy ML libraries)
- Focuses on core functionality
- Tested for Docker build compatibility

**`requirements-minimal.txt`** - Minimal core dependencies
- Only essential packages for basic operation
- Fastest build time
- Good for development and testing

**`requirements-fixed.txt`** - Full feature set with fixes
- Commented out problematic packages
- Organized by functionality
- Includes optional packages as comments

#### 2. Improved Dockerfile

**`Dockerfile.fixed`** - Production-ready Docker build
- Multi-stage build for smaller images
- Better error handling
- Fallback installation strategy
- Health checks included

### Build Commands

#### Option 1: Use Docker-optimized requirements (Recommended)
```bash
# Build with Docker-optimized requirements
docker build -f Dockerfile.fixed -t fxml4:latest .

# Or modify original Dockerfile to use requirements-docker.txt
sed -i 's/requirements.txt/requirements-docker.txt/' Dockerfile
docker build -t fxml4:latest .
```

#### Option 2: Use minimal requirements (Development)
```bash
# Build with minimal requirements for development
sed -i 's/requirements.txt/requirements-minimal.txt/' Dockerfile
docker build -t fxml4:minimal .
```

#### Option 3: Fix original requirements and build
```bash
# The original requirements.txt has been fixed
docker build -t fxml4:latest .
```

### Alternative Package Replacements

#### Instead of `boruta_py`:
Use scikit-learn's built-in feature selection:
```python
from sklearn.feature_selection import SelectKBest, RFE, RFECV
from sklearn.ensemble import RandomForestClassifier

# Recursive Feature Elimination (similar to Boruta)
rfe = RFECV(RandomForestClassifier(), step=1, cv=5)
X_selected = rfe.fit_transform(X, y)
```

#### Heavy ML Libraries (Optional):
These can be installed after deployment if needed:
```bash
# Install in running container
docker exec -it <container_name> pip install tensorflow torch transformers
```

### Docker Compose Usage

#### Start with fixed requirements:
```bash
# Update docker-compose.yml to use fixed Dockerfile
docker-compose up -d
```

#### Access services:
- **API**: http://localhost:8000
- **Dashboard**: http://localhost:8501
- **Monitoring**: http://localhost:3000

### Build Optimization Tips

#### 1. Use .dockerignore
Create `.dockerignore` to exclude large files:
```
venv/
__pycache__/
*.pyc
.git/
node_modules/
.pytest_cache/
output/
logs/
.env
```

#### 2. Layer Caching
Order Dockerfile commands from least to most frequently changing:
1. System dependencies
2. Python dependencies
3. Application code

#### 3. Multi-stage Build Benefits
- Smaller final image size
- Separated build and runtime dependencies
- Better security (no build tools in production)

### Troubleshooting

#### Build fails with package not found:
```bash
# Check if package exists
pip search <package_name>

# Use alternative package or remove from requirements
```

#### Out of memory during build:
```bash
# Increase Docker memory limit
# Or use requirements-minimal.txt for lighter build
```

#### Dependency conflicts:
```bash
# Use pip-tools to generate compatible versions
pip install pip-tools
pip-compile requirements.in
```

### Production Deployment

#### For production, consider:
1. Using `requirements-docker.txt` as base
2. Adding only needed ML packages
3. Using multi-stage builds
4. Implementing proper health checks
5. Setting resource limits

#### Example production Dockerfile modification:
```dockerfile
# Add specific production packages after base install
RUN pip install --no-cache-dir \
    anthropic \
    openai \
    langchain \
    && rm -rf /root/.cache/pip
```

### Testing the Build

#### Quick test after build:
```bash
# Test container starts
docker run --rm fxml4:latest python -c "import fxml4; print('FXML4 imports successfully')"

# Test API starts
docker run --rm -p 8000:8000 fxml4:latest python -m fxml4.api.main &
curl http://localhost:8000/api/health
```

### Summary

The Docker build issues have been resolved with:
- ✅ Fixed requirements files with problematic packages removed
- ✅ Improved Dockerfile with better error handling
- ✅ Multiple build options for different use cases
- ✅ Alternative package suggestions
- ✅ Production-ready configuration

Choose the requirements file that best fits your needs:
- **Core functionality**: `requirements-minimal.txt`
- **Docker builds**: `requirements-docker.txt`  
- **Full features**: `requirements-fixed.txt`