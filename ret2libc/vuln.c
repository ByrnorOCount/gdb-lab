#include <stdio.h>
#include <string.h>

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
