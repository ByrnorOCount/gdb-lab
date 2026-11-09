# Return-to-libc — Q&A Prep

Short answers to likely questions. The first group sticks to concepts demonstrated in `sess2`; the second connects them to this ret2libc demo.

---

## From the earlier labs

**What is the difference between stack and heap memory?**

The stack holds function-call data such as local variables and saved return addresses. The heap is used for dynamically allocated memory, such as the block returned by `malloc`. The `aslr.c` lab prints example addresses to make the locations visible; ASLR can make addresses vary between runs.

**What does ASLR do?**

Address Space Layout Randomization changes where memory regions are placed, making addresses harder to predict. It does not repair an overflow; it makes hard-coded addresses less reliable. The demo disables it so the addresses stay predictable during the presentation.

**How can an overflow change a flag?**

`strcpy` copies until it reaches a NUL byte and does not know the destination buffer’s capacity. If the input runs past the buffer, it may overwrite adjacent stack data. Whether a particular variable is adjacent, and what gets overwritten, depends on the compiled stack layout; C does not guarantee that layout.

**How is changing a flag different from changing control flow?**

Changing a flag affects data the program later reads. Changing control flow means overwriting a saved return address so the function returns somewhere different. Both can arise from an out-of-bounds write, but the overwritten target and resulting behavior differ.

**What was the `pattern.c` value about?**

It illustrates how bytes in memory correspond to a multi-byte integer. On a little-endian machine, `0x41614262` is stored as bytes `62 42 61 41`. Important caveat: the file declares `pattern` without initializing it, then reads it. That is undefined behavior in C, so its comparison result is not a reliable demonstration unless the variable is initialized or the lab is adjusted.

**Does the buffer size alone tell us the offset to the return address?**

No. The compiler lays out the function’s stack frame, including saved registers and padding. Use the disassembly and confirm with a controlled debugger inspection. In this build, the measured offset is 76 bytes, not simply the 64-byte buffer size.

**Why can an overflow behave differently after recompiling?**

Compiler version, flags, architecture, optimization, and source changes can change the stack layout and addresses. Re-check the disassembly, offset, and runtime addresses after a rebuild.

---

## About this ret2libc demo

**What does ret2libc mean?**

It redirects execution to code that is already loaded in a library, rather than injecting new instructions. Here the target function is `system()`, and its argument is the existing string `/bin/sh`.

**If the stack is non-executable, why can this work?**

NX prevents instruction execution from memory marked non-executable, such as this stack. The overwritten return address points to `system()` in executable library memory; the payload bytes on the stack are data, not instructions.

**What do the three addresses in the payload represent?**

`system()` is the function to call; `exit()` is where `system()` should return; and the address of `/bin/sh` is the argument to `system()`. On 32-bit x86, the stack layout after the overwritten return address supplies the return address and argument in the calling convention expected by the function.

**Why is the offset 76 if the buffer is 64 bytes?**

The offset is measured from the beginning of the buffer to the saved return address, so it includes the rest of the compiled stack-frame layout, not just the array. In the shown disassembly, the buffer is at `ebp-0x48` and the return address at `ebp+4`; the difference is `0x4c`, or 76 bytes. Always confirm it for the binary being demonstrated.

**What does `break *(vuln+0x25)` mean?**

It sets a breakpoint 0x25 bytes (37 decimal) after the start of `vuln`. In the shown disassembly, that is address `0x080491ab`, the `nop` immediately after `strcpy` and its stack cleanup. It is build-specific; verify the target instruction with `disas vuln`.

**Why use `exit()` after `system()`?**

When `system()` returns, the next stack word is treated as its return address. Providing `exit()` gives the process a deliberate next destination instead of an invalid address. If the shell is still running, `system()` has not returned yet.

**What does `id` prove?**

It shows the identity and groups of the shell process. `uid=1000` is a normal unprivileged user in many Linux setups; a successful demo does not need to be root.

**What does `build_payload.py` do, and does it run the exploit?**

It parses the three hexadecimal addresses, encodes each as a 4-byte little-endian value, prepends 76 `A` bytes, and prints commands. It does not itself run the exploit. The direct command launches the program; the GDB command writes raw bytes to stdout so command substitution can pass them to GDB’s `run` command.

**Why does the builder use `b'A'*76` instead of printing 76 `A`s?**

They represent the same padding. The compact expression is easier to read; the address tail remains printed as an escaped bytes literal so the exact bytes are visible.

**Why can’t I just use the direct command when I want a GDB stack dump?**

The direct command launches `vuln.out` as a child of Python, outside GDB. To stop at a GDB breakpoint, use the generated GDB command at the GEF prompt so GDB launches the inferior with the payload argument.

**Why are the addresses different from the example?**

They depend on the machine, libc build, process layout, and ASLR. Use addresses from the same running/debugging setup as the payload. If ASLR is enabled again, addresses may change.

**Does `-no-pie` turn off ASLR?**

No. It keeps this executable’s own code at fixed addresses. ASLR can still randomize libraries and other mappings. The runbook’s ASLR setting is separate.

**Does NX stop buffer overflows?**

No. NX limits execution from non-executable memory. It does not stop an out-of-bounds write from corrupting data or control information.

**Do stack canaries, ASLR, or RELRO all stop this exact technique?**

They address different parts of the problem. A canary can detect some stack overwrites before a function returns. ASLR makes useful addresses harder to predict. PIE randomizes the main executable’s code location. RELRO primarily hardens relocation-related memory such as the GOT; it does not by itself prevent overwriting a saved return address. Defense in depth matters, and bounds checking fixes the underlying bug.

**Why are the compiler flags intentionally weak?**

They isolate the concept for a controlled lab: 32-bit mode makes the word layout easy to inspect, debug symbols help GDB, and disabling the stack protector avoids the canary stopping the demonstration. The stack is still non-executable; the build does not request an executable stack.

**What should be restored after the demo?**

If you changed `kernel.randomize_va_space` system-wide, set it back to the value you normally use (commonly `2`). The runbook calls this out because disabling ASLR affects more than this one program.

---

## Useful closing answer

"The demo is intentionally configured to show one mechanism, not to represent a hardened production build. The earlier labs showed how an overflow can corrupt data or redirect execution; this one shows that NX alone does not prevent reuse of already-executable code. The practical fix is to prevent the out-of-bounds write, then keep compiler and operating-system defenses enabled."
