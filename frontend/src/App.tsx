import { useRef, useState } from 'react'
import type { FormEvent } from 'react'

import {
  createSession,
  generateSessionDiagnosis,
  loadSession,
  loadSessionEvidence,
  saveObservation,
} from './api'

import type {
  DiagnosticResult,
  DiagnosticSession,
  SearchResponse,
} from './api'

export default function App() {
  const [equipment, setEquipment] = useState('CX-450')
  const [description, setDescription] = useState('')
  const [session, setSession] = useState<DiagnosticSession | null>(null)
  const [result, setResult] = useState<SearchResponse | null>(null)

  const [reopenId, setReopenId] = useState(
    () => new URLSearchParams(window.location.search).get('session') || '',
  )

  const [question, setQuestion] = useState('')
  const [answer, setAnswer] = useState('')
  const [isUnknown, setIsUnknown] = useState(false)

  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const [diagnosis, setDiagnosis] = useState<DiagnosticResult | null>(null)
  const [diagnosisBusy, setDiagnosisBusy] = useState(false)
  const [diagnosisError, setDiagnosisError] = useState('')

  const generationId = useRef(0)
  const generationInFlight = useRef(false)

  function invalidateDiagnosis() {
    generationId.current += 1
    setDiagnosis(null)
    setDiagnosisError('')
  }

  function rememberSession(sessionId: string) {
    setReopenId(sessionId)

    const url = new URL(window.location.href)
    url.searchParams.set('session', sessionId)
    window.history.replaceState(null, '', url)
  }

  async function showSession(saved: DiagnosticSession) {
    setSession(saved)
    rememberSession(saved.session_id)

    const response = await loadSessionEvidence(saved.session_id)

    if (
      response.session_id !== saved.session_id ||
      response.revision !== saved.revision
    ) {
      throw new Error(
        'The session changed. Reopen it to load the latest information.',
      )
    }

    setResult(response.evidence)
  }

  async function run(action: () => Promise<void>) {
    invalidateDiagnosis()
    setBusy(true)
    setError('')
    setResult(null)

    try {
      await action()
    } catch (problem) {
      setError(
        problem instanceof Error
          ? problem.message
          : 'Something went wrong. Please try again.',
      )
    } finally {
      setBusy(false)
    }
  }

  function handleCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()

    if (!equipment.trim() || !description.trim()) {
      setError('Enter the equipment type and reported problem.')
      return
    }

    void run(async () => {
      const saved = await createSession(
        equipment.trim(),
        description.trim(),
      )

      await showSession(saved)
    })
  }

  function handleReopen(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()

    if (!reopenId.trim()) {
      setError('Enter a session ID.')
      return
    }

    void run(async () => {
      const saved = await loadSession(reopenId.trim())

      setQuestion('')
      setAnswer('')
      setIsUnknown(false)

      await showSession(saved)
    })
  }

  function handleObservation(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()

    if (!session) return

    if (isUnknown && !question.trim()) {
      setError('Enter the question whose answer is unknown.')
      return
    }

    if (!isUnknown && !answer.trim()) {
      setError('Enter an answer or observation.')
      return
    }

    const current = session

    void run(async () => {
      const saved = await saveObservation(current.session_id, {
        question: question.trim() || null,
        answer: isUnknown ? null : answer.trim(),
        is_unknown: isUnknown,
      })

      setQuestion('')
      setAnswer('')
      setIsUnknown(false)

      await showSession(saved)
    })
  }

  async function handleDiagnosis() {
    if (!session || busy || generationInFlight.current) return

    const snapshot = session
    const requestId = ++generationId.current

    generationInFlight.current = true
    setDiagnosisBusy(true)
    setDiagnosisError('')
    setDiagnosis(null)

    try {
      const response = await generateSessionDiagnosis(snapshot.session_id)

      if (generationId.current !== requestId) return

      const latest = await loadSession(snapshot.session_id)

      if (generationId.current !== requestId) return

      if (
        response.session_id !== snapshot.session_id ||
        response.revision !== snapshot.revision ||
        latest.revision !== snapshot.revision
      ) {
        throw new Error(
          'The session changed. Refresh it before generating suggestions again.',
        )
      }

      setDiagnosis(response.result)
    } catch (problem) {
      if (generationId.current === requestId) {
        setDiagnosisError(
          problem instanceof Error
            ? problem.message
            : 'Suggestions are temporarily unavailable.',
        )
      }
    } finally {
      generationInFlight.current = false
      setDiagnosisBusy(false)
    }
  }

  function startNewCase() {
    invalidateDiagnosis()
    setSession(null)
    setResult(null)
    setDescription('')
    setEquipment('CX-450')
    setReopenId('')
    setQuestion('')
    setAnswer('')
    setIsUnknown(false)
    setError('')

    const url = new URL(window.location.href)
    url.searchParams.delete('session')
    window.history.replaceState(null, '', url)
  }

  const readyDraft =
    diagnosis?.status === 'draft_ready' ? diagnosis.draft : null

  const suggestedQuestion = readyDraft?.follow_up_question ?? null

  return (
    <main className="workspace">
      <header>
        <h1>Diagnostic Assist</h1>
        <p>Collect reported information and review historical evidence.</p>
      </header>

      <form className="panel" onSubmit={handleReopen}>
        <fieldset disabled={busy} className="form-fields">
          <label htmlFor="session-id">Reopen a saved session</label>
          <input
            id="session-id"
            value={reopenId}
            onChange={(event) => setReopenId(event.target.value)}
            placeholder="Enter a session ID"
            required
          />
          <button type="submit">Reopen session</button>
        </fieldset>
      </form>

      {!session && (
        <form className="panel" onSubmit={handleCreate}>
          <fieldset disabled={busy} className="form-fields">
            <h2>New case</h2>

            <label htmlFor="equipment">Equipment type</label>
            <input
              id="equipment"
              value={equipment}
              onChange={(event) => setEquipment(event.target.value)}
              required
            />

            <label htmlFor="description">Reported problem</label>
            <textarea
              id="description"
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              rows={4}
              required
            />

            <button type="submit">Start session</button>
          </fieldset>
        </form>
      )}

      {session && (
        <>
          <section className="panel">
            <h2>{session.equipment_type}</h2>
            <p>{session.initial_description}</p>

            <p className="session-id">
              Session: {session.session_id}
            </p>
            <p className="muted">
              Status: {session.status} · Revision: {session.revision}
            </p>

            <div className="actions">
              <button
                type="button"
                disabled={busy}
                onClick={() => {
                  const sessionId = session.session_id

                  void run(async () => {
                    await showSession(await loadSession(sessionId))
                  })
                }}
              >
                Refresh session
              </button>

              <button
                type="button"
                disabled={busy}
                onClick={startNewCase}
              >
                New case
              </button>
            </div>
          </section>

          <section className="panel">
            <h2>Collected information</h2>

            {session.observations.length === 0 && (
              <p>No additional information recorded yet.</p>
            )}

            {session.observations.map((observation) => (
              <div
                className="observation"
                key={observation.observation_id}
              >
                <strong>
                  {observation.question || 'Additional observation'}
                </strong>
                <p>
                  {observation.is_unknown ? 'Unknown' : observation.answer}
                </p>
              </div>
            ))}
          </section>

          {session.status === 'active' && (
            <form className="panel" onSubmit={handleObservation}>
              <fieldset disabled={busy} className="form-fields">
                <h2>Add information</h2>

                <label htmlFor="question">Question, if applicable</label>
                <input
                  id="question"
                  value={question}
                  onChange={(event) => setQuestion(event.target.value)}
                  required={isUnknown}
                />

                <label className="checkbox-row">
                  <input
                    type="checkbox"
                    checked={isUnknown}
                    onChange={(event) => setIsUnknown(event.target.checked)}
                  />
                  Customer does not know
                </label>

                {!isUnknown && (
                  <>
                    <label htmlFor="answer">Answer or observation</label>
                    <textarea
                      id="answer"
                      value={answer}
                      onChange={(event) => setAnswer(event.target.value)}
                      rows={3}
                      required
                    />
                  </>
                )}

                <button type="submit">Save and update evidence</button>
              </fieldset>
            </form>
          )}
        </>
      )}

      {session && result && (
        <section className="panel" aria-busy={diagnosisBusy}>
          <h2>Diagnostic suggestions</h2>
          <p className="muted">
            AI-generated drafts need review. The technician confirms
            the diagnosis.
          </p>

          <button
            type="button"
            disabled={busy || diagnosisBusy}
            onClick={() => void handleDiagnosis()}
          >
            {diagnosisBusy ? 'Generating…' : 'Generate suggestions'}
          </button>

          <div aria-live="polite">
            {diagnosisBusy && (
              <p>
                A generation request is in progress. Historical evidence
                remains available.
              </p>
            )}

            {diagnosisError && (
              <p className="error" role="alert">
                {diagnosisError} Historical evidence remains available below.
              </p>
            )}

            {diagnosis?.status === 'unavailable' && (
              <p className="notice">
                {diagnosis.message ||
                  'Suggestions are temporarily unavailable.'}
              </p>
            )}

            {readyDraft && (
              <>
                <h3>Reported problem</h3>
                <p>{readyDraft.summary}</p>

                {readyDraft.possible_causes.length === 0 && (
                  <p>No diagnostic causes were suggested.</p>
                )}

                {readyDraft.possible_causes.map((cause, index) => (
                  <article key={`${cause.cause}-${index}`}>
                    <h3>{cause.cause}</h3>

                    {cause.evidence.map((reference, referenceIndex) => (
                      <blockquote
                        key={`${reference.case_id}-${referenceIndex}`}
                      >
                        <p>{reference.quote}</p>
                        <footer>
                          Historical case {reference.case_id}
                          {' · '}
                          {reference.field === 'technician_notes'
                            ? 'Technician notes'
                            : 'Recorded resolution'}
                        </footer>
                      </blockquote>
                    ))}
                  </article>
                ))}

                {suggestedQuestion && (
                  <div className="observation">
                    <h3>Suggested follow-up</h3>
                    <p>{suggestedQuestion}</p>

                    {session.status === 'active' && (
                      <button
                        type="button"
                        disabled={
                          busy ||
                          Boolean(question.trim()) ||
                          Boolean(answer.trim()) ||
                          isUnknown
                        }
                        onClick={() => {
                          setQuestion(suggestedQuestion)
                          setAnswer('')
                          setIsUnknown(false)
                        }}
                      >
                        Use this question
                      </button>
                    )}

                    <p className="muted">
                      Ask the customer, then record their answer in
                      Add information. Clear any unfinished entry before
                      selecting this question.
                    </p>
                  </div>
                )}

                {readyDraft.limitations.length > 0 && (
                  <>
                    <h3>Limitations</h3>
                    <ul>
                      {readyDraft.limitations.map((limitation, index) => (
                        <li key={index}>{limitation}</li>
                      ))}
                    </ul>
                  </>
                )}
              </>
            )}
          </div>
        </section>
      )}

      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}

      <section aria-live="polite" aria-busy={busy}>
        {busy && <p>Loading session and evidence…</p>}

        {result && (
          <>
            <h2>Historical evidence</h2>
            <p className="muted">
              Similar cases are evidence to review, not a confirmed diagnosis.
            </p>

            {result.warnings.map((warning) => (
              <p className="notice" key={warning}>
                {warning}
              </p>
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