/**
 * Envio do briefing por e-mail, em HTML, com a edição em português.
 *
 * Fica no mesmo projeto do Apps Script de Codigo.gs (usa REPO, RAMO, PADRAO_PASTA
 * e chamarGitHub_ de lá) e usa o mesmo token do GitHub somente leitura.
 *
 * Como funciona:
 *   - Um gatilho roda verificarEEnviar() a cada 15 minutos.
 *   - Se houver um relatório de hoje que ainda não foi enviado, o script baixa
 *     relatorio-pt.md, monta um e-mail em HTML (resumo no topo, seções em cartões,
 *     links clicáveis) e envia para o dono da conta Google.
 *   - Cada relatório é enviado uma vez só (o nome da última pasta enviada fica em
 *     Propriedades do script, chave EMAIL_ULTIMO_ENVIADO).
 *
 * Troca de idioma: o botão "Read in English" do e-mail abre doGet() (abaixo), publicado como
 * app da web visível só para você, com o mesmo visual e o botão de volta para o português.
 *
 * Segurança:
 *   - A página só abre para a sua conta Google ("Quem pode acessar: somente eu") e só aceita
 *     pastas de relatorios/ com o nome no formato das execuções.
 *   - O destinatário é sempre o dono da conta Google que roda o script
 *     (ou o endereço da propriedade EMAIL_DESTINO, se você a criar). Nada no
 *     conteúdo dos relatórios muda o destinatário.
 *   - O texto dos relatórios é escapado antes de virar HTML: nenhuma marcação ou
 *     script vindo do relatório é executado. Só links http(s) viram links.
 *   - Escopo de envio: script.send_mail (só enviar, sem ler a sua caixa de entrada).
 *
 * Passo a passo de instalação: integracoes/google-drive/README.md, seção "E-mail diário".
 */

const EMAIL_EDICAO = 'relatorio-pt.md';
const EMAIL_EDICAO_EN = 'relatorio-en.md';
const EMAIL_LIMITE_HTML = 100000; // o Gmail corta mensagens acima de ~102 KB

// ---------- Gatilho e envio ----------

/** Executado pelo gatilho a cada 15 minutos. Envia o relatório de hoje, se ainda não foi enviado. */
function verificarEEnviar() {
  const props = PropertiesService.getScriptProperties();
  const token = props.getProperty('GITHUB_TOKEN');
  if (!token) throw new Error('Falta a propriedade GITHUB_TOKEN (Configurações do projeto → Propriedades do script).');

  const hora = Number(Utilities.formatDate(new Date(), 'America/Sao_Paulo', 'H'));
  if (hora < 7) return; // nenhum relatório sai antes das 07h30; poupa a cota do Apps Script
  const hoje = Utilities.formatDate(new Date(), 'America/Sao_Paulo', 'yyyy-MM-dd');
  const ultimo = props.getProperty('EMAIL_ULTIMO_ENVIADO') || '';
  const pendentes = execucoesDoDia_(token, hoje).filter(function (ex) { return ex.nome > ultimo; });
  if (!pendentes.length) return;

  const ex = pendentes[pendentes.length - 1]; // a mais recente de hoje
  // A paridade é o último arquivo da etapa 6: sem ela o relatório ainda não está completo.
  if (chamarGitHub_(token, ex.caminho + '/paridade.md', true) === null) return;
  const md = chamarGitHub_(token, ex.caminho + '/' + EMAIL_EDICAO, true);
  if (md === null) return;

  enviarRelatorio_(md, ex);
  props.setProperty('EMAIL_ULTIMO_ENVIADO', ex.nome);
}

/** Rode à mão para receber agora o relatório mais recente (teste). Não muda o controle de envio. */
function enviarUltimoAgora() {
  const token = PropertiesService.getScriptProperties().getProperty('GITHUB_TOKEN');
  if (!token) throw new Error('Falta a propriedade GITHUB_TOKEN.');
  const mes = Utilities.formatDate(new Date(), 'America/Sao_Paulo', 'yyyy/MM');
  let lista = execucoesDoMes_(token, mes);
  if (!lista.length) {
    const anterior = Utilities.formatDate(new Date(Date.now() - 32 * 86400000), 'America/Sao_Paulo', 'yyyy/MM');
    lista = execucoesDoMes_(token, anterior);
  }
  if (!lista.length) throw new Error('Nenhum relatório encontrado neste mês nem no anterior.');
  const ex = lista[lista.length - 1];
  const md = chamarGitHub_(token, ex.caminho + '/' + EMAIL_EDICAO, true);
  if (md === null) throw new Error('A pasta ' + ex.nome + ' não tem ' + EMAIL_EDICAO);
  enviarRelatorio_(md, ex);
}

