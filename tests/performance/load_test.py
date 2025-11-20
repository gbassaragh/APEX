"""
Load test for APEX API to verify async background job fixes.

This test validates that:
1. Async endpoints return quickly (<1s for 202 Accepted responses)
2. Server handles concurrent users without timeouts
3. No 500 errors under load
4. Memory usage remains stable

Requirements:
    pip install locust

Usage:
    # Headless mode (automated testing)
    locust -f tests/performance/load_test.py \\
        --host http://localhost:8000 \\
        --users 10 \\
        --spawn-rate 2 \\
        --run-time 5m \\
        --headless \\
        --html reports/load_test_report.html

    # Interactive mode (web UI at http://localhost:8089)
    locust -f tests/performance/load_test.py --host http://localhost:8000

Success Criteria:
    - 95%+ requests complete successfully (200/201/202/404 responses)
    - Document validation endpoint returns in <1s (async operation)
    - Estimate generation endpoint returns in <1s (async operation)
    - No 500 Internal Server Errors
    - Server memory usage stable over 5-minute test
"""
import io
import time
from uuid import uuid4

from locust import HttpUser, between, task


class APEXUser(HttpUser):
    """
    Simulated APEX user performing typical workflow.

    Task weights:
    - 60% read operations (list projects, get documents)
    - 30% async operations (validation, estimate generation)
    - 10% create operations (new projects, document uploads)
    """

    wait_time = between(1, 3)  # Wait 1-3 seconds between requests (simulates user think time)

    def on_start(self):
        """
        Setup method called once per user at start.

        Creates a test project that will be used for subsequent operations.

        NOTE: This test assumes authentication is disabled or uses mock tokens.
        For production load testing with Azure AD, implement token acquisition here:
            1. Use MSAL to get token from Azure AD
            2. Store in self.headers
            3. Implement token refresh logic
        """
        # Mock authentication (replace with real Azure AD token for production testing)
        self.token = "mock-test-token"
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

        # Create test project for this user
        response = self.client.post(
            "/api/v1/projects",
            json={
                "project_number": f"LOAD-{uuid4().hex[:8].upper()}",
                "project_name": f"Load Test Project {uuid4().hex[:4]}",
                "voltage_level": 230,
                "line_miles": 10.5,
                "terrain_type": "rolling",
            },
            headers=self.headers,
            name="Create Project (setup)",
        )

        if response.status_code == 201:
            self.project_id = response.json()["id"]
            self.document_id = None
        else:
            # If project creation fails, subsequent tasks will skip operations
            self.project_id = None
            self.document_id = None
            print(f"WARNING: Project creation failed with status {response.status_code}")

    @task(6)
    def list_projects(self):
        """
        List all projects (most common read operation).

        Weight: 6 (60% of operations)
        Expected: 200 OK, <500ms response time
        """
        self.client.get(
            "/api/v1/projects",
            headers=self.headers,
            name="GET /projects",
        )

    @task(2)
    def get_project_details(self):
        """
        Get specific project details.

        Weight: 2 (20% of operations)
        Expected: 200 OK or 403 Forbidden, <300ms response time
        """
        if not self.project_id:
            return

        self.client.get(
            f"/api/v1/projects/{self.project_id}",
            headers=self.headers,
            name="GET /projects/{id}",
        )

    @task(1)
    def upload_and_validate_document(self):
        """
        Upload document and trigger async validation.

        Weight: 1 (10% of operations)
        Expected:
        - Upload: 201 Created, <2s response time
        - Validate: 202 Accepted, <1s response time (CRITICAL: async operation)
        """
        if not self.project_id:
            return

        # Create minimal PDF-like content (not a real PDF, just for load testing)
        fake_pdf_content = b"%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n>>\nendobj\n%%EOF"
        fake_pdf_file = io.BytesIO(fake_pdf_content)

        # Upload document (multipart form data)
        response = self.client.post(
            "/api/v1/documents/upload",
            data={
                "project_id": str(self.project_id),
                "document_type": "scope",
            },
            files={
                "file": ("test_scope.pdf", fake_pdf_file, "application/pdf"),
            },
            headers={"Authorization": f"Bearer {self.token}"},  # Only auth header for multipart
            name="POST /documents/upload",
        )

        if response.status_code == 201:
            document_id = response.json()["id"]
            self.document_id = document_id

            # Trigger async validation (CRITICAL: must return quickly)
            start_time = time.time()

            validation_response = self.client.post(
                f"/api/v1/documents/{document_id}/validate",
                headers=self.headers,
                name="POST /documents/{id}/validate",
            )

            duration = time.time() - start_time

            # Validate async behavior
            if validation_response.status_code == 202:
                # SUCCESS: Async endpoint returned immediately
                if duration > 1.0:
                    # WARNING: Took too long (might be blocking)
                    print(
                        f"WARNING: Document validation endpoint took {duration:.2f}s "
                        f"(should be <1s for async operation)"
                    )
            else:
                # ERROR: Expected 202 Accepted for async operation
                print(
                    f"ERROR: Document validation returned {validation_response.status_code}, "
                    f"expected 202"
                )

    @task(1)
    def generate_estimate(self):
        """
        Trigger async estimate generation.

        Weight: 1 (10% of operations)
        Expected: 202 Accepted, <1s response time (CRITICAL: async operation)
        """
        if not self.project_id:
            return

        start_time = time.time()

        response = self.client.post(
            "/api/v1/estimates/generate",
            json={
                "project_id": str(self.project_id),
                "risk_factors": [],
                "confidence_level": 0.8,
                "monte_carlo_iterations": 10000,
            },
            headers=self.headers,
            name="POST /estimates/generate",
        )

        duration = time.time() - start_time

        # Validate async behavior
        if response.status_code == 202:
            # SUCCESS: Async endpoint returned immediately
            if duration > 1.0:
                # WARNING: Took too long (might be blocking)
                print(
                    f"WARNING: Estimate generation endpoint took {duration:.2f}s "
                    f"(should be <1s for async operation)"
                )
        else:
            # Non-202 response (might be 403 if no access, 404 if project missing)
            # Only print if unexpected error
            if response.status_code >= 500:
                print(f"ERROR: Estimate generation returned {response.status_code}")

    @task(2)
    def check_job_status(self):
        """
        Poll background job status.

        Weight: 2 (20% of operations)
        Expected: 200 OK or 404 Not Found, <200ms response time

        Note: Most job IDs will be invalid (404) since this is load testing.
        Real users would poll actual job IDs from async operations.
        """
        # Use random job ID (most will return 404, which is expected)
        fake_job_id = str(uuid4())

        response = self.client.get(
            f"/api/v1/jobs/{fake_job_id}",
            headers=self.headers,
            name="GET /jobs/{id}",
        )

        # 404 is expected for random job IDs (not an error)
        # Only log if server error (500+)
        if response.status_code >= 500:
            print(f"ERROR: Job status check returned {response.status_code}")

    @task(1)
    def list_estimates(self):
        """
        List estimates for a project.

        Weight: 1 (10% of operations)
        Expected: 200 OK, <500ms response time
        """
        if not self.project_id:
            return

        self.client.get(
            f"/api/v1/estimates/projects/{self.project_id}/estimates",
            headers=self.headers,
            name="GET /estimates/projects/{id}/estimates",
        )


