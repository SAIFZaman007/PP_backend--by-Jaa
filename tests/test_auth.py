"""Smoke tests for the registration / login / me flow."""
import pytest

API = "/api/v1"


@pytest.mark.asyncio
async def test_register_login_me(client):
    # Register
    r = await client.post(
        f"{API}/auth/register",
        json={"email": "jane@example.com", "password": "supersecret", "first_name": "Jane"},
    )
    assert r.status_code == 201, r.text
    tokens = r.json()
    assert "access_token" in tokens and "refresh_token" in tokens

    # Duplicate registration is rejected
    r2 = await client.post(
        f"{API}/auth/register",
        json={"email": "jane@example.com", "password": "supersecret", "first_name": "Jane"},
    )
    assert r2.status_code == 409

    # Login
    r3 = await client.post(
        f"{API}/auth/login", json={"email": "jane@example.com", "password": "supersecret"}
    )
    assert r3.status_code == 200, r3.text
    access = r3.json()["access_token"]

    # Authenticated /me
    r4 = await client.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {access}"})
    assert r4.status_code == 200
    assert r4.json()["email"] == "jane@example.com"
    assert r4.json()["role"] == "client"

    # Wrong password fails
    r5 = await client.post(
        f"{API}/auth/login", json={"email": "jane@example.com", "password": "nope"}
    )
    assert r5.status_code == 401


@pytest.mark.asyncio
async def test_me_requires_auth(client):
    r = await client.get(f"{API}/auth/me")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_public_booking_creates_lead(client):
    r = await client.post(
        f"{API}/bookings",
        json={
            "name": "Lead Person",
            "email": "lead@example.com",
            "service": "Free Intro Call",
            "start_time": "2030-01-01T15:00:00+00:00",
        },
    )
    assert r.status_code == 201, r.text
    assert r.json()["status"] == "pending"
