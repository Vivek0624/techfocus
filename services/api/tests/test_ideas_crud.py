def _new(client, title):
    r = client.post("/api/ideas/quick", json={"title": title, "note": "first note", "force": True})
    assert r.status_code == 201
    return r.json()["id"]


def test_quick_idea_keeps_note_and_patch_fields(client):
    iid = _new(client, "Zebra crossing of databases explained")
    got = client.get(f"/api/content/{iid}").json()
    assert got["notes"] == "first note"
    r = client.patch(
        f"/api/content/{iid}",
        json={
            "title": "Indexes explained with a library",
            "notes": "try the library analogy",
            "pillar": "tech_concepts",
            "audience": "beginners",
            "recommended_hook": "Your library is a DB",
        },
    ).json()
    assert r["title"].startswith("Indexes") and r["notes"] == "try the library analogy"
    assert r["audience"] == "beginners" and r["recommended_hook"] == "Your library is a DB"


def test_duplicate_archive_delete(client):
    iid = _new(client, "Quantum cats for absolute beginners")
    dup = client.post(f"/api/content/{iid}/clone").json()
    assert dup["title"].endswith("(copy)") and dup["status"] == "idea" and dup["notes"] == "first note"
    assert client.patch(f"/api/content/{iid}", json={"status": "archived"}).json()["status"] == "archived"
    assert client.delete(f"/api/content/{dup['id']}").status_code == 204
    assert client.get(f"/api/content/{dup['id']}").status_code == 404


def test_bulk_move_archive_restore_delete(client):
    ids = [_new(client, f"Bulk idea number {n} about kettles") for n in range(3)]
    r = client.post("/api/ideas/bulk", json={"ids": ids, "action": "move", "status": "script"}).json()
    assert r["affected"] == 3
    assert all(client.get(f"/api/content/{i}").json()["status"] == "script" for i in ids)
    assert client.post("/api/ideas/bulk", json={"ids": ids, "action": "move"}).status_code == 422
    client.post("/api/ideas/bulk", json={"ids": ids[:1], "action": "archive"})
    assert client.get(f"/api/content/{ids[0]}").json()["status"] == "archived"
    client.post("/api/ideas/bulk", json={"ids": ids[:1], "action": "restore"})
    assert client.get(f"/api/content/{ids[0]}").json()["status"] == "idea"
    assert client.post("/api/ideas/bulk", json={"ids": ids, "action": "delete"}).json()["affected"] == 3
    assert all(client.get(f"/api/content/{i}").status_code == 404 for i in ids)


def test_search_filter_content(client):
    _new(client, "Searchable walrus idea")
    r = client.get("/api/content", params={"search": "walrus"}).json()
    assert r["total"] >= 1 and all("walrus" in i["title"].lower() for i in r["items"])