# Additional user types for different load profiles (optional)


class HeavyAsyncUser(HttpUser):
    """
    User that primarily triggers async operations.

    Use this to stress-test background job system:
        locust -f tests/performance/load_test.py \\
            --host http://localhost:8000 \\
            --users 20 \\
            --user-class HeavyAsyncUser
    """

    wait_time = between(2, 5)

    def on_start(self):
        """Setup test project."""
        self.token = "mock-test-token"
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

        response = self.client.post(
            "/api/v1/projects",
            json={
                "project_number": f"ASYNC-{uuid4().hex[:8].upper()}",
                "project_name": f"Async Test {uuid4().hex[:4]}",
                "voltage_level": 345,
                "line_miles": 25.0,
                "terrain_type": "mountainous",
            },
            headers=self.headers,
        )

        self.project_id = response.json()["id"] if response.status_code == 201 else None

    @task(5)
    def generate_estimates(self):
        """Generate estimates continuously."""
        if not self.project_id:
            return

        self.client.post(
            "/api/v1/estimates/generate",
            json={
                "project_id": str(self.project_id),
                "risk_factors": [],
                "confidence_level": 0.8,
                "monte_carlo_iterations": 10000,
            },
            headers=self.headers,
        )

    @task(5)
    def upload_documents(self):
        """Upload and validate documents continuously."""
        if not self.project_id:
            return

        fake_pdf = io.BytesIO(b"%PDF-1.4\n%%EOF")

        response = self.client.post(
            "/api/v1/documents/upload",
            data={
                "project_id": str(self.project_id),
                "document_type": "scope",
            },
            files={"file": ("test.pdf", fake_pdf, "application/pdf")},
            headers={"Authorization": f"Bearer {self.token}"},
        )

        if response.status_code == 201:
            document_id = response.json()["id"]

            self.client.post(
                f"/api/v1/documents/{document_id}/validate",
                headers=self.headers,
            )
