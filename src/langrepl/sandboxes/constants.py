"""Non-configurable sandbox constants."""

WORKER_MODULE = "langrepl.sandboxes.worker"

# Seatbelt (macOS) specific constants.
SEATBELT_BSD_PROFILE = "/System/Library/Sandbox/Profiles/bsd.sb"
SEATBELT_MDNS_RESPONDER_PATH = "/private/var/run/mDNSResponder"
SEATBELT_MACH_SERVICES = (
    # Logging
    "com.apple.logd",
    "com.apple.system.logger",
    # Notifications
    "com.apple.system.notification_center",
    "com.apple.distributed_notifications@Uv3",
    # Core services
    "com.apple.CoreServices.coreservicesd",
    "com.apple.coreservices.launchservicesd",
    "com.apple.lsd.mapdb",
    "com.apple.lsd.modifydb",
    # Security (HTTPS/TLS certificates)
    "com.apple.SecurityServer",
    "com.apple.securityd.xpc",
    "com.apple.trustd",
    "com.apple.trustd.agent",
    "com.apple.secinitd",
    # Directory services
    "com.apple.system.opendirectoryd.libinfo",
    "com.apple.system.opendirectoryd.membership",
    # Preferences
    "com.apple.cfprefsd.daemon",
    "com.apple.cfprefsd.agent",
    # Fonts
    "com.apple.fonts",
    "com.apple.FontObjectsServer",
    # System
    "com.apple.DiskArbitration.diskarbitrationd",
    "com.apple.audio.audiohald",
    "com.apple.audio.coreaudiod",
    "com.apple.audio.systemsoundserver",
    "com.apple.PowerManagement.control",
    "com.apple.bsd.dirhelper",
    # Network (DNS, mDNS, SystemConfiguration)
    "com.apple.dnssd.service",
    "com.apple.networkd",
    "com.apple.SystemConfiguration.configd",
    "com.apple.SystemConfiguration.DNSConfiguration",
    "com.apple.SystemConfiguration.NetworkInformation",
    "com.apple.SystemConfiguration.SCNetworkReachability",
    # Keychain (Python SSL/HTTPS)
    "com.apple.securityd",
    "com.apple.ocspd",
)

MAX_STDOUT = 10 * 1024 * 1024  # 10MB
MAX_STDERR = 1 * 1024 * 1024  # 1MB

# Bubblewrap (Linux) specific constants.
BWRAP_AF_UNIX = 1
BWRAP_PTRACE_TRACEME = 0

# Syscalls to block via seccomp (beyond ptrace/AF_UNIX)
# These could allow sandbox escape or host system manipulation
BWRAP_BLOCKED_SYSCALLS = (
    # Cross-process memory access
    "process_vm_readv",
    "process_vm_writev",
    # Kernel keyring (credential storage)
    "add_key",
    "request_key",
    "keyctl",
    # Kernel module loading
    "init_module",
    "finit_module",
    "delete_module",
    # System state manipulation
    "reboot",
    "kexec_load",
    "kexec_file_load",
    "swapon",
    "swapoff",
    # Can disable ASLR
    "personality",
    # eBPF (potential kernel exploit vector)
    "bpf",
    # Namespace manipulation (already isolated but defense in depth)
    "setns",
    "unshare",
)

ALLOWED_MODULE_PREFIX = "langrepl.tools."

# Base environment for sandboxed processes
# HOME is set per-backend to the working directory to avoid leaking user paths
SANDBOX_ENV_BASE = {
    "PATH": "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin",
    "LANG": "en_US.UTF-8",
    "TERM": "xterm-256color",
    "PYTHONUNBUFFERED": "1",
}
