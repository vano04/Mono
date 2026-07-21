from __future__ import annotations

import os

import httpx


BASE_URL = "http://localhost:8000"
PROJECT = "integration-test-semantic-search"
TEST_USERNAME = os.getenv("MONO_TEST_USERNAME", "integration-owner")
TEST_PASSWORD = os.environ["MONO_TEST_PASSWORD"]


def main() -> None:
    token_id: str | None = None
    project_created = False
    with httpx.Client(base_url=BASE_URL, timeout=180) as owner:
        response = owner.post(
            "/api/v1/auth/login",
            json={"username": TEST_USERNAME, "password": TEST_PASSWORD},
        )
        response.raise_for_status()
        try:
            response = owner.post(
                "/api/v1/projects",
                json={
                    "name": "Integration Test Semantic Search",
                    "slug": PROJECT,
                    "description": "Disposable optional-embedding verification.",
                },
            )
            response.raise_for_status()
            project = response.json()
            project_created = True

            response = owner.post(
                "/api/v1/auth/tokens",
                json={
                    "name": "Disposable semantic-search verification",
                    "expires_in_days": 1,
                    "project_ids": [project["id"]],
                },
            )
            response.raise_for_status()
            token_payload = response.json()
            token_id = token_payload["api_token"]["id"]

            with httpx.Client(
                base_url=BASE_URL,
                headers={"Authorization": f"Bearer {token_payload['token']}"},
                timeout=180,
            ) as agent:
                response = agent.post(
                    f"/api/v1/projects/{PROJECT}/experiments",
                    json={
                        "title": "Kitten comfort surface",
                        "hypothesis": "A household cat naps on a woven mat.",
                        "reasoning": "Soft fibers support calm animal sleep.",
                        "source": "agent",
                        "source_model": "codex",
                    },
                )
                response.raise_for_status()
                expected_id = response.json()["id"]

                response = agent.post(
                    f"/api/v1/projects/{PROJECT}/experiments",
                    json={
                        "title": "Database index tuning",
                        "hypothesis": "A narrower relational index reduces query latency.",
                        "reasoning": "Planner selectivity should improve for lookup workloads.",
                        "source": "agent",
                        "source_model": "codex",
                    },
                )
                response.raise_for_status()

                response = agent.post(
                    "/api/v1/search",
                    json={
                        "project": PROJECT,
                        "query": "domestic feline resting atop a rug",
                        "limit": 10,
                    },
                )
                response.raise_for_status()
                results = response.json()["results"]

            match = next((item for item in results if item["id"] == expected_id), None)
            assert match is not None, results
            assert match["semantic_score"] > 0, match
            assert match["match_type"] == "semantic", match
            print(
                "live semantic verification: optional FastEmbed result returned "
                f"with score {match['semantic_score']}"
            )
        finally:
            if token_id:
                response = owner.delete(f"/api/v1/auth/tokens/{token_id}")
                response.raise_for_status()
            if project_created:
                response = owner.delete(f"/api/v1/projects/{PROJECT}")
                response.raise_for_status()


if __name__ == "__main__":
    main()
