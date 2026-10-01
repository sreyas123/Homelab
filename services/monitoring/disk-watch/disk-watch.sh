#!/bin/bash
# disk-watch: early-warning for the failing drive (sda). Runs from cron every 2 minutes as your normal user.
#  - new kernel disk errors (I/O error, UNC, ata resets, EXT4 errors)  -> high-priority ntfy push
#  - root filesystem flipped read-only                                 -> urgent ntfy push
#  - sustained very slow reads (avg > 250 ms while ~saturated, ~16 min)-> ntfy push, then "back to normal"
# Titles deliberately avoid the prefixes light-alerts reacts to (DOWN:/DISK ALERT/MEMORY ALERT/RECOVERED:)
# so hardware alerts reach the phone without leaving the lantern stuck red.
# SMART attribute changes are handled separately by smartd (/etc/smartmontools/run.d/20ntfy).
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
set -u

DEV=sda
# (Replace YOUR_USER with your own Linux username, here and on the TOPIC line below; the TOPIC line must point at the .env file that holds your ntfy topic)
DIR=/home/YOUR_USER/.local/state/disk-watch
mkdir -p "$DIR"
TOPIC=$(grep -oP '^NTFY_TOPIC=\K\S+' /home/YOUR_USER/server/light-alerts/.env)
[ -n "$TOPIC" ] || { echo "no ntfy topic found" >&2; exit 1; }

notify() { # title priority tags message
  curl -fsS -m 20 -H "Title: $1" -H "Priority: $2" -H "Tags: $3" -d "$4" "https://ntfy.sh/$TOPIC" >/dev/null \
    || echo "ntfy push failed: $1" >&2
}

if [ "${1:-}" = "test" ]; then
  notify "Drive watch: test message" default white_check_mark \
    "disk-watch on the server is installed and can reach ntfy. Ignore this."
  exit 0
fi

now=$(date +%s)
age() { echo $(( now - $(cat "$DIR/$1" 2>/dev/null || echo 0) )); }

# --- 1) new kernel disk errors --------------------------------------------------------------
last=$(cat "$DIR/last_ts" 2>/dev/null || echo $((now - 180)))
echo "$now" > "$DIR/last_ts"
errs=$(journalctl -k -o short-unix --since "@$last" --no-pager 2>/dev/null \
  | grep -E "I/O error, dev $DEV|Unrecovered read error|ata1(\.00)?: (failed command|hard resetting link|SError)|EXT4-fs (error|warning).*$DEV|Buffer I/O error on dev $DEV|Remounting filesystem read-only")
if [ -n "$errs" ] && [ "$(age last_err_alert)" -gt 1200 ]; then
  n=$(echo "$errs" | grep -cE "I/O error, dev $DEV")
  notify "Drive error on the server" high warning \
    "$n new read/write failure(s) logged by the kernel for /dev/$DEV. Latest lines:
$(echo "$errs" | tail -3 | cut -c1-200)
Check: sudo smartctl -A /dev/$DEV | grep -E 'Pending|Realloc|Uncorrect'"
  echo "$now" > "$DIR/last_err_alert"
fi

# --- 2) root filesystem went read-only (ext4 errors=remount-ro triggered) -------------------
if awk '$2=="/"{print $4}' /proc/mounts | grep -qE '(^|,)ro(,|$)' && [ "$(age last_ro_alert)" -gt 3600 ]; then
  notify "URGENT: server disk went read-only" urgent rotating_light \
    "The root filesystem on the server is now read-only, so containers will start failing. The drive probably hit a serious error. Back up what matters and reboot into a filesystem check."
  echo "$now" > "$DIR/last_ro_alert"
fi

# --- 3) sustained very slow reads -----------------------------------------------------------
read -r reads rms busy < <(awk -v d="$DEV" '$3==d{print $4, $7, $13}' /proc/diskstats)
if [ -f "$DIR/prev" ]; then
  read -r pts preads prms pbusy < "$DIR/prev"
  dt=$(( now - pts ))
  if [ "$dt" -gt 0 ]; then
    verdict=$(awk -v r=$((reads - preads)) -v ms=$((rms - prms)) -v b=$((busy - pbusy)) -v dt=$dt '
      BEGIN { if (r < 20) { print "skip"; exit }
              lat = ms / r; util = b / (dt * 10)
              print ((lat > 250 && util > 90) ? "slow" : "ok"), int(lat) }')
    state=${verdict%% *}; lat=${verdict##* }
    slow=$(cat "$DIR/slow_count" 2>/dev/null || echo 0)
    case "$state" in
      slow) slow=$((slow + 1)) ;;
      ok)   if [ "$slow" -ge 8 ] && [ -f "$DIR/slow_alerted" ]; then
              notify "Drive speed back to normal" low white_check_mark "Average read latency is down to ${lat} ms."
              rm -f "$DIR/slow_alerted"
            fi
            slow=0 ;;
    esac
    echo "$slow" > "$DIR/slow_count"
    if [ "$slow" -ge 8 ] && [ "$(age last_slow_alert)" -gt 21600 ]; then
      notify "Drive very slow on the server" default snail \
        "Reads have averaged over 250 ms (now ${lat} ms) with the disk saturated for about 16 minutes. Apps will time out and containers may flap unhealthy."
      echo "$now" > "$DIR/last_slow_alert"; touch "$DIR/slow_alerted"
    fi
  fi
fi
echo "$now $reads $rms $busy" > "$DIR/prev"
