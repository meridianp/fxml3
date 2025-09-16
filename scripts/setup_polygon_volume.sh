#!/bin/bash
# Setup script for polygon data volume

set -e

echo "Setting up /dev/vdb as polygon data volume..."

# Create partition table and partition
echo "Creating partition..."
sudo parted -s /dev/vdb mklabel gpt
sudo parted -s /dev/vdb mkpart primary ext4 0% 100%

# Wait for partition to be created
sleep 2

# Format the partition
echo "Formatting partition as ext4..."
sudo mkfs.ext4 -F /dev/vdb1

# Create mount point
echo "Creating mount point /polygon..."
sudo mkdir -p /polygon

# Mount the partition
echo "Mounting partition..."
sudo mount /dev/vdb1 /polygon

# Add to fstab for persistent mounting
echo "Adding to /etc/fstab..."
echo "/dev/vdb1 /polygon ext4 defaults 0 0" | sudo tee -a /etc/fstab

# Set permissions
echo "Setting permissions..."
sudo chown -R $USER:$USER /polygon

# Create directory structure
echo "Creating directory structure..."
mkdir -p /polygon/{raw,processed,cache,logs}

# Show results
echo ""
echo "✅ Volume mounted successfully!"
df -h /polygon
ls -la /polygon/

echo ""
echo "Polygon data volume is ready at: /polygon"
