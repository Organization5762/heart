#!/bin/bash

# Configuration
SOURCE_DIR="/Users/sebastien/source/heart"
REMOTE_HOST="michael@totem3.local"
REMOTE_DIR="~/Desktop/"
REMOTE_PASS="totemlib2024"
IGNORE_LIST="__pycache__ *.pyc .DS_Store"

# Generate exclusion parameters
EXCLUSIONS=""
for item in $IGNORE_LIST; do
  EXCLUSIONS="$EXCLUSIONS --exclude=$item"
done

# Function to sync changes
sync_changes() {
  echo "$(date): Changes detected, syncing..."
  sshpass -p "$REMOTE_PASS" rsync -a --delete $EXCLUSIONS -e "ssh -o StrictHostKeyChecking=no" "$SOURCE_DIR" "$REMOTE_HOST:$REMOTE_DIR"
  echo "$(date): Sync complete"
}

# Initial sync
echo "Performing initial sync..."
sync_changes
echo "Initial sync complete. Watching for changes..."

# Watch for changes and sync
fswatch -o -r "$SOURCE_DIR" | while read f; do
  sync_changes
done 