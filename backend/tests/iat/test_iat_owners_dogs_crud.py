"""IAT: Owner and Dog CRUD endpoints not exercised by other flows."""

import pytest
from .conftest import create_owner, create_dog, get_first_large_kennel


# ── Owner endpoints ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_owner_by_id(iat_client, iat_headers):
    owner = await create_owner(iat_client, iat_headers, last_name="Retriever")
    r = await iat_client.get(f"/api/owners/{owner['owner_id']}", headers=iat_headers)
    assert r.status_code == 200
    assert r.json()["last_name"] == "Retriever"


@pytest.mark.asyncio
async def test_get_owner_not_found(iat_client, iat_headers):
    r = await iat_client.get("/api/owners/nonexistent-id", headers=iat_headers)
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_list_owners_no_filter(iat_client, iat_headers):
    await create_owner(iat_client, iat_headers, last_name="Alpha")
    await create_owner(iat_client, iat_headers, last_name="Beta")
    r = await iat_client.get("/api/owners", headers=iat_headers)
    assert r.status_code == 200
    names = [o["last_name"] for o in r.json()]
    assert "Alpha" in names and "Beta" in names


@pytest.mark.asyncio
async def test_list_owners_with_query(iat_client, iat_headers):
    await create_owner(iat_client, iat_headers, last_name="Zeppelin")
    await create_owner(iat_client, iat_headers, last_name="Smith")
    r = await iat_client.get("/api/owners?q=Zeppelin", headers=iat_headers)
    assert r.status_code == 200
    data = r.json()
    assert len(data) >= 1
    assert all("Zeppelin" in o["last_name"] for o in data)


@pytest.mark.asyncio
async def test_update_owner(iat_client, iat_headers):
    owner = await create_owner(iat_client, iat_headers, phone_number="303-000-0001")
    r = await iat_client.put(f"/api/owners/{owner['owner_id']}",
                             json={"phone_number": "303-999-8888"}, headers=iat_headers)
    assert r.status_code == 200
    assert r.json()["phone_number"] == "303-999-8888"


@pytest.mark.asyncio
async def test_update_owner_not_found(iat_client, iat_headers):
    r = await iat_client.put("/api/owners/no-such-owner",
                             json={"phone_number": "000"}, headers=iat_headers)
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_archive_owner(iat_client, iat_headers):
    owner = await create_owner(iat_client, iat_headers)
    r = await iat_client.delete(f"/api/owners/{owner['owner_id']}", headers=iat_headers)
    assert r.status_code == 204

    r2 = await iat_client.get(f"/api/owners/{owner['owner_id']}", headers=iat_headers)
    assert r2.json()["archived"] is True


@pytest.mark.asyncio
async def test_archive_owner_not_found(iat_client, iat_headers):
    r = await iat_client.delete("/api/owners/no-such-owner", headers=iat_headers)
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_list_owner_dogs(iat_client, iat_headers):
    owner = await create_owner(iat_client, iat_headers)
    await create_dog(iat_client, iat_headers, owner_id=owner["owner_id"], name="Rex")
    await create_dog(iat_client, iat_headers, owner_id=owner["owner_id"], name="Bella")
    r = await iat_client.get(f"/api/owners/{owner['owner_id']}/dogs", headers=iat_headers)
    assert r.status_code == 200
    names = {d["name"] for d in r.json()}
    assert {"Rex", "Bella"} == names


@pytest.mark.asyncio
async def test_list_owner_dogs_not_found(iat_client, iat_headers):
    r = await iat_client.get("/api/owners/no-such-owner/dogs", headers=iat_headers)
    assert r.status_code == 404


# ── Dog endpoints ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_dog_by_id(iat_client, iat_headers):
    owner = await create_owner(iat_client, iat_headers)
    dog = await create_dog(iat_client, iat_headers, owner_id=owner["owner_id"], name="Sparky")
    r = await iat_client.get(f"/api/dogs/{dog['dog_id']}", headers=iat_headers)
    assert r.status_code == 200
    assert r.json()["name"] == "Sparky"


@pytest.mark.asyncio
async def test_get_dog_not_found(iat_client, iat_headers):
    r = await iat_client.get("/api/dogs/no-such-dog", headers=iat_headers)
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_list_dogs_with_query(iat_client, iat_headers):
    owner = await create_owner(iat_client, iat_headers)
    await create_dog(iat_client, iat_headers, owner_id=owner["owner_id"], name="Torpedo")
    r = await iat_client.get("/api/dogs?q=Torpedo", headers=iat_headers)
    assert r.status_code == 200
    assert any(d["name"] == "Torpedo" for d in r.json())


