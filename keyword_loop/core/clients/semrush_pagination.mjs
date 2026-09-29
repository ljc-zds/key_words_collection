export async function paginateKeywords(request, first, cap, fetchPage) {
  if (!Number.isInteger(cap) || cap < 0) throw Error('Invalid keyword cap');
  const size = request.params.page.size;
  const maxPages = cap ? Math.ceil(cap / size) : Infinity;
  const seen = new Set();
  const rows = [];
  let result = first;
  let pages = 0;
  for (let page = 1; page <= maxPages; page++) {
    if (page > 1) {
      const next = structuredClone(request);
      next.params.page.number = page;
      result = await fetchPage(next);
    }
    if (!Array.isArray(result?.keywords)) throw Error(`Semrush page ${page}: invalid keyword response`);
    pages++;
    let added = 0;
    for (const row of result.keywords) {
      const key = String(row.keyword ?? row.phrase ?? '').trim().toLowerCase();
      if (key && !seen.has(key)) {seen.add(key); rows.push(row); added++;}
    }
    if (page > 1 && result.keywords.length && !added) throw Error(`Semrush page ${page}: repeated page`);
    if (result.keywords.length < size || (cap && rows.length >= cap)) break;
  }
  return {...first, keywords:cap ? rows.slice(0,cap) : rows, pages_fetched:pages};
}
