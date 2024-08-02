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
        branch_name = data['pull_request']['head']['ref']
        installation_id = data['installation']['id']

        if action in ['opened', 'synchronize', 'reopened']:
            try:
                # Get installation access token
                access_token = get_installation_access_token(installation_id)
                comment_url = f"https://api.github.com/repos/{repo_name}/issues/{pr_number}/comments"

                # Notify stakeholders (comment on the PR)
                notify_stakeholders(comment_url, "Deployment started for this pull request.", access_token)

                # Run the deployment script with the branch name and PR number
                container_name, deployment_link, log_file_path = run_deployment_script(branch_name, pr_number)

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
                return jsonify({'message': 'Deployment failed'}), 500

        elif action == 'closed':
            try:
                # Pull request closed, trigger cleanup regardless of merge status
                log_file_path = run_cleanup_script(branch_name, pr_number)
                
                # Notify stakeholders about the cleanup
                access_token = get_installation_access_token(installation_id)
                comment_url = f"https://api.github.com/repos/{repo_name}/issues/{pr_number}/comments"
                notify_stakeholders(comment_url, "Cleanup completed for this pull request.", access_token)

                # Send cleanup log via email
                send_email(RECIPIENT_EMAIL, 'Cleanup Log', 'Please find the attached cleanup log.', log_file_path)

                return jsonify({'message': 'Cleanup processed'}), 200
            except Exception as e:
                logger.error(f"Cleanup failed: {e}")
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

def run_deployment_script(branch_name, pr_number):
    log_file_path = f'/tmp/deployment_log_{branch_name}_{pr_number}.txt'
    details = {}
    with open(log_file_path, 'w') as log_file:
        try:
            result = subprocess.run(['./deploy.sh', branch_name, str(pr_number)], check=True, capture_output=True, text=True)
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

def run_cleanup_script(branch_name, pr_number):
    log_file_path = f'/tmp/cleanup_log_{branch_name}_{pr_number}.txt'
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

def send_email(to_address, subject, body, attachment_path):
    from_address = SMTP_USERNAME
    msg = MIMEMultipart()
    msg['From'] = from_address
    msg['To'] = to_address
    msg['Subject'] = subject

    msg.attach(MIMEText(body, 'plain'))

    attachment = open(attachment_path, 'rb')
    part = MIMEBase('application', 'octet-stream')
    part.set_payload(attachment.read())
    encoders.encode_base64(part)
    part.add_header('Content-Disposition', f'attachment; filename= {os.path.basename(attachment_path)}')
    msg.attach(part)

    server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
    server.starttls()
    server.login(from_address, SMTP_PASSWORD)
    text = msg.as_string()
    server.sendmail(from_address, to_address, text)
    server.quit()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
