# PR_TESTBOT

## Introduction

In modern software development, pull requests are essential for maintaining code quality and facilitating collaboration. They allow developers to submit changes for review before merging into the main codebase, ensuring that new contributions are vetted for potential issues.

However, managing pull requests can be challenging due to:

1. **Manual Testing**: Testing every pull request manually is time-consuming and prone to errors.
2. **Delayed Feedback**: Waiting for human reviewers to provide feedback can slow down the integration process.
3. **Inconsistent Deployment**: Variations in testing environments can lead to inconsistencies.
4. **Resource Management**: Overlooking the cleanup of testing resources can waste resources and cause conflicts.

Introducing **PR_TestBot**, an automated solution to streamline the pull request testing process. PR_TestBot triggers upon the creation, update, or reopening of a pull request, deploying Docker or Docker Compose applications in a containerized environment for testing. It provides real-time feedback and notifications at each step, ensuring stakeholders are informed. Additionally, it performs automated cleanups when pull requests are closed, managing resources efficiently.

### Key Features of PR_TestBot

- **Automated Deployment**: Instantly deploys Docker or Docker Compose applications from pull requests in a consistent, isolated environment.
- **Real-time Notifications**: Keeps stakeholders informed about the deployment status through pull request comments.
- **Resource Cleanup**: Automatically cleans up containers and resources upon pull request closure.
- **Detailed Logging**: Sends detailed deployment logs via email to designated recipients.

PR_TestBot enhances productivity, ensures faster feedback, and maintains a clean development environment, improving the overall quality and reliability of the software.

## The `pr_testbot` Application `main.py`

The `main.py` script is the core of the `pr_testbot` application. It is a Flask-based web application that listens to GitHub webhook events and triggers deployments or cleanups based on the pull request actions.

### Key Features

- **Webhook Listener**: Listens to GitHub webhook events and verifies their signatures.
- **Authentication**: Uses JWT for GitHub App authentication and fetches installation access tokens.
- **Deployment Trigger**: Triggers the deployment script for pull request actions (opened, synchronized, reopened).
- **Cleanup Trigger**: Triggers the cleanup script when a pull request is closed.
- **Notifications**: Sends notifications to stakeholders via GitHub comments and emails detailed logs.
- **Error Handling and Logging**: Provides comprehensive error handling and logging for debugging and reliability.

