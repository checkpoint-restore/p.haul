#include <unistd.h>
#include <errno.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <sys/mman.h>
#include <signal.h>
#include <fcntl.h>
#include <stdio.h>

#ifndef PAGE_SIZE
#define PAGE_SIZE	4096
#endif

#ifndef CLONE_NEWPID
#define CLONE_NEWPID	0x20000000
#endif

#define STK_SIZE	(16 * PAGE_SIZE)
#define FIN_FILE	"mem-touch-stop"

struct child_arg {
	char *logfile;
	unsigned long mem;		/* amount of mem to map */
	unsigned long mem_pre;		/* amount of mem to randomly pre-touch */
	unsigned long mem_pause;	/* pause between touching pages */

	int pipe[2];
};

static void print_mem(char *s, unsigned long p)
{
	unsigned long size;
	char *sf = "KMG???";

	size = (p <<= 12) >> 10;
	while (size >> 10) {
		size >>= 10;
		sf++;
	}

	printf("%s %lu%c\n", s, size, *sf);
}

static unsigned long mem_pages(char *s, char **end)
{
	unsigned long size;

	printf("%s\n", s);

	size = strtol(s, end, 0);
	if (**end == 'g' || **end == 'G')
		size <<= 30;
	else if (**end == 'm' || **end == 'M')
		size <<= 20;
	else if (**end == 'k' || **end == 'K')
		size <<= 10;
	else
		(*end)--;

	printf("\t%lu\n", size);
	size = (size + PAGE_SIZE - 1) / PAGE_SIZE;
	printf("\t%lu\n", size);
	(*end) += 2;
	return size;
}

static void touch_random_page(char *mem, char *chk, unsigned long max_pfn)
{
	unsigned long pfn;
	char c;

	pfn = random() % max_pfn;
	c = random();
	mem[pfn << 12] = c;
	chk[pfn] = c;
}

static int do_mem_touch(void *arg)
{
	struct child_arg *c = arg;
	int i;
	char *mem, *chk, ec;

	srand(time(NULL));
	close(c->pipe[0]);

	setsid();

	ec = 'L';
	i = open(c->logfile, O_WRONLY | O_CREAT | O_TRUNC, 0666);
	if (i == -1)
		goto err;

	close(0);
	dup2(i, 1);
	dup2(i, 2);
	close(255); /* bash */
	close(i);

	ec = 'M';
	print_mem("Mapping", c->mem);
	mem = mmap(NULL, c->mem * PAGE_SIZE,
			PROT_READ | PROT_WRITE, MAP_PRIVATE | MAP_ANON, 0, 0);
	if (mem == MAP_FAILED)
		goto err;

	printf("Created %#p vma\n", mem);

	chk = malloc(c->mem);
	memset(chk, 0, c->mem);

	print_mem("Pre-touching", c->mem_pre);
	for (i = 0; i < c->mem_pre; i++)
		touch_random_page(mem, chk, c->mem);

	printf("Done\n");
	ec = 'O';
	write(c->pipe[1], &ec, 1);
	close(c->pipe[1]);

	printf("Touch 1 page per %lu usec\n", c->mem_pause);
	while (access(FIN_FILE, R_OK) != 0) {
		usleep(c->mem_pause);
		touch_random_page(mem, chk, c->mem);
	}

	printf("Finish\n");
	for (i = 0; i < c->mem; i++)
		if (chk[i] != mem[i << 12])
			printf("\tMismatch %d %c != %c\n",
					i, chk[i], mem[i << 12]);

err:
	write(c->pipe[1], &ec, 1);
	close(c->pipe[1]);
	exit(1);
}

int main(int argc, char **argv)
{
	int pid;
	void *stk;
	char c = '\0', *aux;
	struct child_arg a;

	a.logfile = argv[1];
	a.mem = mem_pages(argv[2], &aux);
	a.mem_pre = mem_pages(aux, &aux);
	a.mem_pause = strtol(aux, NULL, 10);

	pipe(a.pipe);

	stk = mmap(NULL, STK_SIZE, PROT_READ | PROT_WRITE,
			MAP_PRIVATE | MAP_ANON | MAP_GROWSDOWN, 0, 0);
	pid = clone(do_mem_touch, stk + STK_SIZE, SIGCHLD | CLONE_NEWPID, &a);

	close(a.pipe[1]);
	read(a.pipe[0], &c, 1);
	close(a.pipe[0]);

	printf("Child %d done, code %c\n", pid, c);
	if (c != 'O') {
		printf("Waiting for it\n");
		wait(NULL);
	}

	return 0;
}
