#!/bin/bash

# This script is used to deploy a Docker or Docker Compose application for a specific branch and PR.

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

# Check if the repository URL is provided
if [ -z "$3" ]; then
  echo "Repository URL not provided."
  exit 1
fi

# Variables
BRANCH_NAME=$1
PR_NUMBER=$2
REPO_URL=$3
REMOTE_HOST=$(curl -s https://api.ipify.org)
REMOTE_DIR="/tmp/pr_testbot-$BRANCH_NAME"
TIMESTAMP=$(date +%s)
CONTAINER_INFO_FILE="/tmp/container_info_${BRANCH_NAME}_${PR_NUMBER}_${TIMESTAMP}.txt"
COMPOSE_FILE_YML="docker-compose.yml"
COMPOSE_FILE_YAML="docker-compose.yaml"

# Remove existing directory if it exists to avoid conflicts
if [ -d "$REMOTE_DIR" ]; then
  rm -rf "$REMOTE_DIR"
fi

echo "Cloning the repository..."
# Clone the repository and checkout the branch
if ! git clone --branch "$BRANCH_NAME" "$REPO_URL" "$REMOTE_DIR"; then
  echo "Failed to clone the repository or checkout branch $BRANCH_NAME"
  exit 1
fi

echo "Changing directory to $REMOTE_DIR..."
# Navigate to the project directory
if ! cd "$REMOTE_DIR"; then
  echo "Failed to change directory to $REMOTE_DIR"
  exit 1
fi

if [ -f "$COMPOSE_FILE_YML" ] || [ -f "$COMPOSE_FILE_YAML" ]; then
  echo "Found docker-compose file, using Docker Compose for deployment..."
  # Deploy using Docker Compose
  if ! docker-compose up -d; then
    echo "Docker Compose up failed"
    exit 1
  fi

  # Extracting services and ports from docker-compose
  SERVICES=$(docker-compose config --services)
  for SERVICE in $SERVICES; do
    PORT=$(docker-compose port $SERVICE 80 | awk -F: '{print $2}')
    echo "Service $SERVICE running on port $PORT"
    echo "Deployment complete: http://$REMOTE_HOST:$PORT"
  done
else
  echo "No docker-compose file found, using Docker for deployment..."
  # Function to find a random available port in the range 4000-7000
  find_random_port() {
      while true; do
          # Generate a random port between 4000 and 7000
          PORT=$((4000 + RANDOM % 3001))

          # Check if the port is available
          if ! lsof -i:$PORT >/dev/null; then
              break
          fi
      done
      echo $PORT
  }

  # Get an available random port
  PORT=$(find_random_port)

  # Unique container name based on branch, port, and PR number
  CONTAINER_NAME="container_${BRANCH_NAME}_${PR_NUMBER}_${PORT}"

  # Build the Docker image with a unique tag
  if ! docker build -t $CONTAINER_NAME .; then
    echo "Docker build failed"
    exit 1
  fi

  echo "Running Docker container $CONTAINER_NAME on port $PORT..."
  # Run the Docker container with the random port and unique container name
  if ! docker run -d -p $PORT:80 --name $CONTAINER_NAME $CONTAINER_NAME; then
    echo "Docker run failed"
    exit 1
  fi

  # Save container name and port information to a file for cleanup
  echo "$CONTAINER_NAME $PORT" > $CONTAINER_INFO_FILE

  # Output the container name and deployment link
  echo "Container name: $CONTAINER_NAME"
  echo "Deployment complete: http://$REMOTE_HOST:$PORT"
fi
