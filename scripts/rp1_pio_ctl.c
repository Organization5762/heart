// SPDX-License-Identifier: MIT
#include <errno.h>
#include <fcntl.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <unistd.h>

#define DEFAULT_DEV_PATH "/dev/pio0"
#define RP1_PIO_SM_COUNT 4
#define PIO_IOC_MAGIC 102

struct rp1_pio_sm_claim_args {
    uint16_t mask;
};

struct rp1_pio_sm_set_enabled_args {
    uint16_t mask;
    uint8_t enable;
    uint8_t rsvd;
};

struct rp1_pio_sm_clear_fifos_args {
    uint16_t sm;
};

struct rp1_pio_remove_program_args {
    uint16_t num_instrs;
    uint16_t origin;
};

#define PIO_IOC_SM_CLAIM _IOW(PIO_IOC_MAGIC, 20, struct rp1_pio_sm_claim_args)
#define PIO_IOC_SM_UNCLAIM _IOW(PIO_IOC_MAGIC, 21, struct rp1_pio_sm_claim_args)
#define PIO_IOC_SM_SET_ENABLED _IOW(PIO_IOC_MAGIC, 37, struct rp1_pio_sm_set_enabled_args)
#define PIO_IOC_SM_CLEAR_FIFOS _IOW(PIO_IOC_MAGIC, 33, struct rp1_pio_sm_clear_fifos_args)
#define PIO_IOC_REMOVE_PROGRAM _IOW(PIO_IOC_MAGIC, 12, struct rp1_pio_remove_program_args)

struct program_spec {
    uint16_t origin;
    uint16_t length;
};

static void usage(const char *argv0)
{
    fprintf(stderr,
            "Usage: %s [options]\n"
            "\n"
            "Options:\n"
            "  --dev PATH                 PIO device path (default: %s)\n"
            "  --claim SMS                Claim SMs: all | 0,1 | 0x3\n"
            "  --unclaim SMS              Unclaim SMs: all | 0,1 | 0x3\n"
            "  --enable SMS               Enable SMs: all | 0,1 | 0x3\n"
            "  --disable SMS              Disable SMs: all | 0,1 | 0x3\n"
            "  --clear-fifos SMS          Clear FIFOs for listed SMs\n"
            "  --remove-program O:L       Remove program at origin O with length L\n"
            "  --help                     Show this help\n"
            "\n"
            "Examples:\n"
            "  %s --disable all --unclaim all\n"
            "  %s --claim 0 --clear-fifos 0\n"
            "  %s --remove-program 16:14 --remove-program 0:16\n",
            argv0,
            DEFAULT_DEV_PATH,
            argv0,
            argv0,
            argv0);
}

static int xioctl(int fd, unsigned long req, void *arg, const char *label)
{
    int ret;

    do {
        ret = ioctl(fd, req, arg);
    } while (ret < 0 && errno == EINTR);

    if (ret < 0) {
        fprintf(stderr, "%s: %s\n", label, strerror(errno));
        return -errno;
    }
    return ret;
}

static int parse_sm_mask(const char *text, uint16_t *mask_out)
{
    char *end = NULL;
    char *copy = NULL;
    char *token = NULL;
    char *save = NULL;
    uint16_t mask = 0;

    if (strcmp(text, "all") == 0) {
        *mask_out = (1u << RP1_PIO_SM_COUNT) - 1u;
        return 0;
    }

    errno = 0;
    unsigned long numeric = strtoul(text, &end, 0);
    if (errno == 0 && end != NULL && *end == '\0') {
        if (numeric > UINT16_MAX) {
            return -ERANGE;
        }
        *mask_out = (uint16_t)numeric;
        return 0;
    }

    copy = strdup(text);
    if (copy == NULL) {
        return -ENOMEM;
    }

    for (token = strtok_r(copy, ",", &save); token != NULL;
         token = strtok_r(NULL, ",", &save)) {
        errno = 0;
        unsigned long sm = strtoul(token, &end, 10);
        if (errno != 0 || end == token || *end != '\0' || sm >= RP1_PIO_SM_COUNT) {
            free(copy);
            return -EINVAL;
        }
        mask |= (uint16_t)(1u << sm);
    }

    free(copy);
    *mask_out = mask;
    return 0;
}

static int parse_remove_spec(const char *text, struct program_spec *spec)
{
    char *copy = strdup(text);
    char *sep = NULL;
    char *end = NULL;
    unsigned long origin = 0;
    unsigned long length = 0;

    if (copy == NULL) {
        return -ENOMEM;
    }
    sep = strchr(copy, ':');
    if (sep == NULL) {
        free(copy);
        return -EINVAL;
    }
    *sep = '\0';

    errno = 0;
    origin = strtoul(copy, &end, 0);
    if (errno != 0 || end == copy || *end != '\0' || origin > UINT16_MAX) {
        free(copy);
        return -EINVAL;
    }

    errno = 0;
    length = strtoul(sep + 1, &end, 0);
    if (errno != 0 || end == sep + 1 || *end != '\0' || length > UINT16_MAX) {
        free(copy);
        return -EINVAL;
    }

    free(copy);
    spec->origin = (uint16_t)origin;
    spec->length = (uint16_t)length;
    return 0;
}

static int set_enabled_mask(int fd, uint16_t mask, bool enable)
{
    struct rp1_pio_sm_set_enabled_args args = {
        .mask = mask,
        .enable = enable ? 1 : 0,
    };

    return xioctl(fd, PIO_IOC_SM_SET_ENABLED, &args,
                  enable ? "PIO_IOC_SM_SET_ENABLED(enable)"
                         : "PIO_IOC_SM_SET_ENABLED(disable)");
}

