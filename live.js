const $ = (selector) => document.querySelector(selector);
const escapeHtml = (value) => String(value ?? '').replace(/[&<>"']/g, (character) => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
})[character]);
const safeUrl = (value) => {
  try {
    const url = new URL(value);
    return ['http:', 'https:'].includes(url.protocol) ? escapeHtml(url.href) : '';
  } catch { return ''; }
};
const link = (url, label) => safeUrl(url) ? `<a href="${safeUrl(url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(label)} ↗</a>` : '';
const formatDate = (value) => value ? new Date(value).toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' }) : 'Date not reported';

let statusPoll;

async function showStatus() {
  try {
    const response = await fetch('/api/status');
    const data = await response.json();
    const vet = data.sources.find((source) => source.source === 'vet');
    const hvac = data.sources.find((source) => source.source === 'hvac');
    $('#record-count').textContent = vet && hvac ? `${Number(vet.row_count).toLocaleString()} veterinary listings · ${Number(hvac.row_count).toLocaleString()} HVAC deals` : 'Preparing source downloads';
    $('#sync-summary').textContent = data.sync.running ? 'Updating the research index…' : vet && hvac ? `Sources refreshed ${formatDate(vet.fetched_at)}.` : 'Source downloads unavailable. Retry in a moment.';
    if (data.sync.running) {
      clearTimeout(statusPoll);
      statusPoll = setTimeout(showStatus, 1500);
    }
  } catch {
    $('#sync-summary').textContent = 'Could not read source status.';
  }
}

function badge(text, kind = 'reported') {
  return `<span class="badge badge-${kind}"><span class="badge-dot"></span>${escapeHtml(text)}</span>`;
}

function vetCard(row, source, ambiguous) {
  const exact = row.name.toLowerCase() === $('#name-input').value.trim().toLowerCase();
  const finding = exact && !ambiguous ? 'Group / investor listed' : 'Possible name match';
  return `<article class="result-card">
    <span class="card-sector">VETERINARY PRACTICE</span>
    <h3>${escapeHtml(row.name)}</h3>
    <div class="where">${escapeHtml(row.address || [row.city, row.state].filter(Boolean).join(', '))}</div>
    ${badge(finding, exact && !ambiguous ? 'reported' : 'unresolved')}
    <dl>
      <div><dt>Practice group</dt><dd>${escapeHtml(row.consolidator || 'Not reported')}</dd></div>
      <div><dt>Investor / backer</dt><dd>${escapeHtml(row.investor || 'Not reported')}</dd></div>
      <div><dt>Operating status</dt><dd>${escapeHtml(row.operating_status || 'Not reported')}</dd></div>
      <div><dt>Row updated</dt><dd>${escapeHtml(row.updated || 'Not reported')}</dd></div>
    </dl>
    <p class="note">This listing reports a practice, group, and backer. The downloadable row does not classify this investor as PE or document its present control. Verify the specific practice and the group chain before treating this as a PE finding.</p>
    <div class="result-links">${link(row.website, 'Practice website')}${link(source.url, 'Private Equity Vet map')}</div>
  </article>`;
}

function hvacCard(row, source, place) {
  const closed = row.status === 'closed';
  const sponsor = Boolean(row.sponsor);
  const text = closed && sponsor ? 'PE sponsor named in deal' : closed ? 'Completed deal reported' : 'Deal reported; closing unconfirmed';
  return `<article class="result-card">
    <span class="card-sector">HVAC / HOME SERVICES DEAL</span>
    <h3>${escapeHtml(row.target)}</h3>
    <div class="where">Historical transaction record</div>
    ${badge(text, closed && sponsor ? 'possible' : 'reported')}
    <dl>
      <div><dt>Acquirer</dt><dd>${escapeHtml(row.acquirer || 'Not reported')}</dd></div>
      <div><dt>Named sponsor</dt><dd>${escapeHtml(row.sponsor || 'Not reported')}</dd></div>
      <div><dt>Deal status</dt><dd>${escapeHtml(row.status || 'Not reported')}</dd></div>
      <div><dt>Deal date</dt><dd>${escapeHtml(row.closed_date || row.announced_date || 'Not reported')}</dd></div>
      <div><dt>Dataset review</dt><dd>${row.verified ? 'Marked verified by publisher' : escapeHtml(row.verification_status || 'Not marked verified')}</dd></div>
    </dl>
    <p class="note">${place ? 'The deal export has no address, so this name match has not been tied to your specified place. ' : ''}This deal record establishes a reported transaction, not who owns the company today. Check the original report and look for a later exit or resale.</p>
    <div class="result-links">${link(row.source_url, 'Original report')}${link(source.url, 'hvacrollups data')}</div>
  </article>`;
}

