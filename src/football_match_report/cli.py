"""Command-line interface: scrape + render."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import pandas as pd

from .core import events as core_events
from .io import fotmob, whoscored
from .viz import report as report_viz


# --------------------------------------------------------------------------- #
# scrape
# --------------------------------------------------------------------------- #
def _empty_events() -> pd.DataFrame:
    return pd.DataFrame(columns=["index", "teamId", "playerId", "type", "outcomeType",
                                 "x", "y", "endX", "endY", "minute", "second", "period",
                                 "qualifiers", "isTouch"])


def _write_bundle(out: Path, matchdict: dict | None, fotmob_payload: dict | None, fm_id: int | None, url: str) -> None:
    out.mkdir(parents=True, exist_ok=True)

    if matchdict is not None:
        (out / "matchdict.json").write_text(json.dumps(matchdict))
        xt = core_events.load_xt_grid(Path(__file__).resolve().parent / "data" / "xt_grid.csv")
        df = core_events.build_master_df(matchdict, xt)
        df.to_csv(out / "events.csv", index=False)
    else:
        _empty_events().to_csv(out / "events.csv", index=False)

    meta = {}
    if matchdict is not None:
        meta = {
            "teams": {
                "home": {"name": matchdict["home"]["name"], "who_scored_id": matchdict["home"]["teamId"]},
                "away": {"name": matchdict["away"]["name"], "who_scored_id": matchdict["away"]["teamId"]},
            },
            "score": matchdict.get("score"),
            "ft_score": matchdict.get("ftScore"),
            "start_date": matchdict.get("startDate"),
            "venue": matchdict.get("venueName"),
            "attendance": matchdict.get("attendance"),
            "referee": matchdict.get("referee"),
        }
    if fotmob_payload is not None and fm_id is not None:
        meta.update(fotmob.meta_from_fotmob(fotmob_payload, fm_id))
        meta["match_id_fotmob"] = fm_id
    meta["source_url"] = url
    (out / "meta.json").write_text(json.dumps(meta, indent=2))

    # persist xT grid for the render step
    xt = core_events.load_xt_grid(Path(__file__).resolve().parent / "data" / "xt_grid.csv")
    pd.DataFrame(xt).to_csv(out / "xt_grid.csv", index=False, header=False)


def cmd_scrape(args) -> int:
    out = Path(args.out)
    fm_id = args.fotmob_id
    t0 = time.time()

    # FotMob-only mode (no browser)
    if fm_id or (args.url and "fotmob.com" in args.url):
        if args.url and "fotmob.com" in args.url:
            fm_id = fm_id or fotmob.parse_fotmob_url(args.url)
        if not fm_id:
            print("could not find a match id in the FotMob URL (use ...#123456 or --fotmob-id)", file=sys.stderr)
            return 2
        payload = fotmob.fetch_match_details(fm_id)
        _write_bundle(out, None, payload, fm_id, args.url or "")
        print(f"[fotmob] {fm_id}: shots/momentum/colors saved")
        print(f"✅ Done in {time.time() - t0:.1f}s — FotMob-only bundle (event panels limited)")
        return 0

    if not args.url:
        print("provide a WhoScored URL, a FotMob URL, or --fotmob-id", file=sys.stderr)
        return 2

    # WhoScored path (+ FotMob enrichment)
    if args.no_browser and (out / "matchdict.json").exists():
        print("[whoScored] reusing cached matchdict.json (--no-browser)")
        matchdict = json.loads((out / "matchdict.json").read_text())
    else:
        if "whoscored.com" not in args.url:
            print("a WhoScored URL is required for the event stream", file=sys.stderr)
            return 2
        print("[whoScored] fetching match page with headless Chromium ...")
        matchdict = whoscored.fetch_match(args.url)
        print(f"[whoScored] matchCentreData OK ({len(matchdict.get('events', []))} events)")

    if fm_id is None:
        fm_id = fotmob.resolve_match_id(matchdict)
    payload = None
    if fm_id:
        print(f"[fotmob] resolved match id {fm_id}, fetching matchDetails ...")
        payload = fotmob.fetch_match_details(fm_id)
        print("[fotmob] shots/momentum/colors saved")

    _write_bundle(out, matchdict, payload, fm_id, args.url)
    print(f"✅ Done in {time.time() - t0:.1f}s. Bundle ready in {out}/")
    print(f"   Next:  football-match-report render --data {out} --out report")
    return 0


# --------------------------------------------------------------------------- #
# render
# --------------------------------------------------------------------------- #
def cmd_render(args) -> int:
    data_dir = Path(args.data)
    out_dir = Path(args.out)
    paths = report_viz.save_report(data_dir, out_dir)
    for p in paths:
        print(f"✅ {p}")
    return 0


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="football-match-report", description="Post-match team report (WhoScored + FotMob)")
    sub = ap.add_subparsers(dest="command", required=True)

    p_scrape = sub.add_parser("scrape", help="scrape a match into a data bundle")
    p_scrape.add_argument("url", nargs="?", help="WhoScored or FotMob match URL")
    p_scrape.add_argument("--out", default="data", help="output directory (default: ./data)")
    p_scrape.add_argument("--fotmob-id", type=int, default=None, help="FotMob match id")
    p_scrape.add_argument("--no-browser", action="store_true", help="reuse cached matchdict.json")
    p_scrape.set_defaults(func=cmd_scrape)

    p_render = sub.add_parser("render", help="render a scraped bundle into report PNGs")
    p_render.add_argument("--data", default="data", help="bundle directory (default: ./data)")
    p_render.add_argument("--out", default="report", help="output directory (default: ./report)")
    p_render.set_defaults(func=cmd_render)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
