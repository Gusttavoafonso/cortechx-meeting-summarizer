from __future__ import annotations

import io
from datetime import date
from pathlib import Path

from app.api.v1.meetings import get_audio_storage_service
from app.main import app
from app.models.audio_file import AudioFile
from app.models.meeting import Meeting
from app.models.meeting_status import MeetingStatus
from app.models.summary import Summary
from app.models.task import Task
from app.models.transcript import Transcript
from app.models.transcript_segment import TranscriptSegment
from app.repositories.meeting_repository import MeetingRepository
from app.services.audio_storage import AudioStorageService
from sqlalchemy.orm import Session


def test_list_meetings_includes_summary_preview_and_omits_transcript(
    db_session: Session, make_auth_client
) -> None:
    alice_client, alice = make_auth_client(email="alice_list@example.com", name="Alice")
    meeting = Meeting(
        title="Com Resumo", user_id=alice.id, status=MeetingStatus.COMPLETED
    )
    db_session.add(meeting)
    db_session.commit()
    db_session.refresh(meeting)

    transcript = Transcript(meeting_id=meeting.id, content="Olá mundo")
    db_session.add(transcript)
    db_session.flush()
    db_session.add(
        TranscriptSegment(
            transcript_id=transcript.id, start_time=0.0, end_time=1.0, text="Olá mundo"
        )
    )
    db_session.add(
        Summary(
            meeting_id=meeting.id,
            objective="Alinhar sprint",
            summary="Resumo executivo da sprint.",
        )
    )
    db_session.add(Task(meeting_id=meeting.id, position=0, description="Revisar PR"))
    db_session.commit()

    list_res = alice_client.get("/meetings")
    assert list_res.status_code == 200
    items = list_res.json()
    assert len(items) == 1
    assert items[0]["transcript"] is None
    assert items[0]["summary"] == {
        "objective": "Alinhar sprint",
        "summary": "Resumo executivo da sprint.",
        "tasks_count": 1,
    }

    detail_res = alice_client.get(f"/meetings/{meeting.id}")
    assert detail_res.status_code == 200
    detail = detail_res.json()
    assert detail["transcript"] is not None
    assert len(detail["transcript"]["segments"]) == 1
    assert detail["summary"]["tasks_count"] == 1


def test_meetings_stats_and_tasks_isolated_per_user(
    db_session: Session, make_auth_client
) -> None:
    alice_client, alice = make_auth_client(
        email="alice_stats@example.com", name="Alice"
    )
    bob_client, bob = make_auth_client(email="bob_stats@example.com", name="Bob")

    m1 = Meeting(title="M1", user_id=alice.id, status=MeetingStatus.COMPLETED)
    m2 = Meeting(title="M2", user_id=alice.id, status=MeetingStatus.PROCESSING)
    m3 = Meeting(title="M3", user_id=alice.id, status=MeetingStatus.FAILED)
    m_bob = Meeting(title="Bob", user_id=bob.id, status=MeetingStatus.COMPLETED)
    db_session.add_all([m1, m2, m3, m_bob])
    db_session.commit()

    db_session.add_all(
        [
            AudioFile(
                meeting_id=m1.id,
                filename="a1.wav",
                original_filename="a1.wav",
                file_path="a1.wav",
                file_size_bytes=100,
                content_type="audio/wav",
                duration_seconds=120.5,
            ),
            AudioFile(
                meeting_id=m2.id,
                filename="a2.wav",
                original_filename="a2.wav",
                file_path="a2.wav",
                file_size_bytes=100,
                content_type="audio/wav",
                duration_seconds=60.0,
            ),
            AudioFile(
                meeting_id=m_bob.id,
                filename="b.wav",
                original_filename="b.wav",
                file_path="b.wav",
                file_size_bytes=100,
                content_type="audio/wav",
                duration_seconds=999.0,
            ),
        ]
    )
    db_session.add_all(
        [
            Task(
                meeting_id=m1.id,
                position=0,
                description="Tarefa Alice 1",
                responsible="Alice",
                deadline=date(2026, 12, 1),
            ),
            Task(meeting_id=m1.id, position=1, description="Tarefa Alice 2"),
            Task(meeting_id=m_bob.id, position=0, description="Tarefa Bob"),
        ]
    )
    db_session.commit()

    stats_res = alice_client.get("/meetings/stats")
    assert stats_res.status_code == 200
    stats = stats_res.json()
    assert stats["total_meetings"] == 3
    assert stats["completed_meetings"] == 1
    assert stats["processing_meetings"] == 1
    assert stats["failed_meetings"] == 1
    assert stats["total_audio_seconds"] == 180.5
    assert stats["total_tasks"] == 2
    assert len(stats["recent_meetings"]) == 3

    tasks_res = alice_client.get("/meetings/tasks")
    assert tasks_res.status_code == 200
    tasks = tasks_res.json()
    assert [t["description"] for t in tasks] == ["Tarefa Alice 1", "Tarefa Alice 2"]
    assert tasks[0]["meeting_title"] == "M1"
    assert tasks[0]["responsible"] == "Alice"
    assert tasks[0]["deadline"] == "2026-12-01"

    bob_tasks = bob_client.get("/meetings/tasks").json()
    assert [t["description"] for t in bob_tasks] == ["Tarefa Bob"]