### Code Overview

   ```python
   from flask import Flask, request, jsonify
   import subprocess
   import requests
   import re
   import jwt
   import time
   import os
   import hmac
   import hashlib
   import logging
   from cryptography.hazmat.primitives import serialization
   from cryptography.hazmat.backends import default_backend
   from dotenv import load_dotenv
   import smtplib
   from email.mime.multipart import MIMEMultipart
   from email.mime.text import MIMEText
   from email.mime.base import MIMEBase
   from email import encoders

   # Load environment variables from .env file
   load_dotenv()

   app = Flask(__name__)

   # Configure logging
   logging.basicConfig(level=logging.INFO)
   logger = logging.getLogger(__name__)

   # Load configuration from environment variables
   WEBHOOK_SECRET = os.getenv('WEBHOOK_SECRET')
   APP_ID = os.getenv('APP_ID')
   PRIVATE_KEY_PATH = os.getenv('PRIVATE_KEY_PATH')
   SMTP_SERVER = os.getenv('SMTP_SERVER')
   SMTP_PORT = os.getenv('SMTP_PORT')
   SMTP_USERNAME = os.getenv('SMTP_USERNAME')
   SMTP_PASSWORD = os.getenv('SMTP_PASSWORD')
   RECIPIENT_EMAIL = os.getenv('RECIPIENT_EMAIL')

   # Load the private key
   with open(PRIVATE_KEY_PATH, 'r') as key_file:
      private_key = serialization.load_pem_private_key(
         key_file.read().encode(),
         password=None,
         backend=default_backend()
      )

   def verify_signature(payload, signature):
      """Verify GitHub webhook signature."""
      if not signature:
         return False
      mac = hmac.new(WEBHOOK_SECRET.encode(), msg=payload, digestmod=hashlib.sha256)
      return hmac.compare_digest('sha256=' + mac.hexdigest(), signature)

   def get_jwt_token():
      """Create a JWT token for GitHub App authentication."""
      current_time = int(time.time())
      payload = {
         'iat': current_time,
         'exp': current_time + (10 * 60),  # 10 minute expiration
         'iss': APP_ID
      }
      jwt_token = jwt.encode(payload, private_key, algorithm='RS256')
      return jwt_token

   def get_installation_access_token(installation_id):
      """Get the installation access token."""
      jwt_token = get_jwt_token()
      headers = {
         'Authorization': f'Bearer {jwt_token}',
         'Accept': 'application/vnd.github.v3+json'
      }
      response = requests.post(
         f'https://api.github.com/app/installations/{installation_id}/access_tokens',
         headers=headers
      )
      response.raise_for_status()
      return response.json()['token']

   @app.route('/webhook', methods=['POST'])
   def webhook():
      # Verify payload signature
      signature = request.headers.get('X-Hub-Signature-256')
      if not verify_signature(request.data, signature):
         return jsonify({'message': 'Invalid signature'}), 401

      data = request.json
      action = data.get('action')
      if 'pull_request' in data:
         pr_number = data['pull_request']['number']
         repo_name = data['repository']['full_name']
         repo_url = data['pull_request']['head']['repo']['clone_url']
         branch_name = data['pull_request']['head']['ref']
         installation_id = data['installation']['id']
         comment_url = f"https://api.github.com/repos/{repo_name}/issues/{pr_number}/comments"
         access_token = None

         logger.info(f"Received webhook for PR #{pr_number} on branch '{branch_name}'")

         if action in ['opened', 'synchronize', 'reopened']:
               try:
                  # Get installation access token
                  access_token = get_installation_access_token(installation_id)

                  # Notify stakeholders (comment on the PR)
                  notify_stakeholders(comment_url, "Deployment started for this pull request.", access_token)

                  # Run the deployment script with the branch name, PR number, and repository URL
                  container_name, deployment_link, log_file_path = run_deployment_script(branch_name, pr_number, repo_url, comment_url, access_token)

                  # Notify stakeholders with the result
                  if deployment_link:
                     deployment_message = f"Deployment successful. [Deployed application]({deployment_link})."
                  else:
                     deployment_message = "Deployment failed. Please check the logs."
                  notify_stakeholders(comment_url, deployment_message, access_token)

                  # Send deployment log via email
                  send_email(RECIPIENT_EMAIL, 'Deployment Log', 'Please find the attached deployment log.', log_file_path)

                  return jsonify({'message': 'Deployment processed'}), 200
               except Exception as e:
                  logger.error(f"Deployment failed: {e}")
                  if access_token:
                     notify_stakeholders(comment_url, f"Deployment failed: {e}", access_token)
                  return jsonify({'message': 'Deployment failed'}), 500

         elif action == 'closed':
               try:
                  # Get installation access token
                  access_token = get_installation_access_token(installation_id)

                  # Pull request closed, trigger cleanup regardless of merge status
                  log_file_path = run_cleanup_script(branch_name, pr_number, comment_url, access_token)
                  
                  # Notify stakeholders about the cleanup
                  notify_stakeholders(comment_url, "Cleanup completed for this pull request.", access_token)

                  # Send cleanup log via email
                  send_email(RECIPIENT_EMAIL, 'Cleanup Log', 'Please find the attached cleanup log.', log_file_path)

                  return jsonify({'message': 'Cleanup processed'}), 200
               except Exception as e:
                  logger.error(f"Cleanup failed: {e}")
                  if access_token:
                     notify_stakeholders(comment_url, f"Cleanup failed: {e}", access_token)
                  return jsonify({'message': 'Cleanup failed'}), 500

      return jsonify({'message': 'No action taken'}), 200

   def notify_stakeholders(comment_url, message, access_token, details=None):
      headers = {
         'Authorization': f'token {access_token}',
         'Accept': 'application/vnd.github.v3+json'
      }
      if details:
         table = "| Step | Status | Details |\n|------|--------|---------|\n"
         for step, detail in details.items():
               table += f"| {step} | {detail['status']} | {detail['message']} |\n"
         message += f"\n\n{table}"
      data = {'body': message}
      response = requests.post(comment_url, headers=headers, json=data)
      if response.status_code != 201:
         logger.error(f"Failed to comment on PR: {response.json()}")

   def run_deployment_script(branch_name, pr_number, repo_url, comment_url, access_token):
      log_file_path = f'/tmp/deployment_log_{branch_name}_{pr_number}.txt'
      details = {}
      with open(log_file_path, 'w') as log_file:
         try:
               result = subprocess.run(['./deploy.sh', branch_name, str(pr_number), repo_url], check=True, capture_output=True, text=True)
               log_file.write(result.stdout)
               logger.info(result.stdout)

               # Extract container name and deployment URL from the output
               container_name_match = re.search(r'Container name: ([^\s]+)', result.stdout)
               deployment_url_match = re.search(r'Deployment complete: (http://[^\s]+)', result.stdout)
               container_name = container_name_match.group(1) if container_name_match else None
               deployment_url = deployment_url_match.group(1) if deployment_url_match else None

               details['Clone repository'] = {'status': 'Success', 'message': 'Repository cloned successfully.'}
               details['Checkout branch'] = {'status': 'Success', 'message': f'Checked out branch {branch_name}.'}
               details['Pull latest changes'] = {'status': 'Success', 'message': f'Pulled latest changes for branch {branch_name}.'}
               details['Build Docker image'] = {'status': 'Success', 'message': f'Docker image built successfully for container {container_name}.'}
               details['Run Docker container'] = {'status': 'Success', 'message': f'Container {container_name} running at {deployment_url}.'}

               notify_stakeholders(comment_url, "Deployment process details:", access_token, details)
               return container_name, deployment_url, log_file_path

         except subprocess.CalledProcessError as e:
               log_file.write(f"Deployment script failed with error: {e.stderr}")
               logger.error(f"Deployment script failed with error: {e.stderr}")
               details['Deployment script'] = {'status': 'Failed', 'message': e.stderr}
               notify_stakeholders(comment_url, "Deployment process details:", access_token, details)
               return None, None, log_file_path

   def run_cleanup_script(branch_name, pr_number, comment_url, access_token):
      log_file_path = f'/tmp/cleanup_log_{branch_name}_{

   pr_number}.txt'
      details = {}
      with open(log_file_path, 'w') as log_file:
         try:
               subprocess.run(['./cleanup.sh', branch_name, str(pr_number)], check=True, stdout=log_file, stderr=log_file)
               logger.info("Cleanup script executed successfully.")
               details['Cleanup script'] = {'status': 'Success', 'message': 'Cleanup script executed successfully.'}
               notify_stakeholders(comment_url, "Cleanup process details:", access_token, details)
               return log_file_path
         except subprocess.CalledProcessError as e:
               log_file.write(f"Cleanup script failed with error: {e.stderr}")
               logger.error(f"Cleanup script failed with error: {e.stderr}")
               details['Cleanup script'] = {'status': 'Failed', 'message': e.stderr}
               notify_stakeholders(comment_url, "Cleanup process details:", access_token, details)
               return log_file_path

   def send_email(to_address, subject, body, attachment_path, retries=3, retry_delay=5):
      from_address = SMTP_USERNAME
      msg = MIMEMultipart()
      msg['From'] = from_address
      msg['To'] = to_address
      msg['Subject'] = subject

      msg.attach(MIMEText(body, 'plain'))

      try:
         with open(attachment_path, 'rb') as attachment:
               part = MIMEBase('application', 'octet-stream')
               part.set_payload(attachment.read())
               encoders.encode_base64(part)
               part.add_header('Content-Disposition', f'attachment; filename= {os.path.basename(attachment_path)}')
               msg.attach(part)
      except Exception as e:
         logger.error(f"Failed to attach file: {e}")
         return False

      attempt = 0
      while attempt < retries:
         try:
               with smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=10) as server:
                  server.starttls()
                  server.login(from_address, SMTP_PASSWORD)
                  server.sendmail(from_address, to_address, msg.as_string())
                  logger.info("Email sent successfully")
                  return True
         except (smtplib.SMTPException, ConnectionError) as e:
               attempt += 1
               logger.error(f"Failed to send email, attempt {attempt} of {retries}: {e}")
               time.sleep(retry_delay)

      logger.error("All attempts to send email failed")
      return False

   if __name__ == '__main__':
      app.run(host='0.0.0.0', port=5000)
   ```

