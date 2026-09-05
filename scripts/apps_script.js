/**
 * apps_script.js — Middleware Google Apps Script para o PWA mobile FinTrack
 *
 * COMO USAR:
 * 1. Abra a planilha FinTrack no Google Sheets
 * 2. Clique em Extensões → Apps Script
 * 3. Apague o conteúdo do editor e cole TODO o conteúdo deste arquivo
 * 4. Altere SECRET_KEY abaixo para uma senha forte (a mesma que colocar em config.js)
 * 5. Clique em Salvar (ícone de disquete)
 * 6. Clique em Implantar → Nova implantação
 *    - Tipo: Aplicativo da Web
 *    - Executar como: Eu (sua conta Google)
 *    - Quem tem acesso: Qualquer pessoa
 * 7. Clique em Implantar e copie a URL gerada
 * 8. Cole essa URL como APPS_SCRIPT_URL em mobile/config.js
 *
 * SEGURANÇA:
 * - Toda requisição POST deve incluir o campo "secret" igual a SECRET_KEY
 * - GET retorna apenas dados de referência (categorias, contas, cartões)
 *   sem necessidade de secret, pois esses dados não são financeiros sensíveis
 * - Idempotência: reenvios com o mesmo id_grupo não duplicam registros
 */

const SECRET_KEY = "TROQUE_ESTA_CHAVE_POR_UMA_SENHA_FORTE";

// Limite de requisições POST por janela de tempo (proteção básica)
const RATE_LIMIT_CACHE_KEY = "fintrack_rate_limit";
const RATE_LIMIT_MAX       = 30;   // requisições máximas
const RATE_LIMIT_JANELA_MS = 60000; // 60 segundos

// ─── Roteador principal ───────────────────────────────────────────────────────

function doGet(e) {
  try {
    const action = (e.parameter && e.parameter.action) || "status";
    let result;

    switch (action) {
      case "status":
        result = { ok: true, msg: "FinTrack API ativa" };
        break;
      case "dados":
        // Retorna categorias + contas + cartões em uma única chamada
        result = getDados();
        break;
      // Manter compatibilidade com chamadas individuais
      case "categorias":
        result = getCategorias();
        break;
      case "contas":
        result = getContas();
        break;
      case "cartoes":
        result = getCartoes();
        break;
      default:
        result = { ok: false, error: "Ação desconhecida" };
    }

    return jsonResponse(result);
  } catch (err) {
    return jsonResponse({ ok: false, error: "Erro interno" });
  }
}

function doPost(e) {
  try {
    // Rate limiting
    if (!verificarRateLimit()) {
      return jsonResponse({ ok: false, error: "Muitas requisições. Aguarde um momento." });
    }

    let payload;
    try {
      payload = JSON.parse(e.postData.contents);
    } catch (_) {
      return jsonResponse({ ok: false, error: "Payload inválido" });
    }

    // Verificação do secret (comparação de tempo constante simulada)
    if (!payload.secret || payload.secret.length !== SECRET_KEY.length ||
        !_secretIgual(payload.secret, SECRET_KEY)) {
      return jsonResponse({ ok: false, error: "Não autorizado" });
    }

    const action = String(payload.action || "").substring(0, 50);
    let result;

    switch (action) {
      case "salvar_gasto":
        result = salvarGasto(payload);
        break;
      default:
        result = { ok: false, error: "Ação desconhecida" };
    }

    return jsonResponse(result);
  } catch (err) {
    return jsonResponse({ ok: false, error: "Erro interno" });
  }
}

// ─── Helpers ─────────────────────────────────────────────────────────────────

function jsonResponse(data) {
  return ContentService
    .createTextOutput(JSON.stringify(data))
    .setMimeType(ContentService.MimeType.JSON);
}

function getSheet(name) {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const ws = ss.getSheetByName(name);
  if (!ws) throw new Error("Aba não encontrada: " + name);
  return ws;
}

function generateId() {
  return Utilities.getUuid();
}

function nowIso() {
  return new Date().toISOString().replace("T", " ").substring(0, 19);
}