/** Rode uma vez para criar o gatilho de 15 em 15 minutos. */
function instalarGatilhoEmail() {
  ScriptApp.getProjectTriggers().forEach(function (t) {
    if (t.getHandlerFunction() === 'verificarEEnviar') ScriptApp.deleteTrigger(t);
  });
  ScriptApp.newTrigger('verificarEEnviar').timeBased().everyMinutes(15).create();
  console.log('Gatilho criado: verificarEEnviar, a cada 15 minutos.');
}

function enviarRelatorio_(md, ex) {
  const destino = PropertiesService.getScriptProperties().getProperty('EMAIL_DESTINO') ||
    Session.getEffectiveUser().getEmail();
  const email = montarEmail_(md, { nome: ex.nome, caminho: ex.caminho, repo: REPO, ramo: RAMO, idioma: 'pt', urlWeb: urlWeb_() });
  MailApp.sendEmail({
    to: destino,
    subject: email.assunto,
    htmlBody: email.html,
    body: email.texto,
    name: 'Briefing Econômico',
  });
  console.log('E-mail enviado: ' + ex.nome + ' (' + email.html.length + ' caracteres de HTML)');
}

// ---------- Página com troca de idioma (app da web do Apps Script) ----------

/**
 * Página do relatório com o mesmo visual do e-mail e o botão PT/EN.
 * Parâmetros: ed=pt|en e pasta=relatorios/AAAA/MM/<execução> (sem pasta: a mais recente).
 * Publique como app da web com "Executar como: eu" e "Quem pode acessar: somente eu".
 */
function doGet(e) {
  const p = (e && e.parameter) || {};
  const idioma = p.ed === 'en' ? 'en' : 'pt';
  const token = PropertiesService.getScriptProperties().getProperty('GITHUB_TOKEN');
  if (!token) return HtmlService.createHtmlOutput('Falta a propriedade GITHUB_TOKEN.');
  if (p.pg === 'conjuntura') return paginaConjuntura_(token, idioma);
  if (p.pg === 'panorama') return paginaPanorama_(token, idioma);

  let ex = null;
  if (p.pasta) {
    const m = /^relatorios\/(\d{4})\/(\d{2})\/([^/]+)$/.exec(String(p.pasta));
    if (!m || !PADRAO_PASTA.test(m[3])) return HtmlService.createHtmlOutput('Pasta inválida.');
    ex = { nome: m[3], caminho: String(p.pasta) };
  } else {
    const lista = execucoesDoMes_(token, Utilities.formatDate(new Date(), 'America/Sao_Paulo', 'yyyy/MM'));
    if (!lista.length) return HtmlService.createHtmlOutput('Nenhum relatório neste mês.');
    ex = lista[lista.length - 1];
  }
  const md = chamarGitHub_(token, ex.caminho + '/' + (idioma === 'en' ? EMAIL_EDICAO_EN : EMAIL_EDICAO), true);
  if (md === null) return HtmlService.createHtmlOutput('Edição não encontrada em ' + ex.nome + '.');

  const pagina = montarEmail_(md, {
    nome: ex.nome, caminho: ex.caminho, repo: REPO, ramo: RAMO, idioma: idioma, urlWeb: urlWeb_(), web: true,
  });
  return HtmlService.createHtmlOutput(pagina.html)
    .setTitle(pagina.assunto)
    .addMetaTag('viewport', 'width=device-width, initial-scale=1');
}

/**
 * Dashboard da conjuntura (painel/dashboard.html), aberto com ?pg=conjuntura (e &ed=en para inglês).
 * O arquivo é gerado pelo workflow de coleta a partir de scripts/indicadores/dashboard_modelo.html,
 * que está no próprio repositório: é código do projeto, não conteúdo de terceiros. Os dados vão
 * embutidos como JSON e a página não chama nenhum endereço externo.
 */
function paginaConjuntura_(token, idioma) {
  const html = chamarGitHub_(token, 'painel/dashboard.html', true);
  if (html === null) return HtmlService.createHtmlOutput('O dashboard ainda não foi gerado (painel/dashboard.html).');
  const pagina = idioma === 'en' ? html.replace('let lang = "pt"', 'let lang = "en"') : html;
  return HtmlService.createHtmlOutput(pagina)
    .setTitle(idioma === 'en' ? 'Macro conditions' : 'Conjuntura macro')
    .addMetaTag('viewport', 'width=device-width, initial-scale=1');
}