## The Deployment Script `deploy.sh`

The `deploy.sh` script handles the deployment process for the PR_TestBot. It clones the repository, checks out the specific branch, and deploys the application using Docker or Docker Compose.

### Key Features

- **Repository Cloning**: Clones the repository and checks out the specific branch.
- **Deployment**: Detects if a Docker Compose file is present and uses Docker Compose for deployment, otherwise uses Docker.
- **Port Allocation**: Allocates a random available port for the Docker container if Docker Compose is not used.
- **Output**: Outputs the deployment link for the deployed application.

### Code Overview

   ```bash
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
   ```

## The Cleanup Script `cleanup.sh`

The `cleanup.sh` script handles the cleanup process for the PR_TestBot. It stops and removes Docker containers or Docker Compose services created during deployment.

### Key Features

- **Service Detection**: Detects if Docker Compose services are used and stops them accordingly.
- **Container Cleanup**: Stops and removes individual Docker containers if Docker Compose is not used.
- **Logging**: Provides feedback on the cleanup process for each container or service.

### Code Overview

   ```bash
   #!/bin/bash

   # This script is used to clean up the Docker containers created for a specific branch and PR.

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

   # Stop and remove Docker Compose services if docker-compose file exists
   if [ -f "$REMOTE_DIR/docker-compose.yml" ] || [ -f "$REMOTE_DIR/docker-compose.yaml" ]; then
   echo "Found docker-compose file, stopping Docker Compose services..."
   docker-compose -f "$REMOTE_DIR/docker-compose.yml" down || docker-compose -f "$REMOTE_DIR/docker-compose.yaml" down
   else
   # Find and read all container info files for the given branch and PR
   for CONTAINER_INFO_FILE in /tmp/container_info_${BRANCH_NAME}_${PR_NUMBER}_*.txt; do
      if [ -f "$CONTAINER_INFO_FILE" ]; then
         # Read the container name and port from the file
         while read -r CONTAINER_NAME PORT; do
         if [ -n "$CONTAINER_NAME" ]; then
            # Stop and remove the container
            docker stop "$CONTAINER_NAME"
            docker rm "$CONTAINER_NAME"
            echo "Container $CONTAINER_NAME cleaned up successfully."

            # Remove the container info file
            rm "$CONTAINER_INFO_FILE"
         

   else
            echo "No container found for branch $BRANCH_NAME with PR $PR_NUMBER."
         fi
         done < "$CONTAINER_INFO_FILE"
      else
         echo "No container information file found for branch $BRANCH_NAME with PR $PR_NUMBER."
      fi
   done
   fi
   ```