/** Lê uma aba como array de objetos usando a primeira linha como cabeçalhos. */
function sheetToObjects(ws) {
  const data = ws.getDataRange().getValues();
  if (data.length < 2) return [];
  const headers = data[0];
  return data.slice(1).map(row => {
    const obj = {};
    headers.forEach((h, i) => { obj[h] = String(row[i]); });
    return obj;
  });
}

/**
 * Sanitiza string para evitar injeção de fórmula no Google Sheets.
 * Valores que começam com = + - @ | são prefixados com apóstrofo,
 * fazendo o Sheets tratá-los como texto literal.
 */
function sanitizeCelula(valor) {
  if (typeof valor !== "string") return valor;
  return valor.replace(/^([=+\-@|])/, "'$1");
}

/** Comparação de strings resistente a timing attacks. */
function _secretIgual(a, b) {
  if (a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) {
    diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  }
  return diff === 0;
}

/** Rate limiting simples via CacheService (best-effort). */
function verificarRateLimit() {
  try {
    const cache = CacheService.getScriptCache();
    const val = cache.get(RATE_LIMIT_CACHE_KEY);
    const count = val ? parseInt(val) : 0;
    if (count >= RATE_LIMIT_MAX) return false;
    cache.put(RATE_LIMIT_CACHE_KEY, String(count + 1), Math.ceil(RATE_LIMIT_JANELA_MS / 1000));
    return true;
  } catch (_) {
    return true; // fail open se CacheService indisponível
  }
}

// ─── Leitura de dados (GET) ───────────────────────────────────────────────────

function getDados() {
  return {
    ok: true,
    categorias: getCategorias().data,
    contas: getContas().data,
    cartoes: getCartoes().data,
  };
}

function getCategorias() {
  const rows = sheetToObjects(getSheet("categorias"));
  const ativas = rows
    .filter(r => r.ativo === "True")
    .map(r => ({ id: r.id, nome: r.nome, icone: r.icone }));
  return { ok: true, data: ativas };
}

function getContas() {
  const rows = sheetToObjects(getSheet("contas_bancarias"));
  const ativas = rows
    .filter(r => r.ativo === "True")
    .map(r => ({ id: r.id, nome: r.nome, tipo: r.tipo }));
  return { ok: true, data: ativas };
}

function getCartoes() {
  const rows = sheetToObjects(getSheet("cartoes"));
  const ativos = rows
    .filter(r => r.ativo === "True")
    .map(r => ({
      id: r.id,
      nome: r.nome,
      dia_fechamento: r.dia_fechamento,
      dia_vencimento: r.dia_vencimento,
    }));
  return { ok: true, data: ativos };
}

// ─── Escrita de dados (POST) ──────────────────────────────────────────────────

/**
 * Salva um gasto recebido do PWA mobile.
 *
 * Campos esperados no payload:
 *   id_grupo       : UUID gerado pelo mobile (para idempotência)
 *   data_compra    : "YYYY-MM-DD"
 *   valor_total    : número
 *   num_parcelas   : inteiro (1 para à vista)
 *   categoria      : string (nome da categoria)
 *   forma_pagamento: "Dinheiro" | "Pix" | "Débito" | "Crédito"
 *   conta_cartao   : string (nome da conta ou cartão)
 *   descricao      : string (opcional)
 */
