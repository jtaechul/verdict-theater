#!/usr/bin/env python3
"""⭐ 릴리스에 파일을 올리고 내린다 (완성 영상은 저장소에 커밋하지 않는다).

    python3 tools/release_file.py get  <태그> <파일이름> <저장할곳>
    python3 tools/release_file.py put  <태그> <파일이름> <올릴파일>

왜 (2026-08-20)
    · MP4 는 편당 수십 MB 다. 한 번 커밋하면 지워도 깃 이력에 영구히 남아
      저장소가 되돌릴 수 없이 커진다 — 그래서 **릴리스에만** 둔다.
    · 처음엔 이 일을 워크플로 안에 셸+파이썬 한 줄짜리로 박아 넣었는데
      **YAML 이 깨졌다.** 줄이 길고 따옴표가 겹치면 그렇게 된다.
      따로 빼 두면 여기서 직접 돌려 볼 수도 있다.

    GH_TOKEN 과 GITHUB_REPOSITORY 를 환경에서 읽는다.
"""
import json
import os
import pathlib
import sys
import urllib.error
import urllib.request

API = "https://api.github.com"
UP = "https://uploads.github.com"


def call(url, method="GET", data=None, ctype=None, raw=False):
    tok = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN") or ""
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {tok}")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    req.add_header("User-Agent", "verdict-theater")
    req.add_header("Accept", "application/octet-stream" if raw
                   else "application/vnd.github+json")
    if ctype:
        req.add_header("Content-Type", ctype)
    with urllib.request.urlopen(req, timeout=300) as r:
        body = r.read()
    return body if raw else (json.loads(body) if body else {})


def repo():
    r = os.environ.get("GITHUB_REPOSITORY") or "jtaechul/verdict-theater"
    return f"{API}/repos/{r}"


def release(tag, make=False):
    try:
        return call(f"{repo()}/releases/tags/{tag}")
    except urllib.error.HTTPError as e:
        if e.code != 404 or not make:
            raise
    return call(f"{repo()}/releases", "POST",
                json.dumps({"tag_name": tag, "name": tag}).encode(),
                "application/json")


def get(tag, name, dest):
    rel = release(tag)
    a = next((x for x in rel.get("assets", []) if x["name"] == name), None)
    if not a:
        # 이름이 달라도 하나뿐이면 그것을 쓴다 (사람이 올린 파일 이름은 제각각이다)
        others = rel.get("assets", [])
        if len(others) == 1:
            a = others[0]
            print(f"  ('{name}' 이 없어 '{a['name']}' 를 받는다)")
        else:
            print(f"❌ {tag} 에 {name} 이 없다 "
                  f"(있는 것: {[x['name'] for x in others] or '없음'})", file=sys.stderr)
            return 1
    data = call(f"{repo()}/releases/assets/{a['id']}", raw=True)
    # ⚠️ 2026-08-23 — 받을 폴더(build/)가 아직 없으면 여기서 통째로 죽었다.
    #    그 바람에 릴리스에 멀쩡히 있는 인물 카드를 못 받고 매번 새로
    #    만들어(397원) 돈이 샜다. 폴더는 만들어 주면 되는 일이다.
    pathlib.Path(dest).parent.mkdir(parents=True, exist_ok=True)
    with open(dest, "wb") as f:
        f.write(data)
    print(f"✅ {tag}/{a['name']} → {dest} ({len(data):,} 바이트)")
    return 0


def put(tag, name, src):
    rel = release(tag, make=True)
    for a in rel.get("assets", []):
        if a["name"] == name:                    # 다시 만들 수 있어야 하므로 지우고 새로
            call(f"{repo()}/releases/assets/{a['id']}", "DELETE")
    with open(src, "rb") as f:
        data = f.read()
    ct = "video/mp4" if name.endswith(".mp4") else "application/octet-stream"
    call(f"{UP}/repos/{os.environ.get('GITHUB_REPOSITORY', 'jtaechul/verdict-theater')}"
         f"/releases/{rel['id']}/assets?name={name}", "POST", data, ct)
    print(f"✅ {src} → {tag}/{name} ({len(data):,} 바이트)")
    return 0


def main():
    if len(sys.argv) < 5:
        print(__doc__, file=sys.stderr)
        return 2
    what, tag, name, path = sys.argv[1:5]
    if what == "get":
        return get(tag, name, path)
    if what == "put":
        return put(tag, name, path)
    print(f"❌ 알 수 없는 명령: {what}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
