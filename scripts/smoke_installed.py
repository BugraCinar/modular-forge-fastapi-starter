"""Run from a directory outside the checkout after installing the built wheel."""

from fastapi.testclient import TestClient

from modular_forge.app import create_app


def main():
    with TestClient(create_app(), base_url="http://localhost") as client:
        response = client.get("/health/ready")
        if response.status_code != 200 or response.json() != {"status": "up"}:
            raise RuntimeError("Installed application is not ready")
        if len(client.get("/api/v1/modules").json()) != 15:
            raise RuntimeError("Installed module catalog is incomplete")
    print("Installed wheel, packaged templates, migrations and application startup verified.")


if __name__ == "__main__":
    main()
