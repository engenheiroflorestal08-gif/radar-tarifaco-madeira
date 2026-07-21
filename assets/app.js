const state = {
  items: [],
  filtered: [],
  metadata: {},
};

const els = {
  updateStatus: document.querySelector('#update-status'),
  lastUpdate: document.querySelector('#last-update'),
  coverageText: document.querySelector('#coverage-text'),
  metricTotal: document.querySelector('#metric-total'),
  metricCritical: document.querySelector('#metric-critical'),
  metricWood: document.querySelector('#metric-wood'),
  metricOfficial: document.querySelector('#metric-official'),
  criticalBanner: document.querySelector('#critical-banner'),
  criticalTitle: document.querySelector('#critical-title'),
  criticalDescription: document.querySelector('#critical-description'),
  showCritical: document.querySelector('#show-critical'),
  categoryChart: document.querySelector('#category-chart'),
  searchInput: document.querySelector('#search-input'),
  categoryFilter: document.querySelector('#category-filter'),
  priorityFilter: document.querySelector('#priority-filter'),
  periodFilter: document.querySelector('#period-filter'),
  newsList: document.querySelector('#news-list'),
  resultCount: document.querySelector('#result-count'),
  emptyState: document.querySelector('#empty-state'),
  template: document.querySelector('#news-card-template'),
  themeToggle: document.querySelector('#theme-toggle'),
};

const priorityLabels = {
  critica: 'Crítica',
  alta: 'Alta',
  media: 'Média',
  baixa: 'Baixa',
};

function formatDate(value, withTime = false) {
  if (!value) return 'Data não informada';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat('pt-BR', {
    dateStyle: 'medium',
    ...(withTime ? { timeStyle: 'short' } : {}),
  }).format(date);
}

function normalize(value = '') {
  return value
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase();
}

function isWithinDays(dateValue, days) {
  if (days === 'all') return true;
  const date = new Date(dateValue);
  if (Number.isNaN(date.getTime())) return false;
  const difference = Date.now() - date.getTime();
  return difference <= Number(days) * 24 * 60 * 60 * 1000;
}

function renderMetrics() {
  const items = state.items;
  const critical = items.filter(item => item.prioridade === 'critica');
  const wood = items.filter(item => item.foco_madeira || normalize(item.categoria).includes('madeira'));
  const official = items.filter(item => item.tipo_fonte === 'Oficial');

  els.metricTotal.textContent = items.length;
  els.metricCritical.textContent = critical.length;
  els.metricWood.textContent = wood.length;
  els.metricOfficial.textContent = official.length;

  if (critical.length) {
    const newest = critical[0];
    els.criticalTitle.textContent = newest.titulo;
    els.criticalDescription.textContent = `${critical.length} alerta(s) crítico(s) na base. O mais recente foi publicado por ${newest.fonte}.`;
    els.criticalBanner.classList.remove('hidden');
  }
}

function renderCategoryOptions() {
  const categories = [...new Set(state.items.map(item => item.categoria).filter(Boolean))].sort();
  for (const category of categories) {
    const option = document.createElement('option');
    option.value = category;
    option.textContent = category;
    els.categoryFilter.append(option);
  }
}

function renderCategoryChart() {
  const counts = state.items.reduce((acc, item) => {
    const category = item.categoria || 'Outros';
    acc[category] = (acc[category] || 0) + 1;
    return acc;
  }, {});

  const sorted = Object.entries(counts).sort((a, b) => b[1] - a[1]).slice(0, 6);
  const max = Math.max(...sorted.map(([, count]) => count), 1);
  els.categoryChart.innerHTML = '';

  for (const [category, count] of sorted) {
    const item = document.createElement('div');
    item.className = 'bar-item';
    item.innerHTML = `
      <div class="bar-item-head"><span>${category}</span><b>${count}</b></div>
      <div class="bar-track"><div class="bar-fill" style="width:${Math.max((count / max) * 100, 7)}%"></div></div>
    `;
    els.categoryChart.append(item);
  }
}

function applyFilters() {
  const query = normalize(els.searchInput.value.trim());
  const category = els.categoryFilter.value;
  const priority = els.priorityFilter.value;
  const period = els.periodFilter.value;

  state.filtered = state.items.filter(item => {
    const searchable = normalize([
      item.titulo,
      item.resumo,
      item.fonte,
      item.categoria,
      ...(item.tags || []),
    ].join(' '));

    return (!query || searchable.includes(query))
      && (category === 'all' || item.categoria === category)
      && (priority === 'all' || item.prioridade === priority)
      && isWithinDays(item.data_publicacao, period);
  });

  renderNews();
}