function salvarGasto(payload) {
  const required = ["id_grupo", "data_compra", "valor_total", "num_parcelas",
                    "categoria", "forma_pagamento", "conta_cartao"];
  for (const field of required) {
    if (payload[field] === undefined || payload[field] === "") {
      return { ok: false, error: "Campo obrigatório ausente: " + field };
    }
  }

  const idGrupo      = String(payload.id_grupo).substring(0, 36);
  const dataCompra   = String(payload.data_compra).substring(0, 10);
  const valorTotal   = parseFloat(payload.valor_total);
  const numParcelas  = Math.min(Math.max(parseInt(payload.num_parcelas) || 1, 1), 360);
  const categoria    = sanitizeCelula(String(payload.categoria).substring(0, 100));
  const formaPgto    = sanitizeCelula(String(payload.forma_pagamento).substring(0, 20));
  const contaCartao  = sanitizeCelula(String(payload.conta_cartao).substring(0, 100));
  const descricao    = sanitizeCelula(String(payload.descricao || "").substring(0, 500));

  if (isNaN(valorTotal) || valorTotal <= 0 || valorTotal > 1e7) {
    return { ok: false, error: "Valor inválido" };
  }
  if (!/^\d{4}-\d{2}-\d{2}$/.test(dataCompra)) {
    return { ok: false, error: "Data inválida" };
  }

  const ws = getSheet("gastos");

  // Idempotência: verificar se id_grupo já existe
  const existentes = sheetToObjects(ws);
  if (existentes.some(r => r.id_grupo === idGrupo)) {
    return { ok: true, msg: "Gasto já registrado anteriormente.", id_grupo: idGrupo };
  }

  let parcelas;
  if (formaPgto === "Crédito") {
    parcelas = calcularParcelas(dataCompra, valorTotal, numParcelas, contaCartao);
  } else {
    const mesRef = dataCompra.substring(0, 7);
    parcelas = [{
      data_fatura:    dataCompra,
      mes_referencia: mesRef,
      parcela_num:    1,
      total_parcelas: 1,
      valor_parcela:  valorTotal,
    }];
  }

  const rows = parcelas.map(p => [
    generateId(),
    idGrupo,
    dataCompra,
    p.data_fatura,
    p.mes_referencia,
    String(p.parcela_num),
    String(p.total_parcelas),
    String(p.valor_parcela.toFixed(2)),
    String(valorTotal.toFixed(2)),
    categoria,
    formaPgto,
    contaCartao,
    descricao,
    nowIso(),
  ]);

  ws.getRange(ws.getLastRow() + 1, 1, rows.length, rows[0].length).setValues(rows);

  return {
    ok: true,
    msg: `${parcelas.length} parcela(s) salva(s)`,
    id_grupo: idGrupo,
  };
}

/**
 * Calcula as datas de fatura e mes_referencia para cada parcela de crédito.
 * Regra: ciclo começa no dia_fechamento. Compra feita no dia_fechamento ou
 * após → vai para o PRÓXIMO ciclo.
 */
function calcularParcelas(dataCompraStr, valorTotal, numParcelas, nomeCartao) {
  let diaFechamento = 28;
  let diaVencimento = 10;

  try {
    const cartoes = sheetToObjects(getSheet("cartoes"));
    const cartao  = cartoes.find(c => c.nome === nomeCartao && c.ativo === "True");
    if (cartao) {
      diaFechamento = parseInt(cartao.dia_fechamento) || 28;
      diaVencimento = parseInt(cartao.dia_vencimento) || 10;
    }
  } catch (_) { /* usa fallback */ }

  const compra    = new Date(dataCompraStr + "T12:00:00");
  const diaCompra = compra.getDate();

  let anoCiclo = compra.getFullYear();
  let mesCiclo = compra.getMonth(); // 0-indexed

  if (diaCompra >= diaFechamento) {
    mesCiclo += 1;
    if (mesCiclo > 11) { mesCiclo = 0; anoCiclo += 1; }
  }

  const valorParcela = valorTotal / numParcelas;
  const parcelas = [];

  for (let i = 0; i < numParcelas; i++) {
    let anoFat = anoCiclo;
    let mesFat = mesCiclo + i;
    while (mesFat > 11) { mesFat -= 12; anoFat += 1; }

    const ultimoDia = new Date(anoFat, mesFat + 1, 0).getDate();
    const diaVenc   = Math.min(diaVencimento, ultimoDia);
    const dataFatura = `${anoFat}-${String(mesFat + 1).padStart(2, "0")}-${String(diaVenc).padStart(2, "0")}`;
    const mesRef     = `${anoFat}-${String(mesFat + 1).padStart(2, "0")}`;

    parcelas.push({
      data_fatura:    dataFatura,
      mes_referencia: mesRef,
      parcela_num:    i + 1,
      total_parcelas: numParcelas,
      valor_parcela:  valorParcela,
    });
  }

  return parcelas;
}
