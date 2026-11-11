# Return-to-libc - Q&A Prep

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
