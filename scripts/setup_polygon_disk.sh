#!/bin/bash
# Setup script for Polygon data storage on /dev/vdb

set -e  # Exit on error

echo "Polygon.io Data Storage Setup Script"
echo "===================================="
echo ""
echo "This script will set up /dev/vdb for Polygon.io forex data storage."
echo "Requirements: sudo access"
echo ""

# Check if running as root or with sudo
if [[ $EUID -ne 0 ]]; then
   echo "This script must be run with sudo"
   echo "Usage: sudo bash setup_polygon_disk.sh"
   exit 1
fi

# Check if disk exists
if [ ! -b /dev/vdb ]; then
    echo "Error: /dev/vdb not found!"
    exit 1
fi

echo "Step 1: Checking disk status..."
fdisk -l /dev/vdb

read -p "Do you want to proceed with partitioning /dev/vdb? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Aborted."
    exit 1
fi

echo ""
echo "Step 2: Creating partition..."
# Create partition automatically
(
echo n # Add a new partition
echo p # Primary partition
echo 1 # Partition number
echo   # First sector (default)
echo   # Last sector (default)
echo w # Write changes
) | fdisk /dev/vdb

echo ""
echo "Step 3: Formatting partition as ext4..."
mkfs.ext4 /dev/vdb1

echo ""
echo "Step 4: Creating mount point..."
mkdir -p /mnt/polygon-data

echo ""
echo "Step 5: Mounting partition..."
mount /dev/vdb1 /mnt/polygon-data

echo ""
echo "Step 6: Adding to /etc/fstab for persistent mounting..."
echo "/dev/vdb1 /mnt/polygon-data ext4 defaults 0 0" >> /etc/fstab

echo ""
echo "Step 7: Setting permissions..."
# Get the user who invoked sudo
REAL_USER=${SUDO_USER:-$USER}
chown -R $REAL_USER:$REAL_USER /mnt/polygon-data

echo ""
echo "Step 8: Creating directory structure..."
sudo -u $REAL_USER mkdir -p /mnt/polygon-data/{raw/forex,processed,cache,download_logs}

echo ""
echo "Step 9: Verifying setup..."
df -h /mnt/polygon-data
ls -la /mnt/polygon-data/

echo ""
echo "✅ Setup complete!"
echo ""
echo "Storage available at: /mnt/polygon-data"
echo "Total space: $(df -h /mnt/polygon-data | tail -1 | awk '{print $2}')"
echo "Available space: $(df -h /mnt/polygon-data | tail -1 | awk '{print $4}')"
echo ""
echo "Next steps:"
echo "1. Set up Polygon.io credentials:"
echo "   export POLYGON_ACCESS_KEY='your-key'"
echo "   export POLYGON_SECRET_KEY='your-secret'"
echo "2. Run the Polygon data manager to download forex data"
