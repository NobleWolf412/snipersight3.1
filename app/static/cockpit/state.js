// Each selection and each resource have independently ordered requests.
// A response from an old account, workspace or screen can never paint a new one.
export class Selection {
  constructor() { this.generation = 0; this.sequences = new Map(); this.pending = new Set(); }
  change() { this.generation++; for (const controller of this.pending) controller.abort(); this.pending.clear(); this.sequences.clear(); }
  invalidate(resource) { this.sequences.set(resource, (this.sequences.get(resource) || 0) + 1); }
  async read(resource, url, options = {}) {
    const generation = this.generation;
    const sequence = (this.sequences.get(resource) || 0) + 1;
    this.sequences.set(resource, sequence);
    const controller = new AbortController(); this.pending.add(controller);
    try {
      const response = await fetch(url, {cache:'no-store', ...options, signal:controller.signal});
      const data = await response.json();
      if (generation !== this.generation || sequence !== this.sequences.get(resource)) return null;
      if (!response.ok) { const error = new Error(data.detail || `Request failed (${response.status})`); error.status=response.status; throw error; }
      return data;
    } catch(error) { if (error.name === 'AbortError') return null; throw error; }
    finally { this.pending.delete(controller); }
  }
}
