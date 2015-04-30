import time

def usec2sec(usec):
	return usec / 1000000.

class migration_stats:
	def __init__(self):
		self._iter_fr_times = []
		self._frozen_time = 0

	def start(self):
		self._start_time = time.time()

	def stop(self, iters):
		self._rst_time = iters.th.restore_time()
		self._img_sync_time = iters.img.img_sync_time()
		self._end_time = time.time()

		self._print_stats()

	def iteration(self, stats):
		print "Dumped %d pages, %d skipped" % \
				(stats.pages_written, stats.pages_skipped_parent)

		self._iter_fr_times.append("%.2lf" % usec2sec(stats.frozen_time))
		self._frozen_time += stats.frozen_time

	def _print_stats(self):
		print "Migration succeeded"
		print "\t   total time is ~%.2lf sec" % (self._end_time - self._start_time)
		print "\t  frozen time is ~%.2lf sec (" % usec2sec(self._frozen_time), self._iter_fr_times, ")"
		print "\t restore time is ~%.2lf sec" % usec2sec(self._rst_time)
		print "\timg sync time is ~%.2lf sec" % (self._img_sync_time)
