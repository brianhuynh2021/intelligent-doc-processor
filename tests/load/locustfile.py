"""Locust load test for the Doc Processor API.

Usage:
    pip install locust
    locust -f tests/load/locustfile.py --host http://localhost:8000

Set API_TOKEN env (a JWT) or API_KEY env (dpk_... key) to hit authenticated
endpoints; otherwise only public endpoints (health) are exercised.
"""
import os

from locust import HttpUser, between, task


class DocProcessorUser(HttpUser):
    wait_time = between(1, 3)

    def on_start(self):
        token = os.getenv("API_TOKEN")
        api_key = os.getenv("API_KEY")
        self.headers = {}
        if api_key:
            self.headers["X-API-Key"] = api_key
        elif token:
            self.headers["Authorization"] = f"Bearer {token}"

    @task(5)
    def health(self):
        self.client.get("/health", name="GET /health")

    @task(3)
    def readiness(self):
        self.client.get("/api/v1/health/ready", name="GET /health/ready")

    @task(4)
    def semantic_search(self):
        if not self.headers:
            return
        self.client.post(
            "/api/v1/search",
            json={"query": "invoice total amount", "top_k": 5},
            headers=self.headers,
            name="POST /search",
        )

    @task(2)
    def keyword_search(self):
        if not self.headers:
            return
        self.client.get(
            "/api/v1/search/keyword",
            params={"q": "invoice", "limit": 10},
            headers=self.headers,
            name="GET /search/keyword",
        )

    @task(2)
    def chat(self):
        if not self.headers:
            return
        self.client.post(
            "/api/v1/chat/ask",
            json={"question": "What is the total?", "top_k": 4, "stream": False},
            headers=self.headers,
            name="POST /chat/ask",
        )
