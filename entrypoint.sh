#!/bin/bash
set -e

if [ -d "/data/config" ]; then
  if [ -f "/data/config/config.yaml" ]; then
    cp /data/config/config.yaml /app/config.yaml
  else
    if [ -f "/app/config.yaml" ]; then
      cp /app/config.yaml /data/config/config.yaml
    fi
    echo "Warning: config.yaml not found, using default configuration."
  fi
else
  echo "Using default configuration."
fi

exec "$@"
