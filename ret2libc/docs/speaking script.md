# Return-to-libc — Speaking Script

Timed for ~7 minutes across 7 slides (~1 min each). This is a script to work from,
not something to read verbatim — say it in your own words, but hit the same beats
in the same order so the timing holds.

---

## Slide 1 — Title

"Today I'm talking about return-to-libc — a way to get arbitrary code to run on a
system even when the stack itself can't execute anything. By the end of this I'll
show it live: turning a simple buffer overflow into a shell, without ever injecting
a single instruction of my own."

_(~15 sec, then move on — don't linger on the title.)_

---

## Slide 2 — Recap: the stack buffer overflow

"Quick recap, since this builds directly on what we've already done. `strcpy` into
a fixed-size buffer with no bounds check — give it a long enough input and it
writes past the buffer, into the return address sitting right after it on the
stack. That's the value a function uses to jump back to wherever it was called
from.

We've already used this twice: redirecting execution into our own code, and
flipping a check by overwriting a variable instead. Same bug both times — just a
different target. Today the target changes again."

_(Point at the diagram while saying "return address.")_

---

## Slide 3 — The wall: NX / DEP

"Here's the complication. Modern systems mark the stack non-executable — the CPU
just refuses to run any instructions stored there, no matter how you jumped in.

The classic way around a protection like a canary is to inject your own code —
shellcode — onto the stack and jump to it. That needs the stack to be executable.
With NX on, that jump just segfaults. So the question becomes: can you still get
arbitrary code to run without ever writing new code onto the stack?"

_(Gesture at the readelf screenshot — "this is what that actually looks like on a
real binary: RW, no execute bit.")_

---

## Slide 4 — The idea: reuse code that's already there

"That's the whole idea behind return-to-libc. Instead of injecting code, you reuse
code that's already loaded and already marked executable — specifically, libc.
Every program that calls printf or strcpy already has libc mapped in. So instead
of jumping to shellcode you wrote, you overwrite the return address to point
directly at a real function — `system()` — and hand it whatever argument you
want.

Nothing new gets executed. You're just redirecting where execution already goes."

---

## Slide 5 — Anatomy of the payload

"Concretely, the payload is four pieces. Padding to reach the return address —
76 bytes for this binary. Then the address of `system()`. Then a second address,
right after it, which `system()` will treat as its own return address — that's
`exit()`, so the program exits cleanly instead of crashing into garbage after
`system()` finishes. And last, the address of the string `/bin/sh`, which becomes
`system()`'s argument.

So `system()` runs, with `/bin/sh` as input — that's a real shell."

_(This is the slide to slow down on — it's the core mechanic.)_

---

## Slide 6 — Why NX can't stop this

"So why does NX let this through? NX's rule is: don't execute memory that isn't
marked executable. It has no opinion about _where_ execution jumps between
functions that already are executable. Return-to-libc never touches the stack as
code — it only ever runs instructions that were already fair game.

You're not writing new code. You're choosing which existing code runs, and in
what order.

Push this idea further — chain many tiny snippets of existing code instead of
whole functions — and that's Return-Oriented Programming, ROP. Same principle,
smaller pieces."

---

## Slide 7 — What actually stops this → transition to demo

"So what does stop this? Three things, mainly. ASLR randomizes where libc loads
each run, so you can't hardcode `system()`'s address anymore. Stack canaries
catch the overflow before the return address is ever reached. And full RELRO
locks down parts of memory that similar tricks depend on.

For this demo, I've turned ASLR off and left the canary off, specifically so you
can see the mechanism clearly — in a real target you'd need to defeat or work
around those first, which is its own topic.

Now let's actually do it."

_(Transition directly into the live demo — switch windows, don't pause for
questions yet. Save Q&A for after the demo lands.)_

---

## After the demo

Once `id` prints a uid and you're sitting in a shell: "That's it — a shell,
spawned entirely by redirecting into code that was already sitting in memory.
No shellcode, no executable stack required." Then open it up for questions.
