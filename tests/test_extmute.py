"""
extmute: muting the bot from the command line through .muted_until.

A script runs `docker exec <bot> sh -c "echo <epoch> > /app/config/.muted_until"`
while the bot is up; the watcher applies it and removes the file.
"""

import os
import sys
import time
from unittest.mock import MagicMock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import harness

dcb, store, _root = harness.load_bot()


def _write(until, age=5):
	path = os.path.join(store.root(), dcb.EXTERNAL_MUTE_FILE)
	with open(path, "w", encoding="utf-8") as handle:
		handle.write(f"{until}\n")
	# Older than the settle time, as a file the shell finished writing is.
	stamp = time.time() - age
	os.utime(path, (stamp, stamp))
	return path


class _Quiet:
	def __enter__(self):
		self.original = dcb.send_message
		dcb.send_message = MagicMock()
		return dcb.send_message

	def __exit__(self, *exc):
		dcb.unmute()
		dcb.send_message = self.original


def test_the_script_line_mutes_the_bot_and_the_file_is_consumed():
	with _Quiet():
		path = _write(int(time.time()) + 600)
		dcb.check_external_mute()
		assert dcb.is_muted()
		assert 590 <= dcb._mute_until() - time.time() <= 600
		assert not os.path.exists(path)
		assert dcb._unmute_timer is not None


def test_the_file_shortens_a_longer_mute():
	"""extend_only=False semantics: what the script writes always wins."""
	with _Quiet():
		dcb.mute(480)
		_write(int(time.time()) + 120)
		dcb.check_external_mute()
		assert dcb._mute_until() - time.time() <= 120


def test_the_file_lengthens_a_shorter_mute():
	with _Quiet():
		dcb.mute(5)
		_write(int(time.time()) + 3600)
		dcb.check_external_mute()
		assert dcb._mute_until() - time.time() > 3500


def test_a_past_time_or_zero_unmutes():
	with _Quiet():
		dcb.mute(60)
		_write(0)
		dcb.check_external_mute()
		assert not dcb.is_muted()


def test_a_file_still_being_written_is_left_for_the_next_pass():
	with _Quiet():
		path = _write(int(time.time()) + 600, age=0)
		dcb.check_external_mute()
		assert not dcb.is_muted()
		assert os.path.exists(path)
		os.remove(path)


def test_garbage_is_removed_without_muting():
	with _Quiet():
		path = _write("not-a-number")
		dcb.check_external_mute()
		assert not dcb.is_muted()
		assert not os.path.exists(path)


def test_an_absurd_time_is_capped_like_mute():
	with _Quiet():
		_write(int(time.time()) + 10 ** 9)
		dcb.check_external_mute()
		assert dcb._mute_until() - time.time() <= dcb.MUTE_MAX_MINUTES * 60
