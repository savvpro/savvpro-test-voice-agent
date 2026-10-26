import os
import subprocess
import sys


def test_repository_root_launch_reads_backend_env_without_exposing_the_key(tmp_path):
    backend = tmp_path / "backend"
    backend.mkdir()
    (backend / ".env").write_text("GROQ_API_KEY=unit-test-value\n", encoding="utf-8")
    environment = dict(os.environ)
    environment.pop("GROQ_API_KEY", None)
    environment.pop("ENV_FILE", None)
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from lost_property.config import Settings; "
            "print(Settings().groq_api_key == 'unit-test-value')",
        ],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout.strip() == "True"
