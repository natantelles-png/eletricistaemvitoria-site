#!/usr/bin/env python3
"""Gera os arquivos de SEO/AEO/GEO a partir das próprias páginas HTML.

Arquivos gerados (na raiz do site):
  sitemap.xml          páginas com lastmod real e imagem de capa dos textos do blog
  llms-full.txt        conteúdo das páginas em texto simples, para IAs
  blog/feed.xml        RSS do blog
  indexnow-urls.json   lista de URLs enviada ao IndexNow depois de cada publicação

Uso, na raiz do repositório:
  python3 tools/gerar_seo.py

Regras:
  - o texto sai do HTML publicado; nada é escrito à mão aqui;
  - lastmod vem do dateModified do JSON-LD de cada página e nunca passa de hoje (fuso de Brasília);
  - o índice do blog usa a data do texto mais recente.
"""
import datetime as dt
import email.utils
import html
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASE = "https://eletricistaemvitoria.com.br"
HOST = "eletricistaemvitoria.com.br"
HOJE = dt.datetime.now(dt.timezone(dt.timedelta(hours=-3))).strftime("%Y-%m-%d")

SERVICOS = ["eletricista-24h-vitoria", "residencial", "lojas-shopping",
            "empresas-condominios", "carregador-veicular", "projetos-revisoes"]

LD_RE = re.compile(r'<script type="application/ld\+json">(.*?)</script>', re.S)


def ler(p):
    return p.read_text(encoding="utf8")


def grafo(src):
    m = LD_RE.search(src)
    return json.loads(m.group(1))["@graph"] if m else []


def tipo(graph, nome):
    return next((g for g in graph if g.get("@type") == nome), None)


def limitar(data):
    """Nunca devolve data no futuro."""
    return min(data, HOJE)


def paginas():
    """Lista [(url, caminho, graph)] de tudo que deve ir ao sitemap."""
    itens = [("/", ROOT / "index.html")]
    itens += [(f"/{s}/", ROOT / s / "index.html") for s in SERVICOS]
    itens.append(("/blog/", ROOT / "blog" / "index.html"))
    posts = sorted(p for p in (ROOT / "blog").iterdir() if (p / "index.html").exists())
    itens += [(f"/blog/{p.name}/", p / "index.html") for p in posts]
    saida = []
    for url, path in itens:
        src = ler(path)
        saida.append((BASE + url, path, src, grafo(src)))
    return saida


def data_pagina(src, graph):
    for t in ("BlogPosting", "WebPage"):
        g = tipo(graph, t)
        if g and g.get("dateModified"):
            return g["dateModified"]
    return None


# ------------------------------------------------------------------ sitemap
def gerar_sitemap(pags):
    datas = {}
    for url, path, src, g in pags:
        datas[url] = data_pagina(src, g)
    posts = [d for (u, d) in datas.items() if "/blog/" in u and u != BASE + "/blog/" and d]
    datas[BASE + "/blog/"] = max(posts) if posts else HOJE
    for u, d in datas.items():
        datas[u] = limitar(d or HOJE)

    linhas = ['<?xml version="1.0" encoding="UTF-8"?>',
              '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" '
              'xmlns:image="http://www.google.com/schemas/sitemap-image/1.1">']
    for url, path, src, g in pags:
        extra = ""
        post = tipo(g, "BlogPosting")
        if post and post.get("image"):
            extra = "<image:image><image:loc>%s</image:loc></image:image>" % html.escape(post["image"])
        linhas.append("  <url><loc>%s</loc><lastmod>%s</lastmod>%s</url>" % (url, datas[url], extra))
    linhas.append("</urlset>")
    (ROOT / "sitemap.xml").write_text("\n".join(linhas) + "\n", encoding="utf8")
    return datas