/**
 * Panorama Econômico (panorama/ultimo.html), aberto com ?pg=panorama (e &ed=en para inglês).
 * Gerado pelo workflow panorama.yml a partir de scripts/indicadores/panorama_modelo.html (código do
 * projeto). Os textos do briefing chegam escapados; a página não chama nenhum endereço externo.
 */
function paginaPanorama_(token, idioma) {
  const html = chamarGitHub_(token, 'panorama/ultimo.html', true);
  if (html === null) return HtmlService.createHtmlOutput('O Panorama ainda não foi gerado (panorama/ultimo.html).');
  const pagina = html.replace('const LANG_FIXO = "";', 'const LANG_FIXO = "' + idioma + '";');
  return HtmlService.createHtmlOutput(pagina)
    .setTitle(idioma === 'en' ? 'Economic Overview' : 'Panorama Econômico')
    .addMetaTag('viewport', 'width=device-width, initial-scale=1');
}

/**
 * Endereço do app da web, lido só da propriedade URL_PAGINA; sem ela, vazio (os botões abrem o GitHub).
 * Não usa ScriptApp.getService().getUrl(): no editor novo do Apps Script ela devolve um endereço
 * /exec que não corresponde à implantação "Briefing PT/EN" e o Google responde "Não foi possível
 * abrir o arquivo" (página 404), como nos botões do e-mail de 25/11/2026.
 */
function urlWeb_() {
  const u = PropertiesService.getScriptProperties().getProperty('URL_PAGINA');
  return u && /^https:\/\/script\.google\.com\/macros\/s\/AKfycb[\w-]{20,}\/exec$/.test(u.trim()) ? u.trim() : '';
}

/** Rode à mão para ver no registro qual endereço os botões do e-mail vão usar. */
function conferirUrlPagina() {
  const u = urlWeb_();
  console.log(u
    ? 'Os botões do e-mail vão abrir: ' + u + '?pg=panorama  (abra este endereço no navegador para conferir)'
    : 'URL_PAGINA não está definida ou não termina em /exec. Os botões vão abrir o GitHub.');
}

function execucoesDoMes_(token, mes) {
  const json = chamarGitHub_(token, 'relatorios/' + mes, false);
  if (json === null) return [];
  return JSON.parse(json)
    .filter(function (item) { return item.type === 'dir' && PADRAO_PASTA.test(item.name); })
    .map(function (item) { return { nome: item.name, caminho: 'relatorios/' + mes + '/' + item.name }; })
    .sort(function (a, b) { return a.nome < b.nome ? -1 : 1; });
}

function execucoesDoDia_(token, dia) {
  return execucoesDoMes_(token, dia.slice(0, 4) + '/' + dia.slice(5, 7))
    .filter(function (ex) { return ex.nome.slice(0, 10) === dia; });
}

// ---------- Montagem do e-mail (funções puras, sem serviços do Google) ----------

const TXT = {
  pt: {
    lang: 'pt-BR', marca: 'Briefing econômico', outro: 'Read in English', panorama: '📊 Panorama Econômico', github: 'Ver no GitHub',
    indice: 'Nesta edição:', fonte: 'Ler na fonte', apoio: 'Fontes de apoio:', analise: 'análise do briefing',
    arquivos: 'Arquivos desta execução:', execucao: 'Execução',
    rodapeEmail: 'E-mail automático enviado pelo seu Apps Script "Briefing → Drive".',
    rodapeWeb: 'Página do seu Apps Script "Briefing → Drive", visível só para você.',
    incompleto: 'Relatório INCOMPLETO: a verificação ou a paridade não foi concluída. Veja o motivo no log da execução.',
    nomes: ['Edição em português', 'International Edition', 'Fontes', 'Verificação', 'Paridade', 'Log'],
  },
  en: {
    lang: 'en', marca: 'Economic briefing', outro: 'Ler em português', panorama: '📊 Economic Overview', github: 'View on GitHub',
    indice: 'In this edition:', fonte: 'Read source', apoio: 'Supporting sources:', analise: 'briefing analysis',
    arquivos: 'Files from this run:', execucao: 'Run',
    rodapeEmail: 'Automatic email sent by your "Briefing → Drive" Apps Script.',
    rodapeWeb: 'Page served by your "Briefing → Drive" Apps Script, visible only to you.',
    incompleto: 'INCOMPLETE report: verification or parity was not completed. See the run log for the reason.',
    nomes: ['Portuguese edition', 'International Edition', 'Sources', 'Verification', 'Parity', 'Log'],
  },
};

