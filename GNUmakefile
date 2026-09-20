# eucalypt-distro
#
# Top-level orchestration for the eucalypt OS.
#
# Pipeline: tools (cross-compiler) -> mlibc (C library, cross-compiled)
#           -> userland binaries -> kernel -> initramfs -> ISO.
#
#   make          build everything up to the bootable ISO
#   make run      build everything, then boot the ISO in QEMU
#   make sync     pull the newest commits in all submodules, then build
#   make clean    remove build artifacts
#   make distclean remove build artifacts, toolchain and mlibc staging

.DEFAULT_GOAL := all

ROOT := $(CURDIR)

TOOLS_DIR   := tools
CROSS       := x86_64-eucalypt-elf
CROSS_PREFIX := $(ROOT)/$(TOOLS_DIR)/cross/bin
GCC         := $(CROSS_PREFIX)/$(CROSS)-gcc
STRIP       := $(CROSS_PREFIX)/$(CROSS)-strip

MLIBC_SRC   := eucalypt-mlibc
MLIBC_BUILD := $(MLIBC_SRC)/build
MLIBC_STAGE := $(MLIBC_BUILD)/install/src
MLIBC_INSTALL := $(abspath $(MLIBC_STAGE))/usr/local
MLIBC_INC   := $(MLIBC_INSTALL)/include
MLIBC_LIB   := $(MLIBC_INSTALL)/lib

# Kept for parity: some makefiles expect an `mlibc` wrapper name.
MLIBC_LINK  := mlibc

USERLAND_DIR  := eucalypt-userland
USERLAND_SRC  := $(USERLAND_DIR)/src
USERLAND_BIN  := build/userland/bin

KERNEL_DIR   := Eucalypt-Kernel
KERNEL_ARCH  := x86_64
KERNEL_BIN   := $(KERNEL_DIR)/kernel/bin-$(KERNEL_ARCH)/kernel
LIMINE_BIN   := $(KERNEL_DIR)/limine-binary/limine
OVMF         := $(KERNEL_DIR)/edk2-ovmf-bins/ovmf-code-$(KERNEL_ARCH).fd

INITRAMFS    := build/initramfs
LIMINE_CONF  := build/limine.conf
ISO_ROOT     := build/iso_root
ISO          := build/eucalypt.iso

JOBS := $(shell nproc 2>/dev/null || echo 1)

# ------- userland ----------

CFLAGS  := -O2 -ffreestanding -fno-stack-protector -fno-stack-check \
           -fno-asynchronous-unwind-tables -mno-red-zone -m64 -mcmodel=small \
           -Wall -Wextra
LDFLAGS := -nostdlib -static -z max-page-size=0x1000 -z noexecstack

LIBS := $(MLIBC_LIB)/libc.a $(MLIBC_LIB)/libssp_nonshared.a \
        $(MLIBC_LIB)/libssp.a $(MLIBC_LIB)/libpthread.a \
        $(MLIBC_LIB)/libm.a $(MLIBC_LIB)/libutil.a