## Prerequisites

1. **Server**: A running server (e.g., AWS EC2, DigitalOcean Droplet, or any other cloud provider) with Ubuntu.

2. **GitHub Repository**: A repository with Docker or Docker Compose configuration.

3. **Security Group/Firewall**:
   - Open ports 22 (SSH).
   - Open port 5000 (Flask).
   - Open ports 4000-7000 (for Docker container deployment).

4. **SSH Key Pair**: Access to the server via SSH.

5. **Software on the Server**:
   - Docker
   - Docker Compose
   - Python 3 and pip
   - snapd
   - screen
   - ngrok

6. **Environment Variables**:
   - `WEBHOOK_SECRET`
   - `APP_ID`
   - `PRIVATE_KEY_PATH`
   - `SMTP_SERVER`
   - `SMTP_PORT`
   - `SMTP_USERNAME`
   - `SMTP_PASSWORD`
   - `RECIPIENT_EMAIL`

7. **ngrok Authtoken**: An ngrok account with an authtoken.

## Setting up the Test Server

1. **Launch an AWS EC2 Instance**:
   - Select **t2.micro** instance type with an Ubuntu AMI.

2. **Configure Security Group**:
   - Open ports **22** (SSH), **5000** (Flask), and any other necessary ports.

3. **Connect to the Instance**:

   ```sh
   ssh -i /path/to/your-key.pem ubuntu@your-ec2-instance-public-dns
   ```

