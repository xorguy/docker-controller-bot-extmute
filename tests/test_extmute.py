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
import commands


def _write(until, age=5):
	path = os.path.join(store.root(), dcb.EXTERNAL_MUTE_FILE)
	with open(path, "w", encoding="utf-8") as handle:
		handle.write(f"{until}\n")
	# Older than the settle time, as a file the shell finished writing is.
	stamp = time.time() - age
	os.utime(path, (stamp, stamp))
	return path


def _poll():
	"""One watcher pass with no file: what the thread does between changes."""
	dcb.check_external_mute()


class _Quiet:
	def __enter__(self):
		self.original = dcb.send_message
		dcb.send_message = MagicMock()
		_poll()
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


def test_the_file_shortens_an_earlier_longer_mute():
	"""Latest change wins: a /mute from a previous poll is replaced."""
	with _Quiet():
		commands.cmd_mute(argument="480")
		_poll()
		_write(int(time.time()) + 120)
		dcb.check_external_mute()
		assert 0 < dcb._mute_until() - time.time() <= 120


def test_the_file_lengthens_an_earlier_shorter_mute():
	with _Quiet():
		commands.cmd_mute(argument="5")
		_poll()
		_write(int(time.time()) + 3600)
		dcb.check_external_mute()
		assert dcb._mute_until() - time.time() > 3500


def test_a_telegram_mute_after_the_script_replaces_it():
	"""/mute in Telegram still works, and as the latest change it wins, shorter too."""
	with _Quiet():
		_write(int(time.time()) + 7200)
		dcb.check_external_mute()
		commands.cmd_mute(argument="10")
		_poll()
		assert 0 < dcb._mute_until() - time.time() <= 600


def test_at_the_same_time_the_longer_telegram_mute_is_kept():
	"""/mute and the file in the same poll window: the longer one stays."""
	with _Quiet():
		_write(int(time.time()) + 120)
		commands.cmd_mute(argument="480")
		dcb.check_external_mute()
		assert dcb._mute_until() - time.time() > 470 * 60


def test_at_the_same_time_the_longer_script_mute_is_kept():
	with _Quiet():
		_write(int(time.time()) + 7200)
		commands.cmd_mute(argument="10")
		dcb.check_external_mute()
		assert dcb._mute_until() - time.time() > 7000


def test_a_script_unmute_ends_a_telegram_mute():
	with _Quiet():
		commands.cmd_mute(argument="60")
		_poll()
		_write(0)
		dcb.check_external_mute()
		assert not dcb.is_muted()


def test_a_script_unmute_is_honoured_even_at_the_same_time():
	with _Quiet():
		commands.cmd_mute(argument="60")
		_write(0)
		dcb.check_external_mute()
		assert not dcb.is_muted()


def test_a_telegram_unmute_ends_a_script_mute():
	with _Quiet():
		_write(int(time.time()) + 3600)
		dcb.check_external_mute()
		commands.cmd_mute(argument="0")
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
