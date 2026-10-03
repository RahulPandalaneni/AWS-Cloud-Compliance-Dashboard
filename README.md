# AWS Cloud Compliance Live Dashboard

A real-time AWS Cloud Compliance and Cross-Region Replication (CRR) monitoring dashboard built with **Python Flask**, **boto3**, and **modern responsive HTML5/CSS3/JavaScript**.

This system continuously tracks compliance benchmarks and Amazon S3 Cross-Region Replication between:
- **Source Bucket:** `compliance-source-rahul-2026` in `ap-south-1` (Mumbai)
- **Destination Bucket:** `compliance-destination-rahul-2026` in `ap-southeast-1` (Singapore)

---

## Features

- **Live AWS S3 Integration:** Uses `boto3` to audit real bucket configurations and object-level metadata rather than hardcoded mock data.
- **S3 Replication Status Metadata:** Reads individual object replication statuses (`COMPLETED`, `PENDING`, `REPLICA`, `FAILED`) using `head_object` and `list_object_versions`.
- **Figma Design Architecture:**
  - **Dark Left Sidebar:** AWS compliance branding, navigation, and active region tags (`ap-south-1` & `ap-southeast-1`).
  - **AWS COMPLIANCE Title & Live Header:** Real-time sync button, last updated timestamps, and connection status pills.
  - **Four Summary Cards:** Compliant count & rate, Non-Compliant count, Warnings count, and Resources Monitored.
  - **Cross-Region Replication Pipeline:** Visual flow diagram featuring the Mumbai source card, animated directional sync arrow, and Singapore destination card.
  - **Compliance Status & Objects Table:** Searchable, filterable table showing object replication states and security control evaluations.
- **Security & Credential Safety:** AWS credentials are never hardcoded or exposed in source code. Supports environment variables, `.env`, and the standard AWS credential chain (`~/.aws/credentials` / IAM roles).
- **Graceful Error Handling & Transparent Labeling:** If AWS credentials are not yet configured or an S3 request fails, the app provides immediate setup guidance and distinctly labels demo/preview values.

---

## Architecture

```text
┌─────────────────────────────────────────────────────────────┐
│                 Frontend (HTML / CSS / JS)                  │
│  - Dark Left Sidebar         - 4 Summary Cards              │
│  - AWS COMPLIANCE Header     - Visual CRR Flow (IN -> SG)   │
│  - Object & Controls Table   - Interactive Search & Filter  │
└──────────────────────────────┬──────────────────────────────┘
                               │ REST API (JSON)
┌──────────────────────────────▼──────────────────────────────┐
│                    Flask Backend (app.py)                   │
│  - GET  /                    - GET /api/compliance          │
│  - GET  /api/status          - POST /api/refresh            │
└──────────────────────────────┬──────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────┐
│               S3 Compliance Service (s3_service.py)         │
│  - Boto3 Client (ap-south-1) - Boto3 Client (ap-southeast-1)│
│  - Bucket Configurations     - Object Replication Metadata  │
└──────────────────────────────┬──────────────────────────────┘
                               │
            ┌──────────────────┴──────────────────┐
            ▼                                     ▼
┌──────────────────────────────┐       ┌──────────────────────────────┐
│  Source S3 Bucket (Mumbai)   │  CRR  │ Destination S3 Bucket (SG)   │
│ compliance-source-rahul-2026 ├──────►│compliance-destination-rahul- │
│ Region: ap-south-1           │       │ 2026 (ap-southeast-1)        │
└──────────────────────────────┘       └──────────────────────────────┘
```

---

## Prerequisites

- **Python 3.10+** (Tested on Python 3.14)
- **pip** package manager
- **AWS Account** with read access to the source and destination S3 buckets

---

## Setup & Installation

### 1. Clone or Navigate to the Workspace
```powershell
cd c:\Users\FixMe\Downloads\AWS-Cloud-Compliance-Live
```

### 2. (Optional) Create and Activate a Virtual Environment
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

### 3. Install Dependencies
```powershell
pip install -r requirements.txt
```

### 4. Configure AWS Credentials
You can provide AWS credentials using either a `.env` file or the AWS CLI.

#### Option A: Using `.env` (Recommended for Local Dev)
Copy `.env.example` to `.env`:
```powershell
Copy-Item .env.example .env
```
Open `.env` and fill in your AWS credentials:
```env
AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE
AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
SOURCE_BUCKET_NAME=compliance-source-rahul-2026
SOURCE_BUCKET_REGION=ap-south-1
DEST_BUCKET_NAME=compliance-destination-rahul-2026
DEST_BUCKET_REGION=ap-southeast-1
PORT=5000
DEBUG=False
```

#### Option B: Using AWS CLI
```powershell
aws configure
```

> **Note:** If no credentials are provided, the application will still launch and display the full UI in preview mode with setup instructions, clearly labeling unauthenticated demo values.

---

## Running the Application

Start the Flask server:
```powershell
python app.py
```

Once started, open your web browser and navigate to:
```
http://127.0.0.1:5000
```

---

## Recommended IAM Policy

For the IAM user or role used by the dashboard, attach the following minimal read-only permissions:

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "S3ComplianceBucketAudit",
            "Effect": "Allow",
            "Action": [
                "s3:ListBucket",
                "s3:GetBucketLocation",
                "s3:GetBucketVersioning",
                "s3:GetBucketReplication",
                "s3:GetBucketPublicAccessBlock",
                "s3:GetEncryptionConfiguration"
            ],
            "Resource": [
                "arn:aws:s3:::compliance-source-rahul-2026",
                "arn:aws:s3:::compliance-destination-rahul-2026"
            ]
        },
        {
            "Sid": "S3ObjectMetadataAudit",
            "Effect": "Allow",
            "Action": [
                "s3:GetObject",
                "s3:GetObjectVersion"
            ],
            "Resource": [
                "arn:aws:s3:::compliance-source-rahul-2026/*",
                "arn:aws:s3:::compliance-destination-rahul-2026/*"
            ]
        }
    ]
}
```

---

## API Endpoints

| Endpoint | Method | Description |
| :--- | :--- | :--- |
| `/` | `GET` | Main responsive compliance dashboard web page |
| `/api/status` | `GET` | Checks AWS credential presence, authorization, and bucket configurations |
| `/api/compliance`| `GET` | Audits both S3 buckets, object replication statuses, and evaluates compliance |
| `/api/refresh` | `POST` | Forces on-demand cache re-sync with AWS S3 |

---

## S3 Object Replication Status Reference

The dashboard inspects the `ReplicationStatus` attribute on S3 objects:

- **`COMPLETED`**: Object has successfully replicated to the Singapore destination bucket.
- **`REPLICA`**: Object in the destination bucket that was created via Cross-Region Replication.
- **`PENDING`**: Object replication is currently in progress.
- **`FAILED`**: S3 replication rule encountered an error (e.g., KMS permission issue or IAM role misconfiguration).