4. **Install Required Software**:

   ```sh
   sudo apt update
   sudo apt install docker.io docker-compose python3 python3-pip snapd screen
   sudo snap install ngrok
   ```

5. **Set Up Docker and Docker Compose**:
   - Enable and start Docker:

   ```sh
   sudo systemctl enable docker
   sudo systemctl start docker
   sudo usermod -aG docker $USER
   newgrp docker
   ```

6. **Set Up ngrok**:

   ```sh
   ngrok authtoken your-ngrok-authtoken
   ```

7. **Clone Your Repository**:

   ```sh
   git clone https://github.com/your-username/your-repo.git
   cd your-repo
   ```

8. **Set Up Environment Variables**:
   - Create a `.env` file with the necessary variables.

9. **Install Python Dependencies**:

   ```sh
   pip3 install -r requirements.txt
   ```

10. **Run Flask App and ngrok in Screen Sessions**:

    ```sh
    screen -S flask
    python3 main.py
    # Press Ctrl+A, then D to detach

    screen -S ngrok
    ngrok http 5000
    # Press Ctrl+A, then D to detach
    ```

Your test server is now ready to deploy and test pull requests using PR_TestBot.

## Detailed Steps to Install PR_TestBot on GitHub

### Step 1: Create a GitHub App

1. **Go to GitHub Settings**:
   - Navigate to your GitHub account settings by clicking on your profile picture in the top-right corner and selecting "Settings".

2. **Developer Settings**:
   - In the left-hand sidebar, scroll down and click on "Developer settings".

3. **GitHub Apps**:
   - Click on "GitHub Apps" in the left sidebar.

4. **Create a New GitHub App**:
   - Click the "New GitHub App" button.

5. **Configure the GitHub App**:
   - **App name**: Enter a name for your app (e.g., `PR_TestBot`).
   - **Homepage URL**: Enter your homepage URL or the URL of your repository.
   - **Webhook URL**: Set this to your ngrok URL (e.g., `http://your-ngrok-url.ngrok.io/webhook`).
   - **Webhook Secret**: Enter a secret key (make note of this for later).
   - **Repository Permissions**:
     - **Contents**: Read-only
     - **Issues**: Read & write
     - **Pull requests**: Read & write
     - **Commit statuses**: Read & write
   - **Subscribe to Events**:
     - Check the box for "Pull request".
   - **Where can this GitHub App be installed?**: Choose "Any account".

6. **Create GitHub App**:
   - Click the "Create GitHub App" button.

7. **Generate a Private Key**:
   - After creating the app, generate a private key and save the `.pem` file. This will be used for authentication.

