#!/usr/bin/env python3
import sys

import multisend_core as core

TARGETS = [
    {
        "name": "Perplexity",
        "wm_class": "crx_pdblnecalpedecgehiadglkhjcbjcfgj.Brave-browser",
        "send_key": "ctrl+Return",
        "focus_delay": core.FOCUS_DELAY_DEFAULT,
        "post_send_delay": core.POST_SEND_DELAY_DEFAULT,
        "use_perplexity_probe": True,
    },
    {
        "name": "Claude",
        "wm_class": "crx_fmpnliohjhemenmnlpbfagaolkdacoja.Brave-browser",
        "send_key": "ctrl+Return",
        "focus_delay": core.FOCUS_DELAY_CLAUDE,
        "post_send_delay": core.POST_SEND_DELAY_CLAUDE,
    },
    {
        "name": "ChatGPT",
        "wm_class": "crx_cadlkienfkclaiaibeoongdcgmdikeeg.Brave-browser",
        "send_key": "Return",
        "focus_delay": core.FOCUS_DELAY_DEFAULT,
        "post_send_delay": core.POST_SEND_DELAY_DEFAULT,
    },
]

def _build_cli_ruleset() -> dict:
    rules = core.default_ruleset()
    by_class = rules.setdefault("by_wm_class", {})
    for target in TARGETS:
        by_class[target["wm_class"]] = {
            "send_key": target["send_key"],
            "focus_delay": target["focus_delay"],
            "post_send_delay": target["post_send_delay"],
            "use_perplexity_probe": target.get("use_perplexity_probe", False),
        }
    return rules


def main():
    if len(sys.argv) > 1:
        msg = " ".join(sys.argv[1:])
    else:
        msg = sys.stdin.read()

    msg = msg.strip()
    if not msg:
        print("No message.", file=sys.stderr)
        return 1

    try:
        wins = core.list_windows()
    except core.ToolMissingError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except core.MultiSendError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    window_ids = []
    id_to_name = {}
    for t in TARGETS:
        w = next((x for x in wins if x["wm_class"] == t["wm_class"]), None)
        if not w:
            print(f"Missing: {t['name']} ({t['wm_class']})", file=sys.stderr)
            continue
        window_ids.append(w["id_hex"])
        id_to_name[w["id_hex"]] = t["name"]

    for wid in window_ids:
        print(f"Sending to: {id_to_name.get(wid, wid)}")

    try:
        result = core.send_to_windows(msg, window_ids, _build_cli_ruleset())
    except core.ToolMissingError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except core.MultiSendError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    for warning in result["warnings"]:
        print(f"WARN: {warning}", file=sys.stderr)
    for error in result["errors"]:
        print(f"ERROR: {error}", file=sys.stderr)

    if result["errors"]:
        return 2

    print("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
