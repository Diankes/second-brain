"""The timing floor for checkpoints: when the Stop hook blocks, and when it must not."""

from helpers import VALID_CHECKPOINT, VALID_INSIGHT, run_script


def stop(stop_hook_active=False, env=None):
    return run_script(
        "cadence.py", {"hook_event_name": "Stop", "stop_hook_active": stop_hook_active}, env
    )


def prompts(memory, n):
    for i in range(n):
        memory.append(f"prompt {i}", "prompt")


def test_blocks_at_the_default_threshold(memory):
    prompts(memory, 5)
    assert stop().returncode == 0
    prompts(memory, 1)
    result = stop()
    assert result.returncode == 2
    assert "6 prompts since the last curated entry (threshold 6)" in result.stderr
    assert "append_event" in result.stderr and "checkpoint" in result.stderr


def test_never_blocks_twice_in_a_row(memory):
    prompts(memory, 10)
    assert stop().returncode == 2
    assert stop(stop_hook_active=True).returncode == 0


def test_a_curated_entry_or_checkpoint_resets_the_count(memory):
    prompts(memory, 7)
    assert stop().returncode == 2
    memory.append(VALID_INSIGHT, "insight")
    assert stop().returncode == 0
    prompts(memory, 7)
    assert stop().returncode == 2
    memory.checkpoint(VALID_CHECKPOINT)
    assert stop().returncode == 0
    prompts(memory, 2)
    assert stop().returncode == 0


def test_threshold_is_configurable(memory):
    prompts(memory, 2)
    assert stop(env={"SECOND_BRAIN_CADENCE": "2"}).returncode == 2
    assert stop(env={"SECOND_BRAIN_CADENCE": "3"}).returncode == 0
    assert stop(env={"SECOND_BRAIN_CADENCE": "0"}).returncode == 0
    assert stop(env={"SECOND_BRAIN_CADENCE": "garbage"}).returncode == 0  # default 6 applies


def test_missing_database_never_blocks(memory, tmp_path):
    prompts(memory, 20)
    assert stop(env={"MCP_SQLITE_DB": ""}).returncode == 0
    assert stop(env={"MCP_SQLITE_DB": str(tmp_path / "nope.db")}).returncode == 0