### Step 2: Install the GitHub App on Your Repository

1. **Install GitHub App**:
   - After creating the app, you will see an option to install it. Click on the "Install App" button.

2. **Select Repository**:
   - Choose "Only select repositories" and select the repository where you want to install the app (e.g., `your-repo-name`).

3. **Complete Installation**:
   - Click the "Install" button to complete the installation.

### Step 3: Set Up the Server

Follow the instructions in the "Setting up the Test Server" section of your documentation to prepare the server.

### Step 4: Clone the Repository

1. **Clone Your Repository**:

   ```sh
   git clone https://github.com/Hamed-Ayodeji/pr_testbot.git
   cd pr_testbot
   ```

2. **Set Up Environment Variables**:
   - Create a `.env` file in the project directory with the following content:

     ```plaintext
     WEBHOOK_SECRET=your_webhook_secret
     APP_ID=your_github_app_id
     PRIVATE_KEY_PATH=/path/to/your/private-key.pem
     SMTP_SERVER=smtp.your-email-provider.com
     SMTP_PORT=587
     SMTP_USERNAME=your_smtp_username
     SMTP_PASSWORD=your_smtp_password
     RECIPIENT_EMAIL=recipient@example.com
     ```

### Step 5: Set Up and Activate a Virtual Environment

1. **Install `virtualenv`**:

   ```sh
   sudo apt install python3-virtualenv
   ```

2. **Create a Virtual Environment**:

   ```sh
   virtualenv venv
   ```

3. **Activate the Virtual Environment**:

   ```sh
   source venv/bin/activate
   ```

4. **Install Python Dependencies**:

   ```sh
   pip install -r requirements.txt
   ```

### Step 6: Run the Flask App and ngrok

1. **Start the Flask Application in a Screen Session**:

   ```sh
   screen -S flask
   source venv/bin/activate
   python3 main.py
   # Press Ctrl+A, then D to detach
   ```

2. **Start ngrok in a Screen Session**:

   ```sh
   screen -S ngrok
   ngrok http 5000
   # Press Ctrl+A, then D to detach
   ```

3. **Copy the ngrok URL**:
   - After starting ngrok, copy the generated URL (e.g., `http://your-ngrok-url.ngrok.io`).

### Step 7: Update GitHub App Webhook URL

1. **Update Webhook URL**:
   - Go back to the GitHub Developer settings and navigate to your GitHub App settings.
   - Update the "Webhook URL" with your ngrok URL followed by `/webhook` (e.g., `http://your-ngrok-url.ngrok.io/webhook`).

### Step 8: Test PR_TestBot

1. **Create a Pull Request**:
   - Make a change in a branch of your repository and create a pull request to trigger the bot.

2. **Monitor the Deployment**:
   - The bot should automatically deploy the code, notify stakeholders, and provide detailed status updates.

By following these steps, you will have PR_TestBot installed on GitHub, with the ability to deploy Docker or Docker Compose applications, provide notifications, and manage resources efficiently.

## A Simple Demonstration of the `pr_testbot` in Action with Screenshots, Using the `pr_testbot_test` Repository

### Step 1: Cloning the Repository and Creating a Pull Request

1. **Clone the Repository**: Clone the `pr_testbot_test` repository to your local machine.

   ```bash
   git clone https://github.com/Hamed-Ayodeji/pr_testbot_test.git
   cd pr_testbot_test
   ```

2. **Create a New Branch**: Create and switch to a new branch to make your changes.

   ```bash
   git checkout -b feature-test
   ```

3. **Make Changes**: Make some changes to the code. For example, update the README file.

4. **Commit and Push Changes**: Commit and push your changes to GitHub.

   ```bash
   git add .
   git commit -m "Test changes for pr_testbot"
   git push origin feature-test
   ```

