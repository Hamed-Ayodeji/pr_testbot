#!/bin/bash

# This script is used to clean up Docker or Docker Compose applications created for a specific branch and PR.

# Check if the script is run as root
if [[ "$(id -u)" -ne 0 ]]; then
  sudo -E "$0" "$@"
  exit
fi

# Check if the branch name is provided
if [ -z "$1" ]; then
  echo "Branch name not provided."
  exit 1
fi

# Check if the PR number is provided
if [ -z "$2" ]; then
  echo "PR number not provided."
  exit 1
fi

# Variables
BRANCH_NAME=$1
PR_NUMBER=$2
REMOTE_DIR="/tmp/pr_testbot-$BRANCH_NAME"
COMPOSE_FILE_YML="docker-compose.yml"
COMPOSE_FILE_YAML="docker-compose.yaml"

# Find and read all container info files for the given branch and PR
for CONTAINER_INFO_FILE in /tmp/container_info_${BRANCH_NAME}_${PR_NUMBER}_*.txt; do
  if [ -f "$CONTAINER_INFO_FILE" ]; then
    if [ -f "$REMOTE_DIR/$COMPOSE_FILE_YML" ] || [ -f "$REMOTE_DIR/$COMPOSE_FILE_YAML" ]; then
      echo "Found docker-compose file, using Docker Compose for cleanup..."
      # Clean up using Docker Compose
      if ! docker-compose down; then
        echo "Docker Compose down failed"
      fi
    else
      echo "No docker-compose file found, using Docker for cleanup..."
      # Read the container name and port from the file
      while read -r CONTAINER_NAME PORT; do
        if [ -n "$CONTAINER_NAME" ]; then
          echo "Stopping container $CONTAINER_NAME..."
          # Stop and remove the container
          if docker stop "$CONTAINER_NAME" && docker rm "$CONTAINER_NAME"; then
            echo "Container $CONTAINER_NAME cleaned up successfully."

            # Remove the container info file
            rm "$CONTAINER_INFO_FILE"
          else
            echo "Failed to clean up container $CONTAINER_NAME."
          fi
        else
          echo "No container found for branch $BRANCH_NAME with PR $PR_NUMBER."
        fi
      done < "$CONTAINER_INFO_FILE"
    fi
  else
    echo "No container information file found for branch $BRANCH_NAME with PR $PR_NUMBER."
  fi
done
