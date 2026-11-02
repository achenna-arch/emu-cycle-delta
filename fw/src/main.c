/*
 * Kernel latency probes for one commit of Zephyr.
 *
 * The same image runs on silicon and in Renode, and reads CYCCNT in both
 * cases: cycles on the board, retired instructions in Renode, where the
 * DWT model and the CPU model run at the same rate.
 *
 * The registers are addressed directly so that the benchmark builds
 * unchanged across CMSIS versions and kernel commits.
 *
 * QEMU models no DWT: its image reads a free-running MPS2 timer instead, which
 * advances with retired instructions under -icount.
 */

#include <zephyr/kernel.h>
#include <zephyr/irq.h>
#include <zephyr/sys/printk.h>

#define DEMCR      (*(volatile uint32_t *)0xE000EDFCUL)
#define DWT_CTRL   (*(volatile uint32_t *)0xE0001000UL)
#define DWT_CYCCNT (*(volatile uint32_t *)0xE0001004UL)
#define NVIC_ISPR0 (*(volatile uint32_t *)0xE000E200UL)

#define DEMCR_TRCENA  BIT(24)
#define DWT_CYCCNTENA BIT(0)

#define TIMER_CTRL   (*(volatile uint32_t *)0x40000000UL)
#define TIMER_VALUE  (*(volatile uint32_t *)0x40000004UL)
#define TIMER_RELOAD (*(volatile uint32_t *)0x40000008UL)
#define TIMER_ENABLE BIT(0)

#define N              CONFIG_BENCH_SAMPLES
#define HELPER_STACK   1024
#define PRIO_SAME      CONFIG_MAIN_THREAD_PRIORITY
#define PRIO_ABOVE     (CONFIG_MAIN_THREAD_PRIORITY - 1)
#define HEAP_BLOCK     32
#define BENCH_IRQ      CONFIG_BENCH_SW_IRQ
#define BENCH_IRQ_PRIO 1

extern const char bench_pad[];

/* Fixed size: "parent" and "child" must not move .rodata. */
static const char bench_tag[24] = CONFIG_BENCH_TAG;

static uint32_t samples[N];
static volatile uint32_t stamp;
static volatile uint32_t load_word;

K_THREAD_STACK_DEFINE(helper_stack, HELPER_STACK);
static struct k_thread helper;

K_SEM_DEFINE(sem, 0, K_SEM_MAX_LIMIT);
K_MUTEX_DEFINE(mutex);
K_FIFO_DEFINE(fifo);
K_LIFO_DEFINE(lifo);
K_STACK_DEFINE(stack_obj, 4);
K_MSGQ_DEFINE(msgq, sizeof(uint32_t), 4, 4);
K_EVENT_DEFINE(event);
K_CONDVAR_DEFINE(condvar);
K_HEAP_DEFINE(heap, 1024);

static struct {
	void *reserved;
	uint32_t value;
} item;

/*
 * Out of line on purpose: Renode refreshes its instruction count at translation
 * block boundaries, so an inlined read would see a stale value. Here each read
 * sits at the same place in a block of its own, and the offset cancels out.
 */
static __noinline uint32_t now(void)
{
#ifdef CONFIG_BENCH_CMSDK_TIMER
	return ~TIMER_VALUE;
#else
	return DWT_CYCCNT;
#endif
}

static void clock_start(void)
{
#ifdef CONFIG_BENCH_CMSDK_TIMER
	TIMER_RELOAD = UINT32_MAX;
	TIMER_VALUE = UINT32_MAX;
	TIMER_CTRL = TIMER_ENABLE;
#else
	DEMCR |= DEMCR_TRCENA;
	DWT_CYCCNT = 0;
	DWT_CTRL |= DWT_CYCCNTENA;
#endif
}

static void sort_samples(void)
{
	for (int gap = N / 2; gap > 0; gap /= 2) {
		for (int i = gap; i < N; i++) {
			uint32_t v = samples[i];
			int j = i;

			while (j >= gap && samples[j - gap] > v) {
				samples[j] = samples[j - gap];
				j -= gap;
			}
			samples[j] = v;
		}
	}
}

static void report(const char *name)
{
	uint64_t sum = 0;

	for (int i = 0; i < N; i++) {
		sum += samples[i];
	}
	sort_samples();
	printk("R,%s,%d,%u,%u,%u,%u,%u,%u\n", name, N, samples[0], samples[N / 10],
	       samples[N / 2], samples[N * 9 / 10], samples[N - 1], (uint32_t)(sum / N));
}

#define PROBE(name, before, op, after)                                                             \
	do {                                                                                       \
		for (int i = 0; i < N; i++) {                                                      \
			uint32_t t0;                                                               \
			uint32_t t1;                                                               \
                                                                                                   \
			before;                                                                    \
			t0 = now();                                                                \
			op;                                                                        \
			t1 = now();                                                                \
			after;                                                                     \
			samples[i] = t1 - t0;                                                      \
		}                                                                                  \
		report(name);                                                                      \
	} while (false)

static k_tid_t spawn(k_thread_entry_t entry, int prio)
{
	return k_thread_create(&helper, helper_stack, K_THREAD_STACK_SIZEOF(helper_stack), entry,
			       NULL, NULL, NULL, prio, 0, K_NO_WAIT);
}