5. **Open a Pull Request**: Open a pull request from the `feature-test` branch to the `main` branch.
   - Go to the repository on GitHub.
   - Click the "Compare & pull request" button.
   - Provide a title and description for your pull request and click "Create pull request".

### Step 2: Deployment Triggered by Pull Request

Once the pull request is created, the `pr_testbot` is triggered and starts the deployment process.

1. **Webhook Received**: The `pr_testbot` receives the webhook event for the new pull request.
   - ![Webhook Received](./.img/1.png)

2. **Deployment Started**: The bot posts a comment on the pull request indicating that the deployment has started.
   - ![Deployment Started](./.img/2.png)

3. **Deployment Log**: The bot performs the deployment, clones the repository, checks out the branch, and deploys the application.
   - ![Deployment Log](./.img/4.png)

4. **Deployment Success**: Once the deployment is successful, the bot posts another comment with the deployment link.
   - ![Deployment Success](./.img/3.png)

### Step 3: Receiving Deployment Logs via Email

After the deployment, the bot sends detailed logs of the deployment process via email to the configured recipient. The email contains the following information:

- **Repository URL**: The URL of the repository from which the branch was cloned.
- **Branch Name**: The name of the branch that was deployed.
- **Deployment Steps**: Detailed steps of the deployment process including cloning, checking out the branch, building the Docker image, and running the container.
- **Deployment Status**: The status of each step, indicating success or failure.
- **Deployment URL**: The URL of the deployed application if the deployment was successful.

**Example Email with Deployment Logs**:

- ![Deployment Email](./.img/5.png)

### Step 4: Closing the Pull Request

1. **Merge or Close the Pull Request**: Once the changes are reviewed, the pull request can be merged or closed.

2. **Cleanup Triggered**: When the pull request is closed, the `pr_testbot` triggers the cleanup process.
   - ![Cleanup Triggered](./.img/6.png)

3. **Cleanup Log**: The bot performs the cleanup, stopping and removing Docker containers or Docker Compose services.
   - ![Cleanup Log](./.img/8.png)

4. **Cleanup Success**: The bot posts a final comment indicating that the cleanup has been completed successfully.
   - ![Cleanup Success](./.img/7.png)

### Step 5: Receiving Cleanup Logs via Email

Similar to the deployment logs, the bot also sends detailed logs of the cleanup process via email to the configured recipient. The email contains the following information:

- **Repository URL**: The URL of the repository from which the branch was cloned.
- **Branch Name**: The name of the branch that was cleaned up.
- **Cleanup Steps**: Detailed steps of the cleanup process including stopping and removing Docker containers or Docker Compose services.
- **Cleanup Status**: The status of each step, indicating success or failure.

**Example Email with Cleanup Logs**:

- ![Cleanup Email](./.img/9.png)

This demonstration shows how the `pr_testbot` automates the deployment and cleanup processes for pull requests, ensuring that applications are tested in a consistent environment and resources are cleaned up after use. The detailed comments and logs provided by the bot help stakeholders track the status of deployments and cleanups effectively.

### Other Ways to Test

**Forking the Repository**:

1. **Fork the Repository**: Fork the `pr_testbot_test` repository to your GitHub account.
   - Navigate to the repository URL: `https://github.com/Hamed-Ayodeji/pr_testbot_test`.
   - Click on the "Fork" button in the top-right corner of the page.

2. **Clone the Forked Repository**: Clone the forked repository to your local machine.

   ```bash
   git clone https://github.com/YOUR-USERNAME/pr_testbot_test.git
   cd pr_testbot_test
   ```

3. **Follow Steps 2-5**: Create a new branch, make changes, commit, push, and open a pull request following the same steps as described above.

**Creating a Pull Request from a Different Branch**:

1. **Clone the Repository**: Clone the repository to your local machine.

   ```bash
   git clone https://github.com/Hamed-Ayodeji/pr_testbot_test.git
   cd pr_testbot_test
   ```

