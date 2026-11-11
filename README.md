# eletricistaemvitoria.com.br

Site estático (HTML e CSS) da Elétrica Conexão Vix, eletricista 24h em Vitória-ES.

- Sem JavaScript no site: publicar a raiz deste repositório (GitHub Pages: branch `main`, pasta `/ (root)`).
- Domínio: eletricistaemvitoria.com.br (arquivo `CNAME`), com "Enforce HTTPS" ativo.
- As páginas HTML foram geradas a partir de um script externo. Se o site for gerado de novo a partir dele, as edições feitas aqui nas páginas (resposta rápida, JSON-LD, meta robots e Twitter Card) precisam ser levadas para o gerador, senão serão sobrescritas.

## SEO, AEO e GEO

| Arquivo | Função |
| --- | --- |
| `robots.txt` | Libera buscadores e robôs de IA e aponta o sitemap |
| `sitemap.xml` | Páginas com `lastmod` real e imagem de capa dos textos |
| `llms.txt` | Resumo do negócio para IAs (escrito à mão) |
| `llms-full.txt` | Texto completo das páginas (gerado) |
| `blog/feed.xml` | RSS do blog (gerado) |
| `indexnow-urls.json` e `<chave>.txt` | IndexNow: aviso ao Bing a cada publicação |
| `googlef561e982160a5e18.html` | Verificação da propriedade no Google Search Console |
| `.github/workflows/indexnow.yml` | Envia as URLs ao IndexNow depois de cada push na `main` |

### Regenerar os arquivos gerados

Depois de editar qualquer página, na raiz do repositório:

```
python3 tools/gerar_seo.py
```

O script lê o HTML publicado e reescreve `sitemap.xml`, `llms-full.txt`, `blog/feed.xml` e `indexnow-urls.json`. O `lastmod` sai do `dateModified` do JSON-LD de cada página e nunca passa da data de hoje no fuso de Brasília. Ao mudar o conteúdo de uma página, atualize também o `dateModified` dela.

### Regras de conteúdo

- Cada página abre com "Resposta rápida" de 40 a 60 palavras, marcada como `speakable`.
- O FAQ visível tem de ser igual ao `FAQPage` do JSON-LD.
- Um único H1 por página.
- Nada de fatos inventados: preço, prazo, número de registro e nomes de clientes só entram se o cliente confirmou.
- O site usa CSP restritiva (`script-src 'none'`, `style-src 'self'`): não há `style` inline nem scripts de terceiros.
