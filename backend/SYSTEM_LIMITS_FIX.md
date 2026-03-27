# System Limits Fix - "Too Many Open Files"

## Problem
Error: `failed to create fsnotify watcher: too many open files`

This indicates the system has exhausted its file descriptor limit. This can happen when:
1. Connections aren't being closed properly (related to the hanging issue)
2. System limits are too low for the application's needs
3. File handles are leaking

## Quick Fix (Temporary - Until Next Reboot)

```bash
# Check current limits
ulimit -n

# Increase limit for current session (e.g., to 65536)
ulimit -n 65536

# Restart your application
```

## Permanent Fix (Recommended)

### For Docker/Kubernetes Deployment

Add to your `docker-compose.yml` or deployment config:

```yaml
services:
  backend:
    ulimits:
      nofile:
        soft: 65536
        hard: 65536
```

Or in Kubernetes deployment:

```yaml
spec:
  containers:
  - name: backend
    resources:
      limits:
        # Add file descriptor limit
        "fs.file-max": "65536"
```

### For Bare Metal/VM Deployment

1. **Edit system limits:**
```bash
sudo nano /etc/security/limits.conf
```

2. **Add these lines:**
```
* soft nofile 65536
* hard nofile 65536
root soft nofile 65536
root hard nofile 65536
```

3. **Edit sysctl:**
```bash
sudo nano /etc/sysctl.conf
```

4. **Add:**
```
fs.file-max = 2097152
fs.inotify.max_user_watches = 524288
fs.inotify.max_user_instances = 512
```

5. **Apply changes:**
```bash
sudo sysctl -p
```

6. **Logout and login again** (or reboot)

7. **Verify:**
```bash
ulimit -n  # Should show 65536
cat /proc/sys/fs/file-max  # Should show 2097152
```

## Check for File Descriptor Leaks

### Monitor open files:
```bash
# Check current open files for your process
lsof -p $(pgrep -f "python.*uvicorn") | wc -l

# Watch it over time
watch -n 5 'lsof -p $(pgrep -f "python.*uvicorn") | wc -l'
```

### Check what's using file descriptors:
```bash
# See what files are open
lsof -p $(pgrep -f "python.*uvicorn") | head -50

# Count by type
lsof -p $(pgrep -f "python.*uvicorn") | awk '{print $5}' | sort | uniq -c | sort -rn
```

## Why This Happened

The hanging issue we just fixed was likely causing:
1. **HTTP connections not closing** - Timeout meant connections stayed open
2. **Database connections accumulating** - Sessions not being released
3. **File handles leaking** - ChromaDB, logs, temp files not closing

With the timeout fixes in place, connections should now close properly, reducing file descriptor usage.

## Monitoring

After applying the timeout fixes and increasing limits, monitor:

```bash
# Check file descriptor usage every 5 seconds
watch -n 5 'echo "Open files: $(lsof -p $(pgrep -f "python.*uvicorn") 2>/dev/null | wc -l) / $(ulimit -n)"'
```

If file descriptors keep growing even with timeouts, there may be additional leaks to investigate.

## Related to Timeout Fix

The timeout fixes we applied should help by:
- ✅ Closing hung API connections after 60s
- ✅ Releasing database sessions properly
- ✅ Preventing connection accumulation
- ✅ Ensuring cleanup happens even on errors

## Quick Diagnostic

```bash
# 1. Check current limit
ulimit -n

# 2. Check current usage
lsof -p $(pgrep -f "python.*uvicorn") | wc -l

# 3. If usage is high, restart application
# (This will close all connections)

# 4. Increase limit
ulimit -n 65536

# 5. Restart application with new limit
```

## For Production

Consider adding monitoring/alerting for:
- File descriptor usage > 80% of limit
- Connection pool exhaustion
- Database session leaks
- HTTP connection timeouts

The timeout fixes should prevent most of these issues, but monitoring helps catch any remaining problems early.