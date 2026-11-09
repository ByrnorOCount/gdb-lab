# Return-to-libc — Demonstration Script

Timed for about 7 minutes. Use the spoken lines as prompts, not as a word-for-word speech. The commands below assume the WSL lab directory contains `vuln.out` and `build_payload.py`.

---

## Before the demo

- Compile the 32-bit program and verify the build matches the one you tested.
- Check the `GNU_STACK` line with `readelf -l vuln.out`; `RW` with no `E` means the stack is not executable.
- Disable ASLR only for the demo environment if needed, and know how to turn it back on afterward.
- Have the addresses for this run ready, or be ready to find them in GEF. They can change with the binary, libc, or ASLR setting.
- Keep a terminal recording or a known-good command available as a backup.

## 1. Connect it to the earlier labs — about 45 seconds

**Say:**

"This builds on the `sess2` labs. We looked at where stack and heap variables live and how their addresses can change; we used an overflow to affect a nearby flag; we looked at changing the program's control flow; and we examined how byte order affects a value in memory. Today I’m combining those ideas: the overflow will reach the saved return address, but instead of jumping to code I put on the stack, I’ll redirect execution to `system()` that is already in libc."

**Show:** `aslr.c`, `flag.c`, `flow.c`, and `pattern.c` briefly if needed. Do not spend time re-running all four labs.

## 2. Establish the constraint — about 45 seconds

**Run:**

```bash
readelf -l vuln.out | grep -A1 GNU_STACK
```

**Say:**

"The stack is marked `RW`, with no `E` execute flag. That is the ELF program header’s request for a non-executable stack. So putting shellcode in the buffer and trying to run it is not the plan. NX does not stop every buffer overflow; it stops execution from memory marked non-executable."

## 3. Show the vulnerable program and breakpoint — about 1 minute

**Show:** `vuln.c`, especially the fixed-size buffer and `strcpy`.

**Say:**

"`strcpy` has no destination-size check. A long argument can go past the local buffer and overwrite saved stack data, including the saved return address. The exact offset depends on this compiled function’s stack layout, so I checked the disassembly rather than assuming the buffer size is the return-address offset."

**At the GEF prompt:**

```gdb
break *(vuln+0x25)
run AAAA
```

**Say:**

"For this build, `vuln+0x25` lands on the instruction immediately after `strcpy` and its stack cleanup. The breakpoint lets us inspect the copied bytes before the function returns. That offset is specific to this build; the disassembly is the evidence."

## 4. Find the existing code and argument — about 1 minute

**At the GEF prompt:**

```gdb
print system
print exit
find &system,+99999999,"/bin/sh"
```

**Say:**

"I need three values: the address of `system()`, the address of `exit()` to use as `system()`’s return address, and the address of the `/bin/sh` string to pass as its argument. These are addresses in this process, so I use the values from this run rather than copying an example from the notes."

## 5. Explain and run the payload builder — about 1 minute

**Run in a second WSL terminal, or after leaving GDB:**

```bash
python3 build_payload.py <system_addr> <exit_addr> <binsh_addr>
```

Replace each placeholder with the corresponding value GEF printed.

**Say:**

"The Python script does not exploit anything by itself. It converts the three hexadecimal addresses to four-byte little-endian values, adds 76 `A` bytes to reach the saved return address, and prints commands that pass those bytes to the vulnerable program. One command launches it directly; the other is for GDB so the payload is the inferior’s argument and we can stop at our breakpoint."

## 6. Inspect the stack and finish the run — about 1 minute

**At the GEF prompt, run the GDB command printed by `build_payload.py`. At the breakpoint:**

```gdb
x/32xw $esp
```

**Say:**

"Each displayed word is four bytes. The first 76 bytes are the padding, shown as 19 words of `0x41414141`. The next three words should match `system()`, `exit()`, and the `/bin/sh` string address. This is the same payload we just built, now visible in memory before the return instruction uses it."

**Then:**

```gdb
continue
```

If you prefer the direct-run command instead, leave GDB and run the first command printed by the builder in the WSL shell.

**At the resulting shell:**

```sh
id
pwd
uname -m
exit
```

**Say:**

"`id` shows which user this shell runs as. Mine is running with my normal user’s privileges; the point is that the redirected call worked, not that it became root. No instructions were executed from the stack."

## 7. Close with the defenses — about 45 seconds

**Say:**

"This lab turns off ASLR and stack protection to make the mechanism visible and repeatable. NX is still on. In a real build, ASLR makes addresses unpredictable, canaries can detect a stack overwrite before the return, and PIE randomizes the main program’s code too. The lasting lesson is the difference between executing injected bytes and redirecting control to code that is already executable."

---

## What the runbook and builder mean

`RUNBOOK.md` is the checklist for preparing and performing the demo. Its compile flags are deliberate: `-m32` builds a 32-bit program; `-g` adds debug information for GDB; `-fno-stack-protector` disables the canary for this teaching binary; and `-no-pie` keeps the program’s own code at fixed addresses. The command deliberately does not use `-z execstack`, so it does not request an executable stack. The ASLR step changes address randomization for the environment and should be reversed after the demo if it was changed system-wide.

The runbook’s disassembly step is how the 76-byte offset is checked. In the shown build, `buffer` begins at `ebp-0x48` and the saved return address is at `ebp+4`, a difference of `0x4c`, or 76 bytes. Confirm this against the current binary; compiler options and code changes can alter the layout. Likewise, `break *(vuln+0x25)` is valid only when that offset lands after `strcpy` in the current disassembly.

`build_payload.py` accepts the three addresses, converts each to a four-byte little-endian value, and joins them after `b"A" * OFFSET`. Little-endian means the low-order byte comes first; for example, `0xf7dc8ce0` appears in memory as `e0 8c dc f7`. With a 76-byte offset and three four-byte values, the payload is 88 bytes total.

The builder prints two command forms. The `subprocess.run([...])` form launches `vuln.out` directly from Python. The GDB form uses Python to write raw payload bytes to stdout; shell command substitution supplies those bytes as the argument to GDB’s `run`, keeping the vulnerable process under GDB so the breakpoint and stack inspection work. Use the addresses printed by GEF in the same run; sample addresses in notes are examples, not constants.
