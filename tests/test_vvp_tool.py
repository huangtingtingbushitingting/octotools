from pathlib import Path
from unittest.mock import patch

from octotools.tools.vvp.tool import VvpTool


class Process:
    returncode = 0
    stdout = "Simulation finished\nMismatches: 3 in 100 samples\n"
    stderr = ""


def test_vvp_rejects_nonzero_mismatch_count_even_with_zero_exit_code(tmp_path: Path):
    artifact = tmp_path / "candidate.vvp"
    artifact.write_text("placeholder", encoding="utf-8")
    tool = VvpTool()
    tool.set_custom_output_dir(str(tmp_path))
    with patch("shutil.which", return_value="/usr/bin/vvp"), patch(
        "subprocess.run", return_value=Process()
    ):
        result = tool.execute(str(artifact))
    assert result["simulation_success"] is False
    assert result["reported_failure_counts"] == [3]