USERLAND_SRCS := $(filter-out $(USERLAND_SRC)/dso_stub.c,$(wildcard $(USERLAND_SRC)/*.c))
USERLAND_BINS := $(patsubst $(USERLAND_SRC)/%.c,$(USERLAND_BIN)/%,$(USERLAND_SRCS))

.PHONY: all run sync update clean distclean tools mlibc userland kernel

all: $(ISO)

run: $(ISO) $(OVMF)
	qemu-system-x86_64 \
		-M q35 \
		-drive if=pflash,unit=0,format=raw,file=$(OVMF),readonly=on \
		-cdrom $(ISO) \
		-m 2G -d int -device isa-debugcon,chardev=debug \
		-chardev stdio,id=debug

# Pull new commits from every submodule's remote, then build.
sync update:
	git submodule sync --recursive
	git submodule update --init --recursive
	git submodule update --recursive --remote
	$(MAKE) all

# ------- userland bins ----------

userland: $(USERLAND_BINS)

$(USERLAND_BIN)/%: $(USERLAND_SRC)/%.c $(USERLAND_SRC)/linker.ld $(MLIBC_LIB)/libc.a
	@mkdir -p $(dir $@)
	$(GCC) $(CFLAGS) -I$(MLIBC_INC) -c $< -o $@.o
	$(GCC) $(LDFLAGS) -T $(USERLAND_SRC)/linker.ld \
		$(MLIBC_LIB)/crt1.o $(shell $(GCC) -print-file-name=crtbegin.o) $@.o \
		$(LIBS) $(shell $(GCC) -print-file-name=crtend.o) \
		-o $@
	$(STRIP) --strip-debug $@
	rm -f $@.o

# ------- initramfs ----------

# POSIX ustar archive (what kernel/src/fs/ustar.c parses) of the userland
# binaries, served to the kernel as its first Limine module. The kernel
# mounts it at /ram and execs /ram/bin/init.
$(INITRAMFS): $(USERLAND_BINS)
	mkdir -p build/initramfs_root/bin
	cp $(USERLAND_BINS) build/initramfs_root/bin/
	tar --format=ustar -C build/initramfs_root -cf $@ bin
	rm -rf build/initramfs_root

# ------- kernel + ISO ----------

# The kernel consumes userland via a Limine module (initramfs), but its own
# GNUmakefile's iso target does not add modules. Assemble the ISO here.
$(LIMINE_CONF): config/limine.conf
	@mkdir -p $(dir $@)
	cp $< $@

# kernel/GNUmakefile requires cloned deps (git-ignored in the submodule) but
# the kernel repo no longer ships its get-deps script; mirror it here.
KERNEL_DEPS  := $(KERNEL_DIR)/kernel/.deps-obtained
FREESTANDING_HDRS := $(KERNEL_DIR)/kernel/freestanding-c-hdrs
CC_RUNTIME        := $(KERNEL_DIR)/kernel/cc-runtime
LIMINE_PROTOCOL   := $(KERNEL_DIR)/kernel/limine-protocol

$(KERNEL_DEPS): $(FREESTANDING_HDRS) $(CC_RUNTIME) $(LIMINE_PROTOCOL)
	touch $@

$(FREESTANDING_HDRS):
	git clone https://github.com/osdev0/freestanding-c-hdrs.git $@
	git -C $@ checkout 38fed4e1e3365733ddbfa03b0a28936243ad31e9

$(CC_RUNTIME):
	git clone https://github.com/osdev0/cc-runtime.git $@
	git -C $@ checkout dae79833b57a01b9fd3e359ee31def69f5ae899b

$(LIMINE_PROTOCOL):
	git clone https://github.com/Limine-Bootloader/limine-protocol.git $@
	git -C $@ checkout 80ef54bed402b8c0b672a707c1df4c532f3428ad

$(KERNEL_BIN): $(KERNEL_DEPS)
	$(MAKE) -C $(KERNEL_DIR) kernel

$(LIMINE_BIN):
	$(MAKE) -C $(KERNEL_DIR) limine-binary/limine

$(OVMF):
	$(MAKE) -C $(KERNEL_DIR) edk2-ovmf-bins

kernel: $(KERNEL_BIN)

$(ISO): $(KERNEL_BIN) $(LIMINE_BIN) $(INITRAMFS) $(LIMINE_CONF)
	rm -rf $(ISO_ROOT)
	mkdir -p $(ISO_ROOT)/boot/limine $(ISO_ROOT)/EFI/BOOT
	cp $(KERNEL_BIN) $(ISO_ROOT)/boot/kernel
	cp $(INITRAMFS) $(ISO_ROOT)/boot/initramfs
	cp $(LIMINE_CONF) $(ISO_ROOT)/boot/limine/limine.conf
	cp $(KERNEL_DIR)/limine-binary/limine-bios.sys \
	   $(KERNEL_DIR)/limine-binary/limine-bios-cd.bin \
	   $(KERNEL_DIR)/limine-binary/limine-uefi-cd.bin $(ISO_ROOT)/boot/limine/
	cp $(KERNEL_DIR)/limine-binary/BOOTX64.EFI \
	   $(KERNEL_DIR)/limine-binary/BOOTIA32.EFI $(ISO_ROOT)/EFI/BOOT/
	xorriso -as mkisofs -R -r -J -b boot/limine/limine-bios-cd.bin \
		-no-emul-boot -boot-load-size 4 -boot-info-table -hfsplus \
		-apm-block-size 2048 --efi-boot boot/limine/limine-uefi-cd.bin \
		-efi-boot-part --efi-boot-image --protective-msdos-label \
		$(ISO_ROOT) -o $@
	$(LIMINE_BIN) bios-install $@
	rm -rf $(ISO_ROOT)

# ------- mlibc + toolchain ----------

mlibc: $(MLIBC_LIB)/libc.a

$(MLIBC_LIB)/libc.a: $(MLIBC_BUILD)/build.ninja
	ln -sfn $(MLIBC_SRC) $(MLIBC_LINK)
	PATH="$(CROSS_PREFIX):$$PATH" meson compile -C $(MLIBC_BUILD)
	meson install -C $(MLIBC_BUILD) --destdir=$(abspath $(MLIBC_STAGE))

$(MLIBC_BUILD)/build.ninja: tools
	ln -sfn $(MLIBC_SRC) $(MLIBC_LINK)
	PATH="$(CROSS_PREFIX):$$PATH" meson setup $(MLIBC_BUILD) $(MLIBC_SRC) \
		--cross-file $(MLIBC_SRC)/crossfile \
		-Dbuildtype=release \
		-Ddefault_library=static \
		-Duse_freestnd_hdrs=enabled

tools: $(TOOLS_DIR)/gcc-14.1.0/mpfr $(BINUTILS_SYSROFF)
	$(MAKE) -C $(TOOLS_DIR)

# GCC 14 ships no bundled GMP/MPFR/MPC. Download them into the source tree
# (like GCC's own `download_prerequisites` helper) once, so `configure`
# picks them up without system dev packages.
$(TOOLS_DIR)/gcc-14.1.0/mpfr:
	cd $(TOOLS_DIR)/gcc-14.1.0 && ./contrib/download_prerequisites

# binutils/sysroff.info ships in the release tarball but is git-ignored in
# the tools submodule, so fresh checkouts are missing it and the binutils
# build fails on sysroff.h. Extract it from the official tarball when absent.
BINUTILS_SYSROFF := $(TOOLS_DIR)/binutils-2.42/binutils/sysroff.info
$(BINUTILS_SYSROFF):
	@tmp=$$(mktemp -d); \
	curl -sSL https://ftp.gnu.org/gnu/binutils/binutils-2.42.tar.xz -o $$tmp/b.tar.xz; \
	tar -xf $$tmp/b.tar.xz -C $$tmp binutils-2.42/binutils/sysroff.info; \
	cp $$tmp/binutils-2.42/binutils/sysroff.info $@; \
	rm -rf $$tmp

# ------- cleanup ----------

clean:
	$(MAKE) -C $(TOOLS_DIR) clean
	rm -rf $(MLIBC_BUILD) $(MLIBC_LINK)
	rm -rf build
	$(MAKE) -C $(KERNEL_DIR) clean

distclean: clean
	$(MAKE) -C $(TOOLS_DIR) distclean
	rm -rf $(KERNEL_DIR)/iso_root $(KERNEL_DIR)/*.iso $(KERNEL_DIR)/*.hdd \
		$(KERNEL_DIR)/limine-binary $(KERNEL_DIR)/edk2-ovmf-bins