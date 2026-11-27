def test_create_meeting(auth_client):
    response = auth_client.post("/meetings", json={"title": "Reunião de teste"})
    assert response.status_code == 201
    body = response.json()
    assert body["title"] == "Reunião de teste"
    assert body["status"].lower() == "received"


def test_get_meeting_by_id(auth_client):
    created = auth_client.post("/meetings", json={"title": "Teste de busca"})
    meeting_id = created.json()["id"]

    response = auth_client.get(f"/meetings/{meeting_id}")
    assert response.status_code == 200
    assert response.json()["id"] == meeting_id


def test_get_meeting_not_found(auth_client):
    response = auth_client.get("/meetings/99999")
    assert response.status_code == 404


def test_list_meetings(auth_client):
    auth_client.post("/meetings", json={"title": "Teste listagem"})
    response = auth_client.get("/meetings")
    assert response.status_code == 200
    assert isinstance(response.json(), list)
