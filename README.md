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

## The pr_testbot application `main.py`

## The deployment script `deploy.sh`

## The cleanup script `cleanup.sh`

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
