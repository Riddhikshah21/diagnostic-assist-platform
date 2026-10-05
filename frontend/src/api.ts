export interface HistoricalCase {
  case_id: string
  equipment_family: string
  equipment_type: string
  language: string
  customer_description: string
  technician_notes: string | null
  resolution_text: string | null
  parts_replaced: string[]
}

export interface EvidenceHit {
  case: HistoricalCase
  rrf_score: number
  source_ranks: Record<string, number>
  match_scope: 'equipment_type' | 'equipment_family'
}

export interface SearchResponse {
  query: string
  equipment_type: string
  hits: EvidenceHit[]
  used_family_fallback: boolean
  warnings: string[]
}

export async function searchCases(
  query: string,
  equipmentType: string,
): Promise<SearchResponse> {
  const response = await fetch('/api/search', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      query,
      equipment_type: equipmentType,
      limit: 5,
      candidate_depth: 5,
    }),
  })

  if (!response.ok) {
    throw new Error('Search failed. Please check the service and try again.')
  }

  return response.json()
}

export interface SessionObservation {
  observation_id: string
  question: string | null
  answer: string | null
  is_unknown: boolean
  created_at: string
}

export interface DiagnosticSession {
  session_id: string
  equipment_type: string
  initial_description: string
  status: 'active' | 'completed'
  revision: number
  created_at: string
  updated_at: string
  observations: SessionObservation[]
}

export interface SessionEvidenceResponse {
  session_id: string
  revision: number
  evidence: SearchResponse
}

export interface ObservationInput {
  question: string | null
  answer: string | null
  is_unknown: boolean
}

async function sessionRequest<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  let response: Response

  try {
    response = await fetch(`/api${path}`, {
      headers: { 'Content-Type': 'application/json' },
      ...options,
    })
  } catch {
    throw new Error('Unable to reach the service. Please try again.')
  }

  if (!response.ok) {
    const payload: { detail?: unknown } | null = await response
      .json()
      .catch(() => null)

    const message =
      typeof payload?.detail === 'string'
        ? payload.detail
        : 'The request failed. Please check the information and try again.'

    throw new Error(message)
  }

  return response.json() as Promise<T>
}

export function createSession(
  equipmentType: string,
  initialDescription: string,
): Promise<DiagnosticSession> {
  return sessionRequest('/sessions', {
    method: 'POST',
    body: JSON.stringify({
      equipment_type: equipmentType,
      initial_description: initialDescription,
    }),
  })
}

export function loadSession(
  sessionId: string,
): Promise<DiagnosticSession> {
  return sessionRequest(
    `/sessions/${encodeURIComponent(sessionId)}`,
  )
}

export function loadSessionEvidence(
  sessionId: string,
): Promise<SessionEvidenceResponse> {
  return sessionRequest(
    `/sessions/${encodeURIComponent(sessionId)}/evidence`,
  )
}

export function saveObservation(
  sessionId: string,
  observation: ObservationInput,
): Promise<DiagnosticSession> {
  return sessionRequest(
    `/sessions/${encodeURIComponent(sessionId)}/observations`,
    {
      method: 'POST',
      body: JSON.stringify(observation),
    },
  )
}
export interface EvidenceReference {
  case_id: string
  field: 'technician_notes' | 'resolution_text'
  quote: string
}

export interface CauseSuggestion {
  cause: string
  explanation: string
  evidence: EvidenceReference[]
}

export interface DiagnosticDraft {
  summary: string
  possible_causes: CauseSuggestion[]
  follow_up_question: string | null
  limitations: string[]
}

export type DiagnosticResult =
  | {
      status: 'draft_ready'
      evidence: SearchResponse
      draft: DiagnosticDraft
      message: string | null
    }
  | {
      status: 'unavailable'
      evidence: SearchResponse
      draft: null
      message: string | null
    }

export interface SessionDiagnosticResponse {
  session_id: string
  revision: number
  result: DiagnosticResult
}

export function generateSessionDiagnosis(
  sessionId: string,
): Promise<SessionDiagnosticResponse> {
  return sessionRequest(
    `/sessions/${encodeURIComponent(sessionId)}/diagnosis`,
    { method: 'POST' },
  )
}