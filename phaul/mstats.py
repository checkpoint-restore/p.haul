import time
import logging


def usec2sec(usec):
	return usec / 1000000.


class fs_iter_stats:
	def __init__(self, bytes_xferred):
		self.bytes_xferred = bytes_xferred


class migration_stats:
	def __init__(self):
		self._iter_fr_times = []
		self._frozen_time = 0

	def start(self):
		self._start_time = time.time()

	def stop(self, iters):
		self._rst_time = iters.get_target_host().restore_time()
		self._img_sync_time = iters.img.img_sync_time()
		self._end_time = time.time()

		self._print_stats()

	def iteration(self, stats):
		logging.info("Dumped %d pages, %d skipped",
			stats.pages_written, stats.pages_skipped_parent)

		self._iter_fr_times.append("%.2lf" % usec2sec(stats.frozen_time))
		self._frozen_time += stats.frozen_time

	def _print_stats(self):
		logging.info("Migration succeeded")
		logging.info("\t   total time is ~%.2lf sec", self._end_time - self._start_time)
		logging.info("\t  frozen time is ~%.2lf sec (%s)", usec2sec(self._frozen_time), str(self._iter_fr_times))
		logging.info("\t restore time is ~%.2lf sec", usec2sec(self._rst_time))
		logging.info("\timg sync time is ~%.2lf sec", self._img_sync_time)
