import unittest
import json
from app import app
from s3_service import S3ComplianceService

class TestAWSComplianceDashboard(unittest.TestCase):
    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True

    def test_index_page(self):
        """Verify the main UI HTML loads successfully."""
        response = self.app.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"AWS COMPLIANCE", response.data)
        self.assertIn(b"compliance-source-rahul-2026", response.data)
        self.assertIn(b"compliance-destination-rahul-2026", response.data)
        self.assertIn(b"Cross-Region Replication", response.data)

    def test_api_status(self):
        """Verify the /api/status endpoint returns valid connection info."""
        response = self.app.get('/api/status')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertIn('connected', data)
        self.assertIn('source_bucket', data)
        self.assertIn('dest_bucket', data)
        self.assertEqual(data['source_bucket'], 'compliance-source-rahul-2026')
        self.assertEqual(data['dest_bucket'], 'compliance-destination-rahul-2026')

    def test_api_compliance_graceful_handling(self):
        """Verify /api/compliance returns structured data even if AWS credentials are not present."""
        response = self.app.get('/api/compliance')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertIn('summary', data)
        self.assertIn('compliant_count', data['summary'])
        self.assertIn('non_compliant_count', data['summary'])
        self.assertIn('warnings_count', data['summary'])
        self.assertIn('resources_monitored', data['summary'])
        self.assertIn('source_bucket', data)
        self.assertIn('destination_bucket', data)
        self.assertIn('replication_pipeline', data)

    def test_s3_service_credential_verification(self):
        """Verify S3ComplianceService credential check returns boolean and error details."""
        service = S3ComplianceService()
        has_creds, error_code, msg = service.verify_credentials()
        self.assertIsInstance(has_creds, bool)
        if not has_creds:
            self.assertIsNotNone(error_code)
            self.assertIsNotNone(msg)

    def test_static_css_and_js_served(self):
        """Verify CSS and JS static files are served properly."""
        css_resp = self.app.get('/static/css/style.css')
        self.assertEqual(css_resp.status_code, 200)
        self.assertIn(b"--bg-sidebar: #0f172a", css_resp.data)

        js_resp = self.app.get('/static/js/app.js')
        self.assertEqual(js_resp.status_code, 200)
        self.assertIn(b"fetchComplianceData", js_resp.data)

if __name__ == '__main__':
    unittest.main()
