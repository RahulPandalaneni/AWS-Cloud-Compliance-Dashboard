import os
import logging
from datetime import datetime, timezone
import boto3
from botocore.exceptions import (
    ClientError,
    NoCredentialsError,
    PartialCredentialsError,
    EndpointConnectionError,
    ParamValidationError,
)

logger = logging.getLogger(__name__)

class S3ComplianceService:
    """
    Encapsulates Amazon S3 compliance audits and Cross-Region Replication (CRR)
    status inspection using boto3.
    """

    def __init__(self, source_bucket=None, source_region=None, dest_bucket=None, dest_region=None):
        self.source_bucket = source_bucket or os.getenv("SOURCE_BUCKET_NAME", "compliance-source-rahul-2026")
        self.source_region = source_region or os.getenv("SOURCE_BUCKET_REGION", "ap-south-1")
        self.dest_bucket = dest_bucket or os.getenv("DEST_BUCKET_NAME", "compliance-destination-rahul-2026")
        self.dest_region = dest_region or os.getenv("DEST_BUCKET_REGION", "ap-southeast-1")

    def _get_s3_client(self, region_name):
        """
        Initializes an S3 client for a given region using standard AWS credential chain.
        Credentials are not hardcoded.
        """
        aws_access_key = os.getenv("AWS_ACCESS_KEY_ID")
        aws_secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")
        aws_session_token = os.getenv("AWS_SESSION_TOKEN")

        # If environment variables are explicitly passed, use them; otherwise boto3 automatically
        # searches ~/.aws/credentials, IAM instance role, ECS task role, or environment.
        if aws_access_key and aws_secret_key:
            return boto3.client(
                "s3",
                region_name=region_name,
                aws_access_key_id=aws_access_key,
                aws_secret_access_key=aws_secret_key,
                aws_session_token=aws_session_token,
            )
        return boto3.client("s3", region_name=region_name)

    def verify_credentials(self):
        """
        Verifies if AWS credentials exist and can authenticate with AWS STS or S3.
        Returns (is_valid, error_code, error_message).
        """
        try:
            session = boto3.Session(
                aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID") or None,
                aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY") or None,
                aws_session_token=os.getenv("AWS_SESSION_TOKEN") or None,
            )
            creds = session.get_credentials()
            if not creds:
                return False, "NO_CREDENTIALS", "No AWS credentials found in environment, ~/.aws/credentials, or IAM profile."
            
            # Make a lightweight call to verify authorization
            sts_client = session.client("sts")
            caller_identity = sts_client.get_caller_identity()
            return True, None, f"Authenticated as {caller_identity.get('Arn')}"
        except (NoCredentialsError, PartialCredentialsError) as e:
            return False, "NO_CREDENTIALS", str(e)
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "CLIENT_ERROR")
            error_msg = e.response.get("Error", {}).get("Message", str(e))
            return False, error_code, error_msg
        except EndpointConnectionError as e:
            return False, "NETWORK_ERROR", f"Could not connect to AWS endpoint: {e}"
        except Exception as e:
            return False, "AUTH_ERROR", str(e)

    def _get_bucket_metadata(self, client, bucket_name, region_name):
        """
        Gathers compliance metadata for an S3 bucket:
        - Existence & accessibility
        - Versioning status
        - Replication configuration
        - Public access block configuration
        - Default encryption
        - Objects count and sizes
        """
        result = {
            "name": bucket_name,
            "region": region_name,
            "region_display": "Asia Pacific (Mumbai)" if region_name == "ap-south-1" else (
                "Asia Pacific (Singapore)" if region_name == "ap-southeast-1" else region_name
            ),
            "accessible": False,
            "versioning": "Disabled",
            "replication": "Not Configured",
            "replication_rules": [],
            "public_access_block": "Unknown",
            "encryption": "Disabled",
            "encryption_type": None,
            "object_count": 0,
            "total_bytes": 0,
            "error": None,
        }

        # 1. Bucket accessibility check
        try:
            client.head_bucket(Bucket=bucket_name)
            result["accessible"] = True
        except ClientError as e:
            err_code = e.response.get("Error", {}).get("Code", "Error")
            if err_code in ["404", "NoSuchBucket"]:
                result["error"] = "Bucket does not exist"
            elif err_code in ["403", "AccessDenied"]:
                result["error"] = "Access Denied (insufficient permissions)"
            else:
                result["error"] = f"Client error: {err_code}"
            return result
        except Exception as e:
            result["error"] = str(e)
            return result

        # 2. Versioning check
        try:
            v_resp = client.get_bucket_versioning(Bucket=bucket_name)
            v_status = v_resp.get("Status")
            result["versioning"] = v_status if v_status else "Disabled"
        except ClientError as e:
            result["versioning"] = f"Error: {e.response.get('Error', {}).get('Code')}"

        # 3. Replication configuration check
        try:
            rep_resp = client.get_bucket_replication(Bucket=bucket_name)
            rep_config = rep_resp.get("ReplicationConfiguration", {})
            rules = rep_config.get("Rules", [])
            result["replication_rules"] = rules
            if any(r.get("Status") == "Enabled" for r in rules):
                result["replication"] = "Enabled"
            else:
                result["replication"] = "Disabled"
        except ClientError as e:
            err_code = e.response.get("Error", {}).get("Code")
            if err_code == "ReplicationConfigurationNotFoundError":
                result["replication"] = "Not Configured"
            else:
                result["replication"] = f"Check Error ({err_code})"

        # 4. Public access block check
        try:
            pab_resp = client.get_public_access_block(Bucket=bucket_name)
            pab_config = pab_resp.get("PublicAccessBlockConfiguration", {})
            all_blocked = (
                pab_config.get("BlockPublicAcls", False)
                and pab_config.get("IgnorePublicAcls", False)
                and pab_config.get("BlockPublicPolicy", False)
                and pab_config.get("RestrictPublicBuckets", False)
            )
            result["public_access_block"] = "Fully Blocked" if all_blocked else "Partially Blocked"
        except ClientError as e:
            err_code = e.response.get("Error", {}).get("Code")
            if err_code == "NoSuchPublicAccessBlockConfiguration":
                result["public_access_block"] = "Public Allowed (Unrestricted)"
            else:
                result["public_access_block"] = f"Check Error ({err_code})"

        # 5. Default encryption check
        try:
            enc_resp = client.get_bucket_encryption(Bucket=bucket_name)
            rules = enc_resp.get("ServerSideEncryptionConfiguration", {}).get("Rules", [])
            if rules:
                apply_sse = rules[0].get("ApplyServerSideEncryptionByDefault", {})
                sse_algo = apply_sse.get("SSEAlgorithm", "Enabled")
                result["encryption"] = "Enabled"
                result["encryption_type"] = sse_algo
            else:
                result["encryption"] = "Disabled"
        except ClientError as e:
            err_code = e.response.get("Error", {}).get("Code")
            if err_code == "ServerSideEncryptionConfigurationNotFoundError":
                result["encryption"] = "Disabled"
            else:
                result["encryption"] = f"Check Error ({err_code})"

        # 6. Object statistics & replication statuses
        try:
            paginator = client.get_paginator("list_objects_v2")
            total_count = 0
            total_size = 0
            for page in paginator.paginate(Bucket=bucket_name):
                contents = page.get("Contents", [])
                total_count += len(contents)
                total_size += sum(item.get("Size", 0) for item in contents)
            result["object_count"] = total_count
            result["total_bytes"] = total_size
        except ClientError:
            pass

        return result

    def get_recent_objects_and_replication(self, source_client, dest_client):
        """
        Retrieves recent objects and checks their S3 replication status metadata.
        Uses list_object_versions or head_object to fetch ReplicationStatus.
        """
        recent_objects = []

        try:
            # 1. Fetch versions/objects from source bucket
            src_objects = []
            try:
                # Try list_object_versions first because it contains ReplicationStatus
                ver_resp = source_client.list_object_versions(Bucket=self.source_bucket, MaxKeys=50)
                versions = ver_resp.get("Versions", [])
                # Filter for latest versions only to avoid duplicate object rows
                for v in versions:
                    if v.get("IsLatest", True):
                        src_objects.append({
                            "key": v.get("Key"),
                            "size": v.get("Size", 0),
                            "last_modified": v.get("LastModified"),
                            "replication_status": v.get("ReplicationStatus", "UNKNOWN"),
                            "etag": v.get("ETag", "").strip('"'),
                            "version_id": v.get("VersionId"),
                        })
            except ClientError:
                # Fallback to list_objects_v2 + head_object
                resp = source_client.list_objects_v2(Bucket=self.source_bucket, MaxKeys=50)
                for item in resp.get("Contents", []):
                    key = item.get("Key")
                    rep_status = "UNKNOWN"
                    try:
                        head = source_client.head_object(Bucket=self.source_bucket, Key=key)
                        rep_status = head.get("ReplicationStatus", "UNKNOWN")
                    except ClientError:
                        pass
                    src_objects.append({
                        "key": key,
                        "size": item.get("Size", 0),
                        "last_modified": item.get("LastModified"),
                        "replication_status": rep_status,
                        "etag": item.get("ETag", "").strip('"'),
                        "version_id": None,
                    })

            # 2. Fetch destination objects to verify existence in destination bucket
            dest_keys = set()
            try:
                dest_resp = dest_client.list_objects_v2(Bucket=self.dest_bucket, MaxKeys=100)
                for item in dest_resp.get("Contents", []):
                    dest_keys.add(item.get("Key"))
            except ClientError:
                pass

            # 3. Assemble objects list with compliance evaluation
            for obj in src_objects:
                key = obj["key"]
                raw_rep = obj["replication_status"]  # COMPLETED, PENDING, FAILED, REPLICA, or UNKNOWN
                present_in_dest = key in dest_keys

                # S3 Cross-Region Replication Status Evaluation
                if raw_rep == "COMPLETED" or (raw_rep == "UNKNOWN" and present_in_dest):
                    display_rep = "COMPLETED"
                    compliance = "Compliant"
                    compliance_badge = "badge-compliant"
                elif raw_rep == "PENDING":
                    display_rep = "PENDING"
                    compliance = "Warning"
                    compliance_badge = "badge-warning"
                elif raw_rep == "FAILED":
                    display_rep = "FAILED"
                    compliance = "Non-Compliant"
                    compliance_badge = "badge-non-compliant"
                elif raw_rep == "REPLICA":
                    display_rep = "REPLICA"
                    compliance = "Compliant"
                    compliance_badge = "badge-compliant"
                else:
                    display_rep = "NOT REPLICATED" if not present_in_dest else "COMPLETED"
                    compliance = "Warning" if not present_in_dest else "Compliant"
                    compliance_badge = "badge-warning" if not present_in_dest else "badge-compliant"

                recent_objects.append({
                    "key": key,
                    "type": "S3 Object",
                    "source_bucket": self.source_bucket,
                    "source_region": self.source_region,
                    "dest_bucket": self.dest_bucket,
                    "dest_region": self.dest_region,
                    "replication_status": display_rep,
                    "compliance_status": compliance,
                    "compliance_badge": compliance_badge,
                    "size_bytes": obj["size"],
                    "size_formatted": self._format_size(obj["size"]),
                    "last_modified": obj["last_modified"].isoformat() if isinstance(obj["last_modified"], datetime) else str(obj["last_modified"]),
                    "verified_in_destination": present_in_dest,
                })

        except Exception as e:
            logger.warning("Error fetching object replication details: %s", e)

        return recent_objects

    @staticmethod
    def _format_size(num_bytes):
        if num_bytes is None:
            return "0 B"
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if abs(num_bytes) < 1024.0:
                return f"{num_bytes:3.1f} {unit}"
            num_bytes /= 1024.0
        return f"{num_bytes:.1f} PB"

    def get_full_compliance_report(self):
        """
        Executes comprehensive compliance checks against the S3 infrastructure:
        - Verifies credentials
        - Queries source bucket in ap-south-1
        - Queries destination bucket in ap-southeast-1
        - Examines replication status of individual objects
        - Evaluates overall compliance score
        """
        # Step 1: Check AWS Credentials
        has_creds, error_code, auth_message = self.verify_credentials()

        if not has_creds:
            return {
                "connected": False,
                "error": auth_message,
                "error_code": error_code,
                "is_demo_mode": True,
                "checked_at": datetime.now(timezone.utc).isoformat(),
                "summary": {
                    "compliant_count": 0,
                    "non_compliant_count": 0,
                    "warnings_count": 0,
                    "resources_monitored": 0,
                    "compliance_rate": 0,
                    "label": "Awaiting AWS Connection",
                },
                "source_bucket": {
                    "name": self.source_bucket,
                    "region": self.source_region,
                    "region_display": "Asia Pacific (Mumbai)",
                    "accessible": False,
                    "versioning": "Unknown",
                    "replication": "Unknown",
                    "public_access_block": "Unknown",
                    "encryption": "Unknown",
                    "object_count": 0,
                    "total_bytes": 0,
                    "label": "Requires AWS credentials to fetch real data",
                },
                "destination_bucket": {
                    "name": self.dest_bucket,
                    "region": self.dest_region,
                    "region_display": "Asia Pacific (Singapore)",
                    "accessible": False,
                    "versioning": "Unknown",
                    "replication": "Unknown",
                    "public_access_block": "Unknown",
                    "encryption": "Unknown",
                    "object_count": 0,
                    "total_bytes": 0,
                    "label": "Requires AWS credentials to fetch real data",
                },
                "replication_pipeline": {
                    "status": "Unknown",
                    "source_region": self.source_region,
                    "dest_region": self.dest_region,
                    "status_badge": "badge-unknown",
                    "details": "Cross-Region Replication status cannot be checked without AWS credentials.",
                },
                "compliance_checks": [
                    {
                        "control_id": "AWS-S3-01",
                        "title": "Cross-Region Replication Active",
                        "status": "Warning",
                        "badge": "badge-warning",
                        "resource": f"{self.source_bucket} -> {self.dest_bucket}",
                        "description": "Cross-Region Replication ensures cross-region disaster recovery.",
                        "is_demo": True,
                    },
                    {
                        "control_id": "AWS-S3-02",
                        "title": "Bucket Versioning Enabled",
                        "status": "Warning",
                        "badge": "badge-warning",
                        "resource": "Both S3 Buckets",
                        "description": "S3 Versioning preserves, retrieves, and restores every version of every object.",
                        "is_demo": True,
                    },
                    {
                        "control_id": "AWS-S3-03",
                        "title": "S3 Block Public Access",
                        "status": "Warning",
                        "badge": "badge-warning",
                        "resource": "Both S3 Buckets",
                        "description": "Ensures public ACLs and public policies are rejected.",
                        "is_demo": True,
                    },
                    {
                        "control_id": "AWS-S3-04",
                        "title": "Server-Side Encryption (SSE)",
                        "status": "Warning",
                        "badge": "badge-warning",
                        "resource": "Both S3 Buckets",
                        "description": "Encrypts S3 data at rest with SSE-S3 or AWS KMS.",
                        "is_demo": True,
                    },
                ],
                "recent_objects": [],
            }

        # Step 2: Initialize regional clients
        src_client = self._get_s3_client(self.source_region)
        dest_client = self._get_s3_client(self.dest_region)

        # Step 3: Fetch metadata for both buckets
        src_meta = self._get_bucket_metadata(src_client, self.source_bucket, self.source_region)
        dest_meta = self._get_bucket_metadata(dest_client, self.dest_bucket, self.dest_region)

        # Step 4: Fetch objects and replication status
        recent_objects = self.get_recent_objects_and_replication(src_client, dest_client)

        # Step 5: Evaluate compliance controls
        compliance_checks = []
        compliant_count = 0
        non_compliant_count = 0
        warnings_count = 0

        # Control 1: CRR Configuration on source bucket
        crr_active = src_meta.get("replication") == "Enabled"
        if crr_active:
            compliant_count += 1
            compliance_checks.append({
                "control_id": "AWS-S3-CRR",
                "title": "Cross-Region Replication Active",
                "status": "Compliant",
                "badge": "badge-compliant",
                "resource": f"{self.source_bucket} -> {self.dest_bucket}",
                "description": f"CRR rule configured from Mumbai ({self.source_region}) to Singapore ({self.dest_region}).",
                "is_demo": False,
            })
        elif src_meta.get("replication") == "Not Configured":
            non_compliant_count += 1
            compliance_checks.append({
                "control_id": "AWS-S3-CRR",
                "title": "Cross-Region Replication Active",
                "status": "Non-Compliant",
                "badge": "badge-non-compliant",
                "resource": self.source_bucket,
                "description": "No replication configuration detected on source bucket.",
                "is_demo": False,
            })
        else:
            warnings_count += 1
            compliance_checks.append({
                "control_id": "AWS-S3-CRR",
                "title": "Cross-Region Replication Active",
                "status": "Warning",
                "badge": "badge-warning",
                "resource": self.source_bucket,
                "description": f"CRR status: {src_meta.get('replication')}",
                "is_demo": False,
            })

        # Control 2: Versioning on Source Bucket
        if src_meta.get("versioning") == "Enabled":
            compliant_count += 1
            compliance_checks.append({
                "control_id": "AWS-S3-VER-SRC",
                "title": "Source Bucket Versioning",
                "status": "Compliant",
                "badge": "badge-compliant",
                "resource": self.source_bucket,
                "description": "Versioning is active on source bucket (required for CRR).",
                "is_demo": False,
            })
        else:
            non_compliant_count += 1
            compliance_checks.append({
                "control_id": "AWS-S3-VER-SRC",
                "title": "Source Bucket Versioning",
                "status": "Non-Compliant",
                "badge": "badge-non-compliant",
                "resource": self.source_bucket,
                "description": f"Source bucket versioning is {src_meta.get('versioning')}.",
                "is_demo": False,
            })

        # Control 3: Versioning on Destination Bucket
        if dest_meta.get("versioning") == "Enabled":
            compliant_count += 1
            compliance_checks.append({
                "control_id": "AWS-S3-VER-DST",
                "title": "Destination Bucket Versioning",
                "status": "Compliant",
                "badge": "badge-compliant",
                "resource": self.dest_bucket,
                "description": "Versioning is active on destination bucket.",
                "is_demo": False,
            })
        else:
            non_compliant_count += 1
            compliance_checks.append({
                "control_id": "AWS-S3-VER-DST",
                "title": "Destination Bucket Versioning",
                "status": "Non-Compliant",
                "badge": "badge-non-compliant",
                "resource": self.dest_bucket,
                "description": f"Destination bucket versioning is {dest_meta.get('versioning')}.",
                "is_demo": False,
            })

        # Control 4: Public Access Block on Source Bucket
        if src_meta.get("public_access_block") == "Fully Blocked":
            compliant_count += 1
            compliance_checks.append({
                "control_id": "AWS-S3-PAB-SRC",
                "title": "Source S3 Block Public Access",
                "status": "Compliant",
                "badge": "badge-compliant",
                "resource": self.source_bucket,
                "description": "All 4 Public Access Block settings are enabled on source bucket.",
                "is_demo": False,
            })
        else:
            non_compliant_count += 1
            compliance_checks.append({
                "control_id": "AWS-S3-PAB-SRC",
                "title": "Source S3 Block Public Access",
                "status": "Non-Compliant",
                "badge": "badge-non-compliant",
                "resource": self.source_bucket,
                "description": f"Public access block status: {src_meta.get('public_access_block')}.",
                "is_demo": False,
            })

        # Control 5: Public Access Block on Destination Bucket
        if dest_meta.get("public_access_block") == "Fully Blocked":
            compliant_count += 1
            compliance_checks.append({
                "control_id": "AWS-S3-PAB-DST",
                "title": "Destination S3 Block Public Access",
                "status": "Compliant",
                "badge": "badge-compliant",
                "resource": self.dest_bucket,
                "description": "All 4 Public Access Block settings are enabled on destination bucket.",
                "is_demo": False,
            })
        else:
            non_compliant_count += 1
            compliance_checks.append({
                "control_id": "AWS-S3-PAB-DST",
                "title": "Destination S3 Block Public Access",
                "status": "Non-Compliant",
                "badge": "badge-non-compliant",
                "resource": self.dest_bucket,
                "description": f"Public access block status: {dest_meta.get('public_access_block')}.",
                "is_demo": False,
            })

        # Control 6: Server-Side Encryption on Source Bucket
        if src_meta.get("encryption") == "Enabled":
            compliant_count += 1
            compliance_checks.append({
                "control_id": "AWS-S3-ENC-SRC",
                "title": "Source Bucket Encryption at Rest",
                "status": "Compliant",
                "badge": "badge-compliant",
                "resource": self.source_bucket,
                "description": f"Default encryption enabled ({src_meta.get('encryption_type')}).",
                "is_demo": False,
            })
        else:
            warnings_count += 1
            compliance_checks.append({
                "control_id": "AWS-S3-ENC-SRC",
                "title": "Source Bucket Encryption at Rest",
                "status": "Warning",
                "badge": "badge-warning",
                "resource": self.source_bucket,
                "description": "Default encryption is not explicitly configured on source bucket.",
                "is_demo": False,
            })

        # Object replication checks aggregation
        for obj in recent_objects:
            if obj["compliance_status"] == "Compliant":
                compliant_count += 1
            elif obj["compliance_status"] == "Warning":
                warnings_count += 1
            else:
                non_compliant_count += 1

        total_monitored = 2 + len(recent_objects)  # 2 buckets + number of objects
        total_evaluations = compliant_count + non_compliant_count + warnings_count
        rate = round((compliant_count / total_evaluations * 100), 1) if total_evaluations > 0 else 100.0

        # Overall replication status determination
        if crr_active and (not recent_objects or all(o["replication_status"] in ["COMPLETED", "REPLICA"] for o in recent_objects)):
            pipeline_status = "Active & Synced"
            pipeline_badge = "badge-compliant"
            pipeline_details = f"Cross-region replication active from {self.source_region} to {self.dest_region}."
        elif any(o["replication_status"] == "FAILED" for o in recent_objects):
            pipeline_status = "Replication Failed"
            pipeline_badge = "badge-non-compliant"
            pipeline_details = "One or more objects failed cross-region replication."
        elif any(o["replication_status"] == "PENDING" for o in recent_objects):
            pipeline_status = "Sync In Progress"
            pipeline_badge = "badge-warning"
            pipeline_details = "Object replication currently pending across regions."
        elif not crr_active:
            pipeline_status = "Not Configured"
            pipeline_badge = "badge-non-compliant"
            pipeline_details = "Replication rule is not active on the source bucket."
        else:
            pipeline_status = "Active"
            pipeline_badge = "badge-compliant"
            pipeline_details = "Replication rule active."

        return {
            "connected": True,
            "error": None,
            "error_code": None,
            "is_demo_mode": False,
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "summary": {
                "compliant_count": compliant_count,
                "non_compliant_count": non_compliant_count,
                "warnings_count": warnings_count,
                "resources_monitored": total_monitored,
                "compliance_rate": rate,
                "label": "Live AWS Data",
            },
            "source_bucket": src_meta,
            "destination_bucket": dest_meta,
            "replication_pipeline": {
                "status": pipeline_status,
                "source_region": self.source_region,
                "dest_region": self.dest_region,
                "status_badge": pipeline_badge,
                "details": pipeline_details,
            },
            "compliance_checks": compliance_checks,
            "recent_objects": recent_objects,
        }
