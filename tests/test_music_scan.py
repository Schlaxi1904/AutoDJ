from pathlib import Path

from auto_dj.audio.analyzer import summarize_music_directory


def create_file(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"")


def test_summarize_music_directory_counts_supported_files(tmp_path):
    create_file(tmp_path / "track_one.flac")
    create_file(tmp_path / "track_two.mp3")
    create_file(tmp_path / "nested" / "track_three.wav")
    create_file(tmp_path / "notes.txt")

    count, preview = summarize_music_directory(tmp_path)

    assert count == 3
    assert preview == [
        "nested/track_three.wav",
        "track_one.flac",
        "track_two.mp3",
    ]


def test_summarize_music_directory_handles_missing_path(tmp_path):
    missing = tmp_path / "missing"
    count, preview = summarize_music_directory(missing)

    assert count == 0
    assert preview == []
