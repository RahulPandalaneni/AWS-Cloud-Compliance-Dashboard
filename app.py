import os
import logging
from flask import Flask, render_template, jsonify, request
from dotenv import load_dotenv
from s3_service import S3ComplianceService

# Load environment variables from .env if present
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("aws_compliance_app")

app = Flask(__name__)

# Service initialization
service = S3ComplianceService()

@app.route("/")
def index():
    """Renders the main compliance dashboard UI."""
    return render_template(
        "index.html",
        source_bucket=service.source_bucket,
        source_region=service.source_region,
        dest_bucket=service.dest_bucket,
        dest_region=service.dest_region,
    )

@app.route("/api/status", methods=["GET"])
def api_status():
    """Returns the current connection and credentials status."""
    has_creds, error_code, message = service.verify_credentials()
    return jsonify({
        "connected": has_creds,
        "error_code": error_code,
        "message": message,
        "source_bucket": service.source_bucket,
        "source_region": service.source_region,
        "dest_bucket": service.dest_bucket,
        "dest_region": service.dest_region,
    })

@app.route("/api/compliance", methods=["GET"])
def api_compliance():
    """
    Executes live compliance checks against the S3 buckets and returns
    full JSON analysis including replication status.
    """
    try:
        report = service.get_full_compliance_report()
        return jsonify(report)
    except Exception as e:
        logger.exception("Error evaluating compliance: %s", e)
        return jsonify({
            "connected": False,
            "error": str(e),
            "error_code": "INTERNAL_SERVER_ERROR",
            "is_demo_mode": True,
            "summary": {
                "compliant_count": 0,
                "non_compliant_count": 0,
                "warnings_count": 0,
                "resources_monitored": 0,
                "label": "Error Evaluating",
            },
            "recent_objects": [],
            "compliance_checks": [],
        }), 500

@app.route("/api/refresh", methods=["POST"])
def api_refresh():
    """Triggers an on-demand re-sync with AWS S3."""
    try:
        # Re-initialize service in case .env or credentials were changed
        global service
        service = S3ComplianceService()
        report = service.get_full_compliance_report()
        return jsonify({
            "status": "success",
            "data": report,
        })
    except Exception as e:
        logger.exception("Error refreshing compliance: %s", e)
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    debug = os.getenv("DEBUG", "False").lower() in ("true", "1", "t")
    print(f"Starting AWS Compliance Dashboard on http://127.0.0.1:{port}")
    app.run(host="0.0.0.0", port=port, debug=debug)
