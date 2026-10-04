import { useState } from 'react'
import type { FormEvent } from 'react'

import { searchCases } from './api'
import type { SearchResponse } from './api'

export default function App() {
  const [equipment, setEquipment] = useState('CX-450')
  const [query, setQuery] = useState('')
  const [result, setResult] = useState<SearchResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()

    if (!query.trim() || !equipment.trim()) {
      setError('Enter the equipment type and reported problem.')
      return
    }

    setLoading(true)
    setError('')
    setResult(null)

    try {
      const response = await searchCases(query.trim(), equipment.trim())
      setResult(response)
    } catch {
      setError('Unable to search. Check that the backend is running.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <main className="workspace">
      <header>
        <h1>Diagnostic Assist</h1>
        <p>Find historical evidence for a reported machine problem.</p>
      </header>

      <form className="panel" onSubmit={handleSubmit}>
        <label htmlFor="equipment">Equipment type</label>
        <input
          id="equipment"
          value={equipment}
          onChange={(event) => setEquipment(event.target.value)}
          disabled={loading}
          required
        />

        <label htmlFor="problem">Reported problem</label>
        <textarea
          id="problem"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Describe what the customer reported."
          rows={4}
          disabled={loading}
          required
        />

        <button type="submit" disabled={loading}>
          {loading ? 'Searching…' : 'Find similar cases'}
        </button>
      </form>

      {error && <p className="error" role="alert">{error}</p>}

      <section aria-live="polite" aria-busy={loading}>
        {loading && <p>Searching historical cases…</p>}

        {result && (
          <>
            <h2>Historical evidence</h2>
            <p>
              Results for: {result.query}
            </p>
            <p className="muted">
              Similar cases are evidence to review, not a confirmed diagnosis.
            </p>

            {result.warnings.map((warning) => (
              <p className="notice" key={warning}>{warning}</p>
            ))}

            {result.hits.length === 0 && (
              <p>No historical matches were returned.</p>
            )}

            {result.hits.map((hit) => (
              <article className="panel" key={hit.case.case_id}>
                <div className="case-heading">
                  <h3>{hit.case.case_id}</h3>
                  <span>{hit.case.language.toUpperCase()}</span>
                </div>

                <p className="muted">
                  {hit.case.equipment_type} · {hit.case.equipment_family}
                </p>

                <h4>Reported problem</h4>
                <p>{hit.case.customer_description}</p>

                <h4>Technician findings</h4>
                <p>{hit.case.technician_notes || 'Not recorded.'}</p>

                <h4>Recorded resolution</h4>
                <p>{hit.case.resolution_text || 'Not recorded.'}</p>

                <h4>Parts replaced in this case</h4>
                <p>
                  {hit.case.parts_replaced.length
                    ? hit.case.parts_replaced.join(', ')
                    : 'None recorded.'}
                </p>
              </article>
            ))}
          </>
        )}
      </section>
    </main>
  )
}