static int clear_fifos_mask(int fd, uint16_t mask)
{
    unsigned int sm;

    for (sm = 0; sm < RP1_PIO_SM_COUNT; sm++) {
        if ((mask & (1u << sm)) == 0) {
            continue;
        }
        struct rp1_pio_sm_clear_fifos_args args = {
            .sm = (uint16_t)sm,
        };
        int ret = xioctl(fd, PIO_IOC_SM_CLEAR_FIFOS, &args, "PIO_IOC_SM_CLEAR_FIFOS");
        if (ret < 0) {
            return ret;
        }
    }
    return 0;
}

int main(int argc, char **argv)
{
    const char *dev_path = DEFAULT_DEV_PATH;
    struct program_spec remove_specs[32];
    size_t remove_count = 0;
    uint16_t claim_mask = 0;
    uint16_t unclaim_mask = 0;
    uint16_t enable_mask = 0;
    uint16_t disable_mask = 0;
    uint16_t clear_fifos = 0;
    bool do_claim = false;
    bool do_unclaim = false;
    bool do_enable = false;
    bool do_disable = false;
    bool do_clear_fifos = false;
    int fd;
    int ret = 0;
    int i;

    for (i = 1; i < argc; i++) {
        if (strcmp(argv[i], "--help") == 0) {
            usage(argv[0]);
            return 0;
        } else if (strcmp(argv[i], "--dev") == 0 && i + 1 < argc) {
            dev_path = argv[++i];
        } else if (strcmp(argv[i], "--claim") == 0 && i + 1 < argc) {
            ret = parse_sm_mask(argv[++i], &claim_mask);
            do_claim = (ret == 0);
        } else if (strcmp(argv[i], "--unclaim") == 0 && i + 1 < argc) {
            ret = parse_sm_mask(argv[++i], &unclaim_mask);
            do_unclaim = (ret == 0);
        } else if (strcmp(argv[i], "--enable") == 0 && i + 1 < argc) {
            ret = parse_sm_mask(argv[++i], &enable_mask);
            do_enable = (ret == 0);
        } else if (strcmp(argv[i], "--disable") == 0 && i + 1 < argc) {
            ret = parse_sm_mask(argv[++i], &disable_mask);
            do_disable = (ret == 0);
        } else if (strcmp(argv[i], "--clear-fifos") == 0 && i + 1 < argc) {
            ret = parse_sm_mask(argv[++i], &clear_fifos);
            do_clear_fifos = (ret == 0);
        } else if (strcmp(argv[i], "--remove-program") == 0 && i + 1 < argc) {
            if (remove_count >= (sizeof(remove_specs) / sizeof(remove_specs[0]))) {
                fprintf(stderr, "too many --remove-program entries\n");
                return 1;
            }
            ret = parse_remove_spec(argv[++i], &remove_specs[remove_count]);
            if (ret == 0) {
                remove_count++;
            }
        } else {
            usage(argv[0]);
            return 1;
        }

        if (ret < 0) {
            fprintf(stderr, "invalid argument near '%s'\n", argv[i]);
            return 1;
        }
    }

    fd = open(dev_path, O_RDWR | O_CLOEXEC);
    if (fd < 0) {
        perror("open");
        return 1;
    }

    if (do_disable) {
        ret = set_enabled_mask(fd, disable_mask, false);
        if (ret < 0) {
            close(fd);
            return 1;
        }
        printf("disabled SM mask 0x%04x\n", disable_mask);
    }

    if (do_clear_fifos) {
        ret = clear_fifos_mask(fd, clear_fifos);
        if (ret < 0) {
            close(fd);
            return 1;
        }
        printf("cleared FIFOs for SM mask 0x%04x\n", clear_fifos);
    }

    for (size_t idx = 0; idx < remove_count; idx++) {
        struct rp1_pio_remove_program_args args = {
            .num_instrs = remove_specs[idx].length,
            .origin = remove_specs[idx].origin,
        };
        ret = xioctl(fd, PIO_IOC_REMOVE_PROGRAM, &args, "PIO_IOC_REMOVE_PROGRAM");
        if (ret < 0) {
            close(fd);
            return 1;
        }
        printf("removed program origin=%u length=%u\n",
               (unsigned)remove_specs[idx].origin,
               (unsigned)remove_specs[idx].length);
    }

    if (do_unclaim) {
        struct rp1_pio_sm_claim_args args = {
            .mask = unclaim_mask,
        };
        ret = xioctl(fd, PIO_IOC_SM_UNCLAIM, &args, "PIO_IOC_SM_UNCLAIM");
        if (ret < 0) {
            close(fd);
            return 1;
        }
        printf("unclaimed SM mask 0x%04x\n", unclaim_mask);
    }

    if (do_claim) {
        struct rp1_pio_sm_claim_args args = {
            .mask = claim_mask,
        };
        ret = xioctl(fd, PIO_IOC_SM_CLAIM, &args, "PIO_IOC_SM_CLAIM");
        if (ret < 0) {
            close(fd);
            return 1;
        }
        printf("claimed SM mask 0x%04x\n", claim_mask);
    }

    if (do_enable) {
        ret = set_enabled_mask(fd, enable_mask, true);
        if (ret < 0) {
            close(fd);
            return 1;
        }
        printf("enabled SM mask 0x%04x\n", enable_mask);
    }

    close(fd);
    return 0;
}
