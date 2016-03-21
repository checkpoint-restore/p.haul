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

	def handle_start(self):
		self._start_time = time.time()

	def handle_fs_start(self, fsstats):
		self.__print_fsstats(fsstats)

	def handle_stop(self, iters):
		self._rst_time = iters.get_target_host().restore_time()
		self._img_sync_time = iters.img.img_sync_time()
		self._end_time = time.time()
		self.__print_overall_stats()

	def handle_iteration(self, dstats, fsstats):
		self._iter_fr_times.append("%.2lf" % usec2sec(dstats.frozen_time))
		self._frozen_time += dstats.frozen_time
		self.__print_dstats(dstats)
		self.__print_fsstats(fsstats)

	def __print_dstats(self, dstats):
		if dstats:
			logging.info("\tDumped %d pages, %d skipped",
				dstats.pages_written, dstats.pages_skipped_parent)

	def __print_fsstats(self, fsstats):
		if fsstats:
			mbytes_xferred_str = ""
			mbytes_xferred = fsstats.bytes_xferred >> 20
			if mbytes_xferred != 0:
				mbytes_xferred_str = " (~{0}Mb)".format(mbytes_xferred)
			logging.info("\tFs driver transfer %d bytes%s",
				fsstats.bytes_xferred, mbytes_xferred_str)

	def __print_overall_stats(self):
		logging.info("Migration succeeded")
		logging.info("\t   total time is ~%.2lf sec", self._end_time - self._start_time)
		logging.info("\t  frozen time is ~%.2lf sec (%s)", usec2sec(self._frozen_time), str(self._iter_fr_times))
		logging.info("\t restore time is ~%.2lf sec", usec2sec(self._rst_time))
		logging.info("\timg sync time is ~%.2lf sec", self._img_sync_time)
