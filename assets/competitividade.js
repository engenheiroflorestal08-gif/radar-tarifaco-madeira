(() => {
  const els = {
    body: document.querySelector('#competition-body'),
    status: document.querySelector('#competition-status-badge'),
    period: document.querySelector('#competition-period'),
    message: document.querySelector('#competition-message'),
    thickness: document.querySelector('#profile-thickness'),
    width: document.querySelector('#profile-width'),
    recalc: document.querySelector('#recalc-competition'),
    tariffCountry: document.querySelector('#ranking-tariff-country'),
    tariffValue: document.querySelector('#ranking-tariff-value'),
    priceCountry: document.querySelector('#ranking-price-country'),
    priceValue: document.querySelector('#ranking-price-value'),
    landedCountry: document.querySelector('#ranking-landed-country'),
    landedValue: document.querySelector('#ranking-landed-value'),
  };

  let payload = { paises: [], metadata: {}, perfil_conversao: {} };

  const fmtNumber = (value, digits = 2) => {
    const num = Number(value);
    if (!Number.isFinite(num)) return '—';
    return new Intl.NumberFormat('pt-BR', {
      minimumFractionDigits: digits,
      maximumFractionDigits: digits,
    }).format(num);
  };

  const fmtMoney = (value, digits = 2) => {
    const num = Number(value);
    if (!Number.isFinite(num)) return '—';
    return `US$ ${fmtNumber(num, digits)}`;
  };

  const fmtPercent = value => {
    const num = Number(value);
    return Number.isFinite(num) ? `${fmtNumber(num, 2)}%` : '—';
  };

  const activeTariff = country => {
    const legal = Number(country.tarifa_legal_atual_pct);
    if (Number.isFinite(legal)) return legal;
    const effective = Number(country.tarifa_efetiva_pct);
    return Number.isFinite(effective) ? effective : null;
  };

  const convertRows = () => {
    const thickness = Number(els.thickness.value);
    const width = Number(els.width.value);
    const cubicMetersPerLinearMeter = (thickness / 1000) * (width / 1000);

    return (payload.paises || []).map(country => {
      const linearPrice = Number(country.preco_usd_m_linear);
      const priceM3 = Number.isFinite(linearPrice) && cubicMetersPerLinearMeter > 0
        ? linearPrice / cubicMetersPerLinearMeter
        : null;
      const tariff = activeTariff(country);
      const landed = Number.isFinite(priceM3) && Number.isFinite(tariff)
        ? priceM3 * (1 + tariff / 100)
        : null;
      return { ...country, preco_usd_m3_calculado: priceM3, tarifa_aplicada_pct: tariff, preco_apos_tarifa_usd_m3_calculado: landed };
    });
  };

  const tariffClass = value => {
    const num = Number(value);
    if (!Number.isFinite(num)) return '';
    if (num >= 20) return 'tariff-high';
    if (num >= 5) return 'tariff-medium';
    return '';
  };

  const renderRankings = rows => {
    const tariffs = rows.filter(r => Number.isFinite(r.tarifa_aplicada_pct)).sort((a, b) => b.tarifa_aplicada_pct - a.tarifa_aplicada_pct);
    const prices = rows.filter(r => Number.isFinite(r.preco_usd_m3_calculado)).sort((a, b) => b.preco_usd_m3_calculado - a.preco_usd_m3_calculado);
    const landed = rows.filter(r => Number.isFinite(r.preco_apos_tarifa_usd_m3_calculado)).sort((a, b) => a.preco_apos_tarifa_usd_m3_calculado - b.preco_apos_tarifa_usd_m3_calculado);

    const topTariff = tariffs[0];
    els.tariffCountry.textContent = topTariff?.pais || '—';
    els.tariffValue.textContent = topTariff ? fmtPercent(topTariff.tarifa_aplicada_pct) : 'Dados indisponíveis';

    const topPrice = prices[0];
    els.priceCountry.textContent = topPrice?.pais || '—';
    els.priceValue.textContent = topPrice ? `${fmtMoney(topPrice.preco_usd_m3_calculado, 0)}/m³` : 'Dados indisponíveis';

    const bestLanded = landed[0];
    els.landedCountry.textContent = bestLanded?.pais || '—';
    els.landedValue.textContent = bestLanded ? `${fmtMoney(bestLanded.preco_apos_tarifa_usd_m3_calculado, 0)}/m³` : 'Dados indisponíveis';
  };

  const renderTable = rows => {
    els.body.innerHTML = '';
    if (!rows.length) {
      els.body.innerHTML = '<tr><td colspan="7" class="table-loading">Nenhum país configurado.</td></tr>';
      return;
    }

    const sorted = [...rows].sort((a, b) => {
      const aValue = Number.isFinite(a.preco_apos_tarifa_usd_m3_calculado) ? a.preco_apos_tarifa_usd_m3_calculado : Number.POSITIVE_INFINITY;
      const bValue = Number.isFinite(b.preco_apos_tarifa_usd_m3_calculado) ? b.preco_apos_tarifa_usd_m3_calculado : Number.POSITIVE_INFINITY;
      return aValue - bValue || a.pais.localeCompare(b.pais, 'pt-BR');
    });

    sorted.forEach(country => {
      const row = document.createElement('tr');
      const sourceNote = country.observacao_tarifa || country.fonte_tarifa || '';
      row.innerHTML = `
        <td>
          <div class="country-cell">
            <span class="country-code">${country.iso || '--'}</span>
            <span><strong>${country.pais}</strong><small>${sourceNote}</small></span>
          </div>
        </td>
        <td class="value-strong">${fmtMoney(country.preco_usd_m_linear, 2)}</td>
        <td>${Number.isFinite(country.preco_usd_m3_calculado) ? `${fmtMoney(country.preco_usd_m3_calculado, 0)}` : '—'}</td>
        <td class="${tariffClass(country.tarifa_legal_atual_pct)}">${fmtPercent(country.tarifa_legal_atual_pct)}</td>
        <td class="${tariffClass(country.tarifa_efetiva_pct)}">${fmtPercent(country.tarifa_efetiva_pct)}</td>
        <td class="value-strong">${Number.isFinite(country.preco_apos_tarifa_usd_m3_calculado) ? `${fmtMoney(country.preco_apos_tarifa_usd_m3_calculado, 0)}` : '—'}</td>
        <td>${fmtNumber(country.quantidade_m_linear, 0)}</td>
      `;
      els.body.append(row);
    });
  };

  const render = () => {
    const profile = payload.perfil_conversao || {};
    if (!els.thickness.dataset.initialized) {
      els.thickness.value = profile.espessura_mm || 18;
      els.width.value = profile.largura_mm || 70;
      els.thickness.dataset.initialized = 'true';
    }

    const rows = convertRows();
    renderRankings(rows);
    renderTable(rows);

    const metadata = payload.metadata || {};
    const status = metadata.status || 'demonstrativo';
    els.status.textContent = status === 'ok' ? 'Dados oficiais carregados' : status === 'aguardando_chave' ? 'Aguardando chave da API' : 'Base demonstrativa';
    els.status.classList.toggle('warning', status !== 'ok');
    els.status.classList.toggle('error', status === 'erro');
    els.period.textContent = `Período: ${metadata.periodo_referencia || 'não disponível'}`;
    els.message.textContent = metadata.mensagem || 'O preço médio é calculado pelo valor aduaneiro dividido pela quantidade importada.';
  };

  const init = async () => {
    try {
      const response = await fetch(`data/competitividade.json?v=${Date.now()}`);
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      payload = await response.json();
      render();
    } catch (error) {
      console.error(error);
      els.status.textContent = 'Falha ao carregar';
      els.status.classList.add('error');
      els.body.innerHTML = '<tr><td colspan="7" class="table-loading">Não foi possível carregar data/competitividade.json.</td></tr>';
    }
  };

  els.recalc?.addEventListener('click', render);
  [els.thickness, els.width].forEach(input => input?.addEventListener('change', render));
  init();
})();
