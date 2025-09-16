#!/bin/bash
# Script to download and install the latest TWS API client for IB

# Define variables
DOWNLOAD_DIR="/tmp/ibapi_download"
INSTALL_DIR="/Users/cnross/code/fxml4/ibapi_source"
API_VERSION="10.19.01" # Update this to the latest version when available
API_ZIP_FILE="twsapi_macunix.${API_VERSION}.zip"
API_DOWNLOAD_URL="https://download2.interactivebrokers.com/twsapi/twsapi_macunix.${API_VERSION}.zip"

echo "=== Interactive Brokers TWS API Installation ==="
echo "This script will download and install the latest IB TWS API client."
echo "API Version: ${API_VERSION}"
echo "Download URL: ${API_DOWNLOAD_URL}"
echo "Target directory: ${INSTALL_DIR}"
echo

# Create directories
mkdir -p "$DOWNLOAD_DIR"
mkdir -p "$INSTALL_DIR"

# Download the TWS API
echo "Downloading TWS API..."
curl -L -o "${DOWNLOAD_DIR}/${API_ZIP_FILE}" "${API_DOWNLOAD_URL}"

if [ $? -ne 0 ]; then
    echo "Error: Failed to download TWS API. Please check the URL or your internet connection."
    exit 1
fi

# Extract the ZIP file
echo "Extracting API files..."
unzip -q -o "${DOWNLOAD_DIR}/${API_ZIP_FILE}" -d "${DOWNLOAD_DIR}"

if [ $? -ne 0 ]; then
    echo "Error: Failed to extract the ZIP file."
    exit 1
fi

# Copy the API files to the installation directory
echo "Copying API files to ${INSTALL_DIR}..."
cp -R "${DOWNLOAD_DIR}/IBJts/source/"* "${INSTALL_DIR}/"

# Install the Python client
echo "Installing Python client..."
cd "${INSTALL_DIR}/pythonclient"
python setup.py install

if [ $? -ne 0 ]; then
    echo "Error: Failed to install the Python client."
    exit 1
fi

# Clean up
echo "Cleaning up temporary files..."
rm -rf "$DOWNLOAD_DIR"

# Display post-installation instructions
echo
echo "=== Installation Complete ==="
echo "The TWS API has been installed successfully."
echo
echo "Next steps:"
echo "1. Make sure TWS or IB Gateway is running"
echo "2. Configure TWS: Edit -> Global Configuration -> API -> Settings"
echo "   - Enable ActiveX and Socket Clients"
echo "   - Set socket port (7496 for live, 7497 for paper trading)"
echo "3. Test the connection with the test_ib_connection.py script"
echo
echo "Example test command:"
echo "python scripts/test_ib_connection.py --port 7496 --skip-market-data"
echo