/* Out of line: the literal pool of a caller would fall out of range. */
static __noinline void alu_block(void)
{
	__asm__ volatile(".rept 1000\n\tadds r0, r0, #1\n\t.endr\n" : : : "r0", "cc");
}

static __noinline void load_block(volatile uint32_t *word)
{
	__asm__ volatile(".rept 1000\n\tldr r1, [%0]\n\t.endr\n" : : "r"(word) : "r1", "memory");
}

static void probe_calibration(void)
{
	PROBE("clock.overhead", , , );
	PROBE("calib.alu", , alu_block(), );
	PROBE("calib.load", , load_block(&load_word), );
}

static void sem_waiter(void *a, void *b, void *c)
{
	for (int i = 0; i < N; i++) {
		k_sem_take(&sem, K_FOREVER);
		samples[i] = now() - stamp;
	}
}

static void probe_sem(void)
{
	PROBE("sem.give", , k_sem_give(&sem), k_sem_take(&sem, K_NO_WAIT));
	PROBE("sem.take", k_sem_give(&sem), k_sem_take(&sem, K_NO_WAIT), );

	k_tid_t t = spawn(sem_waiter, PRIO_ABOVE);

	for (int i = 0; i < N; i++) {
		stamp = now();
		k_sem_give(&sem);
	}
	k_thread_join(t, K_FOREVER);
	report("sem.wake");
}

static void yield_peer(void *a, void *b, void *c)
{
	for (int i = 0; i < N; i++) {
		samples[i] = now() - stamp;
		k_yield();
	}
}

static void probe_yield(void)
{
	k_tid_t t = spawn(yield_peer, PRIO_SAME);

	for (int i = 0; i < N; i++) {
		stamp = now();
		k_yield();
	}
	k_thread_join(t, K_FOREVER);
	report("yield.switch");
}

static void probe_objects(void)
{
	uint32_t value = 0;
	stack_data_t popped;
	void *block;

	PROBE("mutex.lock", , k_mutex_lock(&mutex, K_FOREVER), k_mutex_unlock(&mutex));
	PROBE("mutex.unlock", k_mutex_lock(&mutex, K_FOREVER), k_mutex_unlock(&mutex), );
	PROBE("fifo.put_get", , (k_fifo_put(&fifo, &item), (void)k_fifo_get(&fifo, K_NO_WAIT)), );
	PROBE("lifo.put_get", , (k_lifo_put(&lifo, &item), (void)k_lifo_get(&lifo, K_NO_WAIT)), );
	PROBE("stack.push_pop", ,
	      ((void)k_stack_push(&stack_obj, 1), (void)k_stack_pop(&stack_obj, &popped, K_NO_WAIT)), );
	PROBE("msgq.put_get", ,
	      ((void)k_msgq_put(&msgq, &value, K_NO_WAIT),
	       (void)k_msgq_get(&msgq, &value, K_NO_WAIT)), );
	PROBE("event.post_wait", ,
	      ((void)k_event_post(&event, 1), (void)k_event_wait(&event, 1, false, K_NO_WAIT)),
	      (void)k_event_clear(&event, 1));
	PROBE("condvar.signal", , (void)k_condvar_signal(&condvar), );
	PROBE("heap.alloc_free", ,
	      (block = k_heap_alloc(&heap, HEAP_BLOCK, K_NO_WAIT), k_heap_free(&heap, block)), );
}

static void spawn_entry(void *a, void *b, void *c)
{
	stamp = now();
}

static void probe_thread(void)
{
	for (int i = 0; i < N; i++) {
		uint32_t t0 = now();
		k_tid_t t = spawn(spawn_entry, PRIO_ABOVE);

		samples[i] = stamp - t0;
		k_thread_join(t, K_FOREVER);
	}
	report("thread.spawn");
}

static void isr_hook(const void *arg)
{
	stamp = now();
}

/* Pends a spare NVIC line, so the probe takes the real interrupt path. */
static ALWAYS_INLINE void fire_irq(void)
{
	NVIC_ISPR0 = BIT(BENCH_IRQ);
	__asm__ volatile("dsb\n\tisb\n");
}

static void probe_irq(void)
{
	PROBE("irq.round_trip", , fire_irq(), );

	for (int i = 0; i < N; i++) {
		uint32_t t0 = now();

		fire_irq();
		samples[i] = stamp - t0;
	}
	report("irq.enter");

	for (int i = 0; i < N; i++) {
		fire_irq();
		samples[i] = now() - stamp;
	}
	report("irq.exit");
}

int main(void)
{
	/* Keeps the padding through --gc-sections. */
	const char *volatile keep = bench_pad;

	ARG_UNUSED(keep);
	printk("BENCH,START,%s,%s,%d,%d\n", CONFIG_BOARD, bench_tag, CONFIG_BENCH_PAD_BYTES, N);

	IRQ_CONNECT(BENCH_IRQ, BENCH_IRQ_PRIO, isr_hook, NULL, 0);
	irq_enable(BENCH_IRQ);

	clock_start();

	uint32_t before = now();

	alu_block();
	if (now() == before) {
		printk("BENCH,ERROR,NO_COUNTER\n");
		return 0;
	}

	for (int round = 0; round < CONFIG_BENCH_ROUNDS; round++) {
		printk("BENCH,ROUND,%d\n", round);
		probe_calibration();
		probe_sem();
		probe_yield();
		probe_objects();
		probe_thread();
		probe_irq();
	}

	printk("BENCH,DONE\n");
	return 0;
}
