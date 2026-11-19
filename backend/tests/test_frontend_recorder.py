from fastapi.testclient import TestClient


def test_index_serves_html_recorder(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")
    assert "CortechX Zumo" in response.text
    assert "btnStartRecord" in response.text


def test_static_files_served_correctly(client: TestClient) -> None:
    # Audio recorder JS
    js_response = client.get("/static/js/audio-recorder.js")
    assert js_response.status_code == 200
    assert "ZumoAudioRecorder" in js_response.text

    # App controller JS
    app_js_response = client.get("/static/js/app.js")
    assert app_js_response.status_code == 200
    assert "DOMContentLoaded" in app_js_response.text

    # CSS
    css_response = client.get("/static/css/style.css")
    assert css_response.status_code == 200
    assert "--bg-primary" in css_response.text

    # Logo image
    logo_response = client.get("/static/img/zumo-logo-final.png")
    assert logo_response.status_code == 200
    assert logo_response.headers.get("content-type") == "image/png"