function renderNews() {
  els.newsList.innerHTML = '';
  els.resultCount.textContent = `${state.filtered.length} resultado${state.filtered.length === 1 ? '' : 's'}`;
  els.emptyState.classList.toggle('hidden', state.filtered.length > 0);

  for (const item of state.filtered) {
    const fragment = els.template.content.cloneNode(true);
    const article = fragment.querySelector('.news-card');
    const priorityBadge = fragment.querySelector('.priority-badge');
    const categoryBadge = fragment.querySelector('.category-badge');
    const sourceType = fragment.querySelector('.source-type');
    const link = fragment.querySelector('.news-link');
    const summary = fragment.querySelector('.news-summary');
    const source = fragment.querySelector('.news-source');
    const date = fragment.querySelector('.news-date');
    const tags = fragment.querySelector('.news-tags');

    priorityBadge.textContent = priorityLabels[item.prioridade] || 'Média';
    priorityBadge.classList.add(`priority-${item.prioridade || 'media'}`);
    categoryBadge.textContent = item.categoria || 'Outros';
    sourceType.textContent = item.tipo_fonte || 'Notícia';
    link.textContent = item.titulo;
    link.href = item.url;
    summary.textContent = item.resumo || 'Acesse a fonte para consultar os detalhes desta publicação.';
    source.textContent = item.fonte || 'Fonte não informada';
    date.textContent = formatDate(item.data_publicacao);
    date.dateTime = item.data_publicacao || '';

    for (const tagText of (item.tags || []).slice(0, 6)) {
      const tag = document.createElement('span');
      tag.className = 'tag';
      tag.textContent = tagText;
      tags.append(tag);
    }

    if (item.prioridade === 'critica') article.setAttribute('data-critical', 'true');
    els.newsList.append(fragment);
  }
}

function setupTheme() {
  const saved = localStorage.getItem('tarifaco-theme');
  if (saved) document.documentElement.dataset.theme = saved;

  els.themeToggle.addEventListener('click', () => {
    const next = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark';
    document.documentElement.dataset.theme = next;
    localStorage.setItem('tarifaco-theme', next);
  });
}

function setupEvents() {
  [els.searchInput, els.categoryFilter, els.priorityFilter, els.periodFilter]
    .forEach(element => element.addEventListener('input', applyFilters));

  els.showCritical.addEventListener('click', () => {
    els.priorityFilter.value = 'critica';
    applyFilters();
    document.querySelector('.feed-panel').scrollIntoView({ behavior: 'smooth' });
  });
}

async function init() {
  setupTheme();
  setupEvents();

  try {
    const response = await fetch(`data/noticias.json?v=${Date.now()}`);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const payload = await response.json();

    state.items = (payload.noticias || []).sort((a, b) => {
      const priorityOrder = { critica: 4, alta: 3, media: 2, baixa: 1 };
      const dateDiff = new Date(b.data_publicacao) - new Date(a.data_publicacao);
      if (Math.abs(dateDiff) > 7 * 24 * 60 * 60 * 1000) return dateDiff;
      return (priorityOrder[b.prioridade] || 0) - (priorityOrder[a.prioridade] || 0) || dateDiff;
    });
    state.filtered = [...state.items];
    state.metadata = payload.metadata || {};

    els.lastUpdate.textContent = formatDate(state.metadata.atualizado_em, true);
    const failures = state.metadata.falhas_de_coleta || [];
    const baseDescription = state.metadata.descricao || 'Monitoramento automatizado de notícias públicas.';
    els.coverageText.textContent = failures.length
      ? `${baseDescription} ${failures.length} fonte(s) apresentaram falha na última execução.`
      : baseDescription;
    els.updateStatus.innerHTML = failures.length
      ? '<span class="pulse"></span>Dados com alertas'
      : '<span class="pulse"></span>Dados carregados';

    renderMetrics();
    renderCategoryOptions();
    renderCategoryChart();
    renderNews();
  } catch (error) {
    console.error(error);
    els.updateStatus.textContent = 'Falha ao carregar dados';
    els.lastUpdate.textContent = 'Arquivo indisponível';
    els.coverageText.textContent = 'Execute o atualizador ou abra o projeto por um servidor local.';
    els.emptyState.classList.remove('hidden');
    els.emptyState.querySelector('strong').textContent = 'Não foi possível carregar data/noticias.json';
    els.emptyState.querySelector('p').textContent = 'Consulte o README para iniciar o painel corretamente.';
  }
}

init();
