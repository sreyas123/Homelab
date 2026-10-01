#!/bin/bash
# Run with:  sudo bash /home/YOUR_USER/server/disk-watch/install-smart-alerts.sh
# 1. Makes smartd push its warnings to your ntfy topic (it currently tries to email root, which fails: no mail program).
# 2. Watches the drive's key SMART attributes and runs scheduled self-tests.
set -eu

# (Replace YOUR_USER with your own Linux username - in the line above and on the next line - and point the TOPIC line at the .env file that holds your ntfy topic)
TOPIC=$(grep -oP '^NTFY_TOPIC=\K\S+' /home/YOUR_USER/server/light-alerts/.env)
[ -n "$TOPIC" ] || { echo "ntfy topic not found"; exit 1; }

# ntfy topic, readable by root only (it works like a password)
install -m 600 /dev/null /etc/smartmontools/ntfy-topic
printf '%s' "$TOPIC" > /etc/smartmontools/ntfy-topic

# smartd-runner executes everything in run.d with SMARTD_* variables set
cat > /etc/smartmontools/run.d/20ntfy <<'EOF'
#!/bin/sh
curl -fsS -m 20 \
  -H "Title: Drive warning: ${SMARTD_FAILTYPE:-SMART}" \
  -H "Priority: high" -H "Tags: warning" \
  -d "${SMARTD_MESSAGE:-SMART warning}" \
  "https://ntfy.sh/$(cat /etc/smartmontools/ntfy-topic)" >/dev/null
EOF
chmod 755 /etc/smartmontools/run.d/20ntfy

# Replace the generic DEVICESCAN line with a tuned entry for this drive:
#  -a            all checks (health, error log, self-test log, pending 197, uncorrectable 198)
#  -o on -S on   automatic offline scans + save attributes (keeps 198 up to date)
#  -R ...        also alert when the RAW values of reallocated(5), uncorrect(187), pending(197), offline(198) change
#  -s ...        short self-test daily 02:00, long self-test Sundays 03:00
#  -W 4,50,55    temperature: log a 4C jump, warn at 50C, critical at 55C
#  -M diminishing  repeat reminders at 1, 2, 4, 8... days rather than daily forever
cp -n /etc/smartd.conf /etc/smartd.conf.bak-before-ntfy
sed -i 's|^DEVICESCAN .*|/dev/sda -d sat -a -o on -S on -n standby,q -s (S/../.././02\|L/../../7/03) -W 4,50,55 -R 5 -R 187 -R 197 -R 198 -m root -M exec /usr/share/smartmontools/smartd-runner -M diminishing|' /etc/smartd.conf
grep -vE '^\s*(#|$)' /etc/smartd.conf

smartd -q showtests | head -8
systemctl restart smartmontools
sleep 2
systemctl is-active smartmontools

# End-to-end test of the notification path (sends one ntfy message)
SMARTD_FAILTYPE=EmailTest SMARTD_MESSAGE="TEST: smartd can now reach your phone via ntfy. Ignore this." /etc/smartmontools/run.d/20ntfy \
  && echo "test notification sent"