def test_download_audio_file_and_delete_meeting(
    db_session: Session, make_auth_client, tmp_path: Path
) -> None:
    storage = AudioStorageService(base_storage_path=tmp_path)
    app.dependency_overrides[get_audio_storage_service] = lambda: storage
    try:
        alice_client, _alice = make_auth_client(
            email="alice_del@example.com", name="Alice"
        )
        bob_client, _bob = make_auth_client(email="bob_del@example.com", name="Bob")

        mid = alice_client.post("/meetings", json={"title": "Com Áudio"}).json()["id"]
        wav_bytes = (
            b"RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00"
            b"D\xac\x00\x00\x88X\x01\x00\x02\x00\x10\x00data\x00\x00\x00\x00"
        )
        upload_res = alice_client.post(
            f"/meetings/{mid}/audio",
            files={"file": ("gravacao.wav", io.BytesIO(wav_bytes), "audio/wav")},
        )
        assert upload_res.status_code == 201
        saved_path = storage.get_file_path(upload_res.json()["file_path"])
        assert saved_path.is_file()

        # Download pelo dono funciona, outro usuário recebe 404
        dl_res = alice_client.get(f"/meetings/{mid}/audio/file")
        assert dl_res.status_code == 200
        assert dl_res.content == wav_bytes
        assert bob_client.get(f"/meetings/{mid}/audio/file").status_code == 404

        # Delete bloqueado por outro usuário (404)
        assert bob_client.delete(f"/meetings/{mid}").status_code == 404

        # Delete bloqueado enquanto em processamento (409)
        repo = MeetingRepository(db_session)
        meeting = repo.get_by_id(mid)
        assert meeting is not None
        repo.update_status(meeting, MeetingStatus.PROCESSING)
        assert alice_client.delete(f"/meetings/{mid}").status_code == 409

        # Delete bem-sucedido (204) remove banco e arquivo físico
        repo.update_status(meeting, MeetingStatus.FAILED)
        del_res = alice_client.delete(f"/meetings/{mid}")
        assert del_res.status_code == 204
        assert alice_client.get(f"/meetings/{mid}").status_code == 404
        assert not saved_path.exists()
    finally:
        app.dependency_overrides.pop(get_audio_storage_service, None)


def test_extract_audio_duration_uses_packet_demux_for_headerless_webm(
    tmp_path: Path,
) -> None:
    import av
    import numpy as np

    webm_path = tmp_path / "sample.webm"
    with av.open(str(webm_path), mode="w", format="webm") as out:
        stream = out.add_stream("libopus", rate=48000)
        for _ in range(50):  # 50 * 20ms = 1.0s
            frame = av.AudioFrame.from_ndarray(
                np.zeros((1, 960), dtype=np.float32), format="fltp", layout="mono"
            )
            frame.sample_rate = 48000
            for packet in stream.encode(frame):
                out.mux(packet)
        for packet in stream.encode(None):
            out.mux(packet)

    dur = AudioStorageService(base_storage_path=tmp_path).extract_audio_duration(
        webm_path
    )
    assert dur is not None
    assert 0.8 <= dur <= 1.2