const COR = {
  fundo: '#eef1f5', papel: '#ffffff', tinta: '#1f2933', suave: '#52606d', linha: '#dde3ea',
  marca: '#0b2545', destaque: '#13315c', link: '#0b5cad', resumo: '#f3f7fc',
};
const FONTE = "-apple-system,'Segoe UI',Roboto,Helvetica,Arial,sans-serif";
const TIPOS = {
  'comunicado oficial': ['#e3f4ea', '#1b6b3a'], 'official release': ['#e3f4ea', '#1b6b3a'],
  'reportagem original': ['#e4eefb', '#174a8b'], 'original reporting': ['#e4eefb', '#174a8b'],
  'análise': ['#fdf1dc', '#8a5300'], 'analysis': ['#fdf1dc', '#8a5300'],
};
const ROTULOS_META = {
  titulo: ['título original', 'original headline'],
  publicacao: ['publicação', 'publication'],
  tipo: ['tipo de fonte', 'source type'],
  link: ['link'],
  apoio: ['fontes de apoio', 'supporting sources'],
};

/**
 * Converte o relatório em Markdown num e-mail (ou página) em HTML.
 * ctx: { nome, caminho, repo, ramo, idioma ('pt' | 'en'), urlWeb (endereço do app da web, ou ''),
 *        web (true quando a saída é a página, não o e-mail) }. Devolve { assunto, html, texto }.
 */
