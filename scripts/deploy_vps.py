#!/usr/bin/env python3
"""
Remote deployment script for Contabo VPS (158.220.102.37) using Paramiko SSH & SFTP.
Syncs binance ai bot updated source files, updates configuration, and restarts bot daemon.
"""

import os
import sys
import paramiko

HOST = "158.220.102.37"
USER = "root"
PASS = "7EfOJ1iTE4xjz7KJ5lvCM7ZJPv"
TARGET_DIR = "/bot"
LOCAL_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

EXCLUDE_DIRS = {
    "venv", ".git", ".pytest_cache", "__pycache__", ".idea", ".vscode",
    "xml bots", "xml_bots", "historical", "logs", "test_tmp", "training", "scratch"
}

def run_ssh_cmd(ssh, cmd, ignore_errors=False):
    print(f"\n[SSH RUN] {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd, get_pty=True)
    
    output_lines = []
    for line in iter(stdout.readline, ""):
        try:
            print(line, end="")
        except UnicodeEncodeError:
            print(line.encode("ascii", errors="replace").decode("ascii"), end="")
        except Exception:
            pass
        output_lines.append(line)
        sys.stdout.flush()
        
    exit_code = stdout.channel.recv_exit_status()
    if exit_code != 0 and not ignore_errors:
        print(f"[ERROR] Command failed with exit code {exit_code}: {cmd}")
        return False
    return True


def upload_directory(sftp, local_dir, remote_dir):
    print(f"[SFTP] Syncing {local_dir} -> {remote_dir}...")
    
    for root, dirs, files in os.walk(local_dir):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS and not d.startswith(".")]
        
        rel_path = os.path.relpath(root, local_dir)
        if rel_path == ".":
            remote_root = remote_dir
        else:
            remote_root = os.path.normpath(os.path.join(remote_dir, rel_path)).replace("\\", "/")
            
        try:
            sftp.stat(remote_root)
        except IOError:
            sftp.mkdir(remote_root)
            
        for file in files:
            if file.endswith((".pyc", ".pyo", ".tmp")) or file.startswith("."):
                continue
            local_file_path = os.path.join(root, file)
            remote_file_path = os.path.normpath(os.path.join(remote_root, file)).replace("\\", "/")
            
            print(f"  -> Uploading: {os.path.join(rel_path, file)}")
            try:
                sftp.put(local_file_path, remote_file_path)
            except (IOError, OSError) as e:
                print(f"  [WARN] Skipped active file {file}: {e}")


def main():
    print("================================================================")
    print(f"Connecting to VPS ({HOST})...")
    print("================================================================")
    
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        ssh.connect(HOST, port=22, username=USER, password=PASS, timeout=15)
        print("[SUCCESS] Connected to SSH server!")
    except Exception as e:
        print(f"[FAILED] SSH Connection failed: {e}")
        sys.exit(1)

    # 1. Ensure target directory exists on VPS
    run_ssh_cmd(ssh, f"mkdir -p {TARGET_DIR}")

    # 2. Upload all project files via SFTP
    print("[INFO] Uploading project files to VPS...")
    sftp = ssh.open_sftp()
    upload_directory(sftp, LOCAL_DIR, TARGET_DIR)
    sftp.close()
    print("[SUCCESS] All project files uploaded.")

    # 3. Check for docker-compose or systemd service or pm2 / daemon script
    print("[INFO] Restarting bot service / daemon on VPS...")
    # Restart docker compose stack if docker compose is present, or systemctl restart
    cmd = f"export PATH=$PATH:/usr/bin:/usr/local/bin && cd {TARGET_DIR} && if [ -f docker-compose.yml ]; then docker compose down && docker compose up --build -d; elif systemctl is-active --quiet deriv-bot; then systemctl restart deriv-bot; elif pgrep -f run_bot_daemon.py; then pkill -f run_bot_daemon.py && nohup python3 scripts/run_bot_daemon.py > daemon.log 2>&1 & else nohup python3 scripts/run_bot_daemon.py > daemon.log 2>&1 & fi"
    run_ssh_cmd(ssh, cmd, ignore_errors=True)

    # 4. Tail recent logs to verify output
    print("\n================================================================")
    print("Verifying Remote Logs:")
    print("================================================================")
    run_ssh_cmd(ssh, f"export PATH=$PATH:/usr/bin:/usr/local/bin && cd {TARGET_DIR} && if [ -f docker-compose.yml ]; then docker compose logs --tail=30; else tail -n 30 daemon.log 2>/dev/null || tail -n 30 data/logs/bot.log 2>/dev/null; fi", ignore_errors=True)

    ssh.close()
    print("\n================================================================")
    print("VPS DEPLOYMENT & VERIFICATION COMPLETE!")
    print("================================================================")

if __name__ == "__main__":
    main()
