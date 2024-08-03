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

#### Step 5: Set Up and Activate a Virtual Environment

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

#### Step 6: Run the Flask App and ngrok

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

#### Step 7: Update GitHub App Webhook URL

1. **Update Webhook URL**:
   - Go back to the GitHub Developer settings and navigate to your GitHub App settings.
   - Update the "Webhook URL" with your ngrok URL followed by `/webhook` (e.g., `http://your-ngrok-url.ngrok.io/webhook`).

#### Step 8: Test PR_TestBot

1. **Create a Pull Request**:
   - Make a change in a branch of your repository and create a pull request to trigger the bot.

2. **Monitor the Deployment**:
   - The bot should automatically deploy the code, notify stakeholders, and provide detailed status updates.

By following these steps, you will have PR_TestBot installed on GitHub, with the ability to deploy Docker or Docker Compose applications, provide notifications, and manage resources efficiently.