function montarEmail_(md, ctx) {
  const idioma = ctx.idioma === 'en' ? 'en' : 'pt';
  const T = TXT[idioma];
  const outroIdioma = idioma === 'pt' ? 'en' : 'pt';
  const base = 'https://github.com/' + ctx.repo + '/blob/' + ctx.ramo + '/' + ctx.caminho + '/';
  const arquivoEdicao = idioma === 'pt' ? EMAIL_EDICAO : EMAIL_EDICAO_EN;
  const arquivoOutro = idioma === 'pt' ? EMAIL_EDICAO_EN : EMAIL_EDICAO;
  // O botão de idioma abre a página do Apps Script, com o mesmo visual; sem ela, abre o GitHub.
  const urlOutro = ctx.urlWeb
    ? ctx.urlWeb + '?ed=' + outroIdioma + '&pasta=' + encodeURIComponent(ctx.caminho)
    : base + arquivoOutro;
  const linhas = md.replace(/\r\n/g, '\n').split('\n');
  const blocos = lerBlocos_(linhas);

  let titulo = 'Briefing econômico';
  let subtitulo = '';
  const avisos = [];
  const secoes = [];
  let atual = null;
  blocos.forEach(function (b) {
    if (b.tipo === 'h' && b.nivel === 1) { titulo = b.texto; return; }
    if (b.tipo === 'h' && b.nivel === 2) { atual = { titulo: b.texto, blocos: [] }; secoes.push(atual); return; }
    if (!atual) {
      if (b.tipo === 'p' && !subtitulo) subtitulo = b.texto;
      else if (b.tipo === 'quote' || b.tipo === 'p') avisos.push(b.texto);
      return;
    }
    atual.blocos.push(b);
  });

  const incompleto = /INCOMPLETO/.test(linhas.slice(0, 6).join(' '));
  const resumo = secoes.filter(function (s) { return /resumo executivo|executive summary/i.test(s.titulo); })[0];
  const destaques = resumo ? (resumo.blocos.filter(function (b) { return b.tipo === 'ul'; })[0] || { itens: [] }).itens : [];
  const manchetes = destaques.map(function (t) {
    const m = /^\*\*(.+?)\*\*/.exec(t);
    return m ? m[1].replace(/[:.]\s*$/, '').trim() : '';
  }).filter(Boolean);

  const data = /(\d{4})-(\d{2})-(\d{2})/.exec(ctx.nome);
  const dataCurta = data ? data[3] + '/' + data[2] : '';
  const assunto = (incompleto ? (idioma === 'en' ? '[INCOMPLETE] ' : '[INCOMPLETO] ') : '') + 'Briefing ' + dataCurta +
    (manchetes.length ? ': ' + manchetes[0] : '');
  const preheader = manchetes.slice(1, 4).join(' · ');

  const r = [];
  r.push('<!doctype html><html lang="', T.lang, '"><head><meta charset="utf-8">',
    '<meta name="viewport" content="width=device-width,initial-scale=1">',
    '<meta name="color-scheme" content="light only">', ctx.web ? '<base target="_top">' : '',
    '<title>', esc_(assunto), '</title></head>',
    '<body style="margin:0;padding:0;background:', COR.fundo, ';">',
    '<div style="display:none;max-height:0;overflow:hidden;opacity:0;">', esc_(preheader), '</div>',
    '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:', COR.fundo, ';">',
    '<tr><td align="center" style="padding:16px 8px;">',
    '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:680px;background:', COR.papel,
    ';border-radius:10px;font-family:', FONTE, ';color:', COR.tinta, ';font-size:16px;line-height:1.55;">');

  // Cabeçalho
  r.push('<tr><td style="background:', COR.marca, ';border-radius:10px 10px 0 0;padding:22px 18px;color:#fff;">',
    '<div style="font-size:12px;letter-spacing:1.5px;text-transform:uppercase;opacity:.75;">Global Economic &amp; Financial Intelligence</div>',
    '<div style="font-size:24px;font-weight:700;margin-top:4px;">', esc_(T.marca), '</div>',
    '<div style="font-size:14px;opacity:.85;margin-top:6px;">', inline_(subtitulo.replace(/\*\*/g, ''), base, '#ffffff'), '</div>',
    '<div style="margin-top:14px;">',
    botao_((idioma === 'pt' ? '🇬🇧 ' : '🇧🇷 ') + T.outro, urlOutro, true), ' ',
    ctx.urlWeb ? botao_(T.panorama, ctx.urlWeb + '?pg=panorama&ed=' + idioma, true) + ' ' : '',
    botao_(T.github, base + arquivoEdicao, true), '</div></td></tr>');

  if (incompleto) {
    r.push('<tr><td style="padding:16px 18px 0;"><div style="background:#fde8e8;border:1px solid #f5b5b5;color:#8a1c1c;',
      'border-radius:8px;padding:12px 14px;font-weight:600;">', esc_(T.incompleto), '</div></td></tr>');
  }

  // Resumo executivo em destaque
  if (resumo) {
    r.push('<tr><td style="padding:20px 18px 4px;">',
      '<div style="background:', COR.resumo, ';border-left:4px solid ', COR.destaque, ';border-radius:8px;padding:14px 18px;">',
      '<div style="font-size:13px;font-weight:700;letter-spacing:1px;text-transform:uppercase;color:', COR.destaque, ';margin-bottom:6px;">',
      esc_(limparNumero_(resumo.titulo)), '</div>');
    resumo.blocos.forEach(function (b) { r.push(renderBloco_(b, base)); });
    r.push('</div></td></tr>');
  }

  // Índice das seções
  const outras = secoes.filter(function (s) { return s !== resumo; });
  r.push('<tr><td style="padding:12px 18px 0;font-size:13px;color:', COR.suave, ';">',
    '<strong>', esc_(T.indice), '</strong> ',
    outras.map(function (s) { return esc_(limparNumero_(s.titulo).replace(/\s*\*\(.*\)\*\s*$/, '')); }).join(' · '),
    '</td></tr>');

  // Avisos da execução (painel ausente, chaves faltando etc.), discretos
  if (avisos.length) {
    r.push('<tr><td style="padding:12px 18px 0;">');
    avisos.forEach(function (a) {
      r.push('<div style="font-size:13px;color:', COR.suave, ';background:#f7f8fa;border-radius:6px;padding:8px 12px;margin-bottom:6px;">',
        inline_(a, base), '</div>');
    });
    r.push('</td></tr>');
  }

  // Seções
  outras.forEach(function (s) {
    const analise = /an[aá]lise do briefing|briefing analysis|briefing's own analysis/i.test(s.titulo);
    const nome = limparNumero_(s.titulo).replace(/\s*\*\(.*\)\*\s*$/, '');
    r.push('<tr><td style="padding:26px 18px 0;">',
      '<div style="font-size:20px;font-weight:700;color:', COR.marca, ';border-bottom:2px solid ', COR.linha, ';padding-bottom:6px;">',
      esc_(nome),
      analise ? ' <span style="font-size:12px;font-weight:600;background:#fdf1dc;color:#8a5300;border-radius:10px;padding:2px 8px;vertical-align:middle;">' + esc_(T.analise) + '</span>' : '',
      '</div>', renderSecao_(s.blocos, base, T), '</td></tr>');
  });

  // Rodapé
  r.push('<tr><td style="padding:26px 18px 24px;font-size:13px;color:', COR.suave, ';">',
    '<div style="border-top:1px solid ', COR.linha, ';padding-top:14px;">',
    esc_(T.arquivos), ' ',
    [EMAIL_EDICAO, EMAIL_EDICAO_EN, 'fontes.json', 'verificacao.md', 'paridade.md', 'execucao.log']
      .map(function (arq, j) { return link_(base + arq, T.nomes[j]); }).join(' · '),
    '<br>', esc_(T.execucao), ' ', esc_(ctx.nome), '. ', esc_(ctx.web ? T.rodapeWeb : T.rodapeEmail), '</div></td></tr>');

  r.push('</table></td></tr></table></body></html>');

  const html = r.join('');
  if (html.length > EMAIL_LIMITE_HTML) {
    // O Gmail mostra "Mensagem cortada" com o link "Ver mensagem inteira"; o conteúdo continua acessível.
    console.warn('E-mail com ' + html.length + ' caracteres: o Gmail pode cortar o final.');
  }
  return { assunto: assunto, html: html, texto: md };
}

