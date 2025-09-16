#!/bin/bash
# Run a command in the development container

if [ $# -eq 0 ]; then
    echo "Usage: $0 <command>"
    exit 1
fi

docker compose -f docker-compose.dev.yml exec dev $@