2. **Create a New Branch**: Create and switch to a new branch to make your changes.

   ```bash
   git checkout -b new-feature-branch
   ```

3. **Make Changes**: Make some changes to the code.

4. **Commit and Push Changes**: Commit and push your changes to GitHub.

   ```bash
   git add .
   git commit -m "New feature branch changes"
   git push origin new-feature-branch
   ```

5. **Open a Pull Request**: Open a pull request from the `new-feature-branch` to the `main` branch on GitHub.

These methods provide flexibility in testing the `pr_testbot` with various scenarios, ensuring it functions correctly across different use cases.

### Security Considerations

When implementing and using the `pr_testbot`, it is crucial to keep security at the forefront. Here are some key security considerations:

1. **Webhook Security**:
   - **Signature Verification**: Ensure that all incoming webhooks from GitHub are verified using the provided signature to prevent unauthorized access.
   - **Secret Management**: Store webhook secrets securely and avoid hardcoding them in your scripts.

2. **Environment Variables**:
   - **Secure Storage**: Use secure methods to store environment variables such as AWS Secrets Manager, HashiCorp Vault, or similar services.
   - **Access Control**: Limit access to environment variables to only those processes and users that absolutely need them.

3. **Authentication Tokens**:
   - **Short-lived Tokens**: Use short-lived tokens for authentication wherever possible and rotate them regularly.
   - **Encryption**: Ensure that all tokens and sensitive data are encrypted both in transit and at rest.

4. **Server Security**:
   - **Firewall Rules**: Configure firewall rules to allow only necessary traffic to and from your server.
   - **Regular Updates**: Keep your server and all dependencies updated with the latest security patches.

5. **Docker Security**:
   - **Image Vulnerabilities**: Regularly scan your Docker images for vulnerabilities using tools like Docker Bench for Security or Clair.
   - **Least Privilege**: Run containers with the least privilege necessary and avoid running containers as root.

### Future Plans for the `pr_testbot`

The current implementation of `pr_testbot` focuses on deploying Docker applications. Future plans for the `pr_testbot` include extending its capabilities to support a variety of deployment tools and environments. Here are some future enhancements:

1. **Terraform**:
   - Integrate Terraform to provision and manage infrastructure as code.
   - Allow deployment scripts to apply Terraform configurations and manage cloud resources dynamically.

2. **Ansible**:
   - Add support for Ansible to automate IT tasks such as configuration management, application deployment, and orchestration.
   - Enable the deployment script to run Ansible playbooks for setting up and managing environments.

3. **Kubernetes**:
   - Support for deploying applications to Kubernetes clusters.
   - Enable the deployment script to apply Kubernetes manifests and manage Kubernetes resources.

4. **CI/CD Integration**:
   - Integrate with popular CI/CD tools like Jenkins, CircleCI, or GitHub Actions to automate the entire deployment pipeline.
   - Provide feedback and status updates directly within these CI/CD platforms.

5. **Extensible Plugin System**:
   - Develop a plugin system that allows users to easily add support for other deployment tools and technologies.
   - Enable community contributions to extend the capabilities of the `pr_testbot`.

### Summary

The `pr_testbot` is a powerful automation tool designed to streamline the deployment and cleanup processes for pull requests. Key features of the `pr_testbot` include:

- Automated deployments triggered by pull request actions.
- Detailed notifications and logs sent via GitHub comments and emails.
- Secure handling of webhook events and authentication tokens.
- Flexible deployment options with support for Docker and Docker Compose.

### Conclusion

The `pr_testbot` provides an efficient and secure way to manage deployments and cleanups for pull requests, ensuring consistency and reliability in testing environments. With planned future enhancements, the `pr_testbot` aims to become a versatile tool capable of handling various deployment technologies and integrating seamlessly into modern CI/CD pipelines.

By leveraging the `pr_testbot`, development teams can focus more on building and improving their applications, knowing that their deployment processes are automated and secure.
