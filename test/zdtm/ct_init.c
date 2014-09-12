#define _GNU_SOURCE
#include <sched.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <stdlib.h>
#include <stdio.h>
#include <sys/mount.h>
#include <unistd.h>
#include <fcntl.h>

int main(int argc, char **argv)
{
	int fd, start[2];
	char res;
	pid_t pid;

	/*
	 * Usage:
	 * run <log> <pid> <cmd> <args>
	 */

	if (unshare(CLONE_NEWNS | CLONE_NEWPID | CLONE_NEWNET | CLONE_NEWIPC))
		return 1;

	pipe(start);
	pid = fork();
	if (pid == 0) {
		if (setsid() == -1) {
			fprintf(stderr, "setsid: %m\n");
			return 1;
		}

		fd = open(argv[1], O_WRONLY|O_CREAT|O_TRUNC|O_APPEND, 0600);
		if (fd < 0)
			return 1;

		dup2(fd, 1);
		dup2(fd, 2);
		close(fd);
		close(0);

		close(start[0]);
		dup2(start[1], 3);
		close(start[1]);

		if (mount(NULL, "/", NULL, MS_REC | MS_PRIVATE, NULL)) {
			fprintf(stderr, "mount(/, S_REC | MS_PRIVATE)): %m");
			return 1;
		}
		umount2("/proc", MNT_DETACH);
		if (mount("zdtm_proc", "/proc", "proc", 0, NULL)) {
			fprintf(stderr, "mount(/proc): %m");
			return 1;
		}

		execv(argv[3], argv + 3);
		fprintf(stderr, "execve: %m");
		return 1;
	}

	close(start[1]);
	res = 'F';
	read(start[0], &res, 1);
	if (res != '!') {
		printf("Failed to start\n");
		return 1;
	}

	printf("Container w/ tests started\n");
	{
		FILE *pidf;
		pidf = fopen(argv[2], "w");
		fprintf(pidf, "%d", pid);
		fclose(pidf);
	}
	return 0;
}
