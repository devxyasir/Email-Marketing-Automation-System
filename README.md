# Automated Email Sender with Licensing System

A professional Python application for sending bulk emails with a secure licensing system and modern UI.

## Features

- Support for Gmail (App Password) and other business email providers
- Bulk email sending from CSV files
- HTML and plain text email support
- Hardware-based licensing system
- Secure credential storage
- Modern PyQt6-based UI
- Multi-threaded email sending
- Comprehensive logging system

## Setup

1. Install requirements:
```bash
pip install -r requirements.txt
```

2. Set up MongoDB:
- Create a MongoDB database
- Add your MongoDB connection string to a `.env` file:
```
MONGODB_URI=your_mongodb_connection_string
```

3. For Gmail users:
- Enable 2-Step Verification in your Google Account
- Generate an App Password for this application

## Usage

1. Run the application:
```bash
python main.py
```

2. First Launch:
- The application will display your Hardware ID
- Provide this ID to the developer for license activation
- Developer will set up your license duration (1, 7, or 30 days)

3. Email Configuration:
- Select your email provider
- Enter your email credentials
- Configure SMTP settings (auto-filled for Gmail)
- Select your recipients CSV file

4. Sending Emails:
- Choose between HTML or plain text format
- Enter your email subject and content
- Click "Send Emails" to start the bulk sending process

## CSV Format

Your recipients CSV file should have at least one column named 'email':

```csv
email,name,company
user1@example.com,John Doe,Company A
user2@example.com,Jane Smith,Company B
```

## Security Features

- Hardware-based licensing
- Encrypted credential storage
- Secure SMTP connections
- MongoDB-based authentication

## Logging

The application logs all activities to `email_sender.log`, including:
- Email sending success/failures
- License validation
- Database operations
- Error messages

## Requirements

- Python 3.8+
- PyQt6
- MongoDB
- Other dependencies listed in requirements.txt

## Developer Credits

This application was developed and maintained by **Muhammd Yasir**.  
For licensing inquiries, support, or custom modifications, contact:  
📧 **devxyasir@gmail.com**  
🔗 [GitHub Profile](https://github.com/devxyasir)
