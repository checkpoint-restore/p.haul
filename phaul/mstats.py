import logging
import time


class fs_iter_stats(object):
	def __init__(self, bytes_xferred):
		self.bytes_xferred = bytes_xferred


class live_stats(object):
	def __init__(self):
		self.__start_time = 0.0
		self.__end_time = 0.0
		self.__restore_time = 0
		self.__img_sync_time = 0.0
		self.__iter_frozen_times = []

	def handle_start(self):
		self.__start_time = time.time()

	def handle_preliminary(self, fsstats):
		_print_fsstats(fsstats)

	def handle_iteration(self, dstats, fsstats):
		self.__iter_frozen_times.append(dstats.frozen_time)
		_print_dstats(dstats)
		_print_fsstats(fsstats)

	def handle_stop(self, iters):
		self.__end_time = time.time()
		self.__restore_time = iters.get_target_host().restore_time()
		self.__img_sync_time = iters.img.img_sync_time()
		self.__print_overall()

	def __print_overall(self):

		total_time = self.__end_time - self.__start_time
		restore_time = self.__usec2sec(self.__restore_time)

		frozen_time = 0.0
		frozen_times = []
		for iter_time in self.__iter_frozen_times:
			frozen_time += self.__usec2sec(iter_time)
			frozen_times.append("%.2lf" % self.__usec2sec(iter_time))

		logging.info("\t   total time is ~%.2lf sec", total_time)
		logging.info("\t  frozen time is ~%.2lf sec (%s)", frozen_time,
					str(frozen_times))
		logging.info("\t restore time is ~%.2lf sec", restore_time)
		logging.info("\timg sync time is ~%.2lf sec", self.__img_sync_time)

	def __usec2sec(self, usec):
		return usec / 1000000.


class restart_stats(object):
	def __init__(self):
		self.__start_time = 0.0
		self.__end_time = 0.0

	def handle_start(self):
		self.__start_time = time.time()

	def handle_preliminary(self, fsstats):
		_print_fsstats(fsstats)

	def handle_iteration(self, fsstats):
		_print_fsstats(fsstats)

	def handle_stop(self):
		self.__end_time = time.time()
		self.__print_overall()

	def __print_overall(self):
		logging.info("\t   total time is ~%.2lf sec",
					self.__end_time - self.__start_time)


def _print_dstats(dstats):
	if dstats:
		logging.info("\tDumped %d pages, %d skipped",
					dstats.pages_written, dstats.pages_skipped_parent)


def _print_fsstats(fsstats):
	if fsstats:
		mbytes_xferred_str = ""
		mbytes_xferred = fsstats.bytes_xferred >> 20
		if mbytes_xferred != 0:
			mbytes_xferred_str = " (~{0}Mb)".format(mbytes_xferred)
		logging.info("\tFs driver transfer %d bytes%s",
					fsstats.bytes_xferred, mbytes_xferred_str)
