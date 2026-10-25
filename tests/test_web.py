"""Comprobaciones SEO técnicas y de enlaces del sitio generado (web/build.py)."""
import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def build(tmp, *args, env=None):
    import os
    out = tmp / "out"
    subprocess.run([sys.executable, str(REPO / "web" / "build.py"), "--out", str(out), *args],
                   check=True, capture_output=True, env={**os.environ, **(env or {})})
    return out


def pages(out):
    return {p: p.read_text(encoding="utf8") for p in out.rglob("*.html")}


def test_prototype_is_noindex_and_blocks_robots(tmp_path):
    out = build(tmp_path)
    assert all('content="noindex, nofollow"' in h for h in pages(out).values())
    assert "Disallow: /" in (out / "robots.txt").read_text()
    assert not (out / "sitemap.xml").exists()


def test_public_mode_requires_domain(tmp_path):
    r = subprocess.run([sys.executable, str(REPO / "web" / "build.py"), "--modo", "publico", "--out", str(tmp_path / "x")],
                       capture_output=True, env={"PATH": "/usr/bin:/bin"})
    assert r.returncode != 0


def test_public_mode_seo(tmp_path):
    out = build(tmp_path, "--modo", "publico", env={"SITE_BASE_URL": "https://dominio.cl"})
    hs = pages(out)
    titles = [re.search(r"<title>(.*?)</title>", h).group(1) for h in hs.values()]
    assert len(titles) == len(set(titles))
    for p, h in hs.items():
        assert 'name="description"' in h and 'rel="canonical" href="https://dominio.cl/' in h
        assert 'lang="es-CL"' in h
        if p.name != "404.html":
            assert 'content="index, follow"' in h
    sitemap = (out / "sitemap.xml").read_text()
    locs = re.findall(r"<loc>(.*?)</loc>", sitemap)
    assert "https://dominio.cl/" in locs and not any("404" in l for l in locs)
    assert len(locs) == len(hs) - 1
    assert "Sitemap: https://dominio.cl/sitemap.xml" in (out / "robots.txt").read_text()


def test_internal_links_resolve(tmp_path):
    out = build(tmp_path, "--modo", "publico", env={"SITE_BASE_URL": "https://dominio.cl"})
    for h in pages(out).values():
        for href in re.findall(r'href="(/[^"#]*)', h):
            assert (out / href.strip("/") / "index.html").exists() or href == "/", href
    prev = build(tmp_path / "p", "--preview")
    for p, h in pages(prev).items():
        for href in re.findall(r'href="([^":#]+\.html)', h):
            assert (p.parent / href).resolve().exists(), (p, href)


def test_prices_come_only_from_data(tmp_path):
    data = json.loads((REPO / "web" / "data" / "ofertas.json").read_text())
    allowed = {"$" + f"{o['precio']:,}".replace(",", ".") for p in data["productos"] for o in p["ofertas"]}
    for h in pages(build(tmp_path)).values():
        assert set(re.findall(r"\$\d{1,3}(?:\.\d{3})+", h)) <= allowed


def test_only_confirmed_benefits_are_listed(tmp_path):
    data = json.loads((REPO / "web" / "data" / "beneficios.json").read_text())
    hs = pages(build(tmp_path, "--hoy", "2026-10-30"))  # viernes
    ben = next(h for p, h in hs.items() if p.parent.name == "beneficios")
    for b in data["benefits"]:
        if b["merchant"] and b["status"] != "confirmado":
            assert f'class="comercio">{b["merchant"]}<' not in ben, b["merchant"]
    home = (tmp_path / "out" / "index.html").read_text(encoding="utf8")
    assert 'class="comercio">Güeros<' in home  # 40% los viernes en BCI