@pytest.mark.asyncio
async def test_list_dogs_by_owner_id(iat_client, iat_headers):
    owner = await create_owner(iat_client, iat_headers)
    await create_dog(iat_client, iat_headers, owner_id=owner["owner_id"], name="Fido")
    r = await iat_client.get(f"/api/dogs?owner_id={owner['owner_id']}", headers=iat_headers)
    assert r.status_code == 200
    assert all(d["owner_id"] == owner["owner_id"] for d in r.json())


@pytest.mark.asyncio
async def test_update_dog(iat_client, iat_headers):
    owner = await create_owner(iat_client, iat_headers)
    dog = await create_dog(iat_client, iat_headers, owner_id=owner["owner_id"], medical_status="Healthy")
    r = await iat_client.put(f"/api/dogs/{dog['dog_id']}",
                             json={"medical_status": "On Medication"}, headers=iat_headers)
    assert r.status_code == 200
    assert r.json()["medical_status"] == "On Medication"


@pytest.mark.asyncio
async def test_update_dog_not_found(iat_client, iat_headers):
    r = await iat_client.put("/api/dogs/no-such-dog",
                             json={"medical_status": "Healthy"}, headers=iat_headers)
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_archive_dog(iat_client, iat_headers):
    owner = await create_owner(iat_client, iat_headers)
    dog = await create_dog(iat_client, iat_headers, owner_id=owner["owner_id"])
    r = await iat_client.delete(f"/api/dogs/{dog['dog_id']}", headers=iat_headers)
    assert r.status_code == 204

    r2 = await iat_client.get(f"/api/dogs/{dog['dog_id']}", headers=iat_headers)
    assert r2.json()["archived"] is True


@pytest.mark.asyncio
async def test_archive_dog_not_found(iat_client, iat_headers):
    r = await iat_client.delete("/api/dogs/no-such-dog", headers=iat_headers)
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_add_vaccination_record(iat_client, iat_headers):
    owner = await create_owner(iat_client, iat_headers)
    dog = await create_dog(iat_client, iat_headers, owner_id=owner["owner_id"])
    vacc = {"vaccine_name": "Rabies", "administered_date": "2026-01-15", "expiration_date": "2027-01-15"}
    r = await iat_client.post(f"/api/dogs/{dog['dog_id']}/vaccinations",
                              json=vacc, headers=iat_headers)
    assert r.status_code == 200
    records = r.json()["vaccination_records"]
    assert len(records) == 1
    assert records[0]["vaccine_name"] == "Rabies"


@pytest.mark.asyncio
async def test_add_vaccination_dog_not_found(iat_client, iat_headers):
    vacc = {"vaccine_name": "Rabies", "administered_date": "2026-01-15", "expiration_date": "2027-01-15"}
    r = await iat_client.post("/api/dogs/no-such-dog/vaccinations",
                              json=vacc, headers=iat_headers)
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_update_vaccination_record(iat_client, iat_headers):
    owner = await create_owner(iat_client, iat_headers)
    dog = await create_dog(iat_client, iat_headers, owner_id=owner["owner_id"])
    vacc = {"vaccine_name": "Bordetella", "administered_date": "2026-01-15", "expiration_date": "2027-01-15"}
    await iat_client.post(f"/api/dogs/{dog['dog_id']}/vaccinations", json=vacc, headers=iat_headers)

    updated = {"vaccine_name": "Bordetella", "administered_date": "2026-03-01", "expiration_date": "2027-03-01"}
    r = await iat_client.put(f"/api/dogs/{dog['dog_id']}/vaccinations/0",
                             json=updated, headers=iat_headers)
    assert r.status_code == 200
    assert r.json()["vaccination_records"][0]["administered_date"] == "2026-03-01"


@pytest.mark.asyncio
async def test_update_vaccination_out_of_range(iat_client, iat_headers):
    owner = await create_owner(iat_client, iat_headers)
    dog = await create_dog(iat_client, iat_headers, owner_id=owner["owner_id"])
    vacc = {"vaccine_name": "Bordetella", "administered_date": "2026-01-15", "expiration_date": "2027-01-15"}
    r = await iat_client.put(f"/api/dogs/{dog['dog_id']}/vaccinations/99",
                             json=vacc, headers=iat_headers)
    assert r.status_code == 404
