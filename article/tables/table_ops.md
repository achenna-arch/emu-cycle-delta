Table: Operations on the useful reading
| Operation | Cycles | Instructions | Cycles per instruction | Layout spread (%) | Floor (%) | Past 2 % | Missed |
|---|---|---|---|---|---|---|---|
| `irq.exit` | 56 | 20 | 2.80 | 11.0 | 11.0 | 0 | 0 |
| `condvar.signal` | 55 | 20 | 2.72 | 9.2 | 11.2 | 6 | 3 |
| `mutex.unlock` | 96 | 41 | 2.22 | 8.3 | 12.9 | 8 | 6 |
| `irq.round_trip` | 111 | 36 | 3.08 | 8.1 | 10.1 | 9 | 8 |
| `msgq.put_get` | 257 | 135 | 1.91 | 7.5 | 14.5 | 11 | 9 |
| `irq.enter` | 51 | 15 | 3.40 | 6.4 | 11.7 | 9 | 9 |
| `stack.push_pop` | 123 | 54 | 2.28 | 4.2 | 7.3 | 10 | 6 |
| `mutex.lock` | 80 | 31 | 2.48 | 3.8 | 7.6 | 5 | 3 |
| `lifo.put_get` | 175 | 84 | 2.14 | 3.5 | 5.2 | 4 | 1 |
| `fifo.put_get` | 172 | 86 | 2.05 | 3.4 | 5.6 | 3 | 0 |
| `event.post_wait` | 237 | 110 | 2.20 | 3.0 | 5.8 | 7 | 6 |
| `thread.spawn` | 1,719 | 732 | 2.35 | 1.8 | 2.7 | 0 | 0 |
| `heap.alloc_free` | 773 | 367 | 2.11 | 1.8 | 2.0 | 4 | 4 |
| `sem.wake` | 1,367 | 570 | 2.41 | 1.4 | 3.3 | 3 | 2 |
| `yield.switch` | 1,971 | 823 | 2.44 | 1.3 | 2.7 | 1 | 1 |
| `sem.give` | 54 | 23 | 2.35 | 0.0 | 5.6 | 4 | 1 |
| `sem.take` | 51 | 23 | 2.22 | 0.0 | 5.9 | 1 | 0 |
Note: Cycles and instructions are medians of the parent images as compiled. Past 2 % and Missed count cells on R1.
