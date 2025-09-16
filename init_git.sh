#!/bin/bash
# Initialize git repository for FXML4

# Check if git is installed
if ! command -v git &> /dev/null; then
    echo "Error: git is not installed. Please install git and try again."
    exit 1
fi

# Check if we're in the right directory
if [ ! -f "README.md" ] || [ ! -d "fxml4" ]; then
    echo "Error: Please run this script from the FXML4 project root directory."
    exit 1
fi

# Initialize git repository if not already initialized
if [ ! -d ".git" ]; then
    echo "Initializing git repository..."
    git init
else
    echo "Git repository already initialized."
fi

# Create .gitignore file
cat > .gitignore << EOL
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg
MANIFEST

# Virtual Environment
venv/
env/
ENV/

# Environment variables
.env

# IDE files
.idea/
.vscode/
*.swp
*.swo
.DS_Store

# Jupyter Notebook
.ipynb_checkpoints

# Log files
logs/
*.log

# Data files
data/
*.parquet
*.csv
*.xlsx
*.pkl

# Docker
.dockerignore

# Credentials
credentials/
*_key.json
*_credentials.json

# Temporary files
tmp/
temp/

# Model files
*.h5
*.joblib
*.pickle
*.pkl
EOL

echo "Created .gitignore file."

# Add all files
git add .

# Create initial commit
git commit -m "Initial commit for FXML4
- Merged core structure from FXML2 and FXML3
- Created unified configuration system
- Set up base components for integrated trading system

🤖 Generated with [Claude Code](https://claude.ai/code)
Co-Authored-By: Claude <noreply@anthropic.com>"

# Create develop branch
git branch develop
git checkout develop

echo "Git repository initialized with main and develop branches."
echo "You are now on the 'develop' branch."
echo ""
echo "Next steps:"
echo "1. Create a remote repository on GitHub/GitLab/etc."
echo "2. Add the remote: git remote add origin <repository-url>"
echo "3. Push to remote: git push -u origin main develop"
echo ""
echo "Happy coding!"