function render(data) {
  const { name, place } = data.query;
  const vets = data.vets;
  const hvac = data.hvac;
  const found = vets.length + hvac.length;
  const openChain = data.wikipedia_chain || [];
  const ambiguous = data.identity_ambiguous;
  $('#results-title').textContent = name ? `Results for “${name}”` : `Listings near “${place}”`;
  $('#results-intro').textContent = found ? 'Read the place and evidence carefully before drawing a conclusion.' : openChain.length ? 'A parent chain appears in open reference data; primary verification is still needed.' : 'No matching row was found in the connected datasets.';
  $('#checked-at').textContent = `Checked ${new Date().toLocaleString()}`;
  let intro;
  if (!found && openChain.length) {
    intro = `<div class="status-card"><strong>Parent-chain lead found; current control unresolved.</strong><p>The connected structured datasets have no matching row. An open encyclopedia reports a parent chain below. Confirm it with current primary sources before relying on it.</p></div>`;
  } else if (!found) {
    intro = `<div class="status-card"><strong>Ownership unresolved.</strong><p>No matching record appears in these veterinary or HVAC datasets. This does not establish independence or rule out private equity. The business may be outside the sources’ coverage or listed under another name.</p></div>`;
  } else if (ambiguous) {
    intro = `<div class="status-card"><strong>Several practices share this name.</strong><p>Add a city or ZIP to identify the right practice. A match from another state says nothing about a Macomb business.</p></div>`;
  } else {
    intro = `<div class="status-card status-found"><strong>${found} source-linked ${found === 1 ? 'record' : 'records'} found.</strong><p>These records report ownership connections or transactions. Read each card’s limits to assess whether current PE control has actually been established.</p></div>`;
  }
  const vetSection = vets.length ? `<h3 class="result-section-title">Veterinary practice listings</h3><div class="result-grid">${vets.map((row) => vetCard(row, data.sources.vet, ambiguous)).join('')}</div><p class="source-credit">Source: ${link(data.sources.vet.url, 'Private Equity Vet')} · spreadsheet synced ${escapeHtml(formatDate(data.sources.vet.synced))}. Individual rows may lack primary evidence and can be outdated.</p>` : '';
  const hvacSection = hvac.length ? `<h3 class="result-section-title">HVAC deal records</h3><div class="result-grid">${hvac.map((row) => hvacCard(row, data.sources.hvac, place)).join('')}</div><p class="source-credit">Source: ${link(data.sources.hvac.url, 'hvacrollups')} · CSV synced ${escapeHtml(formatDate(data.sources.hvac.synced))}. Company identity and current control require verification.</p>` : '';
  const chain = data.wikipedia_chain || [];
  const reachesPe = chain.some((node) => node.pe_firm_description);
  const peActivity = chain.some((node) => node.pe_activity);
  const publicNode = chain.find((node) => node.public_listing);
  const encyclopediaSection = chain.length ? `<h3 class="result-section-title">Open encyclopedia ownership lead</h3><div class="result-card encyclopedia-card">
    ${badge(reachesPe ? 'Chain reaches a PE firm' : peActivity ? 'Investor has PE activity' : 'Parent chain found', reachesPe || peActivity ? 'possible' : 'reported')}
    <div class="open-chain">${chain.map((node, index) => `<div class="open-chain-node"><span>${String(index + 1).padStart(2, '0')}</span><strong>${escapeHtml(node.name)}</strong>${node.reported_parent ? `<small>Reported parent: ${escapeHtml(node.reported_parent)}</small>` : ''}${link(node.url, 'Article')}</div>`).join('')}</div>
    <p class="note">This chain is extracted from Wikipedia infobox fields, which can lag or be wrong. ${publicNode ? `${escapeHtml(publicNode.name)} is also shown as publicly listed; that alone does not settle investor control. ` : ''}Confirm current ownership in company announcements or filings before treating it as a verified finding. Individual franchise locations may have separate owners.</p>
    <p class="source-credit">Source: ${link('https://en.wikipedia.org/wiki/Wikipedia:Copyrights', 'Wikipedia, CC BY-SA')} · pages refreshed from the open API weekly.</p>
  </div>` : '';
  const wikiSection = !chain.length && data.wikidata.length ? `<h3 class="result-section-title">Open entity match</h3><div class="status-card"><strong>${escapeHtml(data.wikidata[0].name)}</strong><p>${escapeHtml(data.wikidata[0].description || 'No description available.')} ${link(data.wikidata[0].url, 'View Wikidata record')} This identity clue is not an ownership conclusion.</p></div>` : '';
  $('#results-content').innerHTML = intro + vetSection + hvacSection + encyclopediaSection + wikiSection;
}

async function check(name, place, updateUrl = true) {
  $('#name-input').value = name;
  $('#place-input').value = place;
  $('#results-content').innerHTML = '<div class="results-placeholder">Checking downloaded research records and open entity data…</div>';
  $('#results-title').textContent = 'Checking ownership';
  $('#results').scrollIntoView({ behavior: 'smooth', block: 'start' });
  if (updateUrl) {
    const url = new URL(location.href);
    url.searchParams.set('name', name);
    if (place) url.searchParams.set('place', place);
    else url.searchParams.delete('place');
    url.hash = 'results';
    history.pushState(null, '', url);
  }
  try {
    const params = new URLSearchParams({ name, place });
    const response = await fetch(`/api/check?${params}`);
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'Lookup failed');
    render(data);
  } catch (error) {
    $('#results-content').innerHTML = `<div class="status-card"><strong>Could not complete the lookup.</strong><p>${escapeHtml(error.message)}. Please retry.</p></div>`;
  }
}

$('#check-form').addEventListener('submit', (event) => {
  event.preventDefault();
  const name = $('#name-input').value.trim();
  const place = $('#place-input').value.trim();
  if (!name && !place) { $('#name-input').focus(); return; }
  check(name, place);
});

window.addEventListener('popstate', () => {
  const params = new URLSearchParams(location.search);
  if (params.has('name')) check(params.get('name') || '', params.get('place') || '', false);
});

showStatus();
const initial = new URLSearchParams(location.search);
if (initial.has('name')) check(initial.get('name') || '', initial.get('place') || '', false);