# ------------------------------------------------------------------ llms-full.txt
class Texto(HTMLParser):
    """Extrai o texto de <main>, em blocos, ignorando navegação, botões e imagens."""
    PULA = {"script", "style", "svg", "nav", "figcaption", "button"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.dentro = False
        self.pula = 0
        self.blocos = []
        self.atual = None
        self.pilha = []
        self.btn = 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "main":
            self.dentro = True
        if not self.dentro:
            return
        if tag in self.PULA:
            self.pula += 1
            return
        if tag == "a" and "btn" in (a.get("class") or ""):
            self.btn += 1
            return
        if tag in ("h1", "h2", "h3", "p", "li", "summary", "dt", "dd", "address"):
            self.fecha()
            self.atual = [tag, ""]
        elif tag == "br" and self.atual:
            self.atual[1] += " "

    def handle_endtag(self, tag):
        if tag == "main":
            self.fecha()
            self.dentro = False
            return
        if not self.dentro:
            return
        if tag in self.PULA:
            self.pula = max(0, self.pula - 1)
            return
        if tag == "a" and self.btn:
            self.btn -= 1
            return
        if tag in ("h1", "h2", "h3", "p", "li", "summary", "dt", "dd", "address"):
            self.fecha()

    def handle_data(self, data):
        if self.dentro and not self.pula and not self.btn and self.atual is not None:
            self.atual[1] += data

    def fecha(self):
        if self.atual:
            t = re.sub(r"\s+", " ", self.atual[1]).strip()
            if t:
                self.blocos.append((self.atual[0], t))
        self.atual = None


def texto_pagina(src):
    p = Texto()
    p.feed(src)
    saida, ult = [], None
    for tag, t in p.blocos:
        if tag == "h1":
            continue
        if tag in ("h2", "h3"):
            saida.append("\n### " + t)
        elif tag == "summary":
            saida.append("\nP: " + t)
        elif tag == "li":
            saida.append("- " + t)
        elif tag == "dt":
            saida.append(t + ": ")
        elif tag == "dd" and saida and saida[-1].endswith(": "):
            saida[-1] += t
        else:
            saida.append(t)
        ult = tag
    return "\n".join(saida).strip()


def gerar_llms_full(pags):
    neg = tipo(grafo(ler(ROOT / "index.html")), "Electrician")
    out = ["# Elétrica Conexão Vix: texto completo",
           "",
           "> Conteúdo das páginas do site em texto simples, gerado a partir do HTML publicado em "
           f"{BASE}/. Atualizado em {HOJE}.",
           "",
           "## Dados do negócio",
           f"- Nome: {neg['name']}",
           "- Endereço: não divulgado; a equipe atende no local do cliente",
           "- Telefone e WhatsApp: (27) 99933-8844",
           "- Horário: aberto 24 horas, todos os dias",
           "- Área de atendimento: Vitória (foco), Vila Velha e Serra",
           f"- Site: {BASE}/",
           ""]
    ordem = ([BASE + "/"] + [f"{BASE}/{s}/" for s in SERVICOS])
    por_url = {u: (path, src, g) for u, path, src, g in pags}

    out.append("# Serviços\n")
    for u in ordem[1:]:
        path, src, g = por_url[u]
        svc = tipo(g, "Service")
        h1 = re.search(r"<h1[^>]*>(.*?)</h1>", src, re.S)
        titulo = html.unescape(re.sub(r"<[^>]+>", "", h1.group(1))).strip() if h1 else svc["name"]
        sub = re.search(r'<p class="pg-sub">(.*?)</p>', src, re.S)
        resp = re.search(r'id="resposta-rapida"><p class="resposta-t">[^<]*</p><p>(.*?)</p>', src, re.S)
        out.append(f"## {titulo}")
        out.append(f"URL: {u}")
        ja_dito = {"Resposta rápida"}
        if resp:
            r_txt = re.sub(r"\s+", " ", html.unescape(resp.group(1))).strip()
            ja_dito.add(r_txt)
            out.append("Resposta rápida: " + r_txt)
        if sub:
            s_txt = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", sub.group(1)))).strip()
            ja_dito.add(s_txt)
            out.append(s_txt)
        corpo = [l for l in texto_pagina(src).split("\n") if l.strip() not in ja_dito]
        out.append("\n".join(corpo).strip())
        out.append("")

    out.append("# Textos do blog\n")
    for u, path, src, g in pags:
        if "/blog/" not in u or u == BASE + "/blog/":
            continue
        post = tipo(g, "BlogPosting")
        out.append(f"## {post['headline']}")
        out.append(f"URL: {u}")
        out.append(f"Publicado em {post['datePublished']}, atualizado em {post['dateModified']}.")
        out.append(texto_pagina(src))
        out.append("")
    (ROOT / "llms-full.txt").write_text("\n".join(out).rstrip() + "\n", encoding="utf8")


# ------------------------------------------------------------------ feed RSS
def gerar_feed(pags):
    itens = []
    for u, path, src, g in pags:
        post = tipo(g, "BlogPosting")
        if not post:
            continue
        d = dt.datetime.strptime(post["datePublished"], "%Y-%m-%d").replace(
            hour=12, tzinfo=dt.timezone(dt.timedelta(hours=-3)))
        itens.append((d, u, post))
    itens.sort(key=lambda x: x[0], reverse=True)
    xml = ['<?xml version="1.0" encoding="UTF-8"?>',
           '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">',
           "<channel>",
           "<title>Blog da Elétrica Conexão Vix</title>",
           f"<link>{BASE}/blog/</link>",
           "<description>Dicas de segurança elétrica, quadros, chuveiro, carregador veicular, condomínios e "
           "lojas em shopping, da equipe da Elétrica Conexão Vix em Vitória, ES.</description>",
           "<language>pt-BR</language>",
           f'<atom:link href="{BASE}/blog/feed.xml" rel="self" type="application/rss+xml"/>']
    for d, u, post in itens:
        xml += ["<item>",
                f"<title>{html.escape(post['headline'])}</title>",
                f"<link>{u}</link>",
                f'<guid isPermaLink="true">{u}</guid>',
                f"<pubDate>{email.utils.format_datetime(d)}</pubDate>",
                f"<description>{html.escape(post['description'])}</description>",
                "</item>"]
    xml += ["</channel>", "</rss>"]
    (ROOT / "blog" / "feed.xml").write_text("\n".join(xml) + "\n", encoding="utf8")


# ------------------------------------------------------------------ IndexNow
def gerar_indexnow(pags):
    chaves = [p.stem for p in ROOT.glob("*.txt") if re.fullmatch(r"[0-9a-f]{32}", p.stem)]
    if len(chaves) != 1:
        sys.exit("IndexNow: esperava exatamente 1 arquivo <chave>.txt de 32 hex na raiz, achei %d" % len(chaves))
    chave = chaves[0]
    dados = {"host": HOST, "key": chave, "keyLocation": f"{BASE}/{chave}.txt",
             "urlList": [u for u, *_ in pags]}
    (ROOT / "indexnow-urls.json").write_text(
        json.dumps(dados, ensure_ascii=False, indent=2) + "\n", encoding="utf8")


def main():
    pags = paginas()
    datas = gerar_sitemap(pags)
    gerar_llms_full(pags)
    gerar_feed(pags)
    gerar_indexnow(pags)
    print("Hoje (BRT):", HOJE)
    for u, d in datas.items():
        print(" ", d, u)


if __name__ == "__main__":
    main()