/** Agrupa as linhas em blocos: títulos, parágrafos, listas, citações, tabelas e separadores. */
function lerBlocos_(linhas) {
  const blocos = [];
  let i = 0;
  while (i < linhas.length) {
    const l = linhas[i];
    const t = l.trim();
    if (!t) { i++; continue; }
    let m = /^(#{1,6})\s+(.*)$/.exec(t);
    if (m) { blocos.push({ tipo: 'h', nivel: m[1].length, texto: m[2].trim() }); i++; continue; }
    if (/^(-{3,}|\*{3,})$/.test(t)) { blocos.push({ tipo: 'hr' }); i++; continue; }
    if (/^\|/.test(t)) {
      const rows = [];
      while (i < linhas.length && /^\|/.test(linhas[i].trim())) {
        const linha = linhas[i].trim();
        if (!/^\|[\s:|-]+\|$/.test(linha)) {
          rows.push(linha.replace(/^\|/, '').replace(/\|$/, '').split('|').map(function (c) { return c.trim(); }));
        }
        i++;
      }
      blocos.push({ tipo: 'table', rows: rows });
      continue;
    }
    if (/^>/.test(t)) {
      const partes = [];
      while (i < linhas.length && /^>/.test(linhas[i].trim())) { partes.push(linhas[i].trim().replace(/^>\s?/, '')); i++; }
      blocos.push({ tipo: 'quote', texto: partes.join(' ') });
      continue;
    }
    if (/^[-*]\s+/.test(t)) {
      const itens = [];
      while (i < linhas.length && linhas[i].trim()) {
        const x = linhas[i].trim();
        if (/^[-*]\s+/.test(x)) itens.push(x.replace(/^[-*]\s+/, ''));
        else if (itens.length) itens[itens.length - 1] += ' ' + x;
        i++;
      }
      blocos.push({ tipo: 'ul', itens: itens });
      continue;
    }
    const partes = [];
    while (i < linhas.length && linhas[i].trim() && !/^(#{1,6}\s|>|\||[-*]\s+|-{3,}$)/.test(linhas[i].trim())) {
      partes.push(linhas[i].trim()); i++;
    }
    blocos.push({ tipo: 'p', texto: partes.join(' ') });
  }
  return blocos;
}

/** Dentro de uma seção, cada título ### ou #### abre um cartão de notícia; um título sem corpo vira rótulo de região. */
function renderSecao_(blocos, base, T) {
  const out = [];
  let k = 0;
  while (k < blocos.length) {
    const b = blocos[k];
    if (b.tipo === 'h') {
      const corpo = [];
      k++;
      // O cartão termina na lista de metadados (fonte, link); o que vier depois fica fora dele.
      while (k < blocos.length && blocos[k].tipo !== 'h') {
        corpo.push(blocos[k]);
        k++;
        if (ehMeta_(corpo[corpo.length - 1])) break;
      }
      if (!corpo.length) {
        out.push('<div style="margin:18px 0 0;font-size:13px;font-weight:700;letter-spacing:1px;text-transform:uppercase;color:',
          COR.suave, ';">', inline_(b.texto, base), '</div>');
      } else if (b.nivel >= 3 && corpo.some(ehMeta_)) {
        out.push(renderCartao_(b.texto, corpo, base, T));
      } else {
        out.push('<div style="margin:18px 0 6px;font-size:17px;font-weight:700;">', inline_(b.texto, base), '</div>');
        corpo.forEach(function (c) { out.push(renderBloco_(c, base)); });
      }
      continue;
    }
    out.push(renderBloco_(b, base));
    k++;
  }
  return out.join('');
}

function renderCartao_(tituloMd, corpo, base, T) {
  let etiqueta = '';
  const m = /^\[([^\]]+)\]\s*(.*)$/.exec(tituloMd);
  if (m) { etiqueta = m[1]; tituloMd = m[2]; }
  const out = ['<div style="margin:14px 0 0;border:1px solid ', COR.linha, ';border-radius:8px;padding:14px 16px;">'];
  if (etiqueta) {
    out.push('<div style="font-size:12px;color:', COR.suave, ';margin-bottom:4px;">● ', esc_(etiqueta), '</div>');
  }
  out.push('<div style="font-size:17px;font-weight:700;line-height:1.35;color:', COR.marca, ';margin-bottom:6px;">',
    inline_(tituloMd, base), '</div>');
  corpo.forEach(function (c) {
    out.push(ehMeta_(c) ? renderMeta_(c.itens, base, T) : renderBloco_(c, base));
  });
  out.push('</div>');
  return out.join('');
}

function campoMeta_(item) {
  const m = /^\*\*([^*:]+):\*\*\s*(.*)$/.exec(item);
  if (!m) return null;
  const rotulo = m[1].trim().toLowerCase();
  for (const chave in ROTULOS_META) {
    if (ROTULOS_META[chave].indexOf(rotulo) >= 0) return { chave: chave, valor: m[2].trim() };
  }
  return null;
}

function ehMeta_(b) {
  return b.tipo === 'ul' && b.itens.length > 0 && b.itens.every(function (x) { return campoMeta_(x) !== null; });
}

/** Rodapé do cartão: tipo de fonte, veículo e data numa linha, título original discreto e botão para a fonte. */
function renderMeta_(itens, base, T) {
  const c = {};
  itens.forEach(function (x) { const f = campoMeta_(x); c[f.chave] = f.valor; });
  const out = ['<div style="margin-top:10px;font-size:13px;color:', COR.suave, ';line-height:1.5;">'];
  if (c.tipo) {
    const cores = TIPOS[c.tipo.toLowerCase()] || ['#eef1f5', COR.suave];
    out.push('<span style="background:', cores[0], ';color:', cores[1], ';border-radius:10px;padding:1px 8px;font-weight:600;font-size:12px;">',
      esc_(c.tipo), '</span> ');
  }
  if (c.publicacao) out.push(inline_(c.publicacao, base));
  if (c.titulo) out.push('<div style="margin-top:4px;font-style:italic;">', inline_(c.titulo, base), '</div>');
  const url = c.link ? (/https?:\/\/\S+/.exec(c.link) || [''])[0] : '';
  if (url) out.push('<div style="margin-top:8px;">', botao_(T.fonte + ' · ' + dominio_(url), url, false), '</div>');
  if (c.apoio) out.push('<div style="margin-top:8px;"><strong>' + esc_(T.apoio) + '</strong> ', inline_(c.apoio, base), '</div>');
  out.push('</div>');
  return out.join('');
}

function renderBloco_(b, base) {
  if (b.tipo === 'p') return '<p style="margin:8px 0;">' + inline_(b.texto, base) + '</p>';
  if (b.tipo === 'quote') {
    return '<div style="margin:10px 0;font-size:14px;color:' + COR.suave + ';border-left:3px solid ' + COR.linha +
      ';padding:4px 12px;">' + inline_(b.texto, base) + '</div>';
  }
  if (b.tipo === 'hr') return '<div style="border-top:1px solid ' + COR.linha + ';margin:18px 0;"></div>';
  if (b.tipo === 'ul') {
    return '<ul style="margin:8px 0;padding-left:20px;">' + b.itens.map(function (x) {
      return '<li style="margin:6px 0;">' + inline_(x, base) + '</li>';
    }).join('') + '</ul>';
  }
  if (b.tipo === 'table') {
    if (!b.rows.length) return '';
    const cab = b.rows[0];
    const corpo = b.rows.slice(1);
    if (cab.length > 3) {
      // Tabelas largas não cabem no celular: cada linha vira um bloco empilhado.
      // As três primeiras colunas formam a linha principal; as demais vão abaixo, com o nome da coluna.
      return '<div style="margin:12px 0;border-top:1px solid ' + COR.linha + ';">' + corpo.map(function (row) {
        const vazio = function (x) { return !x || x === '—' || x === '-'; };
        const principal = row.slice(0, 3).filter(function (x) { return !vazio(x); })
          .map(function (x, j) { return j === 0 ? '<strong>' + inline_(x, base) + '</strong>' : inline_(x, base); }).join(' · ');
        const resto = row.slice(3).map(function (x, j) { return vazio(x) ? '' : esc_(cab[j + 3] || '') + ': ' + inline_(x, base); })
          .filter(Boolean).join(' · ');
        return '<div style="padding:8px 2px;border-bottom:1px solid ' + COR.linha + ';font-size:14px;line-height:1.45;">' + principal +
          (resto ? '<div style="font-size:12px;color:' + COR.suave + ';margin-top:2px;">' + resto + '</div>' : '') + '</div>';
      }).join('') + '</div>';
    }
    const th = 'style="text-align:left;padding:6px 8px;background:#f3f5f8;border-bottom:1px solid ' + COR.linha + ';font-weight:600;"';
    const td = 'style="padding:6px 8px;border-bottom:1px solid ' + COR.linha + ';vertical-align:top;"';
    return '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin:12px 0;border-collapse:collapse;font-size:13px;line-height:1.4;">' +
      '<tr>' + cab.map(function (h) { return '<th ' + th + '>' + inline_(h, base) + '</th>'; }).join('') + '</tr>' +
      corpo.map(function (row) {
        return '<tr>' + row.map(function (x, j) {
          return '<td ' + td + '>' + (j === 0 ? '<strong>' + inline_(x, base) + '</strong>' : inline_(x, base)) + '</td>';
        }).join('') + '</tr>';
      }).join('') + '</table>';
  }
  return '';
}

/** Formatação dentro da linha: escapa o HTML, depois aplica links, negrito, itálico e código. */
function inline_(texto, base, corLink) {
  const guardados = [];
  const guardar = function (html) { guardados.push(html); return '\u0000' + (guardados.length - 1) + '\u0000'; };
  let s = String(texto || '');
  // [texto](url)
  s = s.replace(/\[([^\]]+)\]\(([^)\s]+)\)/g, function (_, rotulo, url) {
    const abs = absoluta_(url, base);
    return abs ? guardar(link_(abs, rotulo, corLink, true)) : rotulo;
  });
  // URLs soltas viram um link curto com o domínio
  s = s.replace(/https?:\/\/[^\s<>()"]+[^\s<>()".,;:!?]/g, function (url) {
    return guardar(link_(url, dominio_(url), corLink));
  });
  // `código`
  s = s.replace(/`([^`]+)`/g, function (_, c) {
    return guardar('<span style="font-family:Menlo,Consolas,monospace;font-size:.9em;background:#f3f5f8;border-radius:4px;padding:0 4px;">' + esc_(c) + '</span>');
  });
  s = esc_(s);
  s = s.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
  s = s.replace(/(^|[^*\w])\*([^*\s][^*]*?)\*(?!\w)/g, '$1<em>$2</em>');
  return s.replace(/\u0000(\d+)\u0000/g, function (_, n) { return guardados[Number(n)]; });
}

function link_(url, rotulo, cor, rotuloMd) {
  const texto = rotuloMd ? inline_(rotulo, '', cor) : esc_(rotulo);
  return '<a href="' + esc_(url) + '" style="color:' + (cor || COR.link) + ';text-decoration:underline;">' + texto + '</a>';
}

function botao_(rotulo, url, claro) {
  const estilo = claro
    ? 'background:#ffffff;color:' + COR.marca + ';'
    : 'background:' + COR.destaque + ';color:#ffffff;';
  return '<a href="' + esc_(url) + '" style="display:inline-block;' + estilo +
    'text-decoration:none;font-weight:600;font-size:13px;border-radius:6px;padding:7px 12px;margin:2px 0;">' + esc_(rotulo) + '</a>';
}

/** Só http(s) vira link. Caminhos relativos do repositório viram links do GitHub. */
function absoluta_(url, base) {
  if (/^https?:\/\//i.test(url)) return url;
  if (/^[a-z][a-z0-9+.-]*:/i.test(url) || !base) return '';
  const raiz = base.replace(/(\/blob\/[^/]+\/).*$/, '$1');
  const partes = (url.charAt(0) === '/' ? raiz : base).split('/');
  partes.pop();
  url.replace(/^\//, '').split('/').forEach(function (p) {
    if (p === '..') { if (partes.length > raiz.split('/').length - 1) partes.pop(); } else if (p !== '.') partes.push(p);
  });
  return partes.join('/');
}

function dominio_(url) {
  const m = /^https?:\/\/(?:www\d*\.)?([^/:?#]+)/i.exec(url);
  return m ? m[1] : url;
}

function limparNumero_(titulo) {
  return titulo.replace(/^\d+\.\s*/, '');
}

function esc_(s) {
  return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}